"""环境自检：把「生成笔记」链路上最容易出问题的环节逐项过一遍。

设计原则：
- 默认只做只读、轻度联网的检查；勾选 deep 才做「调一次大模型」「试拉一段音频」
  这类耗时或花钱的动作；
- 每项返回 {id, name, status, detail, hint}，status ∈ ok / warn / fail / skip；
- 单项异常一律捕获（自检本身不能把服务搞挂），异常原文放进 detail。

为什么需要它：用户报「生成失败」时，只看一句报错很难定位——版本、模型缓存、
HF 端点、Xet、字幕、音频下载、LLM Key 任何一环出问题，表现都是「生成失败」。
"""
import os
import platform
import re
import sys
import time
from typing import Dict, List, Optional

import httpx
import yt_dlp
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import get_db
from ..services import bilibili, whisper
from ..services.llm import build_llm
from ..services.settings_store import get_setting, resolve_llm_config

router = APIRouter()

BILI_TIMEOUT = 8.0          # 只测连通性
PARSE_TIMEOUT = 60.0        # yt-dlp 解析（不下载）
AUDIO_PROBE_BYTES = 1024 * 1024
AUDIO_PROBE_TIMEOUT = 25.0
LLM_TIMEOUT = 40.0

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _item(idx: str, name: str, status: str, detail: str = "", hint: str = "") -> Dict[str, str]:
    return {"id": idx, "name": name, "status": status, "detail": detail, "hint": hint}


def _version(pkg: str) -> str:
    try:
        import importlib.metadata as md

        return md.version(pkg)
    except Exception:  # noqa: BLE001
        return ""


def _is_on(name: str, default: str = "") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in ("1", "true", "on", "yes")


# ---------------------------------------------------------------- 基础环境

def check_runtime(request: Request) -> Dict[str, str]:
    try:
        ver = getattr(request.app, "version", "") or "?"
        return _item("runtime", "后端服务", "ok", "v%s · Python %s · %s %s" % (
            ver, platform.python_version(), platform.system(), platform.release()))
    except Exception as exc:  # noqa: BLE001
        return _item("runtime", "后端服务", "fail", str(exc))


def check_data_dir() -> Dict[str, str]:
    try:
        path = DATA_DIR
        if not path.is_dir():
            return _item("data_dir", "数据目录", "warn", "%s（尚未创建，首次生成时自动建）" % path)
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        writable = os.access(str(path), os.W_OK)
        detail = "%s（约 %.1f MB，%s）" % (path, size / 1048576, "可写" if writable else "不可写")
        if not writable:
            return _item("data_dir", "数据目录", "fail", detail,
                         "目录不可写，笔记无法保存：请检查权限，或用环境变量 BILI_DATA_DIR 换个目录")
        return _item("data_dir", "数据目录", "ok", detail)
    except Exception as exc:  # noqa: BLE001
        return _item("data_dir", "数据目录", "fail", str(exc))


def check_python_version() -> Dict[str, str]:
    """Python 版本是否受支持。

    3.14+ 上 ctranslate2 / onnxruntime / av 这些编译型包还没有 wheel，依赖装不上，
    用户很容易误以为是网络问题（旧提示也确实这么说）。这里提前说清。
    ⚠️ 版本区间与 launcher/pycompat.py 保持一致，改动要同步两处。
    """
    supported_min = (3, 10)
    supported_max = (3, 14)   # 3.14 已有 cp314 轮子可装；3.15 起仍是预发布版、装不上
    recommended = "3.12"
    ver = sys.version_info[:3]
    shown = "%d.%d.%d" % ver
    if ver[:2] < supported_min:
        return _item("python", "Python 版本", "fail", "当前 " + shown + "（需要 3.10 及以上）",
                     "版本过低：请安装 Python " + recommended)
    if ver[:2] > supported_max:
        return _item("python", "Python 版本", "warn", "当前 " + shown + "（推荐 " + recommended + "）",
                     "版本太新：本地语音转写依赖的 ctranslate2 / av 还没有该版本的预编译包，依赖装不上。"
                     "请改用 Python " + recommended + "（支持 3.10 ~ 3.14）")
    if ver[:2] == supported_max:
        return _item("python", "Python 版本", "ok", "当前 " + shown + "（未充分验证，推荐 " + recommended + "）")
    return _item("python", "Python 版本", "ok", "当前 " + shown)


