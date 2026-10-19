"""大模型 JSON 处理回归测试（离线，不联网）。

覆盖三件事：
1. 模型回复里 JSON 前后夹着散文 / LaTeX 大括号时，仍要能取到 JSON（旧实现只从第一个
   { 开始试，遇到就报"未找到合法 JSON"）；
2. 输出被 max_tokens 截断、以及 401/402/429 这类 HTTP 错误，不能被包装成
   "JSON 解析失败"（那会严重误导用户），而且不该白白重试；
3. chat_json 要自动带上供应商的输出上限，否则长笔记会被截断。
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services.llm.base import BaseLLM, LLMError, LLMHTTPError, LLMTruncatedError


class FakeLLM(BaseLLM):
    def __init__(self, replies=None, max_output_tokens=8192):
        super().__init__("fake")
        self.replies = list(replies or [])
        self.calls = []
        self.lock = threading.Lock()
        self.max_output_tokens = max_output_tokens

    def chat(self, messages, temperature=0.3, **kwargs):
        with self.lock:
            self.calls.append({"messages": messages, "kwargs": kwargs})
            reply = self.replies.pop(0) if self.replies else '{"sections": []}'
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_extract_plain_and_fenced():
    llm = FakeLLM()
    assert llm._extract_json('{"a": 1}') == {"a": 1}
    assert llm._extract_json('\u0060\u0060\u0060json\n{"a": 1}\n\u0060\u0060\u0060') == {"a": 1}
    assert llm._extract_json('[{"a": 1}]') == [{"a": 1}]
    print("extract-plain OK")


def test_extract_json_after_latex_braces():
    """关键回归：正文里先出现 LaTeX 的 {}，后面才是真 JSON。"""
    llm = FakeLLM()
    text = "可以用 \\frac{a}{b} 表示这个比例。\n下面是整理好的结果：\n{\"sections\": [{\"title\": \"一\"}]}"
    assert llm._extract_json(text) == {"sections": [{"title": "一"}]}
    # JSON 后面还有说明文字
    assert llm._extract_json('{"a": 2}\n以上就是全部内容，请查收。') == {"a": 2}
    print("extract-after-latex OK")


def test_extract_truncated_hint():
    llm = FakeLLM()
    try:
        llm._extract_json('{"sections": [{"title": "一"')
        raise AssertionError("应当报错")
    except ValueError as exc:
        msg = str(exc)
        assert "未闭合" in msg and "截断" in msg, msg
    print("extract-truncated OK")


def test_chat_json_injects_max_tokens():
    llm = FakeLLM(['{"a": 1}'])
    assert llm.chat_json([{"role": "user", "content": "x"}]) == {"a": 1}
    assert llm.calls[0]["kwargs"].get("max_tokens") == 8192, llm.calls[0]

    llm2 = FakeLLM(['{"a": 1}'], max_output_tokens=0)
    llm2.chat_json([{"role": "user", "content": "x"}])
    assert "max_tokens" not in llm2.calls[0]["kwargs"], llm2.calls[0]

    # 调用方显式指定时以调用方为准
    llm3 = FakeLLM(['{"a": 1}'])
    llm3.chat_json([{"role": "user", "content": "x"}], max_tokens=32000)
    assert llm3.calls[0]["kwargs"]["max_tokens"] == 32000
    print("chat-json-max-tokens OK")


def test_http_and_truncation_are_not_wrapped():
    for err in (LLMHTTPError("模型账户余额不足（402）：请充值"), LLMTruncatedError("模型输出被截断")):
        llm = FakeLLM([err])
        try:
            llm.chat_json([{"role": "user", "content": "x"}])
            raise AssertionError("应当抛出")
        except type(err) as exc:
            assert "JSON 解析失败" not in str(exc), str(exc)
        assert len(llm.calls) == 1, "这类错误不该重试：" + str(len(llm.calls))
    print("not-wrapped OK")


def test_retry_on_bad_json():
    llm = FakeLLM(["这不是 JSON", '{"ok": true}'])
    assert llm.chat_json([{"role": "user", "content": "x"}]) == {"ok": True}
    assert len(llm.calls) == 2
    # 第二次要把纠正指令带上
    second = llm.calls[1]["messages"]
    assert any("不是合法 JSON" in (m.get("content") or "") for m in second), second
    # 全部失败时仍然给出"JSON 解析失败"前缀（这类才该这么说）
    llm2 = FakeLLM(["坏", "还是坏", "依然坏"])
    try:
        llm2.chat_json([{"role": "user", "content": "x"}])
        raise AssertionError("应当报错")
    except LLMError as exc:
        assert "JSON 解析失败" in str(exc), str(exc)
    print("retry-bad-json OK")


def test_two_level_reduce():
    """段数多时先分批汇总再总汇总（避免一次输出过大被截断）。"""
    from backend.app.services import note_generator as ng

    original = ng.split_subtitles
    ng.split_subtitles = lambda subs: [subs[i:i + 5] for i in range(0, len(subs), 5)]
    try:
        subs = [{"start": i, "end": i + 1, "text": "内容"} for i in range(40)]
        llm = FakeLLM()  # 默认永远回 {"sections": []}
        ng.generate_note(subs, "general", llm, "测试视频")
        calls = len(llm.calls)
        # 8 段 → map 8 次 + 分批汇总 2 次 + 总汇总 1 次 = 11
        assert calls == 11, "调用次数 %s，说明没有走两级汇总" % calls
    finally:
        ng.split_subtitles = original
    print("two-level-reduce OK")


def test_400_max_tokens_clamps_to_provider_cap():
    """max_tokens 超过该模型上限时会 400：必须**逐次减半**重试，直到模型接受。

    为什么减半而不是降到某个固定值：默认值可以给大（让 deepseek-flash / v4-pro 写完整篇），
    只支持 8192 的 deepseek-chat 收到 400 后自动降到 8000，用户无感；
    若降到固定 8192，其它上限更低的模型仍会 400。
    """
    import httpx

    from backend.app.services.llm.openai_compat import OpenAICompatLLM

    llm = OpenAICompatLLM(base_url="http://x/v1", api_key="k", model="m")
    llm.max_output_tokens = 8192
    sent = []

    class FakeResp:
        def __init__(self, status, text):
            self.status_code = status
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("err", request=httpx.Request("POST", "http://x"), response=self)

        def json(self):
            return {"choices": [{"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}]}

    def fake_post(url, payload, headers):
        sent.append(dict(payload))
        if int(payload.get("max_tokens") or 0) > 8192:
            return FakeResp(400, '{"error":"max_tokens must be <= 8192"}')
        return FakeResp(200, "")

    llm._post = fake_post
    assert llm.chat([{"role": "user", "content": "x"}], temperature=0, max_tokens=32000) == '{"ok": 1}'
    assert sent[0]["max_tokens"] == 32000
    assert sent[1]["max_tokens"] == 16000, sent[1]          # 32000 被拒 → 减半
    assert sent[2]["max_tokens"] == 8000, sent[2]           # 16000 还被拒（>8192）→ 再减半
    print("400-clamp OK")


def test_truncation_detected_by_finish_reason():
    """finish_reason=length 必须直接报「输出被截断」，而不是让上层报 JSON 解析失败。"""
    from backend.app.services.llm.openai_compat import OpenAICompatLLM

    llm = OpenAICompatLLM(base_url="http://x/v1", api_key="k", model="m")

    class FakeResp:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"a": 1'}, "finish_reason": "length"}]}

    llm._post = lambda url, payload, headers: FakeResp()
    try:
        llm.chat([{"role": "user", "content": "x"}], temperature=0)
        raise AssertionError("应当抛出 LLMTruncatedError")
    except LLMTruncatedError as exc:
        assert "截断" in str(exc), str(exc)
    print("truncation-detected OK")


if __name__ == "__main__":
    test_extract_plain_and_fenced()
    test_extract_json_after_latex_braces()
    test_extract_truncated_hint()
    test_chat_json_injects_max_tokens()
    test_http_and_truncation_are_not_wrapped()
    test_retry_on_bad_json()
    test_two_level_reduce()
    test_400_max_tokens_clamps_to_provider_cap()
    test_truncation_detected_by_finish_reason()
    print("ALL_LLM_JSON_TESTS_PASSED")
