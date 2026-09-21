"""阶梯自测与错题记录接口。"""
import datetime
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Note, WrongAnswer
from ..schemas import JudgeRequest, QuizRequest, RecordItem, RecordRequest, SubmitRequest, VariantRequest
from ..services import features as feature_service
from ..services.llm import build_llm
from ..services.prompts import quiz_explain_prompt, quiz_judge_prompt
from ..services.quiz_generator import _strip_option_prefix, generate_quiz, judge_fill
from ..services.settings_store import resolve_llm_config

router = APIRouter()


def _option_key(answer: str, options) -> str:
    """把单选答案（字母或选项文本）统一为 A/B/C/D。"""
    s = str(answer or "").strip()
    m = re.match(r"^([A-Da-d])(?:[\.、\)）:：]|$)", s)
    if m:
        return m.group(1).upper()
    target = _strip_option_prefix(s)
    for idx, opt in enumerate(options or []):
        opt_clean = _strip_option_prefix(opt)
        if target and (target == opt_clean or target in opt_clean or opt_clean in target):
            return chr(ord("A") + idx)
    return s.upper()


def _judge_bool(answer: str) -> bool:
    s = str(answer or "").strip()
    if re.search(r"(错误|不对|错的|false|wrong|×|✗|^错$)", s, re.I):
        return False
    if re.search(r"(正确|对的?|没错|true|correct|√|✓|^[Aa]$)", s, re.I):
        return True
    return False


def _upsert_wrong(db: Session, note: Note, item: RecordItem) -> WrongAnswer:
    row = (
        db.query(WrongAnswer)
        .filter(WrongAnswer.note_id == note.id, WrongAnswer.question == item.question)
        .first()
    )
    if row:
        row.qtype = item.qtype or row.qtype
        row.user_answer = item.user_answer
        row.correct_answer = item.correct_answer or row.correct_answer
        row.explanation = item.explanation or row.explanation
        row.feedback = item.feedback or row.feedback
        row.difficulty = item.difficulty or row.difficulty
        row.time_stamp = item.time_stamp or row.time_stamp
        row.status = "active"
        row.wrong_count = (row.wrong_count or 1) + 1
        row.updated_at = datetime.datetime.utcnow()
        return row
    row = WrongAnswer(
        note_id=note.id,
        subject=note.subject,
        qtype=item.qtype,
        question=item.question,
        user_answer=item.user_answer or "（未作答）",
        correct_answer=item.correct_answer,
        explanation=item.explanation,
        feedback=item.feedback,
        difficulty=item.difficulty,
        time_stamp=item.time_stamp,
        status="active",
        wrong_count=1,
    )
    db.add(row)
    return row


def _mark_mastered(db: Session, note_id: int, question: str):
    row = (
        db.query(WrongAnswer)
        .filter(WrongAnswer.note_id == note_id, WrongAnswer.question == question)
        .first()
    )
    if row and row.status != "mastered":
        row.status = "mastered"
        row.updated_at = datetime.datetime.utcnow()


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


@router.post("/variant")
def quiz_variant(req: VariantRequest, db: Session = Depends(get_db)):
    """同类变式题：基于原题与笔记上下文，AI 换数字/换情境生成一道新题。"""
    note = db.query(Note).filter(Note.id == req.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.status != "done" or not note.note_json:
        raise HTTPException(status_code=400, detail="笔记尚未生成完成")
    if not req.question:
        raise HTTPException(status_code=400, detail="缺少原题内容")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「设置」页填写")
    try:
        note_json = json.loads(note.note_json)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="笔记数据损坏") from exc
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    try:
        item = feature_service.generate_variant(note_json, note.subject, req.question, llm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="变式题生成失败：" + str(exc)) from exc
    return item


