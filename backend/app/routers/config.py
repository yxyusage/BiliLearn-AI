"""模型配置接口（密钥仅保存在本地 SQLite）。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import SettingBody
from ..services import bilibili
from ..services.llm import PROVIDERS, build_llm
from ..services.settings_store import get_setting, resolve_llm_config, set_setting

router = APIRouter()

_KEYS = (
    "provider",
    "deepseek_api_key",
    "kimi_api_key",
    "qwen_api_key",
    "deepseek_model",
    "kimi_model",
    "qwen_model",
    "ollama_model",
    "ollama_base_url",
    "enable_whisper",
    "whisper_model",
    "whisper_language",
    "bili_cookie",
    "collection_concurrency",
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
    masked = {k: _mask(values.get(k, "")) for k in ("deepseek_api_key", "kimi_api_key", "qwen_api_key")}
    return {
        "provider": values.get("provider") or "deepseek",
        "api_keys": masked,
        "models": {
            p: values.get(p + "_model") or PROVIDERS[p]["default_model"]
            for p in ("deepseek", "kimi", "qwen", "ollama")
        },
        "ollama_base_url": values.get("ollama_base_url") or PROVIDERS["ollama"]["base_url"],
        "enable_whisper": str(values.get("enable_whisper") or "").lower() in ("1", "true", "on", "yes"),
        "whisper_model": values.get("whisper_model") or "base",
        "whisper_language": values.get("whisper_language") or "",
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
    llm = build_llm(cfg["provider"], cfg["api_key"], cfg["model"], cfg["base_url"])
    try:
        text = llm.chat([{"role": "user", "content": "请只回复两个字：正常"}], temperature=0)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="连接失败：" + str(exc)) from exc
    return {"ok": True, "reply": text[:50], "provider": cfg["provider"], "model": cfg["model"]}
