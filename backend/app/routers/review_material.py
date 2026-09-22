"""合集复习资料接口：生成 / 状态 / 下载 PDF。"""
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CollectionJob, ReviewMaterial
from ..services.llm.factory import build_llm
from ..services.review_material import build_review_material_pdf, generate_review_material
from ..services.settings_store import resolve_llm_config

router = APIRouter()


class StartRequest(BaseModel):
    collection_job_id: int


@router.post("/start")
def start_review_material(req: StartRequest, db: Session = Depends(get_db)):
    job = db.query(CollectionJob).filter(CollectionJob.id == req.collection_job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="合集任务不存在")
    if job.done_count == 0:
        raise HTTPException(status_code=400, detail="该合集还没有已完成的笔记，无法生成复习资料")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key")
    existing = (
        db.query(ReviewMaterial)
        .filter(ReviewMaterial.collection_job_id == req.collection_job_id, ReviewMaterial.status == "running")
        .first()
    )
    if existing:
        return {"id": existing.id, "status": "running", "message": "已有正在生成的复习资料"}
    mat = ReviewMaterial(
        collection_job_id=req.collection_job_id,
        title=job.title + " 复习资料",
        subject=job.subject,
        status="running",
        progress="初始化…",
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg.get("model"), llm_cfg.get("base_url"))
    import threading
    threading.Thread(target=generate_review_material, args=(mat.id, llm), daemon=True).start()
    return {"id": mat.id, "status": "running"}


@router.get("/{mat_id}")
def get_review_material(mat_id: int, db: Session = Depends(get_db)):
    mat = db.query(ReviewMaterial).filter(ReviewMaterial.id == mat_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="复习资料不存在")
    return {
        "id": mat.id,
        "collection_job_id": mat.collection_job_id,
        "title": mat.title,
        "subject": mat.subject,
        "status": mat.status,
        "progress": mat.progress,
        "error": mat.error,
        "created_at": mat.created_at.isoformat() if mat.created_at else "",
    }


@router.get("/{mat_id}/pdf")
def download_pdf(mat_id: int, db: Session = Depends(get_db)):
    mat = db.query(ReviewMaterial).filter(ReviewMaterial.id == mat_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="复习资料不存在")
    if mat.status != "done" or not mat.result_json:
        raise HTTPException(status_code=400, detail="复习资料尚未生成完成")
    try:
        data = json.loads(mat.result_json)
        meta = {"subject": mat.subject}
        pdf_bytes = build_review_material_pdf(data, meta)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="PDF 生成失败：" + str(exc)) from exc
    filename = (mat.title or "复习资料") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename)},
    )


@router.get("")
def list_review_materials(db: Session = Depends(get_db)):
    mats = db.query(ReviewMaterial).order_by(ReviewMaterial.created_at.desc()).limit(50).all()
    return [
        {
            "id": m.id,
            "collection_job_id": m.collection_job_id,
            "title": m.title,
            "subject": m.subject,
            "status": m.status,
            "progress": m.progress,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        }
        for m in mats
    ]
