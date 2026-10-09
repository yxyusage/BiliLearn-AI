"""笔记文件的落盘路径：Markdown 与关键帧截图目录。

路由层与数据导入/导出共用这一份逻辑，避免路径规则出现两份实现。
"""
import re
import shutil
import traceback
from pathlib import Path

from ..config import DATA_DIR

# 关键帧与公式截图分目录存放，避免同名文件互相覆盖
FRAME_KINDS = ("keyframes", "formulas", "frames")


def notes_dir() -> Path:
    path = DATA_DIR / "notes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def frames_root(note_id: int) -> Path:
    return DATA_DIR / "notes"


def safe_title(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|\r\n]+', "_", title or "").strip("_") or "note"


def markdown_path(note_id: int, title: str) -> Path:
    return notes_dir() / (str(note_id).zfill(4) + "_" + safe_title(title)[:60] + ".md")


def save_markdown_file(note_id: int, title: str, markdown: str) -> str:
    path = markdown_path(note_id, title)
    path.write_text(markdown, encoding="utf-8")
    return str(path)


def frames_dir(note_id: int, kind: str) -> Path:
    return DATA_DIR / "notes" / (str(note_id) + "_" + kind)


def cleanup_note_files(note_id: int, title: str) -> None:
    """删除笔记时同步清理本地 Markdown 与抽帧目录。"""
    try:
        md = markdown_path(note_id, title)
        if md.exists():
            md.unlink()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
    for kind in FRAME_KINDS:
        folder = frames_dir(note_id, kind)
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