def check_deps() -> Dict[str, str]:
    try:
        parts = ["%s %s" % (n, v) for n, v in (
            (n, _version(n)) for n in ("yt-dlp", "huggingface_hub", "hf_xet", "faster-whisper", "av")
        ) if v]
        detail = " · ".join(parts) or "未读取到版本信息"
        missing = [n for n in ("yt-dlp", "huggingface_hub") if not _version(n)]
        if missing:
            return _item("deps", "关键依赖", "fail", detail,
                         "缺少 " + "、".join(missing) + "：重新运行启动器会自动安装")
        return _item("deps", "关键依赖", "ok", detail)
    except Exception as exc:  # noqa: BLE001
        return _item("deps", "关键依赖", "warn", str(exc))


# ---------------------------------------------------------------- 语音转写

def check_whisper_ready(db: Session) -> Dict[str, str]:
    try:
        enabled = str(get_setting(db, "enable_whisper", "")).strip().lower() in ("1", "true", "on", "yes")
        model = get_setting(db, "whisper_model", "") or "base"
        try:
            import faster_whisper  # noqa: F401

            installed = True
        except Exception:  # noqa: BLE001
            installed = False
        detail = "开关：%s · 模型：%s · faster-whisper：%s" % (
            "已开启" if enabled else "未开启", model, "已安装" if installed else "未安装")
        if not installed:
            too_new = sys.version_info[:2] > (3, 14)
            hint = ("你的 Python 版本太新（当前 %d.%d），本项目按轻量模式安装、不含本地语音转写："
                    "没有字幕的视频会失败。装 Python 3.12 可恢复该功能"
                    % sys.version_info[:2]) if too_new else                    "未安装 faster-whisper：没有字幕的视频会失败。重新运行一次启动器即可自动安装"
            return _item("whisper", "离线语音转写", "warn", detail, hint)
        if not enabled:
            return _item("whisper", "离线语音转写", "warn", detail,
                         "未开启：没有字幕的视频会直接失败，可在「离线语音转写」里打开")
        return _item("whisper", "离线语音转写", "ok", detail)
    except Exception as exc:  # noqa: BLE001
        return _item("whisper", "离线语音转写", "warn", str(exc))


def check_model_cache(db: Session) -> Dict[str, str]:
    try:
        model = get_setting(db, "whisper_model", "") or "base"
        cached = whisper.model_cached(model)
        others = [m for m in ("tiny", "base", "small", "medium", "large-v3")
                  if m != model and whisper.model_cached(m)]
        extra = ("；本地已有：" + "、".join(others)) if others else ""
        if cached:
            return _item("model_cache", "语音模型缓存", "ok",
                         "%s（%s）已缓存%s" % (model, whisper.model_repo_id(model), extra))
        return _item("model_cache", "语音模型缓存", "warn",
                     "%s 未缓存，首次转写需下载（约 150MB）%s" % (model, extra),
                     "首次转写会先下模型：失败时把「模型下载源」设为国内镜像；"
                     "或先用一个「有官方字幕」的视频（有字幕就不需要模型）")
    except Exception as exc:  # noqa: BLE001
        return _item("model_cache", "语音模型缓存", "warn", str(exc))


def check_hf_env(db: Session) -> Dict[str, str]:
    """HuggingFace 下载环境：端点、Xet、超时。Xet 是近期最容易踩的坑。"""
    try:
        endpoint_env = (os.environ.get("HF_ENDPOINT") or "").strip()
        endpoint_setting = (get_setting(db, "hf_endpoint", "") or "").strip()
        xet_off = _is_on("HF_HUB_DISABLE_XET")
        token_off = _is_on("HF_HUB_DISABLE_IMPLICIT_TOKEN")
        timeout = os.environ.get("HF_HUB_DOWNLOAD_TIMEOUT", "")
        hf_xet_ver = _version("hf_xet")

        shown = endpoint_env or {"mirror": "hf-mirror.com", "official": "huggingface.co"}.get(
            endpoint_setting, endpoint_setting)
        detail = "端点：%s · 下载超时：%ss · Xet：%s · hf_xet：%s" % (
            shown or "官方（默认）", timeout or "10",
            "已禁用（推荐）" if xet_off else "启用中", hf_xet_ver or "未安装")
        if hf_xet_ver and not xet_off:
            return _item("hf_env", "模型下载环境", "warn", detail,
                         "装了 hf_xet 却没禁用 Xet：走国内镜像时大文件会 401。"
                         "v1.8.7+ 会自动禁用；旧版本请设 HF_HUB_DISABLE_XET=1 后重启")
        if xet_off and not token_off:
            detail += "（未禁用隐式 token，一般无碍）"
        return _item("hf_env", "模型下载环境", "ok", detail)
    except Exception as exc:  # noqa: BLE001
        return _item("hf_env", "模型下载环境", "warn", str(exc))


