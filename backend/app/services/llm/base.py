"""大模型统一调用基类。"""
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMError(Exception):
    """大模型调用或解析失败。"""


class LLMHTTPError(LLMError):
    """模型接口返回了 HTTP 错误（401 鉴权 / 402 余额 / 429 限流 / 5xx 等）。

    单独成类是为了：① 不再被包装成"JSON 解析失败"（那会严重误导用户）；
    ② 重试没有意义，直接抛给上层。
    """


class LLMTruncatedError(LLMError):
    """模型输出被 max_tokens 截断（finish_reason=length），JSON 必然不完整。

    同样不重试：再问一次还是会被截断。
    """


class BaseLLM(ABC):
    """所有大模型供应商的统一接口。"""

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, **kwargs: Any) -> str:
        """返回纯文本回复。"""

    def chat_stream(self, messages: List[Dict[str, str]], temperature: float = 0.3, **kwargs: Any):
        """流式输出文本增量（默认不支持，由具体供应商实现）。"""
        raise NotImplementedError("当前供应商不支持流式输出")

    def chat_json(self, messages, temperature=0.2, retries=2, **kwargs) -> Any:
        """要求模型输出 JSON，解析失败时自动重试。

        两个关键点：
        1) 未显式指定 max_tokens 时，用供应商给的输出上限（否则会被静默截断成半截 JSON）；
        2) HTTP 错误与"输出被截断"既不重试、也不包装成"JSON 解析失败"，原样抛出，
           上层才能给出准确提示（余额不足 / 限流 / 输出过长）。
        """
        if "max_tokens" not in kwargs:
            cap = getattr(self, "max_output_tokens", 0)
            if cap:
                kwargs["max_tokens"] = int(cap)
        last_err = ""
        history = [dict(m) for m in messages]
        for attempt in range(retries + 1):
            try:
                text = self.chat(history, temperature=temperature, **kwargs)
                return self._extract_json(text)
            except (LLMHTTPError, LLMTruncatedError):
                raise
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
        """从模型回复里取出 JSON。

        模型经常在 JSON 前后写说明文字，甚至正文里先出现 LaTeX 的大括号
        （例如先说一句"用 \\frac{a}{b} 表示…"再给 JSON）。旧实现只从**第一个**
        { 或 [ 开始尝试解析，遇到这种情况必然失败，于是报"未找到合法 JSON"。
        现改为逐个候选起点调用 JSONDecoder.raw_decode，能容忍前后的散文。
        """
        text = cls._strip_code_fence(text)
        try:
            return json.loads(text)
        except Exception:
            pass
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch not in "{[":
                continue
            try:
                value, _end = decoder.raw_decode(text[idx:])
                return value
            except Exception:
                continue
        # 失败时把线索带上：长度 + 括号是否闭合（没闭合多半就是被截断）
        stripped = text.strip()
        hint = "（返回 %d 字" % len(stripped)
        if stripped.count("{") > stripped.count("}"):
            hint += "，花括号未闭合，疑似被截断"
        hint += "；开头：" + stripped[:80].replace(chr(10), " ") + "）"
        raise ValueError("未找到合法 JSON" + hint)
