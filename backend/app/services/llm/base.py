"""大模型统一调用基类。"""
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMError(Exception):
    """大模型调用或解析失败。"""


class BaseLLM(ABC):
    """所有大模型供应商的统一接口。"""

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, **kwargs: Any) -> str:
        """返回纯文本回复。"""

    def chat_json(self, messages, temperature=0.2, retries=2, **kwargs) -> Any:
        """要求模型输出 JSON，解析失败时自动重试。"""
        last_err = ""
        history = [dict(m) for m in messages]
        for attempt in range(retries + 1):
            try:
                text = self.chat(history, temperature=temperature, **kwargs)
                return self._extract_json(text)
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                if attempt < retries:
                    history.append({
                        "role": "user",
                        "content": (
                            "你上一次的输出不是合法 JSON。请严格只输出一个 JSON 对象（或数组），"
                            "不要包含任何解释、注释或 Markdown 代码块。错误信息：" + last_err
                        ),
                    })
        raise LLMError("JSON 解析失败：" + last_err)

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        t = (text or "").strip()
        fence = chr(96) * 3  # 三个反引号
        lines = t.split("\n")
        if lines and lines[0].strip().startswith(fence):
            lines = lines[1:]
        if lines and lines[-1].strip() == fence:
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @classmethod
    def _extract_json(cls, text: str) -> Any:
        text = cls._strip_code_fence(text)
        try:
            return json.loads(text)
        except Exception:
            pass
        start = None
        for idx, ch in enumerate(text):
            if ch in "{[":
                start = idx
                break
        if start is None:
            raise ValueError("未找到 JSON 内容")
        for end in range(len(text), start, -1):
            try:
                return json.loads(text[start:end])
            except Exception:
                continue
        raise ValueError("未找到合法 JSON")