# ---------------------------------------------------------------- 大模型

def check_llm(db: Session, deep: bool) -> Dict[str, str]:
    try:
        cfg = resolve_llm_config(db)
        provider, model = cfg["provider"], cfg["model"]
        if provider != "ollama" and not cfg["api_key"]:
            return _item("llm", "大模型", "fail", "%s / %s（未配置 API Key）" % (provider, model),
                         "到「大模型供应商」填好 API Key 并点「保存设置」")
        if not deep:
            return _item("llm", "大模型", "ok", "%s / %s（Key 已配置；勾选深度检测可测连通性）" % (provider, model))
        llm = build_llm(provider, cfg["api_key"], model, cfg["base_url"], cfg.get("max_tokens"))
        if hasattr(llm, "timeout"):
            llm.timeout = LLM_TIMEOUT
        t0 = time.time()
        reply = llm.chat([{"role": "user", "content": "请只回复两个字：正常"}], temperature=0)
        return _item("llm", "大模型", "ok", "%s / %s 连通正常（%.1fs）：%s" % (
            provider, model, time.time() - t0, (reply or "").strip()[:20]))
    except Exception as exc:  # noqa: BLE001
        return _item("llm", "大模型", "fail", str(exc)[:200],
                     "大模型调不通就没法生成笔记：检查 API Key、余额、网络或代理设置")


# ---------------------------------------------------------------- B站与视频

def check_bili_connectivity() -> Dict[str, str]:
    try:
        t0 = time.time()
        with httpx.Client(timeout=BILI_TIMEOUT, follow_redirects=True,
                          headers={"User-Agent": _UA}) as client:
            resp = client.get("https://www.bilibili.com/")
        ms = (time.time() - t0) * 1000
        if resp.status_code >= 400:
            return _item("bili", "B站连通性", "warn", "HTTP %s（%.0fms）" % (resp.status_code, ms),
                         "B站返回异常状态码，稍后再试或换个网络")
        return _item("bili", "B站连通性", "ok", "HTTP %s（%.0fms）" % (resp.status_code, ms))
    except Exception as exc:  # noqa: BLE001
        return _item("bili", "B站连通性", "fail", str(exc)[:160],
                     "连不上 B站：检查网络/代理；WiFi 下被风控时换手机热点试试")


def check_cookie(db: Session) -> Dict[str, str]:
    try:
        cookie = get_setting(db, "bili_cookie", "")
        if not cookie:
            return _item("cookie", "B站登录态", "warn", "未配置 Cookie",
                         "不配也能用，但「登录后才可见」的字幕和受限视频拿不到")
        if not bilibili.has_sessdata(cookie):
            return _item("cookie", "B站登录态", "warn", "Cookie 里没有 SESSDATA（只是游客身份）",
                         "重新按「设置 → B站 Cookie」里的路径复制一次完整 Cookie")
        return _item("cookie", "B站登录态", "ok", "已配置且包含 SESSDATA")
    except Exception as exc:  # noqa: BLE001
        return _item("cookie", "B站登录态", "warn", str(exc))


def _extract(bvid: str, page: int, cookie: str) -> dict:
    url = bilibili.video_url(bvid, page)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "http_headers": {"User-Agent": _UA, "Referer": "https://www.bilibili.com/"},
    }
    cooked = bilibili.cookie_file(cookie)
    if cooked:
        opts["cookiefile"] = cooked
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def check_video(bvid: str, page: int, db: Session) -> List[Dict[str, str]]:
    """针对具体视频：能否解析、有没有字幕（决定走哪条链路）。"""
    if not bvid:
        return [_item("video", "指定视频", "skip", "未填 BV 号（填上可检测该视频走哪条链路）")]
    items: List[Dict[str, str]] = []
    cookie = get_setting(db, "bili_cookie", "")
    try:
        t0 = time.time()
        info = _extract(bvid, page, cookie)
        title = (info.get("title") or "").strip()
        items.append(_item("video", "视频解析", "ok", "%s（%.1fs）" % (title[:40] or bvid, time.time() - t0)))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        hint = "解析失败常见原因：B站风控（HTTP 412，换网络/配登录 Cookie）、视频已删除或需要登录"
        items.append(_item("video", "视频解析", "fail", msg[:200], hint))
        return items

    try:
        subs, source = bilibili.get_subtitles(bvid, page, cookie)
    except Exception as exc:  # noqa: BLE001
        subs, source = [], "字幕抓取失败：" + str(exc)[:120]
    if subs:
        items.append(_item("subtitle", "视频字幕", "ok",
                           "有官方字幕（%d 条，%s）→ 走「抓字幕 + 大模型」，不需要下载模型和音频" % (len(subs), source)))
    else:
        items.append(_item("subtitle", "视频字幕", "warn", "没有抓到官方字幕（%s）" % source,
                           "会走「下载音轨 + 本地语音转写」：这条路依赖模型缓存与网络，"
                           "也是「音频下载失败 / 模型下载失败」的多发地"))
    return items


