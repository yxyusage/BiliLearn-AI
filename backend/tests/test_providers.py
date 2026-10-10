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
from backend.app.services.llm.factory import VISION_MODELS


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


def test_build_llm_openai():
    llm = build_llm("openai", "sk-test")
    assert llm.base_url == "https://api.openai.com/v1"
    assert llm.model == "gpt-4o-mini"
    assert build_llm("openai", "sk-test", "gpt-4o").model == "gpt-4o"
    assert build_llm("openai", "sk-test", None, "https://my-proxy/v1").base_url == "https://my-proxy/v1"
    print("build-llm-openai OK")


if __name__ == "__main__":
    test_openai_provider_registered()
    test_keys_cover_all_providers()
    test_vision_models()
    test_build_llm_openai()
    print("ALL_PROVIDER_TESTS_PASSED")
