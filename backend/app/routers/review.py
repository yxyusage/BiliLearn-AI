"""AI 复盘与艾宾浩斯复习计划接口。"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Note, ReviewPlan, WrongAnswer
from ..schemas import ReviewRequest
from ..services.llm import build_llm
from ..services.review import analyze_review
from ..services.settings_store import resolve_llm_config

router = APIRouter()


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
    q = db.query(ReviewPlan)
    if due_only:
        today = datetime.date.today().isoformat()
        q = q.filter(ReviewPlan.due_date <= today, ReviewPlan.done == False)  # noqa: E712
    rows = q.order_by(ReviewPlan.due_date.asc()).all()
    return [
        {
            "id": r.id,
            "note_id": r.note_id,
            "content": r.content,
            "due_date": r.due_date,
            "done": r.done,
        }
        for r in rows
    ]


@router.post("/plan/{plan_id}/toggle")
def toggle_plan(plan_id: int, db: Session = Depends(get_db)):
    row = db.query(ReviewPlan).filter(ReviewPlan.id == plan_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="计划不存在")
    row.done = not row.done
    db.commit()
    return {"id": row.id, "done": row.done}
