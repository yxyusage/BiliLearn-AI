"""笔记生成：长字幕自动分段 → 分段小结 → 全局汇总（map-reduce）。

笔记结构 v2（教材精编）：
{
  "title", "summary", "exam_points": [...],
  "chapters": [{
    "title", "time_stamp", "intro", "summary", "key_points": [...],
    "sections": [{
      "type", "heading", "time_stamp", "important",
      "blocks": [{"type": "text|formula|steps|list|code|table|quote", ...}]
    }]
  }],
  "mindmap": "graph TD ..."
}
旧版 chapters[].points 结构在 normalize 时自动转换为 v2，保证历史笔记可读。
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterator, List, Optional, Tuple

from ..config import settings
from .llm import BaseLLM
from .prompts import chunk_prompt, english_extras_prompt, reduce_prompt
from ..utils.timestamp import normalize_hms, seconds_to_hms

SECTION_TYPES = {"definition", "concept", "derivation", "example", "code", "comparison", "conclusion", "keypoints"}
BLOCK_TYPES = {"text", "formula", "steps", "list", "code", "table", "quote"}


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


def fix_mindmap(mindmap: str) -> str:
    """修复模型输出脑图的常见问题：同秒节点 id 冲突/自环。

    节点 id 形如 t_HHMMSS，同一秒出现多个知识点时模型会重复定义 id，
    导致 Mermaid 节点合并、点击跳转错乱。重复定义处追加 _2/_3 后缀。
    """
    text = str(mindmap or "").strip()
    if not text or not re.search(r"\b(?:graph|flowchart)\b", text[:40]):
        return text  # mindmap 关键字语法等不做处理
    counts: Dict[str, int] = {}

    def _repl(m: re.Match) -> str:
        prefix, nid = m.group(1), m.group(2)
        if nid in counts:
            counts[nid] += 1
            return prefix + nid + "_" + str(counts[nid])
        counts[nid] = 1
        return m.group(0)

    return re.sub(r"(^|[\s>])(t_\d{6})(?=[\[\(\{>])", _repl, text, flags=re.MULTILINE)


def _clean(value) -> str:
    return str(value if value is not None else "").strip()


def _hms(value) -> str:
    value = _clean(value)
    return normalize_hms(value) if value else ""


def normalize_block(block: dict) -> Optional[dict]:
    """校验单个内容块；无法识别或为空返回 None。"""
    if not isinstance(block, dict):
        return None
    btype = _clean(block.get("type")).lower()
    if btype not in BLOCK_TYPES:
        # 模型偶尔把段落写成 paragraph/heading 等，统一兜底为 text
        btype = "text"
    if btype == "table":
        headers = [_clean(h) for h in (block.get("headers") or []) if _clean(h)]
        rows = []
        for row in block.get("rows") or []:
            if isinstance(row, list):
                cells = [_clean(c) for c in row]
                if any(cells):
                    rows.append(cells)
        if not rows:
            return None
        return {"type": "table", "headers": headers, "rows": rows}
    if btype in ("steps", "list"):
        items = [_clean(it) for it in (block.get("items") or []) if _clean(it)]
        if not items:
            return None
        return {
            "type": btype,
            "ordered": bool(block.get("ordered")) if btype == "list" else True,
            "items": items,
        }
    if btype == "code":
        content = _clean(block.get("content"))
        if not content:
            return None
        return {"type": "code", "language": _clean(block.get("language")) or "text", "content": content}
    if btype == "formula":
        content = _clean(block.get("content"))
        if not content:
            return None
        content = content.strip("$").strip()
        return {"type": "formula", "content": content}
    # text / quote
    content = _clean(block.get("content"))
    if not content:
        return None
    return {"type": btype, "content": content}


def normalize_section(section: dict) -> Optional[dict]:
    """校验单个小节。"""
    if not isinstance(section, dict):
        return None
    stype = _clean(section.get("type")).lower()
    if stype not in SECTION_TYPES:
        stype = "keypoints"
    heading = _clean(section.get("heading") or section.get("title")) or "未命名小节"
    blocks = []
    for b in section.get("blocks") or []:
        nb = normalize_block(b)
        if nb:
            blocks.append(nb)
    if not blocks:
        return None
    return {
        "type": stype,
        "heading": heading,
        "time_stamp": _hms(section.get("time_stamp") or section.get("timestamp")),
        "important": bool(section.get("important")),
        "blocks": blocks,
    }


def _legacy_points_to_sections(points: List[dict]) -> List[dict]:
    """旧版 points 数组转成一个 keypoints 小节。"""
    items = []
    important = False
    for p in points or []:
        if not isinstance(p, dict):
            continue
        content = _clean(p.get("content"))
        if not content:
            continue
        if p.get("important"):
            important = True
        items.append(content)
    if not items:
        return []
    ts = _hms(points[0].get("time_stamp")) if points and isinstance(points[0], dict) else ""
    return [{
        "type": "keypoints",
        "heading": "知识要点",
        "time_stamp": ts,
        "important": important,
        "blocks": [{"type": "list", "ordered": False, "items": items}],
    }]


def normalize_chapter(chapter: dict) -> Optional[dict]:
    """校验单个章节，兼容旧 points 结构。"""
    if not isinstance(chapter, dict):
        return None
    title = _clean(chapter.get("title")) or "未命名章节"
    raw_sections = chapter.get("sections")
    if isinstance(raw_sections, list) and raw_sections:
        sections = [s for s in (normalize_section(x) for x in raw_sections) if s]
    else:
        sections = _legacy_points_to_sections(chapter.get("points") or [])
    if not sections:
        return None
    # 章节时间戳优先取模型给的，否则取第一个有时间戳的小节
    ch_ts = _hms(chapter.get("time_stamp") or chapter.get("timestamp"))
    if not ch_ts:
        ch_ts = next((s["time_stamp"] for s in sections if s.get("time_stamp")), "")
    key_points = [_clean(k) for k in (chapter.get("key_points") or []) if _clean(k)]
    return {
        "title": title,
        "time_stamp": ch_ts,
        "intro": _clean(chapter.get("intro")),
        "summary": _clean(chapter.get("summary")),
        "key_points": key_points,
        "sections": sections,
    }


def normalize_note(note: dict) -> dict:
    """校验并规范化笔记结构为 v2，统一时间戳格式，兼容旧结构。"""
    if not isinstance(note, dict):
        raise ValueError("笔记输出格式错误")
    chapters = note.get("chapters") or note.get("sections") or []
    out_chapters = [c for c in (normalize_chapter(x) for x in chapters) if c]
    mindmap = note.get("mindmap") or ""
    if isinstance(mindmap, list):
        mindmap = "\n".join(str(x) for x in mindmap)
    exam_points = []
    for ep in note.get("exam_points") or []:
        if isinstance(ep, dict):
            text = _clean(ep.get("point") or ep.get("content"))
        else:
            text = _clean(ep)
        if text:
            exam_points.append(text)
    return {
        "title": _clean(note.get("title")) or "课程笔记",
        "summary": _clean(note.get("summary")),
        "exam_points": exam_points,
        "chapters": out_chapters,
        "mindmap": fix_mindmap(str(mindmap)),
    }


# ===== 结构访问辅助（测验/答疑/复盘/导出/关键帧统一使用） =====

def iter_sections(note: dict) -> Iterator[Tuple[int, dict, dict]]:
    """遍历 (章节索引, 章节, 小节)。"""
    for ci, ch in enumerate(note.get("chapters") or []):
        for sec in ch.get("sections") or []:
            yield ci, ch, sec


def block_text(block: dict) -> str:
    """把单个内容块转成纯文本。"""
    t = block.get("type")
    if t in ("steps", "list"):
        sep = "\n" if t == "steps" else "\n"
        return sep.join(("- " if t == "list" else "") + str(it) for it in block.get("items") or [])
    if t == "table":
        lines = []
        if block.get("headers"):
            lines.append(" | ".join(block["headers"]))
        for row in block.get("rows") or []:
            lines.append(" | ".join(str(c) for c in row))
        return "\n".join(lines)
    if t == "formula":
        return "$$" + str(block.get("content") or "") + "$$"
    if t == "code":
        return str(block.get("content") or "")
    return str(block.get("content") or "")


def section_text(section: dict) -> str:
    """小节纯文本（含标题）。"""
    parts = [str(section.get("heading") or "")]
    for b in section.get("blocks") or []:
        parts.append(block_text(b))
    return "\n".join(p for p in parts if p)


def chapter_plain_text(chapter: dict, include_headings: bool = True) -> str:
    parts = []
    if include_headings:
        parts.append(str(chapter.get("title") or ""))
        if chapter.get("intro"):
            parts.append(str(chapter["intro"]))
    for sec in chapter.get("sections") or []:
        parts.append(section_text(sec))
    if chapter.get("summary"):
        parts.append("本章小结：" + str(chapter["summary"]))
    if chapter.get("key_points"):
        parts.append("\n".join("- " + str(k) for k in chapter["key_points"]))
    return "\n".join(p for p in parts if p)


def note_plain_text(note: dict, char_limit: int = 0) -> str:
    """整篇笔记纯文本，供答疑上下文/测验出题使用。char_limit>0 时按章节边界截断。"""
    parts = []
    if note.get("summary"):
        parts.append("概述：" + str(note["summary"]))
    total = sum(len(p) for p in parts)
    for ch in note.get("chapters") or []:
        text = chapter_plain_text(ch)
        if char_limit and total + len(text) > char_limit:
            remain = max(0, char_limit - total)
            if remain > 200:
                parts.append(text[:remain])
            break
        parts.append(text)
        total += len(text)
    return "\n\n".join(parts)


def all_timestamps(note: dict) -> List[str]:
    """收集笔记中全部非空时间戳（按出现顺序）。"""
    out = []
    for _, _, sec in iter_sections(note):
        ts = sec.get("time_stamp")
        if ts and ts not in out:
            out.append(ts)
    return out


def generate_note(subtitles: List[dict], subject: str, llm: BaseLLM, video_title: str = "") -> dict:
    """map-reduce：分段并发生成小节笔记，再全局汇总为最终笔记。"""
    if not subtitles:
        raise ValueError("字幕为空，无法生成笔记")
    chunks = split_subtitles(subtitles)
    total = len(chunks)

    def _map(idx_chunk):
        idx, chunk = idx_chunk
        data = llm.chat_json(chunk_prompt(subject, build_transcript(chunk), idx, total))
        if isinstance(data, list):
            data = {"sections": data}
        if not isinstance(data, dict):
            data = {}
        return data

    if total >= 3:
        with ThreadPoolExecutor(max_workers=3) as pool:
            section_jsons = list(pool.map(_map, enumerate(chunks, start=1)))
    else:
        section_jsons = [_map(x) for x in enumerate(chunks, start=1)]
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
