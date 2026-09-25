"""笔记生成与历史管理接口。"""
import datetime
import json
import re
import shutil
import threading
import traceback
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import SessionLocal, get_db
from ..models import ConfusionPoint, Note, SubtitleCache, WrongAnswer
from ..schemas import ChatRequest, FormulaRequest, GenerateRequest
from ..services import bilibili, export as export_service, features as feature_service, note_generator, whisper
from ..services.llm import build_llm
from ..services.prompts import CHAT_SYSTEM, SUBJECTS as SUBJECT_NAMES
from ..services.settings_store import get_setting, resolve_llm_config, whisper_enabled

router = APIRouter()

SUBJECTS = ("general", "english", "math", "cs", "liberal")

# 关键帧与公式截图分目录存放，避免同名文件互相覆盖
FRAME_KINDS = ("keyframes", "formulas", "frames")


def _markdown_path(note_id: int, title: str) -> Path:
    notes_dir = DATA_DIR / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\r\n]+', "_", title or "").strip("_") or "note"
    return notes_dir / (str(note_id).zfill(4) + "_" + safe[:60] + ".md")


def _save_markdown_file(note_id: int, title: str, markdown: str) -> str:
    path = _markdown_path(note_id, title)
    path.write_text(markdown, encoding="utf-8")
    return str(path)


def _frames_dir(note_id: int, kind: str) -> Path:
    return DATA_DIR / "notes" / (str(note_id) + "_" + kind)


def _cleanup_note_files(note_id: int, title: str) -> None:
    """删除笔记时同步清理本地 Markdown 与抽帧目录。"""
    try:
        md = _markdown_path(note_id, title)
        if md.exists():
            md.unlink()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
    for kind in FRAME_KINDS:
        d = _frames_dir(note_id, kind)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


def _note_context(note: Note, limit: int = 12000) -> str:
    """构建答疑上下文：基于 v2 结构化正文按章节边界截断，避免切断公式/表格。"""
    data = {}
    if note.note_json:
        try:
            data = json.loads(note.note_json)
        except Exception:
            data = {}
    if data:
        full = note_generator.note_plain_text(data, char_limit=0)
        if len(full) <= limit:
            return full
        cut = note_generator.note_plain_text(data, char_limit=limit)
        return cut + "\n\n（注：笔记较长，此处仅载入前半部分；后半部分内容请指明章节名称后再提问）"
    # 兜底：极端情况下结构化数据缺失时用 Markdown
    body = note.markdown or note.summary or ""
    return body[:limit]


def _build_chat_messages(note: Note, req: ChatRequest) -> list:
    context = _note_context(note)
    messages = [{"role": "system", "content": CHAT_SYSTEM.replace("{note}", context)}]
    for m in (req.history or [])[-10:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = str(m.get("content") or "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": (req.message or "")[:4000]})
    return messages


def _sync_collection_status(db, batch_id: int, bvid: str, page: int):
    """单集笔记生成成功后，同步更新关联合集任务的失败计数。"""
    try:
        from ..models import CollectionJob
        job = db.query(CollectionJob).filter(CollectionJob.id == batch_id).first()
        if not job or not job.result_json:
            return
        results = json.loads(job.result_json)
        changed = False
        for r in results:
            if r.get("page") == page and r.get("status") in ("failed", "pending"):
                r["status"] = "done"
                r["error"] = ""
                changed = True
        if changed:
            job.result_json = json.dumps(results, ensure_ascii=False)
            failed = sum(1 for r in results if r.get("status") == "failed")
            done = sum(1 for r in results if r.get("status") == "done")
            job.failed_count = failed
            job.done_count = done
            if job.total and failed == 0:
                job.status = "done"
            elif job.total and failed == job.total:
                job.status = "failed"
            else:
                job.status = "partial"
            db.commit()
    except Exception:
        pass


