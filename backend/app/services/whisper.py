"""本地离线语音转写（可选能力）。

依赖：pip install faster-whisper（自带 PyAV，解码音频不需要系统 ffmpeg）。
无官方字幕的视频在用户开启转写后走此通道。
"""
import os
import tempfile
from typing import List, Optional

import yt_dlp

from .bilibili import _SILENT_LOGGER
from .netutil import clear_proxy_env, has_proxy_env, restore_proxy_env


def transcribe(bvid: str, page: int = 1, model_name: Optional[str] = None, language: Optional[str] = None, cookie: str = "") -> List[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError("未安装 faster-whisper。请先执行 pip install faster-whisper 后重试") from exc

    url = "https://www.bilibili.com/video/" + bvid + "?p=" + str(page or 1)

    with tempfile.TemporaryDirectory() as tmp:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "logger": _SILENT_LOGGER,
            "noplaylist": True,  # 关键：只处理当前分P，避免合集整单下载
            # 直接下载音轨（DASH m4a 单流），无需 ffmpeg 合并/转码
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
                **({"Cookie": cookie} if cookie else {}),
            },
        }
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

        # 固定 CPU 推理（device=auto 在无 CUDA 库的机器上会因 cublas 缺失而失败）
        model = WhisperModel(model_name or "base", device="cpu", compute_type="int8")
        lang = language or None  # None = 自动检测
        segments, _info = model.transcribe(
            os.path.join(tmp, files[0]), language=lang, beam_size=5
        )
        return [
            {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
            for s in segments
        ]
