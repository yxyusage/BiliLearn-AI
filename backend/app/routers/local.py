"""本地视频笔记：直接读取本机视频文件转写、生成笔记，并提供带 Range 的在线播放。

与 B 站视频的区别：
- 不需要 bvid，也不需要下载，直接在原文件上做语音转写（PyAV 解码）；
- 抽帧（关键帧 / 板书公式）同样直接读原文件，不再下载视频流；
- 笔记详情页用内置播放器播放本机文件（经 /api/local/stream/{note_id} 流式返回，支持拖进度）。
"""
import hashlib
import mimetypes
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Set

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import get_db
from ..models import Note
from ..services.settings_store import resolve_llm_config
from .notes import SUBJECTS, _run_generation

router = APIRouter()

VIDEO_EXTS = {
    ".mp4", ".mkv", ".flv", ".avi", ".mov", ".wmv", ".webm", ".ts", ".m4v",
    ".mpg", ".mpeg", ".rmvb", ".rm", ".m2ts", ".3gp", ".ogv",
}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".wma", ".opus"}
ALLOWED_EXTS: Set[str] = VIDEO_EXTS | AUDIO_EXTS

# 浏览器拖拽拿不到本地路径（安全限制），拖进来的文件先落到这个缓存目录供转写与播放
UPLOAD_DIR = DATA_DIR / "cache" / "local_videos"


class LocalPathRequest(BaseModel):
    path: str = ""
    subject: str = "general"
    title: str = ""


def _clean_path(raw: str) -> Path:
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        raise HTTPException(status_code=400, detail="请先选择或粘贴本地视频路径")
    path = Path(text).expanduser()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在或不可读：" + str(path))
    if path.suffix.lower() not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail="暂不支持该格式（" + (path.suffix or "无扩展名") + "），支持常见视频与音频格式",
        )
    return path.resolve()


def _probe_duration(path: str) -> float:
    """读取视频/音频时长（秒），失败返回 0（不阻断流程）。"""
    try:
        import av
        with av.open(path) as container:
            if container.duration:
                return round(container.duration / av.time_base, 1)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


# ---------------------------------------------------------------- 系统文件选择框

def _pick_windows() -> str:
    """Windows 原生「打开文件」对话框（不切换工作目录，无 Tk 线程依赖）。"""
    import ctypes
    from ctypes import wintypes

    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [
            ("lStructSize", wintypes.DWORD),
            ("hwndOwner", wintypes.HWND),
            ("hInstance", wintypes.HINSTANCE),
            ("lpstrFilter", wintypes.LPCWSTR),
            ("lpstrCustomFilter", wintypes.LPWSTR),
            ("nMaxCustFilter", wintypes.DWORD),
            ("nFilterIndex", wintypes.DWORD),
            ("lpstrFile", wintypes.LPWSTR),
            ("nMaxFile", wintypes.DWORD),
            ("lpstrFileTitle", wintypes.LPWSTR),
            ("nMaxFileTitle", wintypes.DWORD),
            ("lpstrInitialDir", wintypes.LPCWSTR),
            ("lpstrTitle", wintypes.LPCWSTR),
            ("Flags", wintypes.DWORD),
            ("nFileOffset", wintypes.WORD),
            ("nFileExtension", wintypes.WORD),
            ("lpstrDefExt", wintypes.LPCWSTR),
            ("lCustData", wintypes.LPARAM),
            ("lpfnHook", ctypes.c_void_p),
            ("lpTemplateName", wintypes.LPCWSTR),
            ("pvReserved", ctypes.c_void_p),
            ("dwReserved", wintypes.DWORD),
            ("FlagsEx", wintypes.DWORD),
        ]

    patterns = ";".join("*" + ext for ext in sorted(ALLOWED_EXTS))
    filter_str = "视频/音频文件\0" + patterns + "\0所有文件\0*.*\0\0"
    buffer = ctypes.create_unicode_buffer(32768)
    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    try:
        ofn.hwndOwner = ctypes.windll.user32.GetForegroundWindow()
    except Exception:  # noqa: BLE001
        ofn.hwndOwner = None
    ofn.lpstrFilter = filter_str
    ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    ofn.nMaxFile = len(buffer)
    ofn.lpstrTitle = "选择本地视频/音频文件"
    OFN_FILEMUSTEXIST = 0x00001000
    OFN_PATHMUSTEXIST = 0x00000800
    OFN_EXPLORER = 0x00080000
    OFN_NOCHANGEDIR = 0x00000008
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_EXPLORER | OFN_NOCHANGEDIR
    func = ctypes.windll.comdlg32.GetOpenFileNameW
    func.argtypes = [ctypes.POINTER(OPENFILENAMEW)]
    func.restype = wintypes.BOOL
    if func(ctypes.byref(ofn)):
        return buffer.value
    return ""


def _pick_tk() -> str:
    """跨平台回退：tkinter 文件选择框。"""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:  # noqa: BLE001
        pass
    try:
        return filedialog.askopenfilename(
            title="选择本地视频/音频文件",
            filetypes=[
                ("视频/音频文件", " ".join("*" + ext for ext in sorted(ALLOWED_EXTS))),
                ("所有文件", "*.*"),
            ],
        ) or ""
    finally:
        try:
            root.destroy()
        except Exception:  # noqa: BLE001
            pass