def _is_network_error(exc: Exception) -> bool:
    """判断异常是否为网络相关错误。"""
    import httpx
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError,
                        httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout,
                        httpx.PoolTimeout, ConnectionError, OSError)):
        return True
    msg = str(exc).lower()
    for kw in ("connection", "timeout", "network", "unreachable", "refused", "reset",
               "download", "音视频", "音频", "视频流", "字幕获取", "yt_dlp", "errno"):
        if kw in msg:
            return True
    return False


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
            # 若属于合集任务且之前标记为失败，更新合集计数
            if note.batch_id:
                _sync_collection_status(db, note.batch_id, note.bvid, note.page)
        except Exception as exc:  # noqa: BLE001
            if _is_network_error(exc):
                note.status = "pending"
                note.error = "网络中断，待恢复后继续：" + str(exc)[:200]
            else:
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
    # 同一视频已有完成/进行中的笔记时直接复用，避免重复扣费
    existing = (
        db.query(Note)
        .filter(Note.bvid == req.bvid, Note.page == req.page, Note.status.in_(["done", "processing"]))
        .order_by(Note.id.desc())
        .first()
    )
    if existing:
        return {"id": existing.id, "status": existing.status, "reused": True}
    # 重新生成时清理同 bvid+page 的失败旧笔记，继承 batch_id
    old_failed = db.query(Note).filter(
        Note.bvid == req.bvid, Note.page == req.page, Note.status.in_(["failed", "pending"])
    ).all()
    inherited_batch_id = None
    for n in old_failed:
        if n.batch_id and not inherited_batch_id:
            inherited_batch_id = n.batch_id
    for n in old_failed:
        db.delete(n)
    db.commit()
    llm_cfg = resolve_llm_config(db, req.provider, req.api_key, req.model, req.base_url)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(
            status_code=400,
            detail="尚未配置 " + llm_cfg["provider"] + " 的 API Key，请先到「配置」页填写",
        )
    title = req.title or (req.bvid + " P" + str(req.page))
    note = Note(bvid=req.bvid, page=req.page, title=title, subject=req.subject,
                status="processing", batch_id=inherited_batch_id)
    db.add(note)
    db.commit()
    db.refresh(note)
    threading.Thread(target=_run_generation, args=(note.id, llm_cfg), daemon=True).start()
    return {"id": note.id, "status": note.status, "reused": False}


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


@router.post("/{note_id}/keyframes")
def generate_keyframes(note_id: int, db: Session = Depends(get_db)):
    """按章节时间戳提取关键帧，嵌入笔记与导出文档。"""
    from ..services import formulas as formula_service
    from ..utils.timestamp import hms_to_seconds, seconds_to_hms

    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.status != "done" or not note.note_json:
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    try:
        note_json = json.loads(note.note_json)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="笔记数据损坏") from exc
    chapters = note_json.get("chapters") or []
    picks = []
    for idx, ch in enumerate(chapters):
        sec = 0
        for section in (ch.get("sections") or []):
            sec = hms_to_seconds(section.get("time_stamp") or "")
            if sec > 0:
                break
        if sec == 0:  # 兼容旧版 points 结构
            for pt in (ch.get("points") or []):
                sec = hms_to_seconds(pt.get("time_stamp") or "")
                if sec > 0:
                    break
        if sec > 0:
            picks.append((idx, sec))
        if len(picks) >= 8:
            break
    if not picks:
        raise HTTPException(status_code=400, detail="笔记中没有可定位的时间戳")
    frames_dir = _frames_dir(note.id, "keyframes")
    try:
        frames = formula_service.extract_frames(
            note.bvid, note.page, [s for _, s in picks], frames_dir, get_setting(db, "bili_cookie", "")
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="关键帧提取失败：" + str(exc)) from exc
    if not frames:
        raise HTTPException(status_code=500, detail="未能提取到关键帧")
    keyframes = []
    for (idx, sec), img in zip(picks, frames):
        keyframes.append({"chapter": idx, "time_stamp": seconds_to_hms(sec), "image": Path(img).name})
    note.keyframes = json.dumps(keyframes, ensure_ascii=False)
    # 重新渲染 Markdown，嵌入关键帧链接
    words = json.loads(note.words) if note.words else None
    frames_links = {}
    for k in keyframes:
        frames_links.setdefault(k["chapter"], []).append(str(note.id) + "_keyframes/" + k["image"])
    markdown = export_service.render_note_markdown(
        note_json, note.subject, words,
        meta={
            "bvid": note.bvid,
            "page": note.page,
            "subject_name": SUBJECT_NAMES.get(note.subject, note.subject),
            "created_at": note.created_at.isoformat() if note.created_at else "",
        },
        frames=frames_links,
    )
    note.markdown = markdown
    _save_markdown_file(note.id, note.title, markdown)
    db.commit()
    return {"keyframes": keyframes}


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

    provider = req.provider or "deepseek"
    model = req.model or VISION_MODELS.get(provider, "")
    if not model:
        raise HTTPException(
            status_code=400,
            detail="所选供应商不支持视觉模型，请使用 DeepSeek（deepseek-flash）、通义千问（qwen-vl-max）或 Kimi（kimi-k2.6）",
        )
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
    frames_dir = _frames_dir(note.id, "formulas")
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
            + "。可尝试：①检查对应供应商账户余额与服务开通状态；②换用其他支持视觉的供应商",
        )
    note.formulas = json.dumps(
        {
            "items": result.get("items") or [],
            "formulas": result.get("formulas") or [],
            "notes": result.get("notes") or [],
        },
        ensure_ascii=False,
    )
    db.commit()
    base = "/api/notes/" + str(note.id) + "/frames/formulas/"
    return {
        "items": result.get("items") or [],
        "formulas": result.get("formulas") or [],
        "notes": result.get("notes") or [],
        "images": [base + "frame_" + str(i + 1) + ".jpg" for i in range(len(frames))],
    }


