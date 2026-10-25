"""供应商配置回归测试（离线，不联网）：

1. OpenAI 已注册为供应商（接口地址 / 默认模型 / 视觉模型 / 是否需要 Key）；
2. 配置白名单与供应商列表保持一致 —— 以后再加供应商不会漏改白名单，
   否则网页上填的 Key 会存不进去；
3. 视觉模型表覆盖 DeepSeek 与 OpenAI（前端「提取板书公式」默认选中的就是 DeepSeek，
   它的 vision_model 若为空，这个功能必然直接报 400）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.routers.config import _KEYS, _KEY_PROVIDERS
from backend.app.services.llm import PROVIDERS, build_llm
from backend.app.services.llm.factory import VISION_MODELS, normalize_base_url


def test_openai_provider_registered():
    assert "openai" in PROVIDERS, list(PROVIDERS)
    info = PROVIDERS["openai"]
    assert info["base_url"] == "https://api.openai.com/v1"
    assert info["default_model"] == "gpt-4o-mini"
    assert info["vision_model"] == "gpt-4o"
    assert info["kind"] == "openai"
    assert info["need_key"] is True
    assert info["key_url"].startswith("https://platform.openai.com")
    print("openai-provider OK")


def test_keys_cover_all_providers():
    for p in PROVIDERS:
        assert p + "_model" in _KEYS, p + "_model 不在配置白名单里"
        if PROVIDERS[p].get("need_key"):
            assert p + "_api_key" in _KEYS, p + "_api_key 不在配置白名单里"
    assert set(_KEY_PROVIDERS) == {p for p, i in PROVIDERS.items() if i.get("need_key")}
    print("keys-cover-providers OK", list(PROVIDERS))


def test_vision_models():
    assert VISION_MODELS.get("deepseek") == "deepseek-flash", "DeepSeek 视觉模型缺失"
    assert VISION_MODELS.get("openai") == "gpt-4o"
    for p in ("kimi", "qwen"):
        assert VISION_MODELS.get(p), p + " 缺少视觉模型"
    print("vision-models OK", VISION_MODELS)


def test_max_tokens_override():
    """输出上限必须能按用户设置放大。

    换了输出更大的模型（如 32k）却还按供应商默认 8192 送请求，长视频的汇总照样被截断 ——
    所以 build_llm 要支持 max_tokens 覆盖，且 llm_max_tokens 要在配置白名单里。
    """
    assert "llm_max_tokens" in _KEYS, "配置白名单里没有 llm_max_tokens，网页上填了也存不进去"
    # DeepSeek 默认给 32768（flash / v4-pro 支持到 65536；chat 只支持 8192，会自动减半重试）
    assert build_llm("deepseek", "k").max_output_tokens == 32768
    assert build_llm("deepseek", "k", None, None, 65536).max_output_tokens == 65536
    # 非法值忽略，回落到供应商默认
    assert build_llm("deepseek", "k", None, None, 0).max_output_tokens == 32768
    assert build_llm("deepseek", "k", None, None, None).max_output_tokens == 32768
    print("max-tokens-override OK")


def test_build_llm_openai():
    llm = build_llm("openai", "sk-test")
    assert llm.base_url == "https://api.openai.com/v1"
    assert llm.model == "gpt-4o-mini"
    assert build_llm("openai", "sk-test", "gpt-4o").model == "gpt-4o"
    assert build_llm("openai", "sk-test", None, "https://my-proxy/v1").base_url == "https://my-proxy/v1"
    print("build-llm-openai OK")


def test_custom_provider():
    """自定义 OpenAI 兼容接口（硅基流动 / 商汤 / OpenRouter / one-api）。

    这类接入最高频的坑是 base_url 写法：少写 /v1、多写 /chat/completions、
    把控制台地址当接口地址。normalize_base_url 必须把这几种都收敛掉，
    否则用户会在生成笔记时才看到 404，却不知道是地址填错了。
    """
    assert "custom" in PROVIDERS, list(PROVIDERS)
    info = PROVIDERS["custom"]
    assert info["requires_base_url"] is True
    assert info["kind"] == "openai"
    # 地址必须能通过 /config/set 写进去，否则前端填了也白填
    assert "custom_base_url" in _KEYS, "custom_base_url 不在配置白名单里"
    assert "custom_vision_model" in _KEYS, "custom_vision_model 不在配置白名单里"

    assert normalize_base_url("https://api.siliconflow.cn") == "https://api.siliconflow.cn/v1"
    assert normalize_base_url("https://api.siliconflow.cn/v1/") == "https://api.siliconflow.cn/v1"
    assert (
        normalize_base_url("https://api.sensenova.cn/compatible-mode/v1")
        == "https://api.sensenova.cn/compatible-mode/v1"
    )
    assert normalize_base_url("https://token.sensenova.cn/v1") == "https://token.sensenova.cn/v1"
    assert normalize_base_url("https://x.com/v1/chat/completions") == "https://x.com/v1"
    assert normalize_base_url("  ") == ""

    llm = build_llm("custom", "sk-x", "deepseek-ai/DeepSeek-V3", "https://api.siliconflow.cn")
    assert llm.base_url == "https://api.siliconflow.cn/v1"
    assert llm.model == "deepseek-ai/DeepSeek-V3"

    # 缺地址 / 缺模型时报人话，而不是拼出一个能发出请求的坏 URL
    for kwargs, keyword in (
        ({"model": "m", "base_url": ""}, "接口地址"),
        ({"model": "", "base_url": "https://api.siliconflow.cn/v1"}, "模型名称"),
    ):
        try:
            build_llm("custom", "sk-x", **kwargs)
        except ValueError as exc:
            assert keyword in str(exc), str(exc)
        else:
            raise AssertionError("缺参数时应该直接报错：" + str(kwargs))
    print("custom-provider OK")


if __name__ == "__main__":
    test_openai_provider_registered()
    test_keys_cover_all_providers()
    test_vision_models()
    test_max_tokens_override()
    test_build_llm_openai()
    test_custom_provider()
    print("ALL_PROVIDER_TESTS_PASSED")
