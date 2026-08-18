"""合集批量处理：异步队列 + 全课程知识图谱/考点地图。"""
import datetime
import json
import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import CollectionJob, Note
from ..schemas import CollectionStartRequest
from ..services import bilibili
from ..services.llm import build_llm
from ..services.prompts import collection_map_prompt
from ..services.settings_store import resolve_llm_config
from .notes import _run_generation

router = APIRouter()


def _run_job(job_id: int, llm_cfg: dict, pages: list, bvid: str, course_title: str, subject: str):
    db = SessionLocal()
    try:
        job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
        if not job:
            return
        results = []
        for p in pages:
            page = p["page"]
            job.current_page = page
            db.commit()
            # 已完成笔记直接复用，不重复请求 AI
            existing = (
                db.query(Note)
                .filter(Note.bvid == bvid, Note.page == page, Note.subject == subject, Note.status == "done")
                .first()
            )
            if existing:
                job.done_count += 1
                results.append({"page": page, "note_id": existing.id, "status": "done", "title": existing.title, "error": ""})
                job.result_json = json.dumps(results, ensure_ascii=False)
                db.commit()
                continue
            note_title = (p.get("title") or "") or (course_title + " P" + str(page))
            note = Note(
                bvid=bvid, page=page, title=note_title, subject=subject,
                status="processing", batch_id=job_id,
            )
            db.add(note)
            db.commit()
            db.refresh(note)
            # 同步执行单条生成（内部已处理失败状态与落盘）
            _run_generation(note.id, llm_cfg)
            # 关键：刷新会话，避免拿到 identity map 里的旧状态
            db.expire_all()
            note = db.query(Note).filter(Note.id == note.id).first()
            if note and note.status == "done":
                job.done_count += 1
                results.append({"page": page, "note_id": note.id, "status": "done", "title": note.title, "error": ""})
            else:
                job.failed_count += 1
                results.append({
                    "page": page, "note_id": note.id if note else 0, "status": "failed",
                    "title": note.title if note else note_title,
                    "error": (note.error if note else "") or "未知错误",
                })
            job.result_json = json.dumps(results, ensure_ascii=False)
            db.commit()
        if job.total and job.failed_count == job.total:
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
    try:
        info = bilibili.parse_video("https://www.bilibili.com/video/" + req.bvid)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="视频解析失败：" + str(exc)) from exc
    pages = info.get("pages") or [{"page": 1, "title": info.get("title") or ""}]
    if req.max_pages and req.max_pages > 0:
        pages = pages[: req.max_pages]
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
        args=(job.id, llm_cfg, pages, req.bvid, info.get("title") or "", req.subject),
        daemon=True,
    ).start()
    return {"id": job.id, "total": job.total, "status": job.status}


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
        .filter(Note.batch_id == job_id, Note.status == "done", Note.note_json != "")
        .order_by(Note.page.asc())
        .all()
    )
    if not notes:
        raise HTTPException(status_code=400, detail="该任务还没有已完成的笔记，无法生成知识图谱")
    summaries = []
    for n in notes:
        try:
            data = json.loads(n.note_json)
        except Exception:
            continue
        chapters = []
        for ch in (data.get("chapters") or [])[:6]:
            points = []
            for pt in (ch.get("points") or [])[:3]:
                points.append({"content": str(pt.get("content", ""))[:60], "time_stamp": pt.get("time_stamp", "")})
            chapters.append({"title": ch.get("title", ""), "points": points})
        summaries.append({"page": n.page, "title": n.title, "chapters": chapters})
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    try:
        result = llm.chat_json(collection_map_prompt(
            job.title, json.dumps(summaries, ensure_ascii=False)[:20000]
        ))
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
