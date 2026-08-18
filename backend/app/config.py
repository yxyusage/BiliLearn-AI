"""应用配置。密钥优先从本地 SQLite 读取，其次回退到环境变量。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="BILI_",
        extra="ignore",
    )

    app_name: str = "BiliLearn-AI"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = f"sqlite:///{DATA_DIR / 'bililearn.db'}"

    # 默认模型配置（可在网页配置页覆盖，密钥仅存本地）
    default_provider: str = "deepseek"
    deepseek_api_key: str = ""
    kimi_api_key: str = ""
    qwen_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # 长字幕分段的最大字符数（应对上下文窗口限制）
    subtitle_chunk_chars: int = 6000
    # 是否启用无字幕时的本地离线语音转写
    enable_whisper: bool = False
    whisper_model: str = "base"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
