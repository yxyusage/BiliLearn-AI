"""合集复习资料：把多集笔记蒸馏重排成一份可打印的复习资料（PDF）。"""
import html as html_lib
import json
import re
import threading
from typing import Any, Dict, List, Optional

from ..database import SessionLocal
from ..models import CollectionJob, Note, ReviewMaterial
from ..services.llm.base import BaseLLM
from ..services.note_generator import normalize_note
from ..services.prompts import SUBJECTS, review_material_prompt
from ..services.export_assets import html_to_pdf, katex_assets


def distill_note(note_json: dict, page: int, title: str) -> dict:
    chapters = []
    for ch in note_json.get("chapters") or []:
        sections = []
        for sec in ch.get("sections") or []:
            blocks = []
            for b in sec.get("blocks") or []:
                btype = b.get("type")
                if btype in ("formula", "code", "table", "steps", "list", "quote"):
                    blocks.append(b)
                elif btype == "text":
                    content = str(b.get("content") or "")
                    if len(content) > 300:
                        content = content[:300] + "…"
                    blocks.append({"type": "text", "content": content})
            if blocks:
                sections.append({
                    "heading": sec.get("heading") or "",
                    "type": sec.get("type") or "concept",
                    "blocks": blocks,
                })
        if sections:
            chapters.append({
                "title": ch.get("title") or "",
                "sections": sections,
                "key_points": ch.get("key_points") or [],
            })
    return {
        "page": page,
        "title": title,
        "chapters": chapters,
        "exam_points": note_json.get("exam_points") or [],
    }


def _set_progress(mat_id: int, progress: str):
    db = SessionLocal()
    try:
        m = db.query(ReviewMaterial).filter(ReviewMaterial.id == mat_id).first()
        if m:
            m.progress = progress
            db.commit()
    finally:
        db.close()


def generate_review_material(mat_id: int, llm: BaseLLM):
    db = SessionLocal()
    try:
        mat = db.query(ReviewMaterial).filter(ReviewMaterial.id == mat_id).first()
        if not mat:
            return
        job = db.query(CollectionJob).filter(CollectionJob.id == mat.collection_job_id).first()
        if not job:
            mat.status = "failed"
            mat.error = "合集任务不存在"
            db.commit()
            return
        notes = (
            db.query(Note)
            .filter(Note.bvid == job.bvid, Note.status == "done", Note.note_json != "")
            .order_by(Note.page.asc())
            .all()
        )
        if not notes:
            mat.status = "failed"
            mat.error = "该合集还没有已完成的笔记"
            db.commit()
            return
        db.close()

        _set_progress(mat_id, "正在蒸馏 " + str(len(notes)) + " 篇笔记…")
        distilled = []
        for n in notes:
            try:
                nj = normalize_note(json.loads(n.note_json))
                distilled.append(distill_note(nj, n.page, n.title))
            except Exception:
                continue
        if not distilled:
            db = SessionLocal()
            mat = db.query(ReviewMaterial).filter(ReviewMaterial.id == mat_id).first()
            mat.status = "failed"
            mat.error = "笔记数据解析失败"
            db.commit()
            return

        distilled_json = json.dumps(distilled, ensure_ascii=False)
        _set_progress(mat_id, "正在 AI 重排知识体系（" + str(len(distilled)) + " 集）…")

        data = llm.chat_json(review_material_prompt(job.title, mat.subject, distilled_json), max_tokens=32000)

        db = SessionLocal()
        mat = db.query(ReviewMaterial).filter(ReviewMaterial.id == mat_id).first()
        mat.result_json = json.dumps(data, ensure_ascii=False)
        mat.status = "done"
        mat.progress = "完成"
        if not mat.title:
            mat.title = data.get("title") or (job.title + " 复习资料")
        db.commit()
    except Exception as exc:
        db = SessionLocal()
        try:
            mat = db.query(ReviewMaterial).filter(ReviewMaterial.id == mat_id).first()
            if mat:
                mat.status = "failed"
                mat.error = str(exc)[:500]
                db.commit()
        finally:
            db.close()


# ===== HTML 渲染 =====

def _esc(text: Any) -> str:
    return html_lib.escape(str(text or ""))


