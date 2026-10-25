"""大模型工厂与供应商元信息。"""
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .base import BaseLLM
from .ollama import OllamaLLM
from .openai_compat import OpenAICompatLLM


def normalize_base_url(url: str) -> str:
    """把用户填的接口地址整理成能直接拼 /chat/completions 的形式。

    用户常见的三种填法都得能用：
      · https://api.siliconflow.cn        → 补成 .../v1（只填了域名）
      · https://api.siliconflow.cn/v1/    → 去掉尾斜杠
      · https://api.siliconflow.cn/v1/chat/completions → 切掉多余路径
    注意不能盲目补 /v1：商汤是 /compatible-mode/v1，one-api 可能是 /v1，
    自建网关也可能是 /openai —— 已有路径就原样尊重。
    """
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    for suffix in ("/chat/completions", "/completions"):
        if u.endswith(suffix):
            u = u[: -len(suffix)].rstrip("/")
            break
    parsed = urlparse(u)
    if not parsed.path or parsed.path == "/":
        u = u + "/v1"
    return u


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
        # 实测 deepseek-flash / deepseek-v4-pro 支持到 65536；deepseek-chat 只支持 8192。
        # 默认给 32768 让新模型写完整篇，遇到只认 8192 的模型会自动减半重试（见 openai_compat）。
        "max_output_tokens": 32768,
        # 常见模型（下拉候选；真实列表优先从 /models 拉）
        "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-flash", "deepseek-v4-pro"],
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
    # ---------------------------------------------------------------
    # 自定义 OpenAI 兼容接口：硅基流动 / 商汤 / OpenRouter / 自建 one-api 等。
    # 这类平台的差别几乎只在 base_url 和 model id，协议层一致，所以单独做成
    # 一个 provider，而不是给每个内置供应商都加一个地址输入框 ——
    # 后者会让「默认供应商」这个下拉越来越长，用户也不知道该选哪个。
    # ---------------------------------------------------------------
    "custom": {
        "name": "自定义（OpenAI 兼容）",
        "base_url": "",           # 必须由用户填写，见 requires_base_url
        "default_model": "",
        "vision_model": "",       # 由用户在设置里单独填，见 custom_vision_model
        "kind": "openai",
        "need_key": True,
        "key_url": "",
        "max_output_tokens": 8192,
        "models": [],
        "requires_base_url": True,
    },
}


# 常见国内/海外 OpenAI 兼容平台的地址预设：填错 base_url 是这类接入最高频的坑
# （少写 /v1、多写 /chat/completions、把控制台地址当接口地址）。
COMPAT_PRESETS = [
    {
        "id": "siliconflow",
        "name": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "key_url": "https://cloud.siliconflow.cn/account/ak",
        "note": "模型 id 形如 deepseek-ai/DeepSeek-V3，必须带组织名前缀",
    },
    {
        "id": "sensenova",
        "name": "商汤 SenseNova（新版）",
        "base_url": "https://token.sensenova.cn/v1",
        "key_url": "https://platform.sensenova.cn/",
        "note": "Key 以 sk- 开头，与旧版 APP_ID/SECRET 不是一套",
    },
    {
        "id": "sensenova-sc",
        "name": "商汤大装置（旧版）",
        "base_url": "https://api.sensenova.cn/compatible-mode/v1",
        "key_url": "https://console.sensecore.cn/",
        "note": "地址带 /compatible-mode，别只填 api.sensenova.cn",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_url": "https://openrouter.ai/keys",
        "note": "模型 id 形如 anthropic/claude-3.5-sonnet",
    },
    {
        "id": "oneapi",
        "name": "自建 one-api / new-api",
        "base_url": "http://127.0.0.1:3000/v1",
        "key_url": "",
        "note": "把地址和端口换成你自己的网关",
    },
]


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
        resolved_base = normalize_base_url(base_url or info["base_url"])
        if provider == "custom" and not resolved_base:
            raise ValueError("还没填「接口地址」：自定义供应商必须先填 OpenAI 兼容地址（例如 https://api.siliconflow.cn/v1）")
        if provider == "custom" and not (model or info["default_model"]):
            raise ValueError("还没填「模型名称」：自定义供应商没有默认模型，请填写接口里的准确 id")
        llm = OpenAICompatLLM(
            base_url=resolved_base,
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
