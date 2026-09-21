"""导出能力：Markdown / PDF（Edge headless）/ Word（Pandoc）/ XMind / Anki。

笔记结构为 v2「教材精编」schema：chapters[].sections[].blocks[]。
旧版 points 结构请先经 note_generator.normalize_note 转换后再传入。
"""
import csv
import html
import json
import os
import tempfile
import uuid
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from typing import List, Optional

from ..utils.timestamp import normalize_hms
from . import export_assets

SECTION_LABELS = {
    "definition": "定义",
    "concept": "讲解",
    "derivation": "推导",
    "example": "例题",
    "code": "代码",
    "comparison": "对比",
    "conclusion": "结论",
    "keypoints": "要点",
}


def _cell(value) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _sections(ch: dict) -> list:
    return ch.get("sections") or []


def _md_image(path: str) -> str:
    p = Path(path)
    return "![](" + p.as_posix().replace(" ", "%20") + ")"


# ============================ Markdown ============================

def render_note_markdown(note: dict, subject: str = "general", words: Optional[dict] = None,
                         meta: Optional[dict] = None, frames: Optional[dict] = None,
                         mindmap_mode: str = "mermaid") -> str:
    """生成教材精编版 Markdown。

    frames: {章节索引: [图片绝对路径]}；mindmap_mode: "mermaid"（保留源码）/ "outline"（转大纲，供 Word）。
    """
    fence = chr(96) * 3
    lines = ["# " + str(note.get("title") or "课程笔记"), ""]
    meta = meta or {}
    meta_parts = []
    if meta.get("bvid"):
        meta_parts.append("**视频**：B站 " + str(meta["bvid"]) + " P" + str(meta.get("page") or 1))
    if meta.get("subject_name"):
        meta_parts.append("**学科**：" + str(meta["subject_name"]))
    if meta.get("created_at"):
        meta_parts.append("**生成时间**：" + str(meta["created_at"])[:19].replace("T", " "))
    if meta_parts:
        lines.append(" · ".join(meta_parts))
        lines.append("")

    summary = str(note.get("summary") or "").strip()
    if summary:
        lines.append("> " + summary.replace("\n", "  \n> "))
        lines.append("")

    exam_points = note.get("exam_points") or []
    if exam_points:
        lines.append("## 🎯 本课考点")
        lines.append("")
        for ep in exam_points:
            lines.append("- " + str(ep))
        lines.append("")

    chapters = note.get("chapters") or []
    if chapters:
        lines.append("## 目录")
        lines.append("")
        for idx, ch in enumerate(chapters, start=1):
            lines.append(str(idx) + ". " + str(ch.get("title") or "章节"))
        lines.append("")

    for idx, ch in enumerate(chapters, start=1):
        lines.append("---")
        lines.append("")
        lines.append("## " + str(idx) + ". " + str(ch.get("title") or "章节")
                     + ("  `" + str(ch.get("time_stamp")) + "`" if ch.get("time_stamp") else ""))
        lines.append("")
        intro = str(ch.get("intro") or "").strip()
        if intro:
            lines.append("> " + intro)
            lines.append("")
        if frames and (idx - 1) in frames:
            for img in frames[idx - 1]:
                lines.append(_md_image(img))
            lines.append("")
        for sec in _sections(ch):
            lines.extend(_md_section(sec))
        kp = ch.get("key_points") or []
        if kp:
            lines.append("**✅ 本章要点：**")
            lines.append("")
            for k in kp:
                lines.append("- " + str(k))
            lines.append("")
        ch_summary = str(ch.get("summary") or "").strip()
        if ch_summary:
            lines.append("**本章小结：** " + ch_summary)
            lines.append("")

    mindmap = str(note.get("mindmap") or "").strip()
    if mindmap:
        lines.append("---")
        lines.append("")
        lines.append("## 知识框架")
        lines.append("")
        if mindmap_mode == "outline":
            lines.extend(_mindmap_outline_md(chapters))
        else:
            lines.append(fence + "mermaid")
            lines.append(mindmap)
            lines.append(fence)
        lines.append("")

    _md_words(lines, words)
    lines.append("---")
    lines.append("")
    lines.append("> 本笔记由 BiliLearn-AI 自动生成，网页端时间戳可点击跳转到视频对应片段。")
    return "\n".join(lines)