def check_audio(bvid: str, page: int, db: Session, deep: bool) -> Dict[str, str]:
    """深度检测：真正拉一小段音频，验证「音频下载」这一环。"""
    if not deep:
        return _item("audio", "音频下载", "skip", "未检测（勾选「深度检测」后可用）")
    if not bvid:
        return _item("audio", "音频下载", "skip", "未检测（需要 BV 号）")
    try:
        cookie = get_setting(db, "bili_cookie", "")
        info = _extract(bvid, page, cookie)
        fmts = [f for f in (info.get("formats") or [])
                if f.get("url") and f.get("acodec") not in (None, "none")
                and f.get("vcodec") in (None, "none")]
        if not fmts:
            return _item("audio", "音频下载", "fail", "没有找到纯音频流",
                         "该视频可能没有音轨，或需要登录（配好 B站 Cookie 再试）")
        target = sorted(fmts, key=lambda f: f.get("filesize") or f.get("filesize_approx") or 0)[-1]
        headers = {"User-Agent": _UA, "Referer": "https://www.bilibili.com/",
                   "Range": "bytes=0-%d" % (AUDIO_PROBE_BYTES - 1)}
        t0 = time.time()
        got = 0
        with httpx.Client(timeout=AUDIO_PROBE_TIMEOUT, follow_redirects=True, headers=headers) as client:
            with client.stream("GET", target["url"]) as resp:
                if resp.status_code not in (200, 206):
                    raise RuntimeError("HTTP %s" % resp.status_code)
                for chunk in resp.iter_bytes(65536):
                    got += len(chunk)
                    if got >= AUDIO_PROBE_BYTES:
                        break
        spent = max(time.time() - t0, 0.001)
        speed = got / spent / 1024
        return _item("audio", "音频下载", "ok", "拉到 %.0f KB，用时 %.1fs（%.0f KB/s）" % (
            got / 1024, spent, speed))
    except Exception as exc:  # noqa: BLE001
        return _item("audio", "音频下载", "fail", str(exc)[:200],
                     "音频拉不下来就会报「音频下载失败」。点「重新生成」会再试；"
                     "仍失败说明网络到 B站 CDN 不稳，换个网络或稍后再试")


# ---------------------------------------------------------------- 汇总接口

@router.get("")
def diagnose(request: Request,
             bvid: str = Query("", description="可选：要检测的 BV 号"),
             page: int = Query(1, description="分P"),
             deep: bool = Query(False, description="深度检测：会调用一次大模型并试拉一段音频"),
             db: Session = Depends(get_db)):
    # 用户可能填 BV 号，也可能直接粘贴完整链接甚至 b23.tv 短链——统一归一化；
    # 链接里若带 ?p=7（短链展开后常带），调用方又没指定分P，就跟着链接走
    raw_input = (bvid or "").strip()
    expanded = bilibili.normalize_video_input(raw_input) if raw_input else ""
    bvid = bilibili.extract_bvid(expanded) or raw_input
    if bvid and (not page or page <= 1):
        m = re.search(r"[?&]p=([0-9]+)", expanded or "")
        if m:
            page = int(m.group(1))
    items: List[Dict[str, str]] = [
        check_runtime(request),
        check_python_version(),
        check_data_dir(),
        check_deps(),
        check_bili_connectivity(),
        check_cookie(db),
        check_llm(db, deep),
        check_whisper_ready(db),
        check_model_cache(db),
        check_hf_env(db),
    ]
    items.extend(check_video(bvid, page, db))
    items.append(check_audio(bvid, page, db, deep))

    summary = {
        "ok": sum(1 for i in items if i["status"] == "ok"),
        "warn": sum(1 for i in items if i["status"] == "warn"),
        "fail": sum(1 for i in items if i["status"] == "fail"),
        "skip": sum(1 for i in items if i["status"] == "skip"),
    }
    return {"summary": summary, "items": items, "bvid": bvid, "page": page, "deep": bool(deep)}
