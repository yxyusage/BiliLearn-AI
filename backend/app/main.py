"""BiliLearn-AI FastAPI 主应用。"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import Base, SessionLocal, engine, run_migrations
from .models import CollectionJob, Note, ReviewMaterial
from .routers import collections, config, export, favorites, notes, quiz, review, review_material, roadmap, stats, video

Base.metadata.create_all(bind=engine)
run_migrations()

APP_VERSION = "1.6.0"

app = FastAPI(title="BiliLearn-AI", description="B站全学科AI学习助手", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video.router, prefix="/api/video", tags=["视频解析"])
app.include_router(notes.router, prefix="/api/notes", tags=["笔记"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["自测"])
app.include_router(collections.router, prefix="/api/collections", tags=["合集"])
app.include_router(review.router, prefix="/api/review", tags=["复盘"])
app.include_router(config.router, prefix="/api/config", tags=["配置"])
app.include_router(export.router, prefix="/api/export", tags=["导出"])
app.include_router(stats.router, prefix="/api/stats", tags=["统计"])
app.include_router(roadmap.router, prefix="/api/roadmap", tags=["合集线路图"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["收藏夹导入"])
app.include_router(review_material.router, prefix="/api/review-material", tags=["复习资料"])


@app.on_event("startup")
def _startup_recovery():
    """进程重启后，把中断在“生成中/运行中”的任务标记为失败，避免永久卡死。"""
    db = SessionLocal()
    try:
        stuck_notes = db.query(Note).filter(Note.status == "processing").all()
        for n in stuck_notes:
            n.status = "failed"
            n.error = "服务重启导致生成中断，请点击重试"
        stuck_jobs = db.query(CollectionJob).filter(
            CollectionJob.status.in_(["running", "cancelling"])
        ).all()
        for j in stuck_jobs:
            j.status = "cancelled" if j.status == "cancelling" else ("partial" if j.done_count else "failed")
        stuck_mats = db.query(ReviewMaterial).filter(ReviewMaterial.status == "running").all()
        for m in stuck_mats:
            m.status = "failed"
            m.error = "服务重启导致生成中断，请重新生成"
        db.commit()
        # 回收 WAL，避免 -wal 文件无限增长
        db.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))
        db.commit()
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "BiliLearn-AI", "version": APP_VERSION}


# 生产模式：若存在前端构建产物则直接托管（Docker 一键部署）
_frontend_dist = os.environ.get("BILI_FRONTEND_DIST")
if not _frontend_dist:
    _frontend_dist = str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")
if Path(_frontend_dist).exists():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
