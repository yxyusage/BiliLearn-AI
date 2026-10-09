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
        db.query(Note).filter(
            Note.bvid == bvid, Note.page == page, Note.status.in_(["failed", "processing"])
        ).delete(synchronize_session=False)
        db.commit()
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
        if note and note.status == "pending":
            return {"page": page, "note_id": note_id, "status": "pending",
                    "title": note.title if note else note_title,
                    "error": note.error or "网络中断"}
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
        # 续跑（「继续生成未完成的集数」）时继承此前已写入的结果，
        # 否则本次只处理剩余集数，会把之前成功/失败的记录整体覆盖掉。
        if job.result_json:
            try:
                seeded = json.loads(job.result_json)
            except Exception:
                seeded = []
            if isinstance(seeded, list):
                results = [r for r in seeded if isinstance(r, dict) and r.get("page") is not None]
        # 计数与继承的结果对齐（全新任务时 results 为空，等价于归零）
        job.done_count = sum(1 for r in results if r.get("status") == "done")
        job.failed_count = sum(1 for r in results if r.get("status") in ("failed", "pending"))
        db.commit()
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
                        elif r["status"] == "pending":
                            job.failed_count += 1
                            # 连续网络错误超过3个，暂停任务
                            pending_count = sum(1 for x in results if x["status"] == "pending")
                            if pending_count >= 3:
                                cancelled = True
                        else:
                            job.failed_count += 1
                        job.current_page = r["page"]
                        job.result_json = json.dumps(results, ensure_ascii=False)
                        db.commit()

        db.expire_all()
        job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
        has_pending = any(r.get("status") == "pending" for r in results)
        if cancelled and has_pending:
            job.status = "paused"
        elif cancelled:
            job.status = "cancelled"
        elif job.total and job.failed_count == job.total and not has_pending:
            job.status = "failed"
        elif has_pending:
            job.status = "paused"
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
    if req.start_page > 1 or req.end_page > 0:
        s = max(1, req.start_page)
        e = req.end_page if req.end_page > 0 else len(pages)
        pages = [pg for pg in pages if s <= int(pg.get("page", 0)) <= e]
    try:
        concurrency = max(1, min(6, int(get_setting(db, "collection_concurrency", "4") or "4")))
    except ValueError:
        concurrency = 4
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


@router.post("/{job_id}/resume")
def resume_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status not in ("paused", "partial", "failed"):
        return {"ok": False, "message": "当前状态无需继续（" + job.status + "）"}
    # 清理 pending 状态的旧笔记
    pending_notes = db.query(Note).filter(
        Note.bvid == job.bvid, Note.status == "pending", Note.batch_id == job_id
    ).all()
    for n in pending_notes:
        db.delete(n)
    db.commit()
    # 找出还未成功的集数
    if job.result_json:
        try:
            results = json.loads(job.result_json)
        except Exception:
            results = []
    else:
        results = []
    done_pages = {r["page"] for r in results if r.get("status") == "done"}
    # 重新获取合集信息
    cookie = get_setting(db, "bili_cookie", "")
    try:
        info = bilibili.parse_video("https://www.bilibili.com/video/" + job.bvid, cookie)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="视频解析失败：" + str(exc)) from exc
    pages = info.get("pages") or [{"page": 1, "title": info.get("title") or ""}]
    remaining = [pg for pg in pages if int(pg.get("page", 0)) not in done_pages]
    if not remaining:
        job.status = "done"
        db.commit()
        return {"ok": True, "message": "所有集数已完成", "total": 0}
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key")
    try:
        concurrency = max(1, min(6, int(get_setting(db, "collection_concurrency", "4") or "4")))
    except ValueError:
        concurrency = 4
    # 重置计数：只保留已完成的
    job.done_count = len(done_pages)
    job.failed_count = 0
    job.status = "running"
    job.current_page = 0
    # 保留已完成的结果，移除 pending/failed 的
    job.result_json = json.dumps(
        [r for r in results if r.get("status") == "done"], ensure_ascii=False
    )
    db.commit()
    threading.Thread(
        target=_run_job,
        args=(job.id, llm_cfg, remaining, job.bvid, job.title, job.subject, concurrency),
        daemon=True,
    ).start()
    return {"ok": True, "total": len(remaining), "status": "running"}


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


def _knowledge_graph_prompt(course_title: str, notes_text: str) -> str:
    return f"""你是课程知识图谱构建专家。请分析以下课程《{course_title}》的各集笔记，提取核心知识点并构建关联图谱。

【输出要求】
只输出一个 JSON 对象，格式如下：
{{
  "nodes": [
    {{"id": "1", "name": "知识点名称", "category": "类别", "note_ids": [1, 2], "desc": "一句话说明"}}
  ],
  "links": [
    {{"source": "1", "target": "2", "relation": "prerequisite|related|contains"}}
  ]
}}

【规则】
1. 提取 15-30 个核心知识点，不要太多也不要太少。
2. category 分为：基础概念、核心原理、关键技术、应用场景、易错点。
3. note_ids 标注该知识点出现在哪几集笔记中（用笔记的 page 字段）。
4. relation 类型：
   - prerequisite：前置知识（学 B 之前必须先学 A）
   - related：相关（两个知识点有关联）
   - contains：包含（A 包含 B）
5. 每个知识点至少有一条关联，孤立节点不要。
6. 知识点名称要简洁准确，不超过 10 个字。
7. desc 用一句话说明该知识点的核心内容。

【笔记内容】
{notes_text}

请只输出 JSON，不要输出其他内容。"""


@router.post("/{job_id}/knowledge-graph")
def generate_knowledge_graph(job_id: int, db: Session = Depends(get_db)):
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="合集任务不存在")
    results = json.loads(job.result_json or "[]")
    note_ids = [r.get("note_id") for r in results if r.get("status") == "done" and r.get("note_id")]
    if not note_ids:
        raise HTTPException(status_code=400, detail="该合集暂无已完成的笔记")
    notes = db.query(Note).filter(Note.id.in_(note_ids)).all()
    notes_text_parts = []
    for note in notes:
        summary = note.summary or ""
        title = note.title or ""
        notes_text_parts.append(f"第{note.page}集：{title}\n摘要：{summary[:500]}")
    notes_text = "\n\n".join(notes_text_parts)
    if len(notes_text) > 50000:
        notes_text = notes_text[:50000]
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key")
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    try:
        result = llm.chat_json(_knowledge_graph_prompt(job.title, notes_text))
    except Exception as exc:
        raise HTTPException(status_code=502, detail="知识图谱生成失败：" + str(exc)) from exc
    if not isinstance(result, dict) or "nodes" not in result or "links" not in result:
        raise HTTPException(status_code=502, detail="知识图谱输出格式错误")
    return {"nodes": result["nodes"], "links": result["links"]}
