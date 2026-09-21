"""功能专项服务：英语听写填空 / 同类变式题 / 「没懂」AI 换讲。"""
import json
import re
from typing import List

from .llm import BaseLLM
from .note_generator import note_plain_text
from .prompts import dictation_prompt, re_explain_prompt, variant_prompt
from .quiz_generator import normalize_fill_answer, normalize_question
from ..utils.timestamp import normalize_hms

_BLANK = re.compile(r"_{3,}")


def generate_dictation(transcript: str, llm: BaseLLM) -> List[dict]:
    """基于带时间戳字幕生成英语听写填空，返回归一后的条目列表。"""
    data = llm.chat_json(dictation_prompt(transcript[:12000]))
    if not isinstance(data, dict):
        raise ValueError("听写练习输出格式错误")
    items = []
    for it in data.get("items") or []:
        if not isinstance(it, dict):
            continue
        sentence = str(it.get("sentence") or "").strip()
        blanks = [str(b).strip() for b in (it.get("blanks") or []) if str(b).strip()]
        answers = [str(a).strip() for a in (it.get("answers") or []) if str(a).strip()]
        if not sentence or not blanks or not answers:
            continue
        stem = sentence
        for b in blanks:
            stem = stem.replace(b, "____", 1)
        items.append({
            "stem": stem,
            "sentence": sentence,
            "answer": normalize_fill_answer(answers),
            "translation": str(it.get("translation") or "").strip(),
            "hint": str(it.get("hint") or "").strip(),
            "time_stamp": normalize_hms(str(it.get("time_stamp") or "")) if it.get("time_stamp") else "",
        })
    return items


def generate_variant(note: dict, subject: str, question: dict, llm: BaseLLM) -> dict:
    """生成一道同类变式题，返回与自测题同结构的题目；失败抛异常。"""
    note_text = note_plain_text(note, char_limit=8000)
    payload = json.dumps(question, ensure_ascii=False)[:3000]
    data = llm.chat_json(variant_prompt(subject, note_text, payload))
    if not isinstance(data, dict):
        raise ValueError("变式题输出格式错误")
    item = normalize_question(data)
    if not item:
        raise ValueError("变式题内容为空")
    if not item.get("time_stamp") and question.get("time_stamp"):
        item["time_stamp"] = question["time_stamp"]
    return item


def re_explain_section(note: dict, section_text: str, llm: BaseLLM) -> str:
    """针对卡住的小节换一种讲法（通俗类比 + 自查问题），返回 Markdown 文本。"""
    messages = re_explain_prompt(section_text[:2000], json.dumps(note, ensure_ascii=False))
    text = llm.chat(messages, temperature=0.6)
    return str(text or "").strip()
