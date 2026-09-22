"""请求/响应 Pydantic 模型。"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ParseRequest(BaseModel):
    url: str


class GenerateRequest(BaseModel):
    bvid: str
    page: int = 1
    subject: str = "general"  # general/english/math/cs/liberal
    title: str = ""
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


class QuizRequest(BaseModel):
    note_id: int
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


class AnswerItem(BaseModel):
    qtype: str = ""
    question: str = ""
    user_answer: str = ""
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = ""
    time_stamp: str = ""
    correct: bool = False


class RecordItem(BaseModel):
    qtype: str = ""
    question: str = ""
    user_answer: str = ""
    correct_answer: str = ""
    explanation: str = ""
    feedback: str = ""
    difficulty: str = ""
    time_stamp: str = ""
    correct: bool = False


class RecordRequest(BaseModel):
    note_id: int
    answers: List[RecordItem] = []


class SubmitRequest(BaseModel):
    note_id: int
    answers: List[AnswerItem] = []


class ReviewRequest(BaseModel):
    note_id: int


class JudgeRequest(BaseModel):
    note_id: int
    stem: str
    qtype: str = "single"  # single / judge / calc（proof 为自评思考卡）
    options: List[str] = []
    answer: str = ""
    user_answer: str = ""
    explanation: str = ""
    knowledge_point: str = ""
    difficulty: str = ""
    time_stamp: str = ""


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []


class FormulaRequest(BaseModel):
    provider: str = "qwen"
    model: Optional[str] = None


class CollectionStartRequest(BaseModel):
    bvid: str
    subject: str = "general"
    start_page: int = 1
    end_page: int = 0  # 0 = 到最后一集
    title: str = ""


class SettingBody(BaseModel):
    key: str
    value: str


class VariantRequest(BaseModel):
    note_id: int
    question: Dict[str, Any] = {}


class RateRequest(BaseModel):
    rating: int = 3  # 1=重来 2=困难 3=良好 4=简单