def _md_section(sec: dict) -> list:
    lines = []
    label = SECTION_LABELS.get(sec.get("type"), "知识点")
    head = "### 【" + label + "】" + str(sec.get("heading") or "")
    if sec.get("time_stamp"):
        head += "  `" + str(sec["time_stamp"]) + "`"
    if sec.get("important"):
        head += "  🔖**重点**"
    lines.append(head)
    lines.append("")
    for b in sec.get("blocks") or []:
        btype = b.get("type")
        if btype == "formula":
            lines.append("")
            lines.append("$$" + str(b.get("content") or "").strip().strip("$") + "$$")
            lines.append("")
        elif btype == "steps":
            for i, it in enumerate(b.get("items") or [], start=1):
                lines.append(str(i) + ". " + str(it))
            lines.append("")
        elif btype == "list":
            mark = "1." if b.get("ordered") else "-"
            for it in b.get("items") or []:
                lines.append(mark + " " + str(it))
            lines.append("")
        elif btype == "code":
            lines.append("```" + str(b.get("language") or ""))
            lines.append(str(b.get("content") or ""))
            lines.append("```")
            lines.append("")
        elif btype == "quote":
            lines.append("> " + str(b.get("content") or ""))
            lines.append("")
        elif btype == "table":
            headers = b.get("headers") or []
            rows = b.get("rows") or []
            ncol = max(len(headers), max((len(r) for r in rows), default=0))
            headers = headers + [""] * (ncol - len(headers))
            lines.append("| " + " | ".join(_cell(h) for h in headers) + " |")
            lines.append("| " + " | ".join(["---"] * ncol) + " |")
            for row in rows:
                row = list(row) + [""] * (ncol - len(row))
                lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
            lines.append("")
        else:
            content = str(b.get("content") or "").strip()
            if content:
                lines.append(content)
                lines.append("")
    return lines


def _mindmap_outline_md(chapters: list) -> list:
    lines = ["（Word 中以大纲形式呈现知识框架）", ""]
    for ci, ch in enumerate(chapters, start=1):
        lines.append("- **" + str(ch.get("title") or "章节") + "**")
        for sec in _sections(ch):
            lines.append("    - 【" + SECTION_LABELS.get(sec.get("type"), "知识点") + "】" + str(sec.get("heading") or ""))
        for k in (ch.get("key_points") or [])[:6]:
            lines.append("    - " + str(k))
    return lines


