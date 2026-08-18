"""阶梯自测与错题记录接口。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Note, WrongAnswer
from ..schemas import JudgeRequest, QuizRequest, SubmitRequest
from ..services.llm import build_llm
from ..services.prompts import quiz_explain_prompt, quiz_judge_prompt
from ..services.quiz_generator import generate_quiz
from ..services.settings_store import resolve_llm_config

router = APIRouter()


@router.post("/generate")
def quiz_generate(req: QuizRequest, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == req.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.status != "done" or not note.note_json:
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    llm_cfg = resolve_llm_config(db, req.provider, req.api_key, req.model, req.base_url)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「配置」页填写")
    try:
        note_json = json.loads(note.note_json)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="笔记数据损坏") from exc
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    try:
        result = generate_quiz(note_json, note.subject, llm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="生成自测题失败：" + str(exc)) from exc
    note.quizzes = json.dumps(result, ensure_ascii=False)
    db.commit()
    return result


@router.post("/submit")
def quiz_submit(req: SubmitRequest, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == req.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    total = len(req.answers)
    correct_count = 0
    wrong_count = 0
    for a in req.answers:
        if a.correct:
            correct_count += 1
        else:
            wrong_count += 1
            db.add(WrongAnswer(
                note_id=note.id,
                subject=note.subject,
                question=a.question,
                user_answer=a.user_answer,
                correct_answer=a.correct_answer,
                explanation=a.explanation,
                difficulty=a.difficulty,
                time_stamp=a.time_stamp,
            ))
    db.commit()
    return {"total": total, "correct": correct_count, "wrong": wrong_count}


@router.post("/judge")
def quiz_judge(req: JudgeRequest, db: Session = Depends(get_db)):
    """逐题批改：单选题本地判对错 + AI 讲解；简答/计算/证明题由 AI 批改讲解。"""
    note = db.query(Note).filter(Note.id == req.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    llm_cfg = resolve_llm_config(db)
    llm_ok = llm_cfg["provider"] == "ollama" or bool(llm_cfg["api_key"])
    llm = None
    if llm_ok:
        llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    single = req.qtype == "single" and len(req.options) > 0
    if single:
        correct = (req.user_answer or "").strip() == (req.answer or "").strip()
        feedback = ""
        if llm:
            try:
                data = llm.chat_json(quiz_explain_prompt(req.stem, req.options, req.answer, correct))
                feedback = str(data.get("feedback") or "") if isinstance(data, dict) else ""
            except Exception:
                feedback = ""
        if not feedback:
            feedback = req.explanation or (
                "回答正确！这道题考察" + (req.knowledge_point or "对应知识点") + "。" if correct
                else "回答错误。参考答案：" + (req.answer or "见解析")
            )
    else:
        if not llm:
            raise HTTPException(status_code=400, detail="批改简答/计算/证明题需要先配置大模型 API Key")
        try:
            data = llm.chat_json(quiz_judge_prompt(
                req.stem, req.qtype, req.options, req.answer, req.user_answer, req.knowledge_point
            ))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="AI 批改失败：" + str(exc)) from exc
        correct = bool(data.get("correct")) if isinstance(data, dict) else False
        feedback = str(data.get("feedback") or req.explanation or "") if isinstance(data, dict) else ""
    if not correct:
        db.add(WrongAnswer(
            note_id=note.id,
            subject=note.subject,
            question=req.stem,
            user_answer=req.user_answer or "（未作答）",
            correct_answer=req.answer or "",
            explanation=req.explanation or "",
            feedback=feedback,
            difficulty=req.difficulty or "",
            time_stamp=req.time_stamp or "",
        ))
        db.commit()
    return {"correct": correct, "feedback": feedback}


@router.get("/{note_id}/wrong")
def wrong_answers(note_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(WrongAnswer)
        .filter(WrongAnswer.note_id == note_id)
        .order_by(WrongAnswer.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "question": r.question,
            "user_answer": r.user_answer,
            "correct_answer": r.correct_answer,
            "explanation": r.explanation,
            "feedback": r.feedback,
            "difficulty": r.difficulty,
            "time_stamp": r.time_stamp,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]