def _render_inline(text: str) -> str:
    escaped = _esc(text)
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)
    return escaped


def _importance_stars(imp: str) -> str:
    if imp == "必考":
        return '<span class="rm-imp rm-imp-high" title="必考">★★★</span>'
    if imp == "掌握":
        return '<span class="rm-imp rm-imp-mid" title="掌握">★★</span>'
    return '<span class="rm-imp rm-imp-low" title="了解">★</span>'


def _render_block(b: dict) -> str:
    btype = b.get("type")
    if btype == "heading":
        return '<h4 class="rm-subheading">' + _render_inline(b.get("content") or "") + "</h4>"
    if btype == "text":
        return '<p class="rm-text">' + _render_inline(b.get("content") or "") + "</p>"
    if btype == "formula":
        return '<div class="rm-formula">$$' + _esc(b.get("content") or "") + "$$</div>"
    if btype == "steps":
        items = b.get("items") or []
        lis = "".join('<li class="rm-step-item">' + _render_inline(it) + "</li>" for it in items)
        return '<ol class="rm-steps">' + lis + "</ol>"
    if btype == "list":
        items = b.get("items") or []
        ordered = bool(b.get("ordered"))
        lis = "".join("<li>" + _render_inline(it) + "</li>" for it in items)
        tag = "ol" if ordered else "ul"
        return '<' + tag + ' class="rm-list">' + lis + "</" + tag + ">"
    if btype == "code":
        lang = _esc(b.get("language") or "")
        content = _esc(b.get("content") or "")
        return '<pre class="rm-code"><code data-lang="' + lang + '">' + content + "</code></pre>"
    if btype == "table":
        headers = b.get("headers") or []
        rows = b.get("rows") or []
        th = "".join("<th>" + _render_inline(h) + "</th>" for h in headers)
        trs = ""
        for row in rows:
            tds = "".join("<td>" + _render_inline(c) + "</td>" for c in row)
            trs += "<tr>" + tds + "</tr>"
        return '<table class="rm-table"><thead><tr>' + th + "</tr></thead><tbody>" + trs + "</tbody></table>"
    if btype == "quote":
        return '<blockquote class="rm-quote">' + _render_inline(b.get("content") or "") + "</blockquote>"
    return ""


def _render_quiz(q: dict) -> str:
    no = q.get("no", "?")
    qtype = q.get("type", "")
    stem = _render_inline(q.get("stem") or "")
    type_names = {"single": "单选", "fill": "填空", "calc": "计算", "judge": "判断"}
    label = type_names.get(qtype, qtype)
    html = '<div class="rm-quiz-item"><span class="rm-quiz-no">第' + str(no) + "题</span>"
    html += '<span class="rm-quiz-type">' + label + "</span>"
    html += '<div class="rm-quiz-stem">' + stem + "</div>"
    if qtype == "single":
        opts = q.get("options") or []
        letters = ["A", "B", "C", "D", "E", "F"]
        ol = ""
        for i, opt in enumerate(opts):
            letter = letters[i] if i < len(letters) else str(i + 1)
            ol += '<li><span class="rm-opt-letter">' + letter + ".</span> " + _render_inline(opt) + "</li>"
        html += '<ol class="rm-quiz-options">' + ol + "</ol>"
    html += "</div>"
    return html


def _render_answer(a: dict) -> str:
    no = a.get("no", "?")
    answer = _render_inline(a.get("answer") or "")
    explanation = _render_inline(a.get("explanation") or "")
    html = '<div class="rm-answer-item"><span class="rm-answer-no">第' + str(no) + "题</span>"
    html += '<span class="rm-answer-text">答案：' + answer + "</span>"
    if explanation:
        html += '<div class="rm-answer-expl">解析：' + explanation + "</div>"
    html += "</div>"
    return html


def _render_learning_objectives(lo: dict) -> str:
    if not lo:
        return ""
    html = '<div class="rm-objectives"><strong>学习目标</strong><div class="rm-obj-grid">'
    for key, label, cls in [("master", "掌握", "rm-obj-master"), ("understand", "理解", "rm-obj-understand"), ("know", "了解", "rm-obj-know")]:
        items = lo.get(key) or []
        if items:
            html += '<div class="rm-obj ' + cls + '"><span class="rm-obj-label">' + label + '</span><ul>'
            html += "".join("<li>" + _render_inline(m) + "</li>" for m in items)
            html += "</ul></div>"
    html += "</div></div>"
    return html


