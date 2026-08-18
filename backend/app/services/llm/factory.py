"""大模型工厂与供应商元信息。"""
from typing import Any, Dict, Optional

from .base import BaseLLM
from .ollama import OllamaLLM
from .openai_compat import OpenAICompatLLM

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "kind": "openai",
        "need_key": True,
        "key_url": "https://platform.deepseek.com/api_keys",
    },
    "kimi": {
        "name": "Kimi (Moonshot)",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-32k",
        "kind": "openai",
        "need_key": True,
        "key_url": "https://platform.moonshot.cn/console/api-keys",
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "kind": "openai",
        "need_key": True,
        "key_url": "https://bailian.console.aliyun.com/?apiKey=1",
    },
    "ollama": {
        "name": "Ollama 本地模型",
        "base_url": "http://localhost:11434",
        "default_model": "qwen2.5:7b",
        "kind": "ollama",
        "need_key": False,
        "key_url": "https://ollama.com/download",
    },
}


# 支持视觉输入的模型（按供应商）
VISION_MODELS = {
    "qwen": "qwen-vl-plus",
    "kimi": "moonshot-v1-8k-vision-preview",
}


def build_llm(
    provider: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> BaseLLM:
    if provider not in PROVIDERS:
        raise ValueError("不支持的模型供应商: " + str(provider))
    info = PROVIDERS[provider]
    if info["kind"] == "ollama":
        return OllamaLLM(base_url=base_url or info["base_url"], model=model or info["default_model"])
    return OpenAICompatLLM(
        base_url=base_url or info["base_url"],
        api_key=api_key or "",
        model=model or info["default_model"],
    )
