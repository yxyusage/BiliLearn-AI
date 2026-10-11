"""OpenAI 兼容协议客户端（DeepSeek / Kimi / 通义千问 / OpenAI）。"""
import json
from typing import Any, Dict, List

import httpx

from .base import BaseLLM, LLMError, LLMHTTPError, LLMTruncatedError


def _friendly_http_error(status: int, text: str) -> str:
    """把供应商返回的 HTTP 错误翻译成人话。

    特别是 402（余额不足）与 401（Key 失效）：以前它们会被包装成
    "JSON 解析失败"，用户完全看不出是欠费还是格式问题。
    """
    if status == 401:
        return "模型接口鉴权失败（401）：API Key 无效或已过期，请到「大模型供应商」重新填写并保存"
    if status == 402:
        return "模型账户余额不足（402）：请到供应商后台充值后再试"
    if status == 429:
        return "模型接口限流（429）：请求太频繁或超出配额，稍后再试，或换一个供应商"
    if status == 400:
        return "模型接口参数错误（400）：" + text[:200]
    if status >= 500:
        return "模型服务端错误（%d）：供应商暂时故障，稍后重试即可" % status
    return "模型接口返回错误 %d：%s" % (status, text[:200])


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

    def chat_stream(self, messages, temperature=0.3, **kwargs):
        """流式输出：SSE 解析文本增量。代理不可用时自动回退直连。"""
        url = self.base_url + "/chat/completions"
        headers = {"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": temperature, "stream": True}
        payload.update(kwargs)
        last_exc = None
        for trust_env in (True, False):
            try:
                with httpx.Client(timeout=self.timeout, trust_env=trust_env) as client:
                    with client.stream("POST", url, json=payload, headers=headers) as resp:
                        resp.raise_for_status()
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data)
                            except Exception:
                                continue
                            delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content")
                            if delta:
                                yield delta
                return
            except httpx.ConnectError as exc:
                last_exc = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise LLMHTTPError(_friendly_http_error(exc.response.status_code, exc.response.text)) from exc
        raise LLMError("调用模型失败: " + str(last_exc))

    def _request(self, messages, temperature: float, **kwargs: Any) -> str:
        url = self.base_url + "/chat/completions"
        headers = {"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        payload.update(kwargs)
        try:
            resp = self._post(url, payload, headers)
            resp.raise_for_status()
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            content = ((choice.get("message") or {}).get("content") or "")
            # finish_reason=length 说明输出被 max_tokens 掐断：JSON 必然不完整，
            # 与其让上层报"未找到合法 JSON"，不如直接说清是输出太长
            if choice.get("finish_reason") == "length":
                cap = payload.get("max_tokens")
                raise LLMTruncatedError(
                    "模型输出被截断" + ("（达到输出上限 max_tokens=%s）" % cap if cap else "") +
                    "：内容太长，请缩短视频或换输出上限更大的模型"
                )
            return content
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text or ""
            # 有的供应商 max_tokens 上限更低：这类 400 去掉该参数再试一次，
            # 免得因为一个可选参数把整篇笔记卡死
            if status == 400 and "max_tokens" in body and payload.get("max_tokens"):
                # 优先降到该供应商已知的上限；实在没有才去掉参数。
                # （直接去掉会退回供应商默认值，对 DeepSeek 来说就是 4096，反而更容易被截断）
                cap = int(getattr(self, "max_output_tokens", 0) or 0)
                if cap and cap < int(payload.get("max_tokens") or 0):
                    payload["max_tokens"] = cap
                else:
                    payload.pop("max_tokens", None)
                try:
                    retry = self._post(url, payload, headers)
                    retry.raise_for_status()
                    data = retry.json()
                    return ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                except Exception:  # noqa: BLE001  还是失败就按原始错误抛出
                    pass
            raise LLMHTTPError(_friendly_http_error(status, body)) from exc
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
