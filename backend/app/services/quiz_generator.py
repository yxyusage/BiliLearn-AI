"""阶梯式自测题生成。"""
import json
from typing import Dict

from .llm import BaseLLM
from .prompts import quiz_prompt
from ..utils.timestamp import normalize_hms

ALLOWED_DIFFICULTY = ("basic", "medium", "advanced")
ALLOWED_TYPE = ("single", "calc", "short", "proof")


def generate_quiz(note: dict, subject: str, llm: BaseLLM, per_tier: int = 3) -> dict:
    note_text = json.dumps(note, ensure_ascii=False)[:12000]
    data = llm.chat_json(quiz_prompt(subject, note_text, per_tier))
    if not isinstance(data, dict):
        raise ValueError("自测题输出格式错误")
    questions = []
    for q in data.get("questions") or []:
        if not isinstance(q, dict):
            continue
        stem = str(q.get("stem") or "").strip()
        if not stem:
            continue
        difficulty = str(q.get("difficulty") or "basic")
        if difficulty not in ALLOWED_DIFFICULTY:
            difficulty = "basic"
        options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        qtype = str(q.get("type") or ("single" if options else "short"))
        if qtype not in ALLOWED_TYPE:
            qtype = "single" if options else "short"
        ts = q.get("time_stamp") or ""
        questions.append({
            "difficulty": difficulty,
            "type": qtype,
            "stem": stem,
            "options": options,
            "answer": str(q.get("answer") or "").strip(),
            "explanation": str(q.get("explanation") or "").strip(),
            "knowledge_point": str(q.get("knowledge_point") or "").strip(),
            "time_stamp": normalize_hms(ts) if ts else "",
        })
    return {"questions": questions}
