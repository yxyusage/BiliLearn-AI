"""导出接口：Markdown / PDF / Anki 卡片。"""
import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Note, SubtitleCache
from ..services import note_generator, storage
from ..services.export import (
    build_anki_apkg,
    build_note_docx,
    build_note_pdf,
    build_note_xmind,
    render_note_html,
    render_note_markdown,
    words_to_csv,
)
from ..services.export_assets import html_to_pdf
from ..services.prompts import SUBJECTS

router = APIRouter()



def _subtitle_time(seconds) -> str:
    if seconds is None:
        seconds = 0
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, total_ms = divmod(total_ms, 3600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    secs, millis = divmod(total_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"



def _subtitle_items(note: Note, db: Session) -> list:
    cache = (
        db.query(SubtitleCache)
        .filter(SubtitleCache.key == (note.bvid or "") + "_" + str(note.page or 1))
        .first()
    )
    if not cache or not cache.subtitles:
        return []
    try:
        items = json.loads(cache.subtitles)
    except Exception:
        return []
    return items if isinstance(items, list) else []


def _get_note(note_id: int, db: Session) -> Note:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return note


def _attach(filename: str) -> dict:
    return {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename)}


def _load_frames(note: Note) -> dict:
    """读取笔记关键帧，返回 {章节索引: [图片绝对路径]}。"""
    if not note.keyframes:
        return {}
    try:
        kfs = json.loads(note.keyframes)
    except Exception:
        return {}
    frames_dir = storage.frames_dir(note.id, "keyframes")
    out = {}
    for k in kfs:
        if not isinstance(k, dict):
            continue
        img = str(k.get("image") or "")
        if not img:
            continue
        path = frames_dir / img
        if path.exists():
            out.setdefault(int(k.get("chapter") or 0), []).append(str(path))
    return out


def _note_payload(note: Note):
    note_json = None
    words = None
    if note.note_json:
        try:
            note_json = json.loads(note.note_json)
            # 旧版 points 结构实时归一为 v2，不回写数据库
            note_json = note_generator.normalize_note(note_json)
        except Exception:
            note_json = None
    if note.words:
        try:
            words = json.loads(note.words)
        except Exception:
            words = None
    is_local = (getattr(note, "source", "") or "bilibili") == "local"
    local_path = getattr(note, "local_path", "") or ""
    meta = {
        "bvid": "" if is_local else note.bvid,
        "local_name": Path(local_path).name if is_local and local_path else "",
        "page": note.page,
        "subject_name": SUBJECTS.get(note.subject, note.subject),
        "created_at": note.created_at.isoformat() if note.created_at else "",
    }
    return note_json, words, meta


@router.get("/{note_id}/subtitles")
def export_subtitles(note_id: int, format: str = "srt", db: Session = Depends(get_db)):
    """导出已抓取/已转写的字幕，默认 SRT；也支持 txt / json。"""
    note = _get_note(note_id, db)
    items = _subtitle_items(note, db)
    if not items:
        raise HTTPException(status_code=404, detail="这篇笔记没有可用字幕；可先用有字幕的视频生成，或在设置里开启本地转写")

    fmt = (format or "srt").lower()
    if fmt not in ("srt", "txt", "json"):
        raise HTTPException(status_code=400, detail="不支持的字幕格式，可选 srt / txt / json")

    if fmt == "json":
        body = json.dumps(items, ensure_ascii=False, indent=2)
        media = "application/json; charset=utf-8"
        ext = "json"
    elif fmt == "txt":
        body = "\n".join(str(item.get("content") or item.get("text") or "").strip() for item in items if isinstance(item, dict))
        media = "text/plain; charset=utf-8"
        ext = "txt"
    else:
        blocks = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("content") or item.get("text") or "").strip()
            if not text:
                continue
            blocks.append(
                f"{index}\n{_subtitle_time(item.get('from', item.get('start', 0)))} --> "
                f"{_subtitle_time(item.get('to', item.get('end', 0)))}\n{text}"
            )
        body = "\n\n".join(blocks) + "\n"
        media = "application/x-subrip; charset=utf-8"
        ext = "srt"

    base = (note.title or f"note-{note.id}").replace("/", "_").replace("\\", "_")
    filename = f"{base}.字幕.{ext}"
    headers = _attach(filename)
    headers["Cache-Control"] = "no-store"
    return Response(content=body, media_type=media, headers=headers)


