"""BiliLearn-AI FastAPI 主应用。"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, engine, run_migrations
from .routers import collections, config, export, notes, quiz, review, video

Base.metadata.create_all(bind=engine)
run_migrations()

app = FastAPI(title="BiliLearn-AI", description="B站全学科AI学习助手", version="1.0.0")

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


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "BiliLearn-AI"}


# 生产模式：若存在前端构建产物则直接托管（Docker 一键部署）
_frontend_dist = os.environ.get("BILI_FRONTEND_DIST")
if not _frontend_dist:
    _frontend_dist = str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")
if Path(_frontend_dist).exists():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
