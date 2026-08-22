"""导出接口：Markdown / PDF / Anki 卡片。"""
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import get_db
from ..models import Note
from ..services.export import build_anki_apkg, build_note_docx, build_note_pdf, build_note_xmind, markdown_to_pdf_bytes, words_to_csv
from ..services.prompts import SUBJECTS

router = APIRouter()


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
    frames_dir = DATA_DIR / "notes" / (str(note.id) + "_frames")
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
        except Exception:
            note_json = None
    if note.words:
        try:
            words = json.loads(note.words)
        except Exception:
            words = None
    meta = {
        "bvid": note.bvid,
        "page": note.page,
        "subject_name": SUBJECTS.get(note.subject, note.subject),
        "created_at": note.created_at.isoformat() if note.created_at else "",
    }
    return note_json, words, meta


@router.get("/{note_id}/markdown")
def export_markdown(note_id: int, db: Session = Depends(get_db)):
    note = _get_note(note_id, db)
    if not note.markdown:
        raise HTTPException(status_code=400, detail="暂无笔记内容")
    return Response(
        content=note.markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers=_attach(note.title + ".md"),
    )


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
            data = markdown_to_pdf_bytes(note.markdown, note.title)
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
        note_json = json.loads(note.note_json)
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