def _render_confusion_points(cps: list) -> str:
    if not cps:
        return ""
    html = '<div class="rm-confusion"><h4 class="rm-confusion-heading">易混点辨析</h4>'
    for cp in cps:
        html += '<div class="rm-confusion-item">'
        html += '<div class="rm-confusion-point">' + _esc(cp.get("point") or "") + "</div>"
        html += '<div class="rm-confusion-ab">'
        html += '<div class="rm-confusion-a"><span class="rm-cf-label">A</span> ' + _render_inline(cp.get("a") or "") + "</div>"
        html += '<div class="rm-confusion-b"><span class="rm-cf-label">B</span> ' + _render_inline(cp.get("b") or "") + "</div>"
        html += "</div>"
        html += '<div class="rm-confusion-diff"><strong>区别：</strong>' + _render_inline(cp.get("difference") or "") + "</div>"
        html += "</div>"
    html += "</div>"
    return html


def render_review_material_html(data: dict, meta: Optional[dict] = None, page_numbers: Optional[List[int]] = None) -> str:
    meta = meta or {}
    title = data.get("title") or "复习资料"
    subject_name = SUBJECTS.get(data.get("subject") or meta.get("subject", "general"), data.get("subject") or "")
    overview = data.get("overview") or ""
    usage_guide = data.get("usage_guide") or ""
    chapters = data.get("chapters") or []
    answers = data.get("answers") or []
    appendix = data.get("appendix") or {}

    katex_css, katex_js, katex_auto = katex_assets()

    toc_items = ""
    for i, ch in enumerate(chapters):
        ch_title = _esc(ch.get("title") or ("第" + str(i + 1) + "章"))
        page_num = page_numbers[i] if page_numbers and i < len(page_numbers) else ""
        page_span = '<span class="rm-toc-page">' + str(page_num) + "</span>" if page_num else ""
        toc_items += '<li><a href="#rm-ch-' + str(i) + '"><span class="rm-toc-title">' + ch_title + "</span>" + page_span + "</a></li>"

    body = ""
    for i, ch in enumerate(chapters):
        ch_title = _esc(ch.get("title") or ("第" + str(i + 1) + "章"))
        intro = ch.get("intro") or ""
        summary = ch.get("summary") or ""
        key_points = ch.get("key_points") or []
        sections = ch.get("sections") or []
        quiz = ch.get("quiz") or []
        confusion = ch.get("confusion_points") or []
        lo = ch.get("learning_objectives") or {}

        body += '<div class="rm-chapter" id="rm-ch-' + str(i) + '">'
        body += '<h2 class="rm-chapter-title">' + ch_title + "</h2>"
        if intro:
            body += '<p class="rm-chapter-intro">' + _esc(intro) + "</p>"
        body += _render_learning_objectives(lo)

        for sec in sections:
            heading = _esc(sec.get("heading") or "")
            imp = sec.get("importance") or ""
            quick_memo = sec.get("quick_memo") or ""
            scenario = sec.get("scenario") or ""
            body += '<div class="rm-section">'
            body += '<h3 class="rm-section-title">' + heading
            if imp:
                body += " " + _importance_stars(imp)
            body += "</h3>"
            if quick_memo:
                body += '<div class="rm-quick-memo"><span class="rm-qm-label">速记</span> ' + _render_inline(quick_memo) + "</div>"
            for b in sec.get("blocks") or []:
                body += _render_block(b)
            if scenario:
                body += '<div class="rm-scenario"><span class="rm-sc-label">场景</span> ' + _render_inline(scenario) + "</div>"
            src = sec.get("source_pages") or []
            if src:
                body += '<p class="rm-source">来源：第' + "、".join(str(p) for p in src) + "集</p>"
            body += "</div>"

        body += _render_confusion_points(confusion)

        if key_points:
            body += '<div class="rm-keypoints"><strong>本章核心结论</strong><ul>'
            for kp in key_points:
                body += "<li>" + _render_inline(kp) + "</li>"
            body += "</ul></div>"
        if summary:
            body += '<p class="rm-chapter-summary"><strong>本章小结：</strong>' + _esc(summary) + "</p>"
        if quiz:
            body += '<div class="rm-quiz-section">'
            body += '<h4 class="rm-quiz-heading">本章测试</h4>'
            for q in quiz:
                body += _render_quiz(q)
            body += "</div>"
        body += '<div class="rm-notes-area"><h4 class="rm-notes-heading">错题 &amp; 笔记区</h4><div class="rm-notes-lines"></div></div>'
        body += "</div>"

    if answers:
        body += '<div class="rm-answers-all" id="rm-answers">'
        body += '<h2 class="rm-chapter-title">答案篇</h2>'
        current_chapter = ""
        for a in answers:
            ch_name = a.get("chapter") or ""
            if ch_name != current_chapter:
                if current_chapter:
                    body += "</div>"
                current_chapter = ch_name
                body += '<div class="rm-answer-chapter"><h3 class="rm-answer-chapter-title">' + _esc(ch_name) + "</h3>"
            body += _render_answer(a)
        if current_chapter:
            body += "</div>"
        body += "</div>"

    formula_sheet = appendix.get("formula_sheet") or []
    glossary = appendix.get("glossary") or []
    flash_cards = appendix.get("flash_cards") or []
    source_map = appendix.get("source_map") or []

    if formula_sheet or glossary or flash_cards or source_map:
        body += '<div class="rm-appendix">'
        body += '<h2 class="rm-chapter-title">附录</h2>'
        if formula_sheet:
            body += '<h3 class="rm-section-title">核心公式表</h3>'
            body += '<table class="rm-table"><thead><tr><th style="width:25%">名称</th><th style="width:45%">公式</th><th style="width:30%">适用场景</th></tr></thead><tbody>'
            for f in formula_sheet:
                name = _esc(f.get("name") or "") if isinstance(f, dict) else ""
                latex = _esc(f.get("latex") or "") if isinstance(f, dict) else _esc(f)
                scene = _esc(f.get("scene") or "") if isinstance(f, dict) else ""
                body += "<tr><td>" + name + '</td><td><div class="rm-formula-inline">$$' + latex + "$$</div></td><td>" + scene + "</td></tr>"
            body += "</tbody></table>"
        if glossary:
            body += '<h3 class="rm-section-title">术语索引</h3>'
            body += '<table class="rm-table"><thead><tr><th style="width:25%">术语</th><th style="width:50%">定义</th><th style="width:25%">所在章节</th></tr></thead><tbody>'
            for g in glossary:
                ch_name = _esc(g.get("chapter") or "")
                ch_idx = next((ci for ci, c in enumerate(chapters) if c.get("title") == g.get("chapter")), -1)
                ch_link = ('<a href="#rm-ch-' + str(ch_idx) + '">' + ch_name + '</a>') if ch_idx >= 0 else ch_name
                body += "<tr><td>" + _esc(g.get("term") or "") + "</td><td>" + _render_inline(g.get("definition") or "") + "</td><td>" + ch_link + "</td></tr>"
            body += "</tbody></table>"
        if flash_cards:
            body += '<h3 class="rm-section-title">核心考点速记卡</h3>'
            body += '<div class="rm-flash-cards">'
            for fc in flash_cards:
                body += '<div class="rm-flash-card">'
                body += '<div class="rm-fc-front">' + _render_inline(fc.get("front") or "") + "</div>"
                body += '<div class="rm-fc-back">' + _render_inline(fc.get("back") or "") + "</div>"
                body += "</div>"
            body += "</div>"
        if source_map:
            body += '<h3 class="rm-section-title">视频来源映射</h3>'
            body += '<table class="rm-table"><thead><tr><th>集数</th><th>标题</th><th>覆盖章节</th></tr></thead><tbody>'
            for s in source_map:
                page = s.get("page", "")
                stitle = _esc(s.get("title") or "")
                covered = "、".join(_esc(c) for c in (s.get("covered_in") or []))
                body += "<tr><td>第" + str(page) + "集</td><td>" + stitle + "</td><td>" + covered + "</td></tr>"
            body += "</tbody></table>"
        body += "</div>"

    css = (
        "@page{size:A4;margin:2.5cm 2cm 2.5cm 2.5cm;"
        "@bottom-center{content:counter(page);font-size:9px;color:#888;}}"
        "body{font-family:'Microsoft YaHei','PingFang SC',sans-serif;font-size:11px;line-height:1.8;"
        "color:#1e272b;word-break:keep-all;overflow-wrap:break-word;}"
        ".rm-cover{text-align:center;padding-top:80px;page-break-after:always;}"
        ".rm-cover h1{font-size:26px;margin-bottom:10px;color:#1a1a2e;}"
        ".rm-cover .rm-subject{font-size:13px;color:#666;margin-bottom:24px;}"
        ".rm-cover .rm-overview{font-size:11px;text-align:left;max-width:480px;margin:0 auto;line-height:2;color:#444;}"
        ".rm-usage{page-break-after:always;padding:20px 0;}"
        ".rm-usage h2{font-size:18px;border-bottom:2px solid #333;padding-bottom:8px;}"
        ".rm-usage p{line-height:2;white-space:pre-line;}"
        ".rm-toc{page-break-after:always;}"
        ".rm-toc h2{font-size:18px;border-bottom:2px solid #333;padding-bottom:8px;}"
        ".rm-toc ol{list-style:none;padding-left:0;}"
        ".rm-toc li{padding:5px 0;border-bottom:1px dotted #ccc;}"
        ".rm-toc a{color:#1a1a2e;text-decoration:none;display:flex;justify-content:space-between;align-items:center;}"
        ".rm-toc-page{color:#888;font-size:10px;}"
        ".rm-chapter{page-break-before:always;}"
        ".rm-chapter-title{font-size:18px;color:#1a1a2e;border-left:5px solid #2d6a4f;padding-left:12px;margin-top:0;margin-bottom:12px;}"
        ".rm-chapter-intro{color:#555;font-style:italic;margin-bottom:14px;padding-left:12px;}"
        ".rm-objectives{background:#f0f7ff;border-radius:6px;padding:10px 14px;margin:12px 0;page-break-inside:avoid;}"
        ".rm-objectives strong{color:#1565c0;font-size:12px;}"
        ".rm-obj-grid{display:flex;gap:12px;margin-top:6px;}"
        ".rm-obj{flex:1;}"
        ".rm-obj-label{display:inline-block;font-size:10px;font-weight:bold;padding:1px 8px;border-radius:3px;color:#fff;margin-bottom:4px;}"
        ".rm-obj-master .rm-obj-label{background:#c62828;}"
        ".rm-obj-understand .rm-obj-label{background:#ef6c00;}"
        ".rm-obj-know .rm-obj-label{background:#558b2f;}"
        ".rm-obj ul{margin:2px 0;padding-left:16px;font-size:10px;}"
        ".rm-obj li{margin:1px 0;}"
        ".rm-section{margin:14px 0;}"
        ".rm-section-title{font-size:14px;color:#2d6a4f;margin-top:16px;margin-bottom:8px;"
        "border-bottom:1px solid #c8e6c9;padding-bottom:4px;display:flex;align-items:center;gap:8px;}"
        ".rm-subheading{font-size:12px;color:#1b4332;margin:10px 0 4px;padding-left:8px;"
        "border-left:3px solid #95d5b2;font-weight:bold;}"
        ".rm-imp{font-size:10px;letter-spacing:1px;}"
        ".rm-imp-high{color:#c62828;}"
        ".rm-imp-mid{color:#ef6c00;}"
        ".rm-imp-low{color:#9e9e9e;}"
        ".rm-quick-memo{background:#fff3e0;border-left:3px solid #ff9800;padding:6px 12px;"
        "margin:8px 0;font-size:10px;border-radius:0 4px 4px 0;page-break-inside:avoid;}"
        ".rm-qm-label{display:inline-block;background:#ff9800;color:#fff;font-size:9px;"
        "padding:1px 6px;border-radius:3px;margin-right:6px;font-weight:bold;}"
        ".rm-scenario{background:#e8f5e9;border-left:3px solid #66bb6a;padding:6px 12px;"
        "margin:8px 0;font-size:10px;border-radius:0 4px 4px 0;page-break-inside:avoid;}"
        ".rm-sc-label{display:inline-block;background:#66bb6a;color:#fff;font-size:9px;"
        "padding:1px 6px;border-radius:3px;margin-right:6px;font-weight:bold;}"
        ".rm-text{margin:6px 0;text-align:justify;}"
        ".rm-formula{text-align:center;margin:10px 0;font-size:13px;overflow-x:auto;page-break-inside:avoid;}"
        ".rm-formula-inline{font-size:11px;}"
        ".rm-steps{padding-left:20px;margin:8px 0;}"
        ".rm-step-item{margin:3px 0;}"
        ".rm-list{padding-left:20px;margin:8px 0;}"
        ".rm-code{background:#f6f8fa;border:1px solid #e1e4e8;border-radius:4px;padding:10px;"
        "overflow-x:auto;font-size:10px;line-height:1.5;page-break-inside:avoid;}"
        ".rm-code code{font-family:Consolas,'Courier New',monospace;white-space:pre;}"
        ".rm-table{border-collapse:collapse;width:100%;margin:10px 0;font-size:10px;}"
        ".rm-table thead{display:table-header-group;}"
        ".rm-table tr{page-break-inside:avoid;}"
        ".rm-table th{background:#2d6a4f;color:#fff;padding:6px 8px;text-align:left;border:1px solid #1b4332;}"
        ".rm-table td{padding:5px 8px;border:1px solid #ddd;vertical-align:top;}"
        ".rm-table tr:nth-child(even){background:#f8f9fa;}"
        ".rm-quote{border-left:3px solid #e9c46a;background:#fffbeb;padding:8px 12px;"
        "margin:8px 0;color:#7c5e10;font-style:italic;page-break-inside:avoid;}"
        ".rm-source{font-size:9px;color:#999;margin-top:4px;text-align:right;}"
        ".rm-confusion{background:#fce4ec;border-radius:6px;padding:10px 14px;margin:14px 0;page-break-inside:avoid;}"
        ".rm-confusion-heading{color:#ad1457;margin:0 0 8px;font-size:12px;}"
        ".rm-confusion-item{margin:8px 0;padding:8px;background:#fff;border-radius:4px;}"
        ".rm-confusion-point{font-weight:bold;color:#ad1457;margin-bottom:4px;}"
        ".rm-confusion-ab{display:flex;gap:12px;margin:4px 0;}"
        ".rm-confusion-a,.rm-confusion-b{flex:1;font-size:10px;}"
        ".rm-cf-label{display:inline-block;background:#ad1457;color:#fff;font-size:9px;"
        "padding:1px 6px;border-radius:3px;margin-right:4px;font-weight:bold;}"
        ".rm-confusion-diff{font-size:10px;color:#555;margin-top:4px;padding-top:4px;border-top:1px dashed #f8bbd0;}"
        ".rm-keypoints{background:#e8f5e9;border-radius:6px;padding:10px 14px;margin:12px 0;page-break-inside:avoid;}"
        ".rm-keypoints ul{margin:4px 0;padding-left:18px;}"
        ".rm-chapter-summary{background:#f0f4f8;padding:8px 12px;border-radius:4px;margin:10px 0;page-break-inside:avoid;}"
        ".rm-quiz-section{margin-top:16px;border-top:2px solid #2d6a4f;padding-top:10px;page-break-inside:avoid;}"
        ".rm-quiz-heading{font-size:13px;color:#2d6a4f;margin-bottom:8px;}"
        ".rm-quiz-item{margin:10px 0;padding:8px;background:#fafbfc;border-radius:4px;page-break-inside:avoid;}"
        ".rm-quiz-no{background:#2d6a4f;color:#fff;padding:1px 8px;border-radius:3px;font-size:10px;margin-right:6px;}"
        ".rm-quiz-type{color:#888;font-size:10px;}"
        ".rm-quiz-stem{margin:6px 0;font-weight:500;}"
        ".rm-quiz-options{padding-left:20px;margin:4px 0;}"
        ".rm-quiz-options li{margin:2px 0;}"
        ".rm-opt-letter{font-weight:bold;color:#2d6a4f;}"
        ".rm-notes-area{margin-top:14px;page-break-inside:avoid;}"
        ".rm-notes-heading{font-size:11px;color:#999;margin-bottom:6px;}"
        ".rm-notes-lines{height:80px;"
        "background:repeating-linear-gradient(transparent,transparent 19px,#e0e0e0 19px,#e0e0e0 20px);border-radius:2px;}"
        ".rm-answers-all{page-break-before:always;}"
        ".rm-answer-chapter{margin:12px 0;}"
        ".rm-answer-chapter-title{font-size:14px;color:#b8860b;border-bottom:1px solid #ffe082;padding-bottom:4px;}"
        ".rm-answer-item{margin:6px 0;font-size:10px;padding:4px 8px;background:#fffde7;border-radius:3px;page-break-inside:avoid;}"
        ".rm-answer-no{font-weight:bold;color:#b8860b;margin-right:6px;}"
        ".rm-answer-text{color:#333;}"
        ".rm-answer-expl{color:#666;margin-top:2px;padding-left:16px;}"
        ".rm-appendix{page-break-before:always;}"
        ".rm-flash-cards{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0;}"
        ".rm-flash-card{width:48%;border:1px solid #ddd;border-radius:6px;overflow:hidden;page-break-inside:avoid;}"
        ".rm-fc-front{background:#1565c0;color:#fff;padding:8px 12px;font-size:10px;font-weight:bold;}"
        ".rm-fc-back{background:#e3f2fd;padding:8px 12px;font-size:10px;}"
    )

    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>" + _esc(title) + "</title>"
        "<link rel='stylesheet' href='" + katex_css + "'>"
        "<script src='" + katex_js + "'></script>"
        "<script src='" + katex_auto + "'></script>"
        "<style>" + css + "</style></head><body>"
        "<div class='rm-cover'>"
        "<h1>" + _esc(title) + "</h1>"
        "<div class='rm-subject'>学科：" + _esc(subject_name) + "</div>"
        "<div class='rm-overview'>" + _esc(overview) + "</div>"
        "</div>"
    )
    if usage_guide:
        html += "<div class='rm-usage'><h2>复习使用指南</h2><p>" + _esc(usage_guide) + "</p></div>"
    html += "<div class='rm-toc'><h2>目录</h2><ol>" + toc_items + "</ol></div>"
    html += body
    html += (
        "<script>document.addEventListener('DOMContentLoaded',function(){renderMathInElement(document.body,"
        "{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false});});</script>"
        "</body></html>"
    )
    return html


