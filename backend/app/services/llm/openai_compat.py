"""OpenAI 兼容协议客户端（DeepSeek / Kimi / 通义千问）。"""
from typing import Any, Dict, List

import httpx

from .base import BaseLLM, LLMError


class OpenAICompatLLM(BaseLLM):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 180.0):
        super().__init__(model)
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, **kwargs: Any) -> str:
        return self._request(messages, temperature, **kwargs)

    def chat_vision(self, messages, temperature: float = 0.2, **kwargs: Any) -> str:
        """多模态调用：messages 中可含 image_url 内容。"""
        return self._request(messages, temperature, timeout=max(self.timeout, 300.0), **kwargs)

    def _request(self, messages, temperature: float, **kwargs: Any) -> str:
        url = self.base_url + "/chat/completions"
        headers = {"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        payload.update(kwargs)
        try:
            resp = self._post(url, payload, headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise LLMError("模型接口返回错误 " + str(exc.response.status_code) + ": " + detail) from exc
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError("调用模型失败: " + str(exc)) from exc

    def _post(self, url: str, payload: dict, headers: dict):
        """先按系统代理请求，代理不可用时自动回退直连。"""
        try:
            return httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        except httpx.ConnectError:
            return httpx.post(url, json=payload, headers=headers, timeout=self.timeout, trust_env=False)