@router.get("/{note_id}/markdown")
def export_markdown(note_id: int, db: Session = Depends(get_db)):
    note = _get_note(note_id, db)
    note_json, words, meta = _note_payload(note)
    if not note_json:
        raise HTTPException(status_code=400, detail="暂无笔记内容")
    md = render_note_markdown(note_json, note.subject, words, meta)
    return Response(
        content=md.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers=_attach(note.title + ".md"),
    )


def _fallback_pdf(note: Note) -> bytes:
    """结构化数据缺失时的保底 PDF（纯文本排版）。"""
    import html as html_lib
    body = html_lib.escape(note.markdown or "").replace("\n", "<br>")
    page = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
        "@page{size:A4;margin:16mm}body{font-family:'Microsoft YaHei',sans-serif;"
        "font-size:12px;line-height:1.8;color:#1e272b;}</style></head><body>"
        "<h1>" + html_lib.escape(note.title or "课程笔记") + "</h1>" + body + "</body></html>"
    )
    return html_to_pdf(page)


@router.get("/{note_id}/pdf")
def export_pdf(note_id: int, db: Session = Depends(get_db)):
    note = _get_note(note_id, db)
    if not note.markdown:
        raise HTTPException(status_code=400, detail="暂无笔记内容")
    try:
        note_json, words, meta = _note_payload(note)
        if note_json:
            data = build_note_pdf(note_json, note.subject, words, meta, frames=_load_frames(note))
        else:
            data = _fallback_pdf(note)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="PDF 导出失败：" + str(exc)) from exc
    return Response(content=data, media_type="application/pdf", headers=_attach(note.title + ".pdf"))


@router.get("/{note_id}/docx")
def export_docx(note_id: int, db: Session = Depends(get_db)):
    note = _get_note(note_id, db)
    note_json, words, meta = _note_payload(note)
    if not note_json:
        raise HTTPException(status_code=400, detail="暂无笔记内容")
    try:
        data = build_note_docx(note_json, note.subject, words, meta, frames=_load_frames(note))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Word 导出失败：" + str(exc)) from exc
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=_attach(note.title + ".docx"),
    )


@router.get("/{note_id}/xmind")
def export_xmind(note_id: int, db: Session = Depends(get_db)):
    note = _get_note(note_id, db)
    try:
        note_json = note_generator.normalize_note(json.loads(note.note_json))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="笔记数据损坏") from exc
    try:
        data = build_note_xmind(note_json)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="XMind 导出失败：" + str(exc)) from exc
    return Response(content=data, media_type="application/octet-stream", headers=_attach(note.title + ".xmind"))


@router.get("/{note_id}/anki")
def export_anki(note_id: int, db: Session = Depends(get_db)):
    note = _get_note(note_id, db)
    words = []
    if note.words:
        try:
            words = json.loads(note.words).get("words") or []
        except Exception:
            words = []
    if not words:
        raise HTTPException(status_code=400, detail="暂无生词数据（仅英语专项笔记会生成生词本）")
    try:
        data = build_anki_apkg(words, note.title + " 生词本")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Anki 导出失败：" + str(exc)) from exc
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers=_attach("bililearn-words.apkg"),
    )


@router.get("/{note_id}/anki.csv")
def export_anki_csv(note_id: int, db: Session = Depends(get_db)):
    note = _get_note(note_id, db)
    words = []
    if note.words:
        try:
            words = json.loads(note.words).get("words") or []
        except Exception:
            words = []
    if not words:
        raise HTTPException(status_code=400, detail="暂无生词数据")
    csv_text = words_to_csv(words)
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers=_attach("bililearn-words.csv"),
    )
