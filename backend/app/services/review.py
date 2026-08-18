"""AI 复盘分析与艾宾浩斯复习计划。"""
import datetime
import json
from typing import Dict, List, Optional

from .llm import BaseLLM
from .prompts import review_prompt

# 艾宾浩斯遗忘曲线复习间隔（天）
EBBINGHAUS_INTERVALS = [1, 2, 4, 7, 15, 30]


def build_ebbinghaus_plan(note: dict, start_date: Optional[datetime.date] = None) -> List[dict]:
    start = start_date or datetime.date.today()
    items = []
    for ch in note.get("chapters") or []:
        title = str(ch.get("title") or "章节")
        for interval in EBBINGHAUS_INTERVALS:
            due = start + datetime.timedelta(days=interval)
            items.append({
                "content": "复习章节：" + title,
                "day_offset": interval,
                "due_date": due.isoformat(),
                "done": False,
            })
    return items


def analyze_review(note: dict, wrong_answers: List[dict], llm: BaseLLM) -> dict:
    plan = build_ebbinghaus_plan(note)
    if not wrong_answers:
        return {"weak_points": [], "summary": "暂无错题记录，继续保持！", "plan": plan}
    data = llm.chat_json(review_prompt(
        json.dumps(note, ensure_ascii=False)[:8000],
        json.dumps(wrong_answers, ensure_ascii=False)[:6000],
    ))
    if not isinstance(data, dict):
        raise ValueError("复盘分析输出格式错误")
    weak_points = []
    for w in data.get("weak_points") or []:
        if not isinstance(w, dict):
            continue
        point = str(w.get("point") or "").strip()
        if not point:
            continue
        priority = str(w.get("priority") or "medium")
        if priority not in ("high", "medium", "low"):
            priority = "medium"
        weak_points.append({
            "point": point,
            "reason": str(w.get("reason") or "").strip(),
            "priority": priority,
            "replay_timestamps": [str(t) for t in (w.get("replay_timestamps") or [])],
            "suggestion": str(w.get("suggestion") or "").strip(),
        })
    return {
        "weak_points": weak_points,
        "summary": str(data.get("summary") or "").strip(),
        "plan": plan,
    }
