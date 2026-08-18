"""笔记生成：长字幕自动分段 → 分段小结 → 全局汇总（map-reduce）。"""
import json
from typing import Dict, List, Optional

from ..config import settings
from .llm import BaseLLM
from .prompts import chunk_prompt, english_extras_prompt, reduce_prompt
from ..utils.timestamp import normalize_hms, seconds_to_hms


def build_transcript(subtitles: List[dict]) -> str:
    lines = []
    for s in subtitles or []:
        text = str(s.get("text") or "").strip()
        if not text:
            continue
        lines.append("[" + seconds_to_hms(s.get("start") or 0) + "] " + text)
    return "\n".join(lines)


def split_subtitles(subtitles: List[dict], max_chars: Optional[int] = None) -> List[List[dict]]:
    """按累计字符数把字幕拆成多段，应对长视频上下文窗口限制。"""
    max_chars = max_chars or settings.subtitle_chunk_chars
    chunks: List[List[dict]] = []
    current: List[dict] = []
    size = 0
    for s in subtitles or []:
        line = "[" + seconds_to_hms(s.get("start") or 0) + "] " + str(s.get("text") or "").strip()
        if current and size + len(line) > max_chars:
            chunks.append(current)
            current, size = [], 0
        current.append(s)
        size += len(line)
    if current:
        chunks.append(current)
    return chunks


def normalize_note(note: dict) -> dict:
    """校验并规范化笔记结构，统一时间戳格式。"""
    if not isinstance(note, dict):
        raise ValueError("笔记输出格式错误")
    chapters = note.get("chapters") or note.get("sections") or []
    out_chapters = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        title = str(ch.get("title") or "").strip() or "未命名章节"
        points = []
        for p in ch.get("points") or []:
            if not isinstance(p, dict):
                continue
            content = str(p.get("content") or "").strip()
            if not content:
                continue
            ts = p.get("time_stamp") or p.get("timestamp") or ""
            points.append({
                "content": content,
                "time_stamp": normalize_hms(ts) if ts else "",
                "important": bool(p.get("important")),
            })
        if points:
            out_chapters.append({"title": title, "points": points})
    mindmap = note.get("mindmap") or ""
    if isinstance(mindmap, list):
        mindmap = "\n".join(str(x) for x in mindmap)
    return {
        "title": str(note.get("title") or "").strip() or "课程笔记",
        "summary": str(note.get("summary") or "").strip(),
        "chapters": out_chapters,
        "mindmap": str(mindmap).strip(),
    }


def generate_note(subtitles: List[dict], subject: str, llm: BaseLLM, video_title: str = "") -> dict:
    """map-reduce：分段生成小节笔记，再全局汇总为最终笔记。"""
    if not subtitles:
        raise ValueError("字幕为空，无法生成笔记")
    chunks = split_subtitles(subtitles)
    total = len(chunks)
    section_jsons = []
    for idx, chunk in enumerate(chunks, start=1):
        data = llm.chat_json(chunk_prompt(subject, build_transcript(chunk), idx, total))
        if isinstance(data, list):
            data = {"sections": data}
        if not isinstance(data, dict):
            data = {}
        section_jsons.append(data)
    note = llm.chat_json(reduce_prompt(subject, json.dumps(section_jsons, ensure_ascii=False), video_title))
    return normalize_note(note)


def generate_english_extras(subtitles: List[dict], note: dict, llm: BaseLLM) -> dict:
    """英语专项：生词提取 + 语音现象标注。"""
    data = llm.chat_json(english_extras_prompt(build_transcript(subtitles), json.dumps(note, ensure_ascii=False)))
    if not isinstance(data, dict):
        raise ValueError("英语专项输出格式错误")
    words = []
    for w in data.get("words") or []:
        if not isinstance(w, dict):
            continue
        word = str(w.get("word") or "").strip()
        if not word:
            continue
        ts = w.get("time_stamp") or ""
        words.append({
            "word": word,
            "phonetic": str(w.get("phonetic") or "").strip(),
            "meaning": str(w.get("meaning") or "").strip(),
            "sentence": str(w.get("sentence") or "").strip(),
            "time_stamp": normalize_hms(ts) if ts else "",
        })
    pron = []
    for p in data.get("pronunciations") or []:
        if not isinstance(p, dict):
            continue
        sentence = str(p.get("sentence") or "").strip()
        if not sentence:
            continue
        ts = p.get("time_stamp") or ""
        pron.append({
            "phenomenon": str(p.get("phenomenon") or "").strip(),
            "sentence": sentence,
            "time_stamp": normalize_hms(ts) if ts else "",
        })
    return {"words": words, "pronunciations": pron}