@router.post("/record")
def quiz_record(req: RecordRequest, db: Session = Depends(get_db)):
    """单题作答结果上报：答对则消除错题记录，答错则去重入库（含思考卡自评）。"""
    note = db.query(Note).filter(Note.id == req.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    for item in req.answers:
        if not item.question:
            continue
        if item.correct:
            _mark_mastered(db, note.id, item.question)
        else:
            _upsert_wrong(db, note, item)
    db.commit()
    return {"ok": True}


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
            _mark_mastered(db, note.id, a.question)
        else:
            wrong_count += 1
            _upsert_wrong(
                db, note,
                RecordItem(
                    qtype=getattr(a, "qtype", ""),
                    question=a.question,
                    user_answer=a.user_answer,
                    correct_answer=a.correct_answer,
                    explanation=a.explanation,
                    feedback="",
                    difficulty=a.difficulty,
                    time_stamp=a.time_stamp,
                    correct=False,
                ),
            )
    db.commit()
    return {"total": total, "correct": correct_count, "wrong": wrong_count}


@router.post("/judge")
def quiz_judge(req: JudgeRequest, db: Session = Depends(get_db)):
    """单选/判断本地判分 + AI 讲解；计算题 AI 批改。证明/简答为思考卡，不走本接口。"""
    note = db.query(Note).filter(Note.id == req.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    llm_cfg = resolve_llm_config(db)
    llm_ok = llm_cfg["provider"] == "ollama" or bool(llm_cfg["api_key"])
    llm = None
    if llm_ok:
        llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])

    per_blank = None
    if req.qtype == "single" and req.options:
        user_key = _option_key(req.user_answer, req.options)
        right_key = _option_key(req.answer, req.options)
        correct = user_key == right_key
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
    elif req.qtype == "judge":
        correct = _judge_bool(req.user_answer) == _judge_bool(req.answer)
        feedback = req.explanation or (
            "回答正确！" if correct else "回答错误。参考答案：" + req.answer
        )
    elif req.qtype == "fill":
        user = req.user_answer
        parsed = user
        try:
            parsed = json.loads(user)
        except Exception:
            parsed = user
        correct, per_blank = judge_fill(req.answer, parsed)
        if correct:
            feedback = "回答正确，全部空位都填对了！" + (req.explanation or "")
        else:
            wrong_idx = [str(i + 1) for i, ok in enumerate(per_blank) if not ok]
            feedback = (
                "第 " + "、".join(wrong_idx) + " 空不正确。参考答案：" + (req.answer or "")
                + ("\n解析：" + req.explanation if req.explanation else "")
            )
    elif req.qtype == "calc":
        if not llm:
            raise HTTPException(status_code=400, detail="批改计算题需要先配置大模型 API Key")
        try:
            data = llm.chat_json(quiz_judge_prompt(
                req.stem, req.qtype, req.options, req.answer, req.user_answer, req.knowledge_point
            ))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="AI 批改失败：" + str(exc)) from exc
        correct = bool(data.get("correct")) if isinstance(data, dict) else False
        feedback = str(data.get("feedback") or req.explanation or "") if isinstance(data, dict) else ""
    else:
        raise HTTPException(status_code=400, detail="该题型为自评思考卡，无需 AI 批改")

    item = RecordItem(
        qtype=req.qtype,
        question=req.stem,
        user_answer=req.user_answer or "（未作答）",
        correct_answer=req.answer or "",
        explanation=req.explanation or "",
        feedback=feedback,
        difficulty=req.difficulty or "",
        time_stamp=req.time_stamp or "",
        correct=correct,
    )
    if correct:
        _mark_mastered(db, note.id, req.stem)
    else:
        _upsert_wrong(db, note, item)
    db.commit()
    return {"correct": correct, "feedback": feedback, "per_blank": per_blank}


@router.post("/wrong/{row_id}/master")
def manual_master(row_id: int, db: Session = Depends(get_db)):
    row = db.query(WrongAnswer).filter(WrongAnswer.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    row.status = "mastered"
    row.updated_at = datetime.datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.get("/wrong/all")
def all_wrong_answers(active_only: int = 1, limit: int = 300, db: Session = Depends(get_db)):
    """全局错题本（复习中心用），附带笔记标题。"""
    query = db.query(WrongAnswer, Note).join(Note, WrongAnswer.note_id == Note.id)
    if active_only:
        query = query.filter(WrongAnswer.status != "mastered")
    rows = query.order_by(WrongAnswer.updated_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "note_id": r.note_id,
            "note_title": n.title,
            "bvid": n.bvid,
            "page": n.page,
            "qtype": r.qtype or "",
            "question": r.question,
            "user_answer": r.user_answer,
            "correct_answer": r.correct_answer,
            "explanation": r.explanation,
            "feedback": r.feedback,
            "difficulty": r.difficulty,
            "time_stamp": r.time_stamp,
            "status": r.status or "active",
            "wrong_count": r.wrong_count or 1,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r, n in rows
    ]


@router.get("/{note_id}/wrong")
def wrong_answers(note_id: int, all_rows: int = 0, db: Session = Depends(get_db)):
    query = db.query(WrongAnswer).filter(WrongAnswer.note_id == note_id)
    if not all_rows:
        query = query.filter(WrongAnswer.status != "mastered")
    rows = query.order_by(WrongAnswer.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "qtype": r.qtype or "",
            "question": r.question,
            "user_answer": r.user_answer,
            "correct_answer": r.correct_answer,
            "explanation": r.explanation,
            "feedback": r.feedback,
            "difficulty": r.difficulty,
            "time_stamp": r.time_stamp,
            "status": r.status or "active",
            "wrong_count": r.wrong_count or 1,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]
