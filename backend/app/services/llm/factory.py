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
        # 公式/板书识别用的视觉模型（此前这里为空，导致前端默认选中的
        # "DeepSeek Flash（视觉，推荐）" 必然报「所选供应商不支持视觉模型」）
        "vision_model": "deepseek-flash",
        "kind": "openai",
        "need_key": True,
        "key_url": "https://platform.deepseek.com/api_keys",
        # 单次回复输出上限（DeepSeek 官方上限 8192）。不设的话默认只有 4096，
        # 长视频汇总整篇笔记 JSON 时会被截断成半截，表现为"未找到合法 JSON"。
        "max_output_tokens": 8192,
        # 常见模型（下拉候选；真实列表优先从 /models 拉）
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "kimi": {
        "name": "Kimi (Moonshot)",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k2.6",
        "vision_model": "kimi-k2.6",
        "kind": "openai",
        "need_key": True,
        "key_url": "https://platform.moonshot.cn/console/api-keys",
        "max_output_tokens": 8192,
        "models": ["kimi-k2.6", "kimi-k2", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "vision_model": "qwen-vl-max-latest",
        "kind": "openai",
        "need_key": True,
        "key_url": "https://bailian.console.aliyun.com/?apiKey=1",
        "max_output_tokens": 8192,
        "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-long", "qwen-vl-max-latest"],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        # 板书/公式截图识别用视觉模型（gpt-4o 系列都支持图片输入）
        "vision_model": "gpt-4o",
        "kind": "openai",
        "need_key": True,
        "key_url": "https://platform.openai.com/api-keys",
        "max_output_tokens": 8192,
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini"],
    },
    "ollama": {
        "name": "Ollama 本地模型",
        "base_url": "http://localhost:11434",
        "default_model": "qwen2.5:7b",
        "vision_model": "",
        "kind": "ollama",
        "need_key": False,
        "key_url": "https://ollama.com/download",
        # Ollama 用 num_predict 控制输出，这里不注入 max_tokens（由用户在本机模型侧调）
        "max_output_tokens": 0,
        # 本机模型由 Ollama 自己管理，列表从它的 /api/tags 拉
        "models": [],
    },
}


# 支持视觉输入的模型（按供应商），用于板书/公式截图识别
VISION_MODELS = {p: info.get("vision_model", "") for p, info in PROVIDERS.items() if info.get("vision_model")}


def build_llm(
    provider: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> BaseLLM:
    if provider not in PROVIDERS:
        raise ValueError("不支持的模型供应商: " + str(provider))
    info = PROVIDERS[provider]
    if info["kind"] == "ollama":
        llm = OllamaLLM(base_url=base_url or info["base_url"], model=model or info["default_model"])
    else:
        llm = OpenAICompatLLM(
            base_url=base_url or info["base_url"],
            api_key=api_key or "",
            model=model or info["default_model"],
        )
    # 供 chat_json 自动带上 max_tokens：不设就等着被截断（见 base.chat_json）。
    # 用户可在设置里改 llm_max_tokens（0 = 按供应商默认）——
    # 换到输出上限更大的模型（如 32k）时必须能把这个数字一起放大，否则照样被截断。
    cap = int(info.get("max_output_tokens") or 0)
    try:
        user_cap = int(max_tokens or 0)
    except (TypeError, ValueError):
        user_cap = 0
    if user_cap > 0:
        cap = user_cap
    llm.max_output_tokens = cap
    return llm
