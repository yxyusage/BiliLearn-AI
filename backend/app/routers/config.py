"""模型配置接口（密钥仅保存在本地 SQLite）。"""
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import SettingBody
from ..services import bilibili
from ..services.llm import PROVIDERS, build_llm
from ..services.settings_store import get_setting, resolve_llm_config, set_setting

router = APIRouter()

# 需要填 Key 的供应商（deepseek / kimi / qwen / openai…）
# 这里按 PROVIDERS 动态生成，避免以后再加供应商时漏改白名单
_KEY_PROVIDERS = tuple(p for p, info in PROVIDERS.items() if info.get("need_key"))

_KEYS = (
    "provider",
    *[p + "_api_key" for p in _KEY_PROVIDERS],
    *[p + "_model" for p in PROVIDERS],
    "ollama_base_url",
    "enable_whisper",
    "whisper_model",
    "whisper_language",
    "hf_endpoint",
    "bili_cookie",
    "collection_concurrency",
    "llm_max_tokens",
    "dictation_enabled",
    "variant_enabled",
    "diagnosis_enabled",
)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "******"
    return value[:3] + "****" + value[-4:]


@router.get("")
def get_config(db: Session = Depends(get_db)):
    values = {k: get_setting(db, k) for k in _KEYS}
    masked = {p + "_api_key": _mask(values.get(p + "_api_key", "")) for p in _KEY_PROVIDERS}
    return {
        "provider": values.get("provider") or "deepseek",
        "api_keys": masked,
        "models": {
            p: values.get(p + "_model") or PROVIDERS[p]["default_model"]
            for p in PROVIDERS
        },
        # 单次输出上限：0 = 按供应商默认（deepseek/kimi/qwen/openai 目前是 8192）
        "llm_max_tokens": int(values.get("llm_max_tokens") or 0) if str(values.get("llm_max_tokens") or "").isdigit() else 0,
        "ollama_base_url": values.get("ollama_base_url") or PROVIDERS["ollama"]["base_url"],
        "enable_whisper": str(values.get("enable_whisper") or "").lower() in ("1", "true", "on", "yes"),
        "whisper_model": values.get("whisper_model") or "base",
        "whisper_language": values.get("whisper_language") or "",
        "hf_endpoint": values.get("hf_endpoint") or "",
        "hf_endpoint_env": (os.environ.get("HF_ENDPOINT") or "").strip(),
        "bili_cookie_set": bool(values.get("bili_cookie") or ""),
        "bili_cookie_has_sessdata": bilibili.has_sessdata(values.get("bili_cookie") or ""),
        "collection_concurrency": values.get("collection_concurrency") or "4",
        "dictation_enabled": str(values.get("dictation_enabled") or "1").lower() in ("1", "true", "on", "yes"),
        "variant_enabled": str(values.get("variant_enabled") or "1").lower() in ("1", "true", "on", "yes"),
        "diagnosis_enabled": str(values.get("diagnosis_enabled") or "1").lower() in ("1", "true", "on", "yes"),
        "providers": [
            {
                "id": p,
                "name": info["name"],
                "need_key": info["need_key"],
                "default_model": info["default_model"],
                "key_url": info.get("key_url", ""),
            }
            for p, info in PROVIDERS.items()
        ],
    }


@router.get("/models")
def list_models(provider: str = "deepseek", db: Session = Depends(get_db)):
    """列出该供应商当前可用的模型（优先问供应商的 /models，失败回退内置列表）。

    为什么要下拉：模型名手填很容易错 ——
      · 填成不存在的 id → 供应商直接 400/404（这个至少报错明显）；
      · 填成存在但更弱/更贵的模型 → 质量静默下降，用户完全看不出来；
      · 有些中转还会把未知模型静默换成默认模型。
    """
    info = PROVIDERS.get(provider)
    if not info:
        raise HTTPException(status_code=400, detail="不支持的供应商: " + str(provider))
    builtin = [str(m) for m in (info.get("models") or [])]
    key = get_setting(db, provider + "_api_key", "")
    base = (get_setting(db, provider + "_base_url", "") or info["base_url"]).rstrip("/")
    is_ollama = info["kind"] == "ollama"
    if is_ollama:
        url = base + ("/api/tags" if base.endswith("/api") else "/api/tags")
        headers = {}
    else:
        if not key:
            return {"provider": provider, "models": builtin, "source": "builtin",
                    "error": "还没填 API Key，先显示内置列表"}
        url = base + "/models"
        headers = {"Authorization": "Bearer " + key}
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        if is_ollama:
            names = [m.get("name") for m in (data.get("models") or []) if isinstance(m, dict)]
        else:
            names = [m.get("id") for m in (data.get("data") or []) if isinstance(m, dict)]
        names = [n for n in names if isinstance(n, str) and n.strip()]
        merged = builtin + [n for n in sorted(set(names)) if n not in builtin]
        return {"provider": provider, "models": merged, "source": "live", "error": ""}
    except Exception as exc:  # noqa: BLE001  拿不到就用内置列表，不阻断用户
        return {"provider": provider, "models": builtin, "source": "builtin",
                "error": str(exc)[:120]}


@router.post("/set")
def set_config(body: SettingBody, db: Session = Depends(get_db)):
    if body.key not in _KEYS:
        return {"ok": False, "message": "不支持的配置项"}
    set_setting(db, body.key, body.value)
    if body.key == "bili_cookie" and not (body.value or "").strip():
        # 清空 Cookie 时顺手删掉给 yt-dlp 用的 cookie 文件，别留登录凭证在磁盘上
        bilibili.clear_cookie_file()
    return {"ok": True}


@router.post("/verify-cookie")
def verify_cookie(body: Optional[dict] = None, db: Session = Depends(get_db)):
    """校验 B站 Cookie 处于什么状态（可传入未保存的 Cookie 先测，不传则用已保存的）。"""
    cookie = ""
    if isinstance(body, dict):
        cookie = str(body.get("cookie") or "")
    if not cookie:
        cookie = get_setting(db, "bili_cookie", "")
    return bilibili.verify_cookie(cookie)


@router.post("/test")
def test_connection(db: Session = Depends(get_db)):
    cfg = resolve_llm_config(db)
    if cfg["provider"] != "ollama" and not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key")
    llm = build_llm(cfg["provider"], cfg["api_key"], cfg["model"], cfg["base_url"], cfg.get("max_tokens"))
    try:
        text = llm.chat([{"role": "user", "content": "请只回复两个字：正常"}], temperature=0)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="连接失败：" + str(exc)) from exc
    return {"ok": True, "reply": text[:50], "provider": cfg["provider"], "model": cfg["model"]}
