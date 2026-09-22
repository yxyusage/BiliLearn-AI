"""B站收藏夹导入：解析收藏夹视频列表，支持选择性批量生成笔记。"""
import re
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import CollectionJob, Note
from ..services import bilibili
from ..services.settings_store import get_setting, resolve_llm_config

router = APIRouter()


class FavParseRequest(BaseModel):
    url: str


class FavItem(BaseModel):
    bvid: str
    title: str
    uploader: str = ""
    is_collection: bool = False
    page_count: int = 1
    selected: bool = True


class FavStartRequest(BaseModel):
    items: list  # [{bvid, title, is_collection, start_page, end_page}]
    subject: str = "general"


def _extract_fav_id(url: str) -> str:
    """从收藏夹链接提取 media_id (fid)。"""
    m = re.search(r"[?&]fid=(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"ml(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/favlist\?.*?media_id=(\d+)", url)
    if m:
        return m.group(1)
    return ""


@router.post("/parse")
def parse_favorites(req: FavParseRequest, db: Session = Depends(get_db)):
    if not req.url:
        raise HTTPException(status_code=400, detail="请粘贴收藏夹链接")
    fid = _extract_fav_id(req.url)
    if not fid:
        raise HTTPException(status_code=400, detail="无法识别收藏夹 ID，链接格式如 https://space.bilibili.com/123/favlist?fid=456")
    cookie = get_setting(db, "bili_cookie", "")
    import httpx
    items = []
    pn = 1
    while True:
        try:
            r = httpx.get(
                "https://api.bilibili.com/x/v3/fav/resource/list",
                params={"media_id": fid, "pn": pn, "ps": 20, "platform": "web"},
                headers=bilibili._make_headers(cookie),
                timeout=15,
                trust_env=False,
            )
            data = r.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="收藏夹解析失败：" + str(exc)) from exc
        if data.get("code") != 0:
            raise HTTPException(status_code=400, detail="收藏夹解析失败：" + str(data.get("message", "未知错误")))
        medias = (data.get("data") or {}).get("medias") or []
        if not medias:
            break
        for m in medias:
            bvid = m.get("bvid") or ""
            if not bvid:
                continue
            attr = int(m.get("attr") or 0)
            is_coll = bool(attr & 1)
            items.append({
                "bvid": bvid,
                "title": m.get("title") or "",
                "uploader": (m.get("upper") or {}).get("name") or "",
                "is_collection": is_coll,
                "page_count": 1,
                "selected": True,
            })
        if not (data.get("data") or {}).get("has_more"):
            break
        pn += 1
        if pn > 20:
            break
    return {"fid": fid, "total": len(items), "items": items}





@router.post("/start")
def start_favorites(req: FavStartRequest, db: Session = Depends(get_db)):
    from .collections import _run_job as _run_collection_job
    from .notes import _run_generation
    if not req.items:
        raise HTTPException(status_code=400, detail="请先选择要生成的视频")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key")
    cookie = get_setting(db, "bili_cookie", "")
    try:
        concurrency = max(1, min(4, int(get_setting(db, "collection_concurrency", "2") or "2")))
    except ValueError:
        concurrency = 2
    note_ids = []
    collection_job_ids = []
    for item in req.items:
        bvid = item.get("bvid")
        if not bvid:
            continue
        title = item.get("title") or ""
        if item.get("is_collection"):
            try:
                info = bilibili.parse_video("https://www.bilibili.com/video/" + bvid, cookie)
                pages = info.get("pages") or [{"page": 1, "title": title}]
                s = max(1, int(item.get("start_page") or 1))
                e = int(item.get("end_page") or 0)
                if e > 0:
                    pages = [pg for pg in pages if s <= int(pg.get("page", 0)) <= e]
                course_title = info.get("title") or title
            except Exception:
                pages = [{"page": 1, "title": title}]
                course_title = title
            job = CollectionJob(
                bvid=bvid, title=course_title, subject=req.subject,
                status="running", total=len(pages),
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            threading.Thread(
                target=_run_collection_job,
                args=(job.id, llm_cfg, pages, bvid, course_title, req.subject, concurrency),
                daemon=True,
            ).start()
            collection_job_ids.append(job.id)
        else:
            existing = db.query(Note).filter(Note.bvid == bvid, Note.page == 1, Note.status == "done").first()
            if existing:
                note_ids.append(existing.id)
                continue
            note = Note(bvid=bvid, page=1, title=title, subject=req.subject, status="running")
            db.add(note)
            db.commit()
            db.refresh(note)
            threading.Thread(target=_run_generation, args=(note.id, llm_cfg), daemon=True).start()
            note_ids.append(note.id)
    return {
        "note_ids": note_ids,
        "collection_job_ids": collection_job_ids,
        "collection_count": len(collection_job_ids),
        "note_count": len(note_ids),
    }
