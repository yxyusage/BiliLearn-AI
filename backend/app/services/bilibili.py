"""B站视频解析与字幕提取（基于 yt-dlp）。"""
import json
import os
import re
import tempfile
from pathlib import Path
from typing import List, Tuple

import httpx
import yt_dlp

from .netutil import clear_proxy_env, has_proxy_env, restore_proxy_env

_LANG_PREFS = ["zh-Hans", "zh-CN", "ai-zh", "zh", "zh-Hant", "zh-TW", "en"]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def _make_headers(cookie: str = "") -> dict:
    headers = dict(_HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    return headers


class VideoError(Exception):
    """视频解析/字幕提取失败。"""


def extract_bvid(url: str) -> str:
    """从链接/文本中识别 BV 号或 av 号。"""
    if not url:
        return ""
    url = url.strip()
    m = re.search(r"(BV[0-9A-Za-z]{10})", url)
    if m:
        return m.group(1)
    m = re.search(r"av(\d+)", url, re.I)
    if m:
        return "av" + m.group(1)
    return url


def parse_video(url: str, cookie: str = "") -> dict:
    """解析单视频或合集链接，返回 bvid、标题、分P列表。"""
    bvid = extract_bvid(url)
    if not bvid:
        raise VideoError("无法从链接中识别 BV 号，请粘贴完整的 B站视频/合集链接")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "http_headers": _make_headers(cookie),
    }
    saved_proxy = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        if has_proxy_env():
            saved_proxy = clear_proxy_env()
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as exc2:  # noqa: BLE001
                raise VideoError("视频解析失败：" + str(exc2)) from exc2
            finally:
                restore_proxy_env(saved_proxy)
        else:
            raise VideoError("视频解析失败：" + str(exc)) from exc
    entries = info.get("entries") or []
    if info.get("_type") == "playlist" and entries:
        pages = [
            {"page": i, "title": (e.get("title") or "") or ("P" + str(i))}
            for i, e in enumerate(entries, start=1)
        ]
        title = info.get("title") or ""
    else:
        m = re.search(r"[?&]p=(\d+)", url)
        page = int(m.group(1)) if m else 1
        pages = [{"page": page, "title": info.get("title") or ""}]
        title = info.get("title") or ""
    return {
        "bvid": bvid,
        "title": title,
        "uploader": info.get("uploader") or info.get("channel") or "",
        "pages": pages,
    }