@router.get("/{note_id}/frames/{kind}/{filename}")
def get_frame_typed(note_id: int, kind: str, filename: str):
    if kind not in ("keyframes", "formulas") or not re.fullmatch(r"[\w.-]+", filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    path = _frames_dir(note_id, kind) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/{note_id}/frames/{filename}")
def get_frame_legacy(note_id: int, filename: str):
    """兼容旧版本笔记的 {id}_frames 目录。"""
    if not re.fullmatch(r"[\w.-]+", filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    path = _frames_dir(note_id, "frames") / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(str(path), media_type="image/jpeg")


@router.post("/{note_id}/chat/stream")
def note_chat_stream(note_id: int, req: ChatRequest, db: Session = Depends(get_db)):
    """流式 AI 答疑：SSE 逐字输出。"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if not note.markdown:
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「配置」页填写")
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    messages = _build_chat_messages(note, req)

    def event_stream():
        try:
            for delta in llm.chat_stream(messages, temperature=0.4):
                yield "data: " + json.dumps({"delta": delta}, ensure_ascii=False) + "\n\n"
        except Exception as exc:  # noqa: BLE001
            yield "data: " + json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n\n"
        yield "data: " + json.dumps({"done": True}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    messages = _build_chat_messages(note, req)
    try:
        reply = llm.chat(messages, temperature=0.4)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="AI 答疑失败：" + str(exc)) from exc
    return {"reply": reply}


@router.get("/{note_id}/dictation")
def get_dictation(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    try:
        items = json.loads(note.dictations) if note.dictations else []
    except Exception:
        items = []
    return {"items": items if isinstance(items, list) else []}


@router.post("/{note_id}/dictation")
def generate_dictation(note_id: int, db: Session = Depends(get_db)):
    """英语精听听写填空：从字幕中选句挖空，AI 出题，结果存库。"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.subject != "english":
        raise HTTPException(status_code=400, detail="听写填空仅适用于英语笔记")
    if note.status != "done":
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    cache = db.query(SubtitleCache).filter(SubtitleCache.key == note.bvid + "_" + str(note.page)).first()
    if not cache or not cache.subtitles:
        raise HTTPException(status_code=400, detail="没有字幕数据（官方字幕或本地转写均可），无法生成听写")
    try:
        subtitles = json.loads(cache.subtitles)
    except Exception:
        raise HTTPException(status_code=400, detail="字幕数据损坏") from None
    if not subtitles:
        raise HTTPException(status_code=400, detail="字幕为空")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「设置」页填写")
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    transcript = note_generator.build_transcript(subtitles)
    try:
        items = feature_service.generate_dictation(transcript, llm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="听写生成失败：" + str(exc)) from exc
    if not items:
        raise HTTPException(status_code=502, detail="未能从字幕中生成听写题目，可重试")
    note.dictations = json.dumps({"items": items}, ensure_ascii=False)
    db.commit()
    return {"items": items}


@router.post("/{note_id}/confusions")
def create_confusion(note_id: int, body: dict, db: Session = Depends(get_db)):
    """「没懂」瞬时打点：记录卡住的视频片段（可选附带小节标题与补充描述）。"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    time_stamp = str(body.get("time_stamp") or "").strip()
    row = ConfusionPoint(
        note_id=note.id,
        time_stamp=time_stamp[:16],
        section=str(body.get("section") or "").strip()[:200],
        question=str(body.get("question") or "").strip()[:500],
        status="open",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "time_stamp": row.time_stamp, "section": row.section, "status": row.status}


@router.get("/{note_id}/confusions")
def list_confusions(note_id: int, db: Session = Depends(get_db), open_only: int = 0):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    query = db.query(ConfusionPoint).filter(ConfusionPoint.note_id == note.id)
    if open_only:
        query = query.filter(ConfusionPoint.status == "open")
    rows = query.order_by(ConfusionPoint.id.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "time_stamp": r.time_stamp,
            "section": r.section,
            "question": r.question,
            "explanation": r.explanation,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


@router.post("/{note_id}/confusions/{cid}/explain")
def explain_confusion(note_id: int, cid: int, db: Session = Depends(get_db)):
    """针对卡住的小节生成 AI 换讲，存入记录。"""
    row = db.query(ConfusionPoint).filter(
        ConfusionPoint.id == cid, ConfusionPoint.note_id == note_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="打点记录不存在")
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note or not note.note_json:
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    try:
        note_json = json.loads(note.note_json)
    except Exception:
        raise HTTPException(status_code=400, detail="笔记数据损坏") from None
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「设置」页填写")
    # 定位对应小节文本；找不到则用整篇笔记前段
    section_text = row.section or ""
    if row.section:
        for _, _, sec in note_generator.iter_sections(note_json):
            if str(sec.get("heading") or "").strip() == row.section:
                section_text = note_generator.section_text(sec)
                break
    if not section_text:
        section_text = note_generator.note_plain_text(note_json, char_limit=1500)
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    try:
        explanation = feature_service.re_explain_section(note_json, section_text, llm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="换讲生成失败：" + str(exc)) from exc
    row.explanation = explanation
    db.commit()
    return {"id": row.id, "explanation": explanation}


@router.post("/{note_id}/confusions/{cid}/resolve")
def resolve_confusion(note_id: int, cid: int, db: Session = Depends(get_db)):
    row = db.query(ConfusionPoint).filter(
        ConfusionPoint.id == cid, ConfusionPoint.note_id == note_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="打点记录不存在")
    row.status = "closed"
    db.commit()
    return {"ok": True}


@router.get("/{note_id}/diagnosis")
def pre_diagnosis(note_id: int, db: Session = Depends(get_db)):
    """学前诊断：从同合集前面几集抽取先修自测题，判断是否可直接跳看。"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.status != "done":
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    prior = (
        db.query(Note)
        .filter(Note.bvid == note.bvid, Note.page < note.page, Note.status == "done")
        .order_by(Note.page.desc())
        .limit(3)
        .all()
    )
    questions = []
    for p in prior:
        try:
            data = json.loads(p.quizzes) if p.quizzes else {}
        except Exception:
            data = {}
        pool = [q for q in (data.get("questions") or []) if q.get("type") in ("single", "judge", "fill")]
        for q in pool[:2]:
            q = dict(q)
            q["note_id"] = p.id
            questions.append(q)
        if len(questions) >= 6:
            break
    return {
        "has_prior": bool(prior),
        "prior_notes": [
            {"note_id": p.id, "page": p.page, "title": p.title} for p in prior
        ],
        "questions": questions,
    }


@router.delete("/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    title = note.title
    db.delete(note)
    db.commit()
    _cleanup_note_files(note_id, title)
    return {"ok": True}


def _is_legacy_note(data: dict) -> bool:
    """检测是否为旧版 points 结构（无 sections）。"""
    if not isinstance(data, dict):
        return False
    chapters = data.get("chapters") or []
    if not chapters:
        return False
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        if ch.get("sections"):
            return False
        if ch.get("points"):
            return True
    return False


def _note_to_dict(note: Note) -> dict:
    def _load(text, default):
        if not text:
            return default
        try:
            return json.loads(text)
        except Exception:
            return default

    note_data = _load(note.note_json, {})
    # 旧版 points 笔记在响应时实时转换为 v2 结构（不回写数据库）
    if _is_legacy_note(note_data):
        try:
            note_data = note_generator.normalize_note(note_data)
        except Exception:
            pass

    return {
        "id": note.id,
        "bvid": note.bvid,
        "page": note.page,
        "title": note.title,
        "subject": note.subject,
        "status": note.status,
        "error": note.error,
        "summary": note.summary,
        "note": note_data,
        "markdown": note.markdown,
        "mindmap": note.mindmap,
        "quizzes": _load(note.quizzes, {}),
        "words": _load(note.words, {}),
        "formulas": _load(note.formulas, {}),
        "keyframes": _load(note.keyframes, []),
        "review": _load(note.review, {}),
        "dictations": _load(note.dictations, {}),
        "created_at": note.created_at.isoformat() if note.created_at else "",
        "updated_at": note.updated_at.isoformat() if note.updated_at else "",
        "markdown_file": str(_markdown_path(note.id, note.title)) if note.markdown else "",
    }
