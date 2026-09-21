"""多模态公式识别：视频关键帧提取（PyAV，无需 ffmpeg）+ 视觉大模型识别 LaTeX。"""
import base64
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List

import yt_dlp

from ..config import DATA_DIR
from .llm import BaseLLM
from .netutil import clear_proxy_env, has_proxy_env, restore_proxy_env
from .note_generator import all_timestamps
from .prompts import FORMULA_SYSTEM
from ..utils.timestamp import hms_to_seconds

VIDEO_CACHE_DIR = DATA_DIR / "cache" / "video_cache"
VIDEO_CACHE_TTL = 6 * 3600  # 缓存 6 小时
VIDEO_CACHE_KEEP = 6        # 最多保留 6 个视频文件


def pick_timestamps(note: dict, max_frames: int = 8) -> List[int]:
    """从笔记全部非零时间戳中均匀取关键帧位置，覆盖整条视频（去重、上限 max_frames 帧）。"""
    stamps = []
    for ts in all_timestamps(note):
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


def _download_video(url: str, cookie: str = "") -> str:
    """下载最高 1080p 视频流，带本地缓存（关键帧/公式识别复用，避免重复下载整片）。"""
    VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestvideo[height<=1080]/bestvideo/best",
        "outtmpl": str(VIDEO_CACHE_DIR / "%(id)s_p%(playlist_index)s.%(ext)s"),
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            **({"Cookie": cookie} if cookie else {}),
        },
    }

    def _do_download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            path = Path(ydl.prepare_filename(info))
            if path.exists() and time.time() - path.stat().st_mtime < VIDEO_CACHE_TTL:
                return str(path)
            ydl.download([url])
            return str(path)

    try:
        result = _do_download()
    except Exception as exc:  # noqa: BLE001
        if has_proxy_env():
            saved = clear_proxy_env()
            try:
                result = _do_download()
            except Exception as exc2:  # noqa: BLE001
                raise RuntimeError("视频流下载失败：" + str(exc2)) from exc2
            finally:
                restore_proxy_env(saved)
        else:
            raise RuntimeError("视频流下载失败：" + str(exc)) from exc

    # 清理旧缓存
    files = sorted(VIDEO_CACHE_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[VIDEO_CACHE_KEEP:]:
        if old.is_file():
            try:
                old.unlink()
            except OSError:
                pass
    return result


def extract_frames(bvid: str, page: int, timestamps: List[int], out_dir: Path, cookie: str = "") -> List[str]:
    """下载视频流并用 PyAV 在指定时间点抽取关键帧，返回图片路径列表。"""
    import av  # faster-whisper 依赖自带 PyAV，也可单独 pip install av

    out_dir.mkdir(parents=True, exist_ok=True)
    url = "https://www.bilibili.com/video/" + bvid + "?p=" + str(page or 1)
    video_path = _download_video(url, cookie)
    paths = []
    container = av.open(video_path)
    try:
        for idx, ts in enumerate(timestamps, start=1):
            out_path = str(out_dir / ("frame_" + str(idx) + ".jpg"))
            try:
                container.seek(int(ts * 1000000), any_frame=False, stream=container.streams.video[0])
                found = False
                for frame in container.decode(video=0):
                    if float(frame.time) >= ts - 1.0:
                        frame.to_image().save(out_path, quality=88)
                        paths.append(out_path)
                        found = True
                        break
                if not found:
                    container.seek(max(0, int((ts - 3) * 1000000)), any_frame=True, stream=container.streams.video[0])
                    for frame in container.decode(video=0):
                        if float(frame.time) >= ts - 1.5:
                            frame.to_image().save(out_path, quality=88)
                            paths.append(out_path)
                            break
            except Exception:
                continue
    finally:
        container.close()
    return paths


def _recognize_one(idx: int, path: str, llm: BaseLLM):
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
        return idx, [], [], str(exc)
    formulas, notes = [], []
    if isinstance(data, dict):
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
    return idx, formulas, notes, ""


def recognize(frames: List[str], llm: BaseLLM) -> dict:
    """并发逐帧调用视觉模型，返回每帧结果与汇总列表。"""
    items, all_formulas, all_notes, errors = [], [], [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda args: _recognize_one(args[0], args[1], llm),
                               list(enumerate(frames, start=1))))
    results.sort(key=lambda x: x[0])
    for idx, formulas, notes, error in results:
        if error:
            errors.append(error)
        items.append({"frame": idx, "formulas": formulas, "notes": notes})
        all_formulas.extend(formulas)
        for n in notes:
            if n not in all_notes:
                all_notes.append(n)
    return {"items": items, "formulas": all_formulas, "notes": all_notes, "errors": errors}
