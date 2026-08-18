"""笔记生成与历史管理接口。"""
import datetime
import json
import re
import threading
import traceback
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import SessionLocal, get_db
from ..models import Note, SubtitleCache
from ..schemas import ChatRequest, FormulaRequest, GenerateRequest
from ..services import bilibili, export as export_service, note_generator, whisper
from ..services.llm import build_llm
from ..services.prompts import CHAT_SYSTEM, SUBJECTS as SUBJECT_NAMES
from ..services.settings_store import get_setting, resolve_llm_config, whisper_enabled

router = APIRouter()

SUBJECTS = ("general", "english", "math", "cs", "liberal")


def _markdown_path(note_id: int, title: str) -> Path:
    notes_dir = DATA_DIR / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\r\n]+', "_", title or "").strip("_") or "note"
    return notes_dir / (str(note_id).zfill(4) + "_" + safe[:60] + ".md")


def _save_markdown_file(note_id: int, title: str, markdown: str) -> str:
    path = _markdown_path(note_id, title)
    path.write_text(markdown, encoding="utf-8")
    return str(path)


def _run_generation(note_id: int, llm_cfg: dict):
    """后台线程执行：取字幕 → 分学科笔记 → 英语专项 → 落库。"""
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return
        try:
            key = note.bvid + "_" + str(note.page)
            cache = db.query(SubtitleCache).filter(SubtitleCache.key == key).first()
            subtitles = []
            if cache:
                try:
                    subtitles = json.loads(cache.subtitles)
                except Exception:
                    subtitles = []
            if not subtitles:
                subtitles, _source = bilibili.get_subtitles(note.bvid, note.page, get_setting(db, "bili_cookie", ""))
                if subtitles and not cache:
                    db.add(SubtitleCache(
                        key=key,
                        video_title=note.title,
                        subtitles=json.dumps(subtitles, ensure_ascii=False),
                    ))
                    db.commit()
            if not subtitles and whisper_enabled(db):
                note.error = "未获取到官方字幕，正在本地语音转写（耗时较长）..."
                db.commit()
                subtitles = whisper.transcribe(
                    note.bvid,
                    note.page,
                    model_name=get_setting(db, "whisper_model", "base"),
                    language=get_setting(db, "whisper_language", "") or None,
                    cookie=get_setting(db, "bili_cookie", ""),
                )
                # 转写结果同样入缓存，重复处理不再转写
                if subtitles:
                    db.add(SubtitleCache(
                        key=key,
                        video_title=note.title,
                        subtitles=json.dumps(subtitles, ensure_ascii=False),
                    ))
                    db.commit()
            if not subtitles:
                raise ValueError("未获取到字幕。视频可能没有官方字幕，可在配置页开启本地语音转写。")
            note.error = "字幕已就绪，正在生成笔记（长视频会分段处理）..."
            db.commit()
            llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
            note_json = note_generator.generate_note(subtitles, note.subject, llm, note.title)
            words = None
            if note.subject == "english":
                words = note_generator.generate_english_extras(subtitles, note_json, llm)
                note.words = json.dumps(words, ensure_ascii=False)
            markdown = export_service.render_note_markdown(note_json, note.subject, words, meta={
                "bvid": note.bvid,
                "page": note.page,
                "subject_name": SUBJECT_NAMES.get(note.subject, note.subject),
                "created_at": note.created_at.isoformat() if note.created_at else "",
            })
            # 同步保存本地 Markdown 文件
            _save_markdown_file(note.id, note.title, markdown)
            note.note_json = json.dumps(note_json, ensure_ascii=False)
            note.markdown = markdown
            note.mindmap = note_json.get("mindmap", "")
            note.summary = note_json.get("summary", "")
            note.status = "done"
            note.error = ""
        except Exception as exc:  # noqa: BLE001
            note.status = "failed"
            note.error = str(exc)
            traceback.print_exc()
        note.updated_at = datetime.datetime.utcnow()
        db.commit()
    finally:
        db.close()


@router.post("/generate")
def generate_note(req: GenerateRequest, db: Session = Depends(get_db)):
    if not req.bvid:
        raise HTTPException(status_code=400, detail="缺少 BV 号")
    if req.subject not in SUBJECTS:
        raise HTTPException(status_code=400, detail="不支持的学科类型")
    llm_cfg = resolve_llm_config(db, req.provider, req.api_key, req.model, req.base_url)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(
            status_code=400,
            detail="尚未配置 " + llm_cfg["provider"] + " 的 API Key，请先到「配置」页填写",
        )
    title = req.title or (req.bvid + " P" + str(req.page))
    note = Note(bvid=req.bvid, page=req.page, title=title, subject=req.subject, status="processing")
    db.add(note)
    db.commit()
    db.refresh(note)
    threading.Thread(target=_run_generation, args=(note.id, llm_cfg), daemon=True).start()
    return {"id": note.id, "status": note.status}


