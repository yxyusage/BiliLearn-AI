"""多模态公式识别：视频关键帧提取（PyAV，无需 ffmpeg）+ 视觉大模型识别 LaTeX。"""
import base64
import os
import tempfile
from pathlib import Path
from typing import List

import yt_dlp

from .llm import BaseLLM
from .netutil import clear_proxy_env, has_proxy_env, restore_proxy_env
from .prompts import FORMULA_SYSTEM
from ..utils.timestamp import hms_to_seconds


def pick_timestamps(note: dict, max_frames: int = 8) -> List[int]:
    """从笔记全部非零时间戳中均匀取关键帧位置，覆盖整条视频（去重、上限 max_frames 帧）。"""
    stamps = []
    for ch in (note.get("chapters") or []):
        for pt in (ch.get("points") or []):
            ts = pt.get("time_stamp") or ""
            sec = hms_to_seconds(ts)
            if sec > 0 and sec not in stamps:
                stamps.append(sec)
    if not stamps:
        return []
    stamps.sort()
    if len(stamps) <= max_frames:
        return stamps
    # 在首尾之间均匀取样，确保覆盖全片（而不是只取开头几帧）
    step = (len(stamps) - 1) / (max_frames - 1)
    return [stamps[round(i * step)] for i in range(max_frames)]


def extract_frames(bvid: str, page: int, timestamps: List[int], out_dir: Path, cookie: str = "") -> List[str]:
    """下载视频流并用 PyAV 在指定时间点抽取关键帧，返回图片路径列表。"""
    import av  # faster-whisper 依赖自带 PyAV

    out_dir.mkdir(parents=True, exist_ok=True)
    url = "https://www.bilibili.com/video/" + bvid + "?p=" + str(page or 1)
    paths = []
    with tempfile.TemporaryDirectory() as tmp:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestvideo[height<=720]/bestvideo/best",
            "outtmpl": os.path.join(tmp, "video.%(ext)s"),
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
                    raise RuntimeError("视频流下载失败：" + str(exc2)) from exc2
                finally:
                    restore_proxy_env(saved)
            else:
                raise RuntimeError("视频流下载失败：" + str(exc)) from exc
        files = [f for f in os.listdir(tmp) if f.startswith("video.")]
        if not files:
            raise RuntimeError("未找到视频文件")
        video_path = os.path.join(tmp, files[0])
        container = av.open(video_path)
        for idx, ts in enumerate(timestamps, start=1):
            out_path = str(out_dir / ("frame_" + str(idx) + ".jpg"))
            try:
                container.seek(int(ts * 1000000), any_frame=False)
                for frame in container.decode(video=0):
                    if float(frame.time) >= ts - 1.0:
                        frame.to_image().save(out_path, quality=88)
                        paths.append(out_path)
                        break
            except Exception:
                continue
        container.close()
    return paths


def recognize(frames: List[str], llm: BaseLLM) -> dict:
    """逐帧调用视觉大模型识别公式与板书要点。"""
    formulas = []
    notes = []
    errors = []
    for path in frames:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        messages = [
            {"role": "system", "content": FORMULA_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请识别这张板书/课件关键帧中的公式（转 LaTeX）与板书要点。"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
                ],
            },
        ]
        try:
            data = llm.chat_json(messages)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            continue
        if not isinstance(data, dict):
            continue
        for item in data.get("formulas") or []:
            if not isinstance(item, dict):
                continue
            latex = str(item.get("latex") or "").strip()
            if latex:
                formulas.append({
                    "latex": latex,
                    "description": str(item.get("description") or "").strip(),
                })
        for note_text in data.get("notes") or []:
            note_text = str(note_text or "").strip()
            if note_text and note_text not in notes:
                notes.append(note_text)
    return {"formulas": formulas, "notes": notes, "errors": errors}
