"""数据库模型。"""
import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

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
    keyframes = Column(Text, default="")      # 关键帧嵌入 JSON [{chapter, time_stamp, image}]
    review = Column(Text, default="")         # 复盘分析 JSON
    dictations = Column(Text, default="")     # 英语听写填空 JSON（精听听写专项）
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
    qtype = Column(String(16), default="")       # single/judge/calc/proof
    question = Column(Text, default="")
    user_answer = Column(Text, default="")
    correct_answer = Column(Text, default="")
    explanation = Column(Text, default="")
    feedback = Column(Text, default="")  # AI 批改讲解
    difficulty = Column(String(16), default="")
    time_stamp = Column(String(16), default="")
    status = Column(String(16), default="active")  # active/mastered
    wrong_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


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
    # SM-2 动态间隔：重复次数 / 当前间隔（天）/ 难度系数 / 上次复习日期
    repetitions = Column(Integer, default=0)
    interval_days = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)
    last_reviewed = Column(String(32), default="")
    created_at = Column(DateTime, default=_now)


class ConfusionPoint(Base):
    """「没懂」瞬时打点：记录卡住的视频片段与 AI 换讲内容。"""
    __tablename__ = "confusion_points"

    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, index=True)
    time_stamp = Column(String(16), default="")
    section = Column(Text, default="")      # 对应小节标题（可空）
    question = Column(Text, default="")     # 用户补充的困惑描述（可空）
    explanation = Column(Text, default="")  # AI 换讲后的内容
    status = Column(String(16), default="open")  # open/closed
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class RoadmapJob(Base):
    """合集学习线路图任务。"""
    __tablename__ = "roadmap_jobs"

    id = Column(Integer, primary_key=True, index=True)
    bvid = Column(String(32), index=True)
    url = Column(String(1024), default="")
    title = Column(String(512), default="")
    status = Column(String(32), default="running")  # running/done/failed
    total = Column(Integer, default=0)
    done_count = Column(Integer, default=0)
    error = Column(Text, default="")
    result_json = Column(Text, default="")   # 线路图 JSON（模块+标签）
    quiz_json = Column(Text, default="")     # 自测题 JSON
    recommend_json = Column(Text, default="")  # 推荐起点 JSON
    created_at = Column(DateTime, default=_now)
