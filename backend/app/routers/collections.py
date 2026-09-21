"""合集批量处理：异步队列 + 全课程知识图谱/考点地图。"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import CollectionJob, Note
from ..schemas import CollectionStartRequest
from ..services import bilibili
from ..services.llm import build_llm
from ..services.prompts import collection_map_prompt
from ..services.settings_store import get_setting, resolve_llm_config
from .notes import _run_generation

router = APIRouter()


def _process_episode(p: dict, job_id: int, llm_cfg: dict, bvid: str, course_title: str, subject: str) -> dict:
    """worker 线程：复用或生成单集笔记，全程使用独立数据库会话。"""
    page = p["page"]
    db = SessionLocal()
    try:
        existing = (
            db.query(Note)
            .filter(Note.bvid == bvid, Note.page == page, Note.status == "done")
            .order_by(Note.id.desc())
            .first()
        )
        if existing:
            return {"page": page, "note_id": existing.id, "status": "done",
                    "title": existing.title, "error": "", "reused": True}
        note_title = (p.get("title") or "") or (course_title + " P" + str(page))
        note = Note(bvid=bvid, page=page, title=note_title, subject=subject,
                    status="processing", batch_id=job_id)
        db.add(note)
        db.commit()
        note_id = note.id
        db.close()
    finally:
        try:
            db.close()
        except Exception:
            pass

    _run_generation(note_id, llm_cfg)

    db2 = SessionLocal()
    try:
        note = db2.query(Note).filter(Note.id == note_id).first()
        if note and note.status == "done":
            return {"page": page, "note_id": note.id, "status": "done", "title": note.title, "error": ""}
        return {
            "page": page, "note_id": note_id, "status": "failed",
            "title": note.title if note else note_title,
            "error": (note.error if note else "") or "未知错误",
        }
    finally:
        db2.close()


def _run_job(job_id: int, llm_cfg: dict, pages: list, bvid: str, course_title: str,
             subject: str, concurrency: int):
    db = SessionLocal()
    results = []
    try:
        job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
        if not job:
            return
        lock = threading.Lock()
        cancelled = False

        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            pending = set()
            idx = 0
            while idx < len(pages) or pending:
                while len(pending) < concurrency and idx < len(pages) and not cancelled:
                    db.expire_all()
                    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
                    if job and job.status == "cancelling":
                        cancelled = True
                        break
                    pending.add(pool.submit(
                        _process_episode, pages[idx], job_id, llm_cfg, bvid, course_title, subject
                    ))
                    idx += 1
                if not pending:
                    break
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for fut in done:
                    r = fut.result()
                    with lock:
                        results.append(r)
                        results.sort(key=lambda x: x["page"])
                        if r["status"] == "done":
                            job.done_count += 1
                        else:
                            job.failed_count += 1
                        job.current_page = r["page"]
                        job.result_json = json.dumps(results, ensure_ascii=False)
                        db.commit()

        db.expire_all()
        job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
        if cancelled:
            job.status = "cancelled"
        elif job.total and job.failed_count == job.total:
            job.status = "failed"
        elif job.failed_count == 0:
            job.status = "done"
        else:
            job.status = "partial"
        job.current_page = 0
        db.commit()
    finally:
        db.close()


@router.post("/start")
def start_job(req: CollectionStartRequest, db: Session = Depends(get_db)):
    if not req.bvid:
        raise HTTPException(status_code=400, detail="缺少 BV 号")
    if req.subject not in ("general", "english", "math", "cs", "liberal"):
        raise HTTPException(status_code=400, detail="不支持的学科类型")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「配置」页填写")
    cookie = get_setting(db, "bili_cookie", "")
    try:
        info = bilibili.parse_video("https://www.bilibili.com/video/" + req.bvid, cookie)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="视频解析失败：" + str(exc)) from exc
    pages = info.get("pages") or [{"page": 1, "title": info.get("title") or ""}]
    if req.max_pages and req.max_pages > 0:
        pages = pages[: req.max_pages]
    try:
        concurrency = max(1, min(4, int(get_setting(db, "collection_concurrency", "2") or "2")))
    except ValueError:
        concurrency = 2
    job = CollectionJob(
        bvid=req.bvid,
        title=req.title or info.get("title") or "合集任务",
        subject=req.subject,
        status="running",
        total=len(pages),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    threading.Thread(
        target=_run_job,
        args=(job.id, llm_cfg, pages, req.bvid, info.get("title") or "", req.subject, concurrency),
        daemon=True,
    ).start()
    return {"id": job.id, "total": job.total, "status": job.status}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status == "running":
        job.status = "cancelling"
        db.commit()
        return {"ok": True, "status": "cancelling"}
    return {"ok": False, "message": "任务已结束，无需取消"}


@router.get("")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(CollectionJob).order_by(CollectionJob.created_at.desc()).limit(50).all()
    return [
        {
            "id": j.id, "bvid": j.bvid, "title": j.title, "subject": j.subject,
            "status": j.status, "total": j.total, "done_count": j.done_count,
            "failed_count": j.failed_count, "current_page": j.current_page,
            "has_map": bool(j.kg_mindmap),
            "created_at": j.created_at.isoformat() if j.created_at else "",
        }
        for j in jobs
    ]


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    results = []
    if job.result_json:
        try:
            results = json.loads(job.result_json)
        except Exception:
            results = []
    exam = []
    if job.kg_exam:
        try:
            exam = json.loads(job.kg_exam)
        except Exception:
            exam = []
    return {
        "id": job.id, "bvid": job.bvid, "title": job.title, "subject": job.subject,
        "status": job.status, "total": job.total, "done_count": job.done_count,
        "failed_count": job.failed_count, "current_page": job.current_page,
        "results": results,
        "mindmap": job.kg_mindmap,
        "exam_points": exam,
        "created_at": job.created_at.isoformat() if job.created_at else "",
    }


@router.post("/{job_id}/map")
def generate_map(job_id: int, db: Session = Depends(get_db)):
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key")
    notes = (
        db.query(Note)
        .filter(Note.bvid == job.bvid, Note.status == "done", Note.note_json != "")
        .order_by(Note.page.asc())
        .all()
    )
    if not notes:
        raise HTTPException(status_code=400, detail="该任务还没有已完成的笔记，无法生成知识图谱")
    # 按集数自适应预算：集数越多每集采样越少，保证大合集后半不会被整体截断
    # 同一分 P 可能因重复生成存在多条记录，只保留最新一条
    latest_by_page = {}
    for note in notes:
        latest_by_page[note.page] = note
    notes = [latest_by_page[p] for p in sorted(latest_by_page)]
    n = len(notes)
    ch_limit = 6 if n <= 15 else (4 if n <= 40 else 3)
    pt_limit = 4 if n <= 15 else (3 if n <= 40 else 2)
    summaries = []
    for note in notes:
        try:
            data = json.loads(note.note_json)
        except Exception:
            continue
        chapters = []
        for ch in (data.get("chapters") or [])[:ch_limit]:
            sections = []
            raw_sections = ch.get("sections") or []
            if raw_sections:
                for sec in raw_sections[:pt_limit]:
                    sections.append({
                        "heading": str(sec.get("heading", ""))[:80],
                        "type": sec.get("type", ""),
                        "time_stamp": sec.get("time_stamp", ""),
                    })
            else:  # 兼容旧版 points 结构
                sections = [
                    {"heading": str(pt.get("content", ""))[:80], "type": "keypoints",
                     "time_stamp": pt.get("time_stamp", "")}
                    for pt in (ch.get("points") or [])[:pt_limit]
                ]
            chapters.append({
                "title": ch.get("title", ""),
                "time_stamp": ch.get("time_stamp", ""),
                "sections": sections,
                "key_points": [str(k)[:80] for k in (ch.get("key_points") or [])[:pt_limit]],
            })
        summaries.append({
            "page": note.page,
            "title": note.title,
            "summary": str(data.get("summary", ""))[:300],
            "chapters": chapters,
        })
    payload = json.dumps(summaries, ensure_ascii=False)
    if len(payload) > 60000:
        payload = payload[:60000]
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    try:
        result = llm.chat_json(collection_map_prompt(job.title, payload))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="知识图谱生成失败：" + str(exc)) from exc
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="知识图谱输出格式错误")
    mindmap = result.get("mindmap") or ""
    if isinstance(mindmap, list):
        mindmap = "\n".join(str(x) for x in mindmap)
    job.kg_mindmap = str(mindmap).strip()
    job.kg_exam = json.dumps(result.get("exam_points") or [], ensure_ascii=False)
    db.commit()
    return {"mindmap": job.kg_mindmap, "exam_points": result.get("exam_points") or []}


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.delete(job)
    db.commit()
    return {"ok": True}