def get_subtitles(bvid: str, page: int = 1, cookie: str = "") -> Tuple[List[dict], str]:
    """优先抓取 B站官方 CC 字幕（UP 主上传/AI 字幕），返回 (字幕列表, 来源说明)。"""
    url = "https://www.bilibili.com/video/" + bvid
    if page and page > 1:
        url += "?p=" + str(page)
    base_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": list(_LANG_PREFS),
        "http_headers": _make_headers(cookie),
    }
    for attempt in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            # 方式1：从 extract_info 返回的内存数据中读取
            try:
                with yt_dlp.YoutubeDL(base_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                items = _subs_from_info(info)
                if items:
                    return _dedupe(items), "官方字幕(CC)"
            except Exception:
                pass
            # 方式2：下载字幕文件到临时目录再解析
            try:
                disk_opts = dict(base_opts)
                disk_opts["outtmpl"] = os.path.join(tmp, "%(id)s.%(ext)s")
                with yt_dlp.YoutubeDL(disk_opts) as ydl:
                    ydl.download([url])
            except Exception:
                pass
            for name in sorted(os.listdir(tmp)):
                ext = name.rsplit(".", 1)[-1] if "." in name else ""
                try:
                    raw = Path(os.path.join(tmp, name)).read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                items = _parse_subtitle_text(raw, ext)
                if items:
                    return _dedupe(items), "官方字幕(CC)"
        # 首次失败且系统有代理：清代理直连重试一次
        if attempt == 0 and has_proxy_env():
            clear_proxy_env()
        else:
            break
    return [], ""


def _subs_from_info(info: dict) -> List[dict]:
    for source in ("subtitles", "automatic_captions"):
        subs = info.get(source) or {}
        if not isinstance(subs, dict):
            continue
        for lang in _LANG_PREFS:
            for entry in subs.get(lang) or []:
                items = _parse_subtitle_entry(entry)
                if items:
                    return items
    return []


def _parse_subtitle_entry(entry: dict) -> List[dict]:
    if not isinstance(entry, dict):
        return []
    data = entry.get("data")
    if data is not None:
        if isinstance(data, (list, dict)):
            return _parse_json_sub(data)
        return _parse_subtitle_text(str(data), entry.get("ext") or "json")
    url = entry.get("url")
    if url:
        try:
            resp = httpx.get(
                url,
                timeout=30,
                follow_redirects=True,
                headers={"Referer": "https://www.bilibili.com/", "User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            return _parse_subtitle_text(resp.text, entry.get("ext") or "json3")
        except Exception:
            return []
    return []


def _parse_subtitle_text(raw: str, ext: str) -> List[dict]:
    ext = (ext or "").lower().split("+")[0]
    if ext in ("srt", "vtt", "webvtt"):
        return _parse_srt_vtt(raw)
    if ext in ("ass", "ssa"):
        return _parse_ass(raw)
    try:
        data = json.loads(raw)
        return _parse_json_sub(data)
    except Exception:
        return []


def _parse_json_sub(data) -> List[dict]:
    if isinstance(data, dict):
        if isinstance(data.get("body"), list):
            segments = data["body"]
        elif isinstance(data.get("events"), list):
            segments = data["events"]
        elif isinstance(data.get("data"), list):
            segments = data["data"]
        elif isinstance(data.get("subtitles"), list):
            segments = data["subtitles"]
        else:
            segments = []
    elif isinstance(data, list):
        segments = data
    else:
        return []
    items = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        start = seg.get("from", seg.get("start", seg.get("tStartMs")))
        end = seg.get("to", seg.get("end"))
        if end is None and seg.get("dDurationMs") is not None and start is not None:
            end = float(start) + float(seg.get("dDurationMs"))
        text = seg.get("content", seg.get("text", ""))
        if not text and isinstance(seg.get("segs"), list):
            text = "".join(str(s.get("utf8", "")) for s in seg["segs"])
        if start is None or not text:
            continue
        try:
            start = float(start)
            end = float(end) if end is not None else start + 3.0
        except (TypeError, ValueError):
            continue
        if "tStartMs" in seg:  # YouTube json3 风格，明确为毫秒
            start /= 1000.0
            if end is not None:
                end /= 1000.0
        elif end is not None and end - start > 100:  # 时长明显超过 100 秒 => 毫秒
            start /= 1000.0
            end /= 1000.0
        text = _clean_sub_text(str(text))
        if text:
            items.append({"start": start, "end": end, "text": text})
    return items


def _parse_srt_vtt(raw: str) -> List[dict]:
    items = []
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            i += 1
            continue
        m = re.match(
            r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})", line
        )
        if m:
            start = _sub_time_to_sec(m.group(1))
            end = _sub_time_to_sec(m.group(2))
            texts = []
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                texts.append(lines[i].strip())
                i += 1
            text = _clean_sub_text(" ".join(texts))
            if text:
                items.append({"start": start, "end": end, "text": text})
        i += 1
    return items


def _parse_ass(raw: str) -> List[dict]:
    items = []
    for line in raw.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        start = _ass_time(parts[1].strip())
        end = _ass_time(parts[2].strip())
        text = _clean_sub_text(parts[9].replace("\\N", " "))
        if start is not None and text:
            items.append({"start": start, "end": end if end is not None else start + 3.0, "text": text})
    return items


def _ass_time(s: str):
    m = re.match(r"(\d+):(\d{1,2}):(\d{1,2})(?:[.,](\d+))?", s)
    if not m:
        return None
    h, mm, ss = int(m.group(1)), int(m.group(2)), int(m.group(3))
    frac = m.group(4) or "0"
    return h * 3600 + mm * 60 + ss + float("0." + frac)


def _sub_time_to_sec(s: str) -> float:
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(s)


def _clean_sub_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _dedupe(items: List[dict]) -> List[dict]:
    out = []
    for it in items:
        if out and out[-1]["text"] == it["text"] and it["start"] - out[-1]["start"] < 2:
            out[-1]["end"] = it["end"]
            continue
        out.append(it)
    return out
