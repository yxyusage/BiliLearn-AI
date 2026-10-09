"""数据目录管理与学习存档导入 / 导出。

笔记数据独立存放在用户主目录下的 `~/BiliLearn-AI`（可用环境变量 BILI_DATA_DIR 覆盖），
升级或重新下载新版本都不会丢；这里提供目录信息、打开目录、导出存档与合并导入。
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from ..config import DATA_DIR, DB_PATH, LEGACY_DATA_DIR
from ..database import get_db
from ..models import Note
from ..services import data_migrate

router = APIRouter()

ALLOWED_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".zip")


def _dir_stats(path: Path, limit: int = 200000) -> dict:
    """统计目录大小与文件数（有上限，避免超大目录卡住设置页）。"""
    size = 0
    count = 0
    if path.is_dir():
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    size += item.stat().st_size
                except OSError:
                    continue
                count += 1
                if count >= limit:
                    break
    return {"bytes": size, "files": count}


@router.get("/info")
def data_info(db: Session = Depends(get_db)):
    legacy_db = LEGACY_DATA_DIR / "bililearn.db"
    notes_stats = _dir_stats(DATA_DIR / "notes")
    return {
        "data_dir": str(DATA_DIR),
        "db_path": str(DB_PATH),
        "db_size": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        "notes_dir": str(DATA_DIR / "notes"),
        "notes_bytes": notes_stats["bytes"],
        "notes_files": notes_stats["files"],
        "note_count": db.query(Note).count(),
        "legacy_dir": str(LEGACY_DATA_DIR),
        "legacy_present": DATA_DIR != LEGACY_DATA_DIR and legacy_db.exists(),
        "env_override": bool((os.environ.get("BILI_DATA_DIR") or "").strip()),
    }


@router.post("/open")
def open_data_dir():
    """在系统文件管理器里打开数据目录（方便备份 / 手动放存档）。"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(DATA_DIR))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(DATA_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(DATA_DIR)])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="无法打开数据目录：" + str(exc)) from exc
    return {"ok": True, "data_dir": str(DATA_DIR)}


@router.get("/export")
def export_archive():
    """导出学习存档 zip：数据库快照 + Markdown 笔记 + 关键帧截图。"""
    try:
        archive, tmp_dir = data_migrate.export_archive()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="导出失败：" + str(exc)) from exc
    return FileResponse(
        str(archive),
        media_type="application/zip",
        filename=archive.name,
        background=BackgroundTask(shutil.rmtree, str(tmp_dir), True),
    )


@router.post("/import")
def import_archive(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """合并导入：把另一个 bililearn.db / 学习存档 zip 的内容加到本地（同视频跳过）。"""
    name = os.path.basename(file.filename or "bililearn.db")
    if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="只支持 .db 或本工具导出的 .zip 存档")
    tmp_dir = Path(tempfile.mkdtemp(prefix="bililearn-import-"))
    target = tmp_dir / name
    try:
        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="文件保存失败：" + str(exc)) from exc
    finally:
        try:
            file.file.close()
        except Exception:  # noqa: BLE001
            pass
    try:
        summary = data_migrate.import_from_upload(target, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail="导入失败：" + str(exc)) from exc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return summary
