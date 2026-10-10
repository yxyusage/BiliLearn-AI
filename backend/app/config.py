"""应用配置。密钥优先从本地 SQLite 读取，其次回退到环境变量。

数据目录（数据库 / Markdown 笔记 / 关键帧截图）默认放在用户主目录下的
`~/BiliLearn-AI`，与程序目录分离：升级或重新下载新版本都不会丢笔记。
可用环境变量 `BILI_DATA_DIR` 覆盖。
"""
import os
import shutil
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
LEGACY_DATA_DIR = BASE_DIR / "data"                # v1.7 及以前的程序内数据目录


def _env_data_dir() -> str:
    return (os.environ.get("BILI_DATA_DIR") or "").strip()


def _default_data_dir() -> Path:
    return Path.home() / "BiliLearn-AI"


def _migrate_legacy_data(target: Path) -> bool:
    """把旧版本 backend/data 里的数据搬到新目录（只搬一次，搬不动的保留原地）。"""
    legacy_db = LEGACY_DATA_DIR / "bililearn.db"
    if not legacy_db.exists() or (target / "bililearn.db").exists():
        return False
    target.mkdir(parents=True, exist_ok=True)
    moved = []
    for entry in sorted(LEGACY_DATA_DIR.iterdir()):
        if entry.name == "数据已迁移.txt":
            continue
        dest = target / entry.name
        if dest.exists():
            continue
        try:
            shutil.move(str(entry), str(dest))
            moved.append(entry.name)
        except Exception:  # noqa: BLE001  搬迁失败时保留原地数据，绝不丢文件
            continue
    if moved:
        try:
            (LEGACY_DATA_DIR / "数据已迁移.txt").write_text(
                "笔记数据已迁移到新目录，请勿再使用本目录：\n" + str(target) + "\n"
                "已迁移：" + "、".join(moved) + "\n",
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass
    return (target / "bililearn.db").exists()


def _resolve_data_dir() -> Path:
    env_dir = _env_data_dir()
    if env_dir:
        # 用户显式指定目录时不做自动迁移，避免动到别人的数据
        return Path(env_dir).expanduser()
    target = _default_data_dir()
    if not (target / "bililearn.db").exists() and (LEGACY_DATA_DIR / "bililearn.db").exists():
        if not _migrate_legacy_data(target):
            # 迁移失败则继续使用旧目录，保证数据仍然可见
            return LEGACY_DATA_DIR
    return target


DATA_DIR = _resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "bililearn.db"
LEGACY_DATA_PRESENT = (LEGACY_DATA_DIR / "bililearn.db").exists() and DATA_DIR != LEGACY_DATA_DIR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="BILI_",
        extra="ignore",
    )

    app_name: str = "BiliLearn-AI"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "sqlite:///" + str(DB_PATH)

    # 默认模型配置（可在网页配置页覆盖，密钥仅存本地）
    default_provider: str = "deepseek"
    deepseek_api_key: str = ""
    kimi_api_key: str = ""
    qwen_api_key: str = ""
    openai_api_key: str = ""
    # 可选：覆盖默认模型名与接口地址（如启动器注入 BILI_DEEPSEEK_MODEL / BILI_DEEPSEEK_BASE_URL）
    deepseek_model: str = ""
    deepseek_base_url: str = ""
    openai_model: str = ""
    openai_base_url: str = ""
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
