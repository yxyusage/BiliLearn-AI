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


def _assemble_chapters(plan, sections: List[dict]) -> List[dict]:
    """按模型给出的章节划分（小节编号）拼装章节，正文一律取原始小节内容。

    知识点正文与时间戳不经过模型二次转写，因此不会被改写或截断。
    """
    total = len(sections)
    used = set()
    out: List[dict] = []
    for ch in plan or []:
        if not isinstance(ch, dict):
            continue
        title = str(ch.get("title") or "").strip() or "未命名章节"
        idxs = ch.get("sections", ch.get("indexes"))
        if isinstance(idxs, (int, float)):
            idxs = [idxs]
        if not isinstance(idxs, list):
            continue
        points: List[dict] = []
        for raw in idxs:
            try:
                n = int(raw)
            except (TypeError, ValueError):
                continue
            if n < 1 or n > total or n in used:
                continue
            used.add(n)
            points.extend(sections[n - 1].get("points") or [])
        if points:
            out.append({"title": title, "points": points})

    # 兜底：模型漏掉或编号非法的小节，按原顺序补进来，确保知识点不丢失
    if total and len(used) < total:
        leftovers: List[dict] = []
        for i, sec in enumerate(sections, start=1):
            if i not in used:
                leftovers.extend(sec.get("points") or [])
        if leftovers:
            out.append({"title": "补充要点", "points": leftovers})
    return out


def generate_note(subtitles: List[dict], subject: str, llm: BaseLLM, video_title: str = "") -> dict:
    """map-reduce：分段生成小节笔记，再全局汇总为最终笔记。

    注意：汇总（reduce）阶段**只让模型输出章节划分方案**（标题/概述/章节编号归属/脑图），
    知识点正文由程序按编号搬运。原因是模型输出 token 上限（DeepSeek 为 8192）远小于
    输入上限，若要求模型把全部知识点原样重写一遍，长视频必然超出上限被截断，
    导致返回的 JSON 不完整而解析失败。
    """
    if not subtitles:
        raise ValueError("字幕为空，无法生成笔记")
    chunks = split_subtitles(subtitles)
    total = len(chunks)

    # ── map：逐段生成小节笔记 ──
    sections: List[dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        data = llm.chat_json(chunk_prompt(subject, build_transcript(chunk), idx, total))
        if isinstance(data, list):
            data = {"sections": data}
        if not isinstance(data, dict):
            data = {}
        for sec in data.get("sections") or []:
            if isinstance(sec, dict) and (sec.get("points") or []):
                sections.append(sec)

    if not sections:
        raise ValueError("模型未能生成任何小节内容")

    # ── reduce：只生成目录框架，正文由 _assemble_chapters 拼装 ──
    indexed = [
        {
            "i": i,
            "title": str(sec.get("title") or "").strip(),
            "points": sec.get("points") or [],
        }
        for i, sec in enumerate(sections, start=1)
    ]
    reduced = llm.chat_json(
        reduce_prompt(subject, json.dumps(indexed, ensure_ascii=False), video_title)
    )
    if not isinstance(reduced, dict):
        reduced = {}

    return normalize_note({
        "title": reduced.get("title"),
        "summary": reduced.get("summary"),
        "chapters": _assemble_chapters(reduced.get("chapters"), sections),
        "mindmap": reduced.get("mindmap"),
    })


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
