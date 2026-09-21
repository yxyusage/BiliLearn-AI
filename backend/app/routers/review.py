"""AI 复盘与复习计划接口（含 SM-2 动态间隔调度）。"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Note, ReviewPlan, WrongAnswer
from ..schemas import RateRequest, ReviewRequest
from ..services.llm import build_llm
from ..services.review import analyze_review
from ..services.settings_store import resolve_llm_config

router = APIRouter()


def _apply_sm2(row: ReviewPlan, rating: int) -> None:
    """SM-2 间隔算法：按评分更新重复次数/间隔/难度系数，并排下一次到期日。"""
    ef = float(row.ease_factor or 2.5)
    interval = int(row.interval_days or 0)
    reps = int(row.repetitions or 0)
    if rating <= 1:  # 重来：忘光了，明天重学
        reps = 0
        interval = 1
        ef = max(1.3, ef - 0.2)
    elif rating == 2:  # 困难
        reps += 1
        interval = max(1, round(interval * 1.2)) if interval else 1
    elif rating == 3:  # 良好
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 3
        else:
            interval = max(1, round((interval or 1) * ef))
    else:  # 简单
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = max(1, round((interval or 1) * ef * 1.3))
        ef = min(2.5, ef + 0.15)
    row.repetitions = reps
    row.interval_days = interval
    row.ease_factor = round(ef, 2)
    row.last_reviewed = datetime.date.today().isoformat()
    row.due_date = (datetime.date.today() + datetime.timedelta(days=interval)).isoformat()
    row.done = False


@router.post("/analyze")
def analyze(req: ReviewRequest, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == req.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.status != "done" or not note.note_json:
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「配置」页填写")
    try:
        note_json = json.loads(note.note_json)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="笔记数据损坏") from exc
    wrong_rows = db.query(WrongAnswer).filter(WrongAnswer.note_id == note.id).all()
    wrong_answers = [
        {
            "question": r.question,
            "user_answer": r.user_answer,
            "correct_answer": r.correct_answer,
            "difficulty": r.difficulty,
            "time_stamp": r.time_stamp,
        }
        for r in wrong_rows
    ]
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    try:
        result = analyze_review(note_json, wrong_answers, llm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="复盘分析失败：" + str(exc)) from exc
    db.query(ReviewPlan).filter(ReviewPlan.note_id == note.id).delete()
    new_plan = []
    for item in result.get("plan") or []:
        row = ReviewPlan(
            note_id=note.id,
            content=item.get("content", ""),
            due_date=item.get("due_date", ""),
            done=False,
        )
        db.add(row)
        db.flush()
        new_plan.append({**item, "id": row.id})
    result["plan"] = new_plan
    note.review = json.dumps(result, ensure_ascii=False)
    db.commit()
    return result


@router.get("/plan")
def review_plan(db: Session = Depends(get_db), due_only: bool = False):
    today = datetime.date.today().isoformat()
    q = db.query(ReviewPlan, Note).join(Note, ReviewPlan.note_id == Note.id, isouter=True)
    if due_only:
        q = q.filter(ReviewPlan.due_date <= today, ReviewPlan.done == False)  # noqa: E712
    rows = q.order_by(ReviewPlan.done.asc(), ReviewPlan.due_date.asc()).all()
    result = []
    for r, note in rows:
        if r.done:
            status = "done"
        elif r.due_date < today:
            status = "overdue"
        elif r.due_date == today:
            status = "today"
        else:
            status = "upcoming"
        result.append({
            "id": r.id,
            "note_id": r.note_id,
            "note_title": note.title if note else "",
            "bvid": note.bvid if note else "",
            "page": note.page if note else 1,
            "content": r.content,
            "due_date": r.due_date,
            "done": r.done,
            "status": status,
            "repetitions": r.repetitions or 0,
            "interval_days": r.interval_days or 0,
            "ease_factor": float(r.ease_factor or 2.5),
            "last_reviewed": r.last_reviewed or "",
        })
    return result


@router.post("/plan/{plan_id}/toggle")
def toggle_plan(plan_id: int, db: Session = Depends(get_db)):
    row = db.query(ReviewPlan).filter(ReviewPlan.id == plan_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="计划不存在")
    row.done = not row.done
    row.last_reviewed = datetime.date.today().isoformat() if row.done else ""
    db.commit()
    return {"id": row.id, "done": row.done}


@router.post("/plan/{plan_id}/rate")
def rate_plan(plan_id: int, req: RateRequest, db: Session = Depends(get_db)):
    """按 SM-2 评分（1=重来 2=困难 3=良好 4=简单）重新排期。"""
    row = db.query(ReviewPlan).filter(ReviewPlan.id == plan_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="计划不存在")
    rating = int(req.rating)
    if rating not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="评分只能是 1-4")
    _apply_sm2(row, rating)
    db.commit()
    return {
        "id": row.id,
        "done": row.done,
        "due_date": row.due_date,
        "repetitions": row.repetitions,
        "interval_days": row.interval_days,
        "ease_factor": row.ease_factor,
        "status": "done" if row.done else ("overdue" if row.due_date < datetime.date.today().isoformat() else ("today" if row.due_date == datetime.date.today().isoformat() else "upcoming")),
    }
