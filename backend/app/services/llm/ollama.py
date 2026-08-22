"""本地 Ollama 客户端。"""
import json
from typing import Any, Dict, List

import httpx

from .base import BaseLLM, LLMError


class OllamaLLM(BaseLLM):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b", timeout: float = 300.0):
        super().__init__(model)
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, json_mode: bool = False, **kwargs: Any) -> str:
        url = self.base_url + "/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            resp = httpx.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except Exception as exc:  # noqa: BLE001
            raise LLMError("调用 Ollama 失败: " + str(exc)) from exc

    def chat_stream(self, messages, temperature=0.3, **kwargs):
        url = self.base_url + "/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    delta = (data.get("message") or {}).get("content")
                    if delta:
                        yield delta
                    if data.get("done"):
                        return

    def chat_json(self, messages, temperature=0.2, retries=2, **kwargs):
        kwargs["json_mode"] = True
        return super().chat_json(messages, temperature=temperature, retries=retries, **kwargs)
