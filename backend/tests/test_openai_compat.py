"""OpenAI 兼容层的容错回归测试（离线，用假响应，不联网）。

接一个「OpenAI 兼容」平台时最常见的三种 400，都不该原样抛给用户：
  1. 推理类模型不接受 temperature；
  2. 新版模型把 max_tokens 改名成 max_completion_tokens；
  3. 该模型支持的 max_tokens 上限更低（要减半重试）。

这三种如果没有兜住，用户看到的就是「模型接口参数错误（400）」，
而他并不知道问题出在协议差异而不是自己的配置。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import httpx

from backend.app.services.llm.base import LLMTruncatedError
from backend.app.services.llm.openai_compat import OpenAICompatLLM

OK_BODY = {"choices": [{"message": {"content": "正常"}, "finish_reason": "stop"}]}


def _resp(status, body):
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x/v1/chat/completions"))


class _FakePost:
    """按脚本依次返回响应，并记录每次实际发出的 payload。"""

    def __init__(self, script):
        self.script = list(script)
        self.payloads = []

    def __call__(self, url, payload, headers):
        self.payloads.append(dict(payload))
        status, body = self.script.pop(0)
        return _resp(status, body)


def _llm_with(script):
    llm = OpenAICompatLLM("https://api.example.com/v1", "sk-test", "test-model")
    fake = _FakePost(script)
    llm._post = fake  # type: ignore[method-assign]
    return llm, fake


def test_temperature_unsupported():
    llm, fake = _llm_with([
        (400, {"error": {"message": "Unsupported parameter: 'temperature' is not supported with this model."}}),
        (200, OK_BODY),
    ])
    assert llm.chat([{"role": "user", "content": "hi"}], temperature=0.3) == "正常"
    assert "temperature" in fake.payloads[0]
    assert "temperature" not in fake.payloads[1], "重试时应该去掉 temperature"
    print("temperature-fallback OK")


def test_max_completion_tokens_rename():
    llm, fake = _llm_with([
        (400, {"error": {"message": "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead."}}),
        (200, OK_BODY),
    ])
    assert llm.chat([{"role": "user", "content": "hi"}], max_tokens=8000) == "正常"
    assert fake.payloads[0].get("max_tokens") == 8000
    assert "max_tokens" not in fake.payloads[1]
    assert fake.payloads[1].get("max_completion_tokens") == 8000, "应改名为 max_completion_tokens 重试"
    print("max-completion-tokens OK")


def test_max_tokens_halved():
    llm, fake = _llm_with([
        (400, {"error": {"message": "max_tokens is too large: maximum context length exceeded"}}),
        (200, OK_BODY),
    ])
    assert llm.chat([{"role": "user", "content": "hi"}], max_tokens=16384) == "正常"
    assert fake.payloads[1].get("max_tokens") == 8192, fake.payloads[1]
    print("max-tokens-halve OK")


def test_truncated_is_reported():
    llm, _ = _llm_with([(200, {"choices": [{"message": {"content": "半截 JSON"}, "finish_reason": "length"}]})])
    try:
        llm.chat([{"role": "user", "content": "hi"}], max_tokens=4096)
    except LLMTruncatedError as exc:
        assert "截断" in str(exc)
    else:
        raise AssertionError("finish_reason=length 应抛 LLMTruncatedError")
    print("truncation-detect OK")


if __name__ == "__main__":
    test_temperature_unsupported()
    test_max_completion_tokens_rename()
    test_max_tokens_halved()
    test_truncated_is_reported()
    print("ALL_COMPAT_TESTS_PASSED")
