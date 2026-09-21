"""阶梯式自测题生成。"""
import json
import re
from typing import List

from .llm import BaseLLM
from .note_generator import note_plain_text
from .prompts import quiz_prompt
from ..utils.timestamp import normalize_hms

ALLOWED_DIFFICULTY = ("basic", "medium", "advanced")
ALLOWED_TYPE = ("single", "judge", "fill", "calc")

_OPTION_PREFIX = re.compile(r"^[A-Da-d][\.、\)）:：]\s*")
_BLANK = re.compile(r"_{3,}")


def _strip_option_prefix(text: str) -> str:
    return _OPTION_PREFIX.sub("", str(text or "").strip())


def _normalize_single_answer(answer: str, options) -> str:
    """单选答案统一为选项字母（A/B/C/D）；无法判定时保留原文。"""
    answer = str(answer or "").strip()
    m = re.match(r"^([A-Da-d])(?:[\.、\)）:：]|$)", answer)
    if m:
        return m.group(1).upper()
    target = _strip_option_prefix(answer)
    for idx, opt in enumerate(options):
        opt_clean = _strip_option_prefix(opt)
        if target and (target == opt_clean or target in opt_clean or opt_clean in target):
            return chr(ord("A") + idx)
    return answer


def _normalize_judge_answer(answer: str) -> str:
    text = str(answer or "").strip()
    # 先判否定，避免“不对”被“对”抢先匹配
    if re.search(r"(错误|不对|错的|false|wrong|×|✗|^错$)", text, re.I):
        return "错误"
    if re.search(r"(正确|对的?|没错|true|correct|√|✓|^对$)", text, re.I):
        return "正确"
    return text


def normalize_fill_answer(answer) -> str:
    """填空题答案归一为“空 | 空”，每空内等价答案用“ / ”分隔。"""
    if isinstance(answer, list):
        empties = []
        for item in answer:
            if isinstance(item, list):
                empties.append(" / ".join(str(x).strip() for x in item if str(x).strip()))
            else:
                empties.append(str(item).strip())
        return " | ".join(e for e in empties if e)
    text = str(answer or "").strip()
    # 模型偶尔用 ；; 或换行分隔空位，统一为 |
    text = re.sub(r"[；;\n]+", " | ", text)
    text = re.sub(r"\s*\|\s*", " | ", text)
    text = re.sub(r"\s*/\s*", " / ", text)
    return text.strip(" |")


def _canonical_answer(text: str) -> str:
    """答案比对归一：去空白、常见中英文标点、转小写（英文）。"""
    text = str(text or "").lower()
    # 全角转半角空格与标点
    out = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            ch = " "
        elif 0xFF01 <= code <= 0xFF5E:
            ch = chr(code - 0xFEE0)
        out.append(ch)
    text = "".join(out)
    text = re.sub(r"[\s,.;:!?，。；：！？、'\"`’“”‘’()（）\[\]{}<>《》=*\\/\-]+", "", text)
    return text


def split_fill_blanks(stem: str) -> int:
    """统计题干中的空位数。"""
    return len(_BLANK.findall(str(stem or "")))


def judge_fill(canonical_answer: str, user_answer) -> (bool, List[str]):
    """本地判填空题。user_answer 可为数组（每空一项）或字符串（按 |/逗号/空白拆分）。

    返回 (是否全对, 每空是否正确)。
    """
    expected = [
        [alt.strip() for alt in blank.split("/") if alt.strip()]
        for blank in str(canonical_answer).split("|")
    ]
    expected = [b for b in expected if b]
    if isinstance(user_answer, list):
        given = [str(x) for x in user_answer]
    else:
        text = str(user_answer or "")
        given = re.split(r"\s*\|\s*|[，,；;]\s*|\s{2,}", text)
        if len(given) == 1 and len(expected) > 1:
            given = re.split(r"\s+", text.strip())
    per_blank = []
    for idx, alts in enumerate(expected):
        user = given[idx] if idx < len(given) else ""
        user_c = _canonical_answer(user)
        ok = bool(user_c) and any(_canonical_answer(alt) == user_c for alt in alts)
        per_blank.append(ok)
    return len(per_blank) == len(expected) and all(per_blank), per_blank


def normalize_question(q: dict) -> dict:
    """把模型输出的单题 JSON 归一为前端/判分统一结构；无效题目返回空 dict。"""
    stem = str(q.get("stem") or "").strip()
    if not stem:
        return {}
    difficulty = str(q.get("difficulty") or "basic")
    if difficulty not in ALLOWED_DIFFICULTY:
        difficulty = "basic"
    raw_options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
    options = [_strip_option_prefix(o) for o in raw_options]
    raw_type = str(q.get("type") or "").strip().lower()
    if raw_type in ("judge", "bool", "tf") or (not options and re.search(r"(判断|是否|对错|正误)", stem)):
        qtype = "judge"
    elif raw_type in ("fill", "blank", "cloze") or (not options and _BLANK.search(stem)):
        qtype = "fill"
    elif raw_type == "single" or (len(options) >= 2 and raw_type not in ("calc",)):
        qtype = "single"
    elif raw_type == "calc":
        qtype = "calc"
    else:
        # 兜底：模型若仍输出证明/简答等长文作答题型，归入计算题走 AI 批改
        qtype = "calc"
    answer = str(q.get("answer") or "").strip()
    if qtype == "single" and options:
        answer = _normalize_single_answer(answer, options)
    elif qtype == "judge":
        answer = _normalize_judge_answer(answer)
    elif qtype == "fill":
        answer = normalize_fill_answer(q.get("answer") or answer)
    ts = q.get("time_stamp") or ""
    return {
        "difficulty": difficulty,
        "type": qtype,
        "stem": stem,
        "options": options,
        "answer": answer,
        "explanation": str(q.get("explanation") or "").strip(),
        "knowledge_point": str(q.get("knowledge_point") or "").strip(),
        "time_stamp": normalize_hms(ts) if ts else "",
    }


def generate_quiz(note: dict, subject: str, llm: BaseLLM, per_tier: int = 3) -> dict:
    note_text = note_plain_text(note, char_limit=24000)
    data = llm.chat_json(quiz_prompt(subject, note_text, per_tier))
    if not isinstance(data, dict):
        raise ValueError("自测题输出格式错误")
    questions = []
    for q in data.get("questions") or []:
        if not isinstance(q, dict):
            continue
        item = normalize_question(q)
        if item:
            questions.append(item)
    return {"questions": questions}
