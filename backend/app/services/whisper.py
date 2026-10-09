"""本地离线语音转写（可选能力）。

依赖：pip install faster-whisper（自带 PyAV，解码音频不需要系统 ffmpeg）。
无官方字幕的视频在用户开启转写后走此通道。
"""
import os
import tempfile
import threading
from typing import Dict, List, Optional

import yt_dlp

from .bilibili import cookie_file
from .netutil import clear_proxy_env, has_proxy_env, restore_proxy_env

# 模型进程级缓存，避免每集都重新加载（加载一次大模型可达数十秒）
_MODELS: Dict[str, object] = {}
_MODEL_LOCK = threading.Lock()


def _get_model(model_name: str):
    name = model_name or "base"
    with _MODEL_LOCK:
        if name not in _MODELS:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # noqa: BLE001
                raise RuntimeError("未安装 faster-whisper。请先执行 pip install faster-whisper 后重试") from exc
            # 固定 CPU 推理（device=auto 在无 CUDA 库的机器上会因 cublas 缺失而失败）
            _MODELS[name] = WhisperModel(name, device="cpu", compute_type="int8")
        return _MODELS[name]


def _decode(path: str, model_name: Optional[str], language: Optional[str]) -> List[dict]:
    """对本地音视频文件做一次转写（PyAV 解码，不依赖系统 ffmpeg）。"""
    model = _get_model(model_name or "base")
    try:
        segments, _info = model.transcribe(
            path,
            language=language or None,  # None = 自动检测
            beam_size=5,
            vad_filter=True,  # 过滤静音/片头片尾噪声
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "音频解码失败：该文件可能没有音轨，或编码格式不受支持（" + str(exc) + "）"
        ) from exc
    return [
        {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
        for s in segments
    ]


def transcribe_file(path: str, model_name: Optional[str] = None, language: Optional[str] = None) -> List[dict]:
    """直接转写本地视频/音频文件（mp4/mkv/flv/m4a/mp3 等，取决于 PyAV 解码支持）。"""
    if not path or not os.path.isfile(path):
        raise RuntimeError("本地文件不存在或已被移动：" + str(path))
    return _decode(path, model_name, language)


def transcribe(bvid: str, page: int = 1, model_name: Optional[str] = None, language: Optional[str] = None, cookie: str = "") -> List[dict]:
    url = "https://www.bilibili.com/video/" + bvid + "?p=" + str(page or 1)

    with tempfile.TemporaryDirectory() as tmp:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,  # 关键：只处理当前分P，避免合集整单下载
            # 直接下载音轨（DASH m4a 单流），无需 ffmpeg 合并/转码
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
            },
        }
        # 登录态用 yt-dlp 原生 cookiefile（设置里的 B站 Cookie），比塞 Cookie 头可靠
        cooked = cookie_file(cookie)
        if cooked:
            ydl_opts["cookiefile"] = cooked
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as exc:  # noqa: BLE001
            if has_proxy_env():
                saved = clear_proxy_env()
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                except Exception as exc2:  # noqa: BLE001
                    raise RuntimeError("音频下载失败：" + str(exc2)) from exc2
                finally:
                    restore_proxy_env(saved)
            else:
                raise RuntimeError("音频下载失败：" + str(exc)) from exc
        files = [f for f in os.listdir(tmp) if f.startswith("audio.")]
        if not files:
            raise RuntimeError("音频下载失败：未找到音频文件")

        return _decode(os.path.join(tmp, files[0]), model_name, language)