@router.get("")
def list_notes(db: Session = Depends(get_db), limit: int = 50):
    notes = (
        db.query(Note)
        .order_by(Note.created_at.desc())
        .limit(min(max(limit, 1), 200))
        .all()
    )
    return [
        {
            "id": n.id,
            "bvid": n.bvid,
            "page": n.page,
            "title": n.title,
            "subject": n.subject,
            "status": n.status,
            "summary": n.summary,
            "error": n.error,
            "created_at": n.created_at.isoformat() if n.created_at else "",
        }
        for n in notes
    ]


@router.get("/{note_id}/status")
def note_status(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return {"id": note.id, "status": note.status, "error": note.error}


@router.get("/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return _note_to_dict(note)


@router.post("/{note_id}/formulas")
def generate_formulas(note_id: int, req: FormulaRequest, db: Session = Depends(get_db)):
    """提取板书/课件关键帧，调用视觉大模型识别公式为 LaTeX。"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.status != "done" or not note.note_json:
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    from ..services import formulas as formula_service
    from ..services.llm.factory import VISION_MODELS

    provider = req.provider or "qwen"
    model = req.model or VISION_MODELS.get(provider, "")
    if not model:
        raise HTTPException(status_code=400, detail="所选供应商不支持视觉模型，请使用通义千问（qwen-vl-plus）或 Kimi")
    cfg = resolve_llm_config(db, provider=provider, model=model)
    if cfg["provider"] != "ollama" and not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 " + provider + " 的 API Key")
    try:
        note_json = json.loads(note.note_json)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="笔记数据损坏") from exc
    timestamps = formula_service.pick_timestamps(note_json)
    if not timestamps:
        raise HTTPException(status_code=400, detail="笔记中没有可定位的时间戳")
    frames_dir = DATA_DIR / "notes" / (str(note.id) + "_frames")
    try:
        frames = formula_service.extract_frames(
            note.bvid, note.page, timestamps, frames_dir, get_setting(db, "bili_cookie", "")
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="关键帧提取失败：" + str(exc)) from exc
    if not frames:
        raise HTTPException(status_code=500, detail="未能提取到关键帧")
    llm = build_llm(cfg["provider"], cfg["api_key"], cfg["model"], cfg["base_url"])
    try:
        result = formula_service.recognize(frames, llm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="公式识别失败：" + str(exc)) from exc
    errors = result.get("errors") or []
    if not result.get("formulas") and not result.get("notes") and errors:
        raise HTTPException(
            status_code=502,
            detail="视觉模型调用失败：" + errors[0][:200]
            + "。可尝试：①到阿里云百炼检查账户余额/开通服务；②在「模型配置」填写 Kimi Key 后改用 Kimi 视觉模型",
        )
    note.formulas = json.dumps(
        {"formulas": result.get("formulas") or [], "notes": result.get("notes") or []},
        ensure_ascii=False,
    )
    db.commit()
    return {
        "formulas": result.get("formulas") or [],
        "notes": result.get("notes") or [],
        "images": ["/api/notes/" + str(note.id) + "/frames/frame_" + str(i + 1) + ".jpg" for i in range(len(frames))],
    }


@router.get("/{note_id}/frames/{filename}")
def get_frame(note_id: int, filename: str):
    if not re.fullmatch(r"[\w.-]+", filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    path = DATA_DIR / "notes" / (str(note_id) + "_frames") / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
    from fastapi.responses import FileResponse

    return FileResponse(str(path), media_type="image/jpeg")


@router.post("/{note_id}/chat")
def note_chat(note_id: int, req: ChatRequest, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if not note.markdown:
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「配置」页填写")
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    context = (note.summary + "\n\n" + note.markdown)[:6000]
    messages = [{"role": "system", "content": CHAT_SYSTEM.replace("{note}", context)}]
    for m in (req.history or [])[-8:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = str(m.get("content") or "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:2000]})
    messages.append({"role": "user", "content": (req.message or "")[:2000]})
    try:
        reply = llm.chat(messages, temperature=0.4)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="AI 答疑失败：" + str(exc)) from exc
    return {"reply": reply}


@router.delete("/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    db.delete(note)
    db.commit()
    return {"ok": True}


def _note_to_dict(note: Note) -> dict:
    def _load(text, default):
        if not text:
            return default
        try:
            return json.loads(text)
        except Exception:
            return default

    return {
        "id": note.id,
        "bvid": note.bvid,
        "page": note.page,
        "title": note.title,
        "subject": note.subject,
        "status": note.status,
        "error": note.error,
        "summary": note.summary,
        "note": _load(note.note_json, {}),
        "markdown": note.markdown,
        "mindmap": note.mindmap,
        "quizzes": _load(note.quizzes, {}),
        "words": _load(note.words, {}),
        "formulas": _load(note.formulas, {}),
        "review": _load(note.review, {}),
        "created_at": note.created_at.isoformat() if note.created_at else "",
        "updated_at": note.updated_at.isoformat() if note.updated_at else "",
        "markdown_file": str(_markdown_path(note.id, note.title)) if note.markdown else "",
    }