def _md_words(lines: list, words: Optional[dict]):
    if not words:
        return
    word_list = words.get("words") or []
    if word_list:
        lines.append("---")
        lines.append("")
        lines.append("## 生词本")
        lines.append("")
        lines.append("| 单词 | 音标 | 释义 | 原句 | 时间戳 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for w in word_list:
            lines.append(
                "| " + _cell(w.get("word")) + " | " + _cell(w.get("phonetic")) + " | "
                + _cell(w.get("meaning")) + " | " + _cell(w.get("sentence")) + " | "
                + _cell(w.get("time_stamp")) + " |"
            )
        lines.append("")
    pron = words.get("pronunciations") or []
    if pron:
        lines.append("## 语音现象标注")
        lines.append("")
        for it in pron:
            lines.append(
                "- 【" + str(it.get("phenomenon") or "") + "】 "
                + str(it.get("sentence") or "") + "（" + str(it.get("time_stamp") or "") + "）"
            )
        lines.append("")


# ============================ HTML（PDF 打印） ============================

def _inline_md(text: str) -> str:
    """把笔记正文里的轻量 Markdown（粗体/行内代码）转成 HTML，公式交由 KaTeX 渲染。"""
    s = html.escape(str(text or ""))
    s = s.replace("**", "").split("")
    out = []
    for i, part in enumerate(s):
        if i % 2 == 1:
            out.append("<strong>" + part + "</strong>")
        else:
            out.append(part)
    s = "".join(out)
    # `code`
    parts = s.split("`")
    out = []
    for i, part in enumerate(parts):
        out.append(("<code>" + part + "</code>") if i % 2 == 1 else part)
    s = "".join(out)
    return s.replace("\n", "<br>")


def _html_block(b: dict) -> str:
    t = b.get("type")
    if t == "formula":
        return '<div class="b-formula">$$' + html.escape(str(b.get("content") or "").strip().strip("$")) + "$$</div>"
    if t == "steps":
        lis = "".join("<li>" + _inline_md(it) + "</li>" for it in (b.get("items") or []))
        return '<ol class="b-steps">' + lis + "</ol>"
    if t == "list":
        tag = "ol" if b.get("ordered") else "ul"
        lis = "".join("<li>" + _inline_md(it) + "</li>" for it in (b.get("items") or []))
        return "<" + tag + ' class="b-list">' + lis + "</" + tag + ">"
    if t == "code":
        return '<pre class="b-code"><code>' + html.escape(str(b.get("content") or "")) + "</code></pre>"
    if t == "quote":
        return '<blockquote class="b-quote">' + _inline_md(b.get("content")) + "</blockquote>"
    if t == "table":
        headers = b.get("headers") or []
        thead = "".join("<th>" + _inline_md(h) + "</th>" for h in headers)
        rows = ""
        for row in b.get("rows") or []:
            rows += "<tr>" + "".join("<td>" + _inline_md(c) + "</td>" for c in row) + "</tr>"
        return '<table class="b-table"><thead><tr>' + thead + "</tr></thead><tbody>" + rows + "</tbody></table>"
    return '<p class="b-text">' + _inline_md(b.get("content")) + "</p>"


def render_note_html(note: dict, subject: str = "general", words: Optional[dict] = None,
                     meta: Optional[dict] = None, frames: Optional[dict] = None) -> str:
    katex_css, katex_core, katex_js = export_assets.katex_assets()
    mermaid_js = export_assets.mermaid_asset()
    meta = meta or {}
    chapters = note.get("chapters") or []

    meta_parts = []
    if meta.get("bvid"):
        meta_parts.append("B站 " + html.escape(str(meta["bvid"])) + " P" + str(meta.get("page") or 1))
    if meta.get("subject_name"):
        meta_parts.append(html.escape(str(meta["subject_name"])))
    if meta.get("created_at"):
        meta_parts.append(str(meta["created_at"])[:19].replace("T", " "))

    body_chunks = []
    body_chunks.append('<h1 class="doc-title">' + html.escape(str(note.get("title") or "课程笔记")) + "</h1>")
    if meta_parts:
        body_chunks.append('<div class="doc-meta">' + " ｜ ".join(meta_parts) + "</div>")
    summary = str(note.get("summary") or "").strip()
    if summary:
        body_chunks.append('<div class="summary-box">' + _inline_md(summary) + "</div>")

    exam_points = note.get("exam_points") or []
    if exam_points:
        chips = "".join('<span class="exam-chip">' + html.escape(str(ep)) + "</span>" for ep in exam_points)
        body_chunks.append('<div class="exam-points"><div class="exam-head">🎯 本课考点</div><div>' + chips + "</div></div>")

    if chapters:
        toc = "".join(
            '<li><span class="toc-no">' + str(i) + "</span>" + html.escape(str(ch.get("title") or "章节")) + "</li>"
            for i, ch in enumerate(chapters, start=1)
        )
        body_chunks.append('<div class="toc"><div class="toc-head">📑 目录</div><ol>' + toc + "</ol></div>")

    for idx, ch in enumerate(chapters, start=1):
        body_chunks.append('<section class="chapter">')
        body_chunks.append(
            '<h2 class="chapter-title"><span class="chapter-no">' + str(idx) + "</span>"
            + html.escape(str(ch.get("title") or "章节"))
            + ('<span class="ts">' + html.escape(str(ch.get("time_stamp"))) + "</span>" if ch.get("time_stamp") else "")
            + "</h2>"
        )
        if ch.get("intro"):
            body_chunks.append('<p class="chapter-intro">' + _inline_md(ch["intro"]) + "</p>")
        if frames and (idx - 1) in frames:
            imgs = "".join(
                '<img class="frame-img" src="' + Path(p).resolve().as_uri() + '">' for p in frames[idx - 1]
            )
            body_chunks.append('<div class="chapter-frames">' + imgs + "</div>")
        for sec in _sections(ch):
            body_chunks.append(_html_section(sec))
        if ch.get("key_points"):
            lis = "".join("<li>" + _inline_md(k) + "</li>" for k in ch["key_points"])
            body_chunks.append('<div class="chapter-kp"><div class="kp-head">✅ 本章要点</div><ul>' + lis + "</ul></div>")
        if ch.get("summary"):
            body_chunks.append('<div class="chapter-summary"><b>本章小结：</b>' + _inline_md(ch["summary"]) + "</div>")
        body_chunks.append("</section>")

    mindmap = str(note.get("mindmap") or "").strip()
    if mindmap:
        body_chunks.append(
            '<section class="chapter"><h2 class="chapter-title"><span class="chapter-no">★</span>知识框架</h2>'
            '<pre class="mermaid">' + html.escape(mindmap) + "</pre>"
            '<noscript><div class="mermaid-fallback">' + html.escape("\n".join(_mindmap_outline_md(chapters))) + "</div></noscript>"
            "</section>"
        )

    if words and (words.get("words") or []):
        rows = ""
        for w in words["words"]:
            rows += ("<tr><td>" + _cell(w.get("word")) + "</td><td>" + _cell(w.get("phonetic")) + "</td><td>"
                     + _cell(w.get("meaning")) + "</td><td>" + _cell(w.get("sentence")) + "</td><td>"
                     + _cell(w.get("time_stamp")) + "</td></tr>")
        body_chunks.append(
            '<section class="chapter"><h2 class="chapter-title"><span class="chapter-no">Ａ</span>生词本</h2>'
            '<table class="b-table"><thead><tr><th>单词</th><th>音标</th><th>释义</th><th>原句</th><th>时间戳</th></tr></thead>'
            '<tbody>' + rows + "</tbody></table></section>"
        )

    body_chunks.append('<div class="doc-footer">本笔记由 BiliLearn-AI 自动生成</div>')

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>""" + html.escape(str(note.get("title") or "课程笔记")) + """</title>
<link rel="stylesheet" href=\"""" + katex_css + """\">
<style>
@page { size: A4; margin: 15mm 14mm; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #1e272b; font-size: 12px; line-height: 1.75; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.doc-title { font-size: 23px; margin: 0 0 6px; color: #0b665b; }
.doc-meta { color: #8a9296; font-size: 10px; margin-bottom: 14px; }
.summary-box { background: #e6f4f1; border-left: 4px solid #0d7e70; padding: 9px 13px; border-radius: 6px; margin-bottom: 12px; }
.exam-points { border: 1px solid #eed9b4; background: #fbf3e2; border-radius: 8px; padding: 9px 12px; margin-bottom: 12px; break-inside: avoid; }
.exam-head { font-weight: 700; color: #b45309; font-size: 11px; margin-bottom: 5px; }
.exam-chip { display: inline-block; font-size: 10px; color: #b45309; background: #fff; border: 1px solid #eed9b4; border-radius: 999px; padding: 1px 9px; margin: 2px 4px 2px 0; }
.toc { border: 1px solid #e4e2da; border-radius: 8px; padding: 9px 14px; margin-bottom: 14px; break-inside: avoid; }
.toc-head { font-weight: 700; margin-bottom: 4px; color: #0b665b; }
.toc ol { margin: 0; padding-left: 20px; columns: 2; }
.toc li { margin: 2px 0; }
.toc-no { color: #0d7e70; font-weight: 700; margin-right: 5px; }
.chapter { margin-bottom: 14px; }
.chapter-title { font-size: 16px; color: #0b665b; border-bottom: 2px solid #b7ded7; padding-bottom: 4px; margin: 16px 0 8px; break-after: avoid; }
.chapter-no { display: inline-block; min-width: 20px; height: 20px; line-height: 20px; text-align: center; background: #0d7e70; color: #fff; border-radius: 5px; font-size: 11px; margin-right: 8px; padding: 0 5px; }
.ts { float: right; font-size: 10px; color: #8a9296; font-weight: 400; }
.chapter-intro { color: #556066; border-left: 2px solid #e4e2da; padding-left: 11px; margin: 5px 0 8px; }
.chapter-frames { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
.frame-img { width: 32%; border: 1px solid #e4e2da; border-radius: 6px; break-inside: avoid; }
.note-section { border: 1px solid #edebe4; border-radius: 8px; padding: 8px 12px; margin: 9px 0; break-inside: avoid-page; }
.note-section.important { border-color: #eed9b4; background: #fbf3e2; }
.sec-head { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }
.sec-badge { font-size: 9.5px; font-weight: 700; padding: 2px 7px; border-radius: 5px; border: 1px solid; white-space: nowrap; }
.sec-heading { font-weight: 700; font-size: 13px; }
.sec-time { margin-left: auto; font-size: 9.5px; color: #8a9296; }
.sec-definition .sec-badge { color: #1d4ed8; background: #e8effd; border-color: #c6d8f8; }
.sec-concept .sec-badge { color: #0d7e70; background: #e6f4f1; border-color: #b7ded7; }
.sec-derivation .sec-badge { color: #6d28d9; background: #f1ebfd; border-color: #d8c8f6; }
.sec-example .sec-badge { color: #b45309; background: #fbf3e2; border-color: #eed9b4; }
.sec-code .sec-badge { color: #334155; background: #eef1f5; border-color: #d3dae3; }
.sec-comparison .sec-badge { color: #0e7490; background: #e4f4f8; border-color: #b9dee8; }
.sec-conclusion .sec-badge { color: #047857; background: #e3f5ee; border-color: #b8e4d5; }
.sec-keypoints .sec-badge { color: #be123c; background: #fce9ee; border-color: #f4c8d3; }
.b-text { margin: 5px 0; }
.b-formula { background: #f1f0eb; border-radius: 6px; padding: 7px 12px; margin: 7px 0; text-align: center; overflow-x: hidden; white-space: normal; }
.b-steps { margin: 5px 0; padding-left: 0; list-style: none; counter-reset: step; }
.b-steps li { position: relative; padding: 3px 0 3px 26px; margin: 3px 0; counter-increment: step; }
.b-steps li::before { content: counter(step); position: absolute; left: 0; top: 5px; width: 18px; height: 18px; border-radius: 50%; background: #0d7e70; color: #fff; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.b-list { margin: 5px 0; padding-left: 20px; }
.b-code { background: #16202a; color: #dce6ec; border-radius: 7px; padding: 9px 11px; font-size: 10.5px; line-height: 1.55; overflow: hidden; white-space: pre-wrap; word-break: break-word; font-family: Consolas, Monaco, monospace; }
.b-quote { border-left: 3px solid #8a9296; background: #f1f0eb; margin: 6px 0; padding: 5px 11px; color: #556066; border-radius: 0 6px 6px 0; }
.b-table { border-collapse: collapse; width: 100%; margin: 7px 0; font-size: 10.5px; }
.b-table th, .b-table td { border: 1px solid #e4e2da; padding: 5px 9px; text-align: left; vertical-align: top; }
.b-table th { background: #e6f4f1; color: #0b665b; }
.b-table tr:nth-child(even) td { background: #f8f7f3; }
.chapter-kp { background: #fce9ee; border: 1px solid #f4c8d3; border-radius: 8px; padding: 7px 12px; margin: 8px 0; break-inside: avoid; }
.kp-head { color: #be123c; font-weight: 700; font-size: 11px; }
.chapter-kp ul { margin: 4px 0; padding-left: 20px; }
.chapter-summary { background: #e7f4ec; border-radius: 8px; padding: 7px 12px; margin: 8px 0; color: #2f8f5b; break-inside: avoid; }
.mermaid { text-align: center; background: #fff; border: 1px solid #edebe4; border-radius: 8px; padding: 10px; overflow: hidden; }
.mermaid svg { max-width: 100%; height: auto; }
.doc-footer { margin-top: 18px; padding-top: 8px; border-top: 1px solid #e4e2da; color: #8a9296; font-size: 9.5px; text-align: center; }
code { background: rgba(13,126,112,.1); border-radius: 3px; padding: 0 4px; font-family: Consolas, Monaco, monospace; font-size: .92em; }
</style>
</head>
<body>
""" + "\n".join(body_chunks) + """
<script src=\"""" + katex_core + """\"></script>
<script src=\"""" + katex_js + """\"></script>
<script src=\"""" + mermaid_js + """\"></script>
<script>
window.addEventListener('DOMContentLoaded', function () {
  try {
    if (window.renderMathInElement) {
      renderMathInElement(document.body, {
        delimiters: [
          {left: '$$', right: '$$', display: true},
          {left: '$', right: '$', display: false},
          {left: '\\(', right: '\\)', display: false},
          {left: '\\[', right: '\\]', display: true}
        ],
        throwOnError: false
      });
    }
  } catch (e) {}
  try {
    if (window.mermaid) {
      window.mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'loose', flowchart: { htmlLabels: true } });
      window.mermaid.run({ querySelector: '.mermaid' }).catch(function () {});
    }
  } catch (e) {}
});
</script>
</body>
</html>"""


def _html_section(sec: dict) -> str:
    label = SECTION_LABELS.get(sec.get("type"), "知识点")
    important = " important" if sec.get("important") else ""
    head = (
        '<div class="sec-head"><span class="sec-badge">' + label + "</span>"
        '<span class="sec-heading">' + _inline_md(sec.get("heading")) + "</span>"
        + ('<span class="sec-time">' + html.escape(str(sec.get("time_stamp"))) + "</span>" if sec.get("time_stamp") else "")
        + ('<span class="sec-badge" style="color:#be123c;background:#fce9ee;border-color:#f4c8d3">重点</span>' if sec.get("important") else "")
        + "</div>"
    )
    blocks = "".join(_html_block(b) for b in (sec.get("blocks") or []))
    return '<div class="note-section sec-' + str(sec.get("type") or "concept") + important + '">' + head + '<div>' + blocks + "</div></div>"


# ============================ 文档构建 ============================

def build_note_pdf(note: dict, subject: str = "general", words: Optional[dict] = None,
                   meta: Optional[dict] = None, frames: Optional[dict] = None) -> bytes:
    html_text = render_note_html(note, subject, words, meta, frames)
    return export_assets.html_to_pdf(html_text)


def build_note_docx(note: dict, subject: str = "general", words: Optional[dict] = None,
                    meta: Optional[dict] = None, frames: Optional[dict] = None) -> bytes:
    md = render_note_markdown(note, subject, words, meta, frames, mindmap_mode="outline")
    return export_assets.markdown_to_docx(md)


def build_note_xmind(note: dict) -> bytes:
    """生成 .xmind（XMind 2020+ zip 格式），按章→小节→要点组织。"""
    def _node(title, children=None):
        n = {"id": "n" + uuid.uuid4().hex[:12], "class": "topic", "title": str(title)[:160]}
        if children:
            n["children"] = {"attached": children}
        return n

    root_children = []
    for ch in note.get("chapters") or []:
        children = []
        for sec in _sections(ch):
            label = SECTION_LABELS.get(sec.get("type"), "知识点")
            title = "【" + label + "】" + str(sec.get("heading") or "")
            if sec.get("time_stamp"):
                title += "  " + str(sec["time_stamp"])
            children.append(_node(title))
        for k in (ch.get("key_points") or [])[:8]:
            children.append(_node(k))
        if not children:  # 兼容旧版 points
            for p in (ch.get("points") or [])[:10]:
                children.append(_node(str(p.get("content") or "")[:100]))
        root_children.append(_node(ch.get("title") or "章节", children))
    root = _node(note.get("title") or "课程笔记", root_children)
    sheet = {
        "id": "s" + uuid.uuid4().hex[:12],
        "class": "sheet",
        "title": "BiliLearn 笔记",
        "rootTopic": root,
    }
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps([sheet], ensure_ascii=False))
        z.writestr("manifest.json", json.dumps({"file-entries": {"content.json": {}, "metadata.json": {}}}))
        z.writestr("metadata.json", json.dumps({"creator": {"name": "BiliLearn-AI", "version": "1.5"}}))
    return buf.getvalue()


def build_anki_apkg(words: List[dict], deck_name: str = "BiliLearn 生词本") -> bytes:
    try:
        import genanki
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError("未安装 genanki，无法导出 Anki 卡片") from exc
    model = genanki.Model(
        1607392319,
        "BiliLearn Word",
        fields=[
            {"name": "word"}, {"name": "phonetic"}, {"name": "meaning"},
            {"name": "sentence"}, {"name": "time"},
        ],
        templates=[{
            "name": "单词卡",
            "qfmt": "{{word}}<br/><small>{{phonetic}}</small>",
            "afmt": '{{FrontSide}}<hr id="answer">{{meaning}}<br/><i>{{sentence}}</i><br/><small>{{time}}</small>',
        }],
    )
    deck = genanki.Deck(2059400110, deck_name)
    for w in words or []:
        deck.add_note(genanki.Note(model=model, fields=[
            str(w.get("word") or ""),
            str(w.get("phonetic") or ""),
            str(w.get("meaning") or ""),
            str(w.get("sentence") or ""),
            str(normalize_hms(w.get("time_stamp")) if w.get("time_stamp") else ""),
        ]))
    pkg = genanki.Package(deck)
    fd, path = tempfile.mkstemp(suffix=".apkg")
    os.close(fd)
    try:
        pkg.write_to_file(path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def words_to_csv(words: List[dict]) -> str:
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["word", "phonetic", "meaning", "sentence", "time_stamp"])
    for w in words or []:
        writer.writerow([
            w.get("word", ""), w.get("phonetic", ""), w.get("meaning", ""),
            w.get("sentence", ""), w.get("time_stamp", ""),
        ])
    return "\ufeff" + buf.getvalue()
