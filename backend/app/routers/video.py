"""视频解析与字幕获取接口。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SubtitleCache
from ..schemas import ParseRequest
from ..services import bilibili
from ..services.settings_store import get_setting, whisper_enabled

router = APIRouter()


@router.post("/parse")
def parse_video(req: ParseRequest, db: Session = Depends(get_db)):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="请输入视频链接")
    cookie = get_setting(db, "bili_cookie", "")
    try:
        info = bilibili.parse_video(req.url, cookie)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="视频解析失败：" + str(exc)) from exc
    bvid = info["bvid"]
    page = info["pages"][0]["page"] if info["pages"] else 1
    key = bvid + "_" + str(page)
    cache = db.query(SubtitleCache).filter(SubtitleCache.key == key).first()
    subtitles, source = [], ""
    if cache:
        try:
            subtitles = json.loads(cache.subtitles)
            source = "缓存字幕"
        except Exception:
            subtitles = []
    else:
        try:
            subtitles, source = bilibili.get_subtitles(bvid, page, cookie)
        except Exception as exc:  # noqa: BLE001
            source = "字幕获取失败：" + str(exc)
        if subtitles:
            db.add(SubtitleCache(
                key=key,
                video_title=info["title"],
                subtitles=json.dumps(subtitles, ensure_ascii=False),
            ))
            db.commit()
    subtitle_available = bool(subtitles)
    whisper_on = whisper_enabled(db)
    hint = ""
    if not subtitle_available and not whisper_on:
        hint = "未获取到官方字幕。可在「配置」页开启本地语音转写后重试（需安装 ffmpeg 与 faster-whisper）。"
    return {
        "bvid": bvid,
        "title": info["title"],
        "uploader": info["uploader"],
        "pages": info["pages"],
        "subtitle_available": subtitle_available,
        "subtitle_source": source,
        "subtitle_count": len(subtitles),
        "subtitles": subtitles[:300],
        "whisper_enabled": whisper_on,
        "hint": hint,
    }
