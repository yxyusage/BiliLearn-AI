"""学习数据统计接口（仪表盘用）。"""
import datetime
import json
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CollectionJob, ConfusionPoint, Note, ReviewPlan, WrongAnswer

router = APIRouter()


def _load_list(text):
    try:
        data = json.loads(text) if text else {}
    except Exception:
        data = {}
    return data if isinstance(data, list) else []


def _day_counts(rows, attr="created_at", days=14):
    """返回最近 days 天按日期计数的 dict（含空天）。"""
    today = datetime.date.today()
    counts = {(today - datetime.timedelta(days=i)).isoformat(): 0 for i in range(days - 1, -1, -1)}
    for r in rows:
        dt = getattr(r, attr, None)
        if not dt:
            continue
        try:
            key = dt.date().isoformat() if hasattr(dt, "date") else str(dt)[:10]
        except Exception:
            continue
        if key in counts:
            counts[key] += 1
    return counts


@router.get("/summary")
def stats_summary(db: Session = Depends(get_db)):
    notes = db.query(Note).all()
    wrongs = db.query(WrongAnswer).all()
    plans = db.query(ReviewPlan).all()
    jobs = db.query(CollectionJob).all()
    confusions = db.query(ConfusionPoint).all()

    today = datetime.date.today().isoformat()
    due = [
        p for p in plans
        if not p.done and p.due_date and p.due_date <= today
    ]
    done_today = [
        p for p in plans
        if p.done or (p.last_reviewed and p.last_reviewed == today)
    ]

    subject_names = {"general": "通用", "english": "英语", "math": "数理", "cs": "计算机", "liberal": "文科"}
    note_subjects = Counter((subject_names.get(n.subject, n.subject) for n in notes))
    wrong_subjects = Counter((subject_names.get(w.subject, w.subject) for w in wrongs if w.status != "mastered"))

    return {
        "notes": {
            "total": len(notes),
            "done": sum(1 for n in notes if n.status == "done"),
            "failed": sum(1 for n in notes if n.status == "failed"),
            "processing": sum(1 for n in notes if n.status == "processing"),
            "by_subject": [{"name": k, "value": v} for k, v in note_subjects.items()],
            "last_14d": _day_counts(notes),
        },
        "wrong_answers": {
            "total": len(wrongs),
            "active": sum(1 for w in wrongs if w.status != "mastered"),
            "mastered": sum(1 for w in wrongs if w.status == "mastered"),
            "by_subject": [{"name": k, "value": v} for k, v in wrong_subjects.items()],
            "last_14d": _day_counts(wrongs),
        },
        "review": {
            "due_today": len(due),
            "overdue": sum(1 for p in due if p.due_date < today),
            "done_today": len(done_today),
            "total_plan": len(plans),
        },
        "collections": {
            "total": len(jobs),
            "running": sum(1 for j in jobs if j.status in ("running", "cancelling")),
            "done": sum(1 for j in jobs if j.status == "done"),
            "partial": sum(1 for j in jobs if j.status == "partial"),
            "failed": sum(1 for j in jobs if j.status in ("failed", "cancelled")),
        },
        "confusions": {
            "open": sum(1 for c in confusions if c.status == "open"),
            "total": len(confusions),
        },
    }
