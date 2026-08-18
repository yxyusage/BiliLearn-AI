"""数据库模型。"""
import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from .database import Base


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    bvid = Column(String(32), index=True)
    page = Column(Integer, default=1)
    title = Column(String(512), default="")
    subject = Column(String(32), default="general")
    status = Column(String(32), default="pending")  # pending/processing/done/failed
    error = Column(Text, default="")
    summary = Column(Text, default="")        # 摘要
    batch_id = Column(Integer, default=0)     # 合集批量任务 id（0=单条生成）
    note_json = Column(Text, default="")      # 结构化笔记 JSON
    markdown = Column(Text, default="")       # 渲染后的 Markdown
    mindmap = Column(Text, default="")        # Mermaid 脑图
    quizzes = Column(Text, default="")        # 阶梯自测 JSON
    words = Column(Text, default="")          # 生词 JSON（英语专项）
    formulas = Column(Text, default="")       # 板书公式识别 JSON（数理专项）
    review = Column(Text, default="")         # 复盘分析 JSON
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class SubtitleCache(Base):
    __tablename__ = "subtitle_cache"

    id = Column(Integer, primary_key=True)
    key = Column(String(128), unique=True, index=True)  # f"{bvid}_{page}"
    video_title = Column(String(512), default="")
    subtitles = Column(Text, default="")  # JSON 列表
    created_at = Column(DateTime, default=_now)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, default="")


class WrongAnswer(Base):
    __tablename__ = "wrong_answers"

    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, index=True)
    subject = Column(String(32), default="general")
    question = Column(Text, default="")
    user_answer = Column(Text, default="")
    correct_answer = Column(Text, default="")
    explanation = Column(Text, default="")
    feedback = Column(Text, default="")  # AI 批改讲解
    difficulty = Column(String(16), default="")
    time_stamp = Column(String(16), default="")
    created_at = Column(DateTime, default=_now)


class CollectionJob(Base):
    __tablename__ = "collection_jobs"

    id = Column(Integer, primary_key=True, index=True)
    bvid = Column(String(32), index=True)
    title = Column(String(512), default="")
    subject = Column(String(32), default="general")
    status = Column(String(32), default="running")  # running/done/partial/failed
    total = Column(Integer, default=0)
    done_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    current_page = Column(Integer, default=0)
    result_json = Column(Text, default="")  # [{page, note_id, status, title, error}]
    kg_mindmap = Column(Text, default="")   # 全课程知识图谱 mermaid
    kg_exam = Column(Text, default="")      # 考点地图 JSON
    created_at = Column(DateTime, default=_now)


class ReviewPlan(Base):
    __tablename__ = "review_plan"

    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, index=True)
    content = Column(Text, default="")
    due_date = Column(String(32), default="")
    done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)
