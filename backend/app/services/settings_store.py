"""模型配置存取：数据库优先，回退环境变量。密钥仅保存在本地。"""
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings as env_settings
from ..models import Setting
from .llm import PROVIDERS


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row and row.value:
        return row.value
    val = getattr(env_settings, key, "")
    return val or default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def whisper_enabled(db: Session) -> bool:
    val = get_setting(db, "enable_whisper", "")
    return str(val).strip().lower() in ("1", "true", "on", "yes")


def resolve_llm_config(
    db: Session,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    provider = provider or get_setting(db, "provider", "deepseek")
    if provider not in PROVIDERS:
        provider = "deepseek"
    if provider == "ollama":
        return {
            "provider": provider,
            "api_key": "",
            "model": model or get_setting(db, "ollama_model", PROVIDERS["ollama"]["default_model"]),
            "base_url": base_url or get_setting(db, "ollama_base_url", PROVIDERS["ollama"]["base_url"]),
        }
    return {
        "provider": provider,
        "api_key": api_key or get_setting(db, provider + "_api_key", ""),
        "model": model or get_setting(db, provider + "_model", PROVIDERS[provider]["default_model"]),
        "base_url": base_url or PROVIDERS[provider]["base_url"],
    }