@router.post("/pick")
def pick_file():
    """弹出系统文件选择框，返回用户选中的绝对路径（取消时 cancelled=true）。"""
    path = ""
    errors = []
    if os.name == "nt":
        try:
            path = _pick_windows()
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    if not path:
        try:
            path = _pick_tk()
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    if not path:
        if errors:
            raise HTTPException(
                status_code=500,
                detail="无法弹出系统文件选择框（" + errors[0][:120] + "），请直接在输入框粘贴文件路径",
            )
        return {"ok": False, "cancelled": True, "path": ""}
    resolved = str(Path(path).expanduser().resolve())
    return {"ok": True, "cancelled": False, "path": resolved, "name": Path(resolved).name}


@router.post("/probe")
def probe_file(req: LocalPathRequest):
    path = _clean_path(req.path)
    stat = path.stat()
    return {
        "ok": True,
        "path": str(path),
        "name": path.name,
        "size": stat.st_size,
        "ext": path.suffix.lower(),
        "duration": _probe_duration(str(path)),
    }


@router.post("/upload")
def upload_file(file: UploadFile = File(...)):
    """浏览器拖拽进来的文件：复制一份到本地缓存目录（同机上传，速度接近磁盘拷贝）。"""
    original = os.path.basename(file.filename or "video.mp4")
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="暂不支持该格式（" + (ext or "无扩展名") + "）")
    stem = re.sub(r'[^\w.\-()（）【】\[\] ]+', "_", Path(original).stem)[:80] or "video"
    size = getattr(file, "size", None)
    name = stem + (("_" + str(size)) if size else "") + ext
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / name
    if size and target.exists() and target.stat().st_size == size:
        return {"ok": True, "reused": True, "path": str(target.resolve()), "name": target.name, "size": size}
    try:
        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="文件保存失败：" + str(exc)) from exc
    finally:
        try:
            file.file.close()
        except Exception:  # noqa: BLE001
            pass
    return {
        "ok": True,
        "reused": False,
        "path": str(target.resolve()),
        "name": target.name,
        "size": target.stat().st_size,
    }


# ---------------------------------------------------------------- 生成 / 播放

@router.post("/generate")
def generate_local(req: LocalPathRequest, db: Session = Depends(get_db)):
    path = _clean_path(req.path)
    if req.subject not in SUBJECTS:
        raise HTTPException(status_code=400, detail="不支持的学科类型")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「设置」页填写")
    token = "local-" + hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]
    title = (req.title or "").strip() or path.stem
    existing = (
        db.query(Note)
        .filter(Note.bvid == token, Note.page == 1, Note.status.in_(["done", "processing"]))
        .order_by(Note.id.desc())
        .first()
    )
    if existing:
        return {"id": existing.id, "status": existing.status, "reused": True, "source": "local"}
    for old in db.query(Note).filter(
        Note.bvid == token, Note.page == 1, Note.status.in_(["failed", "pending"])
    ).all():
        db.delete(old)
    db.commit()
    note = Note(
        bvid=token,
        page=1,
        title=title,
        subject=req.subject,
        status="processing",
        source="local",
        local_path=str(path),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    threading.Thread(target=_run_generation, args=(note.id, llm_cfg), daemon=True).start()
    return {"id": note.id, "status": note.status, "reused": False, "source": "local"}


@router.get("/stream/{note_id}")
def stream_local(note_id: int, db: Session = Depends(get_db)):
    """流式返回本地视频（Starlette FileResponse 自带 Range 支持，播放器可拖进度）。"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if (note.source or "") != "local":
        raise HTTPException(status_code=400, detail="该笔记不是本地视频")
    path = Path(note.local_path or "")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="本地视频文件已被移动或删除：" + str(path))
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(str(path), media_type=media_type)


@router.get("/uploads")
def upload_stats():
    """本地视频缓存占用（浏览器拖拽上传产生的副本）。"""
    count, total = 0, 0
    if UPLOAD_DIR.exists():
        for item in UPLOAD_DIR.iterdir():
            if item.is_file():
                count += 1
                total += item.stat().st_size
    return {"count": count, "bytes": total, "dir": str(UPLOAD_DIR)}


def _referenced_paths(db: Session) -> Set[str]:
    rows = db.query(Note).filter(Note.source == "local").all()
    return {os.path.normcase(str(Path(n.local_path).resolve())) for n in rows if n.local_path}


@router.post("/uploads/cleanup")
def cleanup_uploads(db: Session = Depends(get_db)):
    """删除上传缓存中已不再被任何笔记引用的副本（不影响通过「选择文件」添加的原文件）。"""
    used = _referenced_paths(db)
    removed, freed = 0, 0
    if UPLOAD_DIR.exists():
        for item in UPLOAD_DIR.iterdir():
            if not item.is_file():
                continue
            if os.path.normcase(str(item.resolve())) in used:
                continue
            try:
                freed += item.stat().st_size
                item.unlink()
                removed += 1
            except OSError:
                pass
    return {"ok": True, "removed": removed, "freed": freed}