def _scan_toc_page_numbers(pdf_bytes: bytes, chapter_count: int) -> List[int]:
    """扫描PDF目录页的内部链接，得到每个章节的页码。"""
    try:
        import pymupdf
    except ImportError:
        return []
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    toc_page_idx = None
    for i, page in enumerate(doc):
        if "目录" in page.get_text() and i < 5:
            toc_page_idx = i
            break
    if toc_page_idx is None:
        doc.close()
        return []
    links = doc[toc_page_idx].get_links()
    goto_links = [l for l in links if l.get("kind") == 4 and l.get("page") is not None and l.get("from")]
    goto_links.sort(key=lambda l: l["from"].y0)
    doc.close()
    toc_pages = [l["page"] + 1 for l in goto_links]
    if len(toc_pages) >= chapter_count:
        return toc_pages[:chapter_count]
    return []


def build_review_material_pdf(data: dict, meta: Optional[dict] = None) -> bytes:
    chapters = data.get("chapters") or []
    html_first = render_review_material_html(data, meta, page_numbers=None)
    pdf_first = html_to_pdf(html_first, timeout=120)
    page_numbers = _scan_toc_page_numbers(pdf_first, len(chapters))
    if page_numbers:
        html_final = render_review_material_html(data, meta, page_numbers=page_numbers)
        return html_to_pdf(html_final, timeout=120)
    return pdf_first
