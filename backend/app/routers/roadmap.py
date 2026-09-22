"""合集学习线路图：解析合集 → AI 生成模块划分/重难点标签 → 自测 → 推荐起点。"""
import json
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import RoadmapJob
from ..services import bilibili
from ..services.llm import build_llm
from ..services.settings_store import get_setting, resolve_llm_config

router = APIRouter()


class PreviewRequest(BaseModel):
    url: str

class AnalyzeRequest(BaseModel):
    url: str
    start_page: int = 1
    end_page: int = 0  # 0 = 到最后一集


class QuizRequest(BaseModel):
    count: int = 5

class RecommendRequest(BaseModel):
    answers: list  # [{page, correct: bool}]


def _subtitle_excerpt(bvid: str, page: int, cookie: str, max_seconds: int = 900) -> str:
    """取某集前 max_seconds 秒字幕，截断到 1500 字符。"""
    try:
        subs, _ = bilibili.get_subtitles(bvid, page, cookie)
    except Exception:
        return ""
    parts = []
    for item in subs:
        start = float(item.get("start", 0) or 0)
        if start > max_seconds:
            break
        parts.append(item.get("text", ""))
    text = " ".join(parts)
    return text[:1500]


def _run_analyze(job_id: int, url: str, llm_cfg: dict, cookie: str, start_page: int, end_page: int):
    db = SessionLocal()
    try:
        job = db.query(RoadmapJob).filter(RoadmapJob.id == job_id).first()
        if not job:
            return
        try:
            info = bilibili.parse_video(url, cookie)
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = "合集解析失败：" + str(exc)
            db.commit()
            return

        bvid = info.get("bvid") or ""
        pages = info.get("pages") or [{"page": 1, "title": info.get("title") or ""}]
        if start_page > 1 or end_page > 0:
            s = max(1, start_page)
            e = end_page if end_page > 0 else len(pages)
            pages = [pg for pg in pages if s <= int(pg.get("page", 0)) <= e]
        job.bvid = bvid
        job.title = info.get("title") or "合集线路图"
        job.total = len(pages)
        db.commit()

        # 逐集取字幕摘要
        episodes = []
        for i, p in enumerate(pages, start=1):
            page = int(p.get("page", i))
            title = p.get("title", "") or f"P{i}"
            excerpt = _subtitle_excerpt(bvid, page, cookie)
            episodes.append({"page": page, "title": title, "excerpt": excerpt})
            job.done_count = i
            db.commit()

        # 一次 AI 聚合：模块分组 + 标签
        llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
        ep_lines = "\n".join(
            f"P{e['page']} 《{e['title']}》 内容摘要: {e['excerpt'][:400] or '（无字幕）'}"
            for e in episodes
        )
        sys = (
            "你是教程学习路线规划师。我给你一个教程合集每一集的标题和前15分钟内容摘要。\n"
            "请完成：\n"
            "1. 按【知识模块】把集重新分组（不要按原顺序）\n"
            "2. 给每集打标签：prereq(前置必学)/core(重点)/optional(可跳过)\n"
            "3. optional 必须说明为什么可跳过；core 必须说明为什么重要\n"
            "严格输出 JSON，格式：\n"
            '{"modules":[{"name":"模块名","episodes":[{"page":1,"tag":"core","reason":"理由"}]}],'
            '"overview":"这个合集整体讲了什么，2-3句话"}'
        )
        msgs = [
            {"role": "system", "content": sys},
            {"role": "user", "content": "合集：" + (info.get("title") or "") + "\n\n" + ep_lines},
        ]
        result = llm.chat_json(msgs, temperature=0.2)
        job.result_json = json.dumps(result, ensure_ascii=False)
        job.status = "done"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job = db.query(RoadmapJob).filter(RoadmapJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(exc)
            db.commit()
    finally:
        db.close()


@router.post("/preview")
def preview(req: PreviewRequest, db: Session = Depends(get_db)):
    if not req.url:
        raise HTTPException(status_code=400, detail="请粘贴合集/视频链接")
    cookie = get_setting(db, "bili_cookie", "")
    info = bilibili.parse_video(req.url, cookie)
    return {
        "bvid": info.get("bvid"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "total": len(info.get("pages") or []),
        "pages": info.get("pages"),
    }


@router.post("/analyze")
def start_analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    if not req.url:
        raise HTTPException(status_code=400, detail="请粘贴合集/视频链接")
    llm_cfg = resolve_llm_config(db)
    if llm_cfg["provider"] != "ollama" and not llm_cfg["api_key"]:
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先到「配置」页填写")
    cookie = get_setting(db, "bili_cookie", "")
    job = RoadmapJob(url=req.url, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    threading.Thread(
        target=_run_analyze,
        args=(job.id, req.url, llm_cfg, cookie, req.start_page, req.end_page),
        daemon=True,
    ).start()
    return {"id": job.id, "status": job.status}


@router.get("/{job_id}")
def get_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(RoadmapJob).filter(RoadmapJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": job.id, "title": job.title, "status": job.status,
        "total": job.total, "done_count": job.done_count,
        "error": job.error, "result": json.loads(job.result_json or "{}"),
        "quiz": json.loads(job.quiz_json or "[]"),
        "recommend": json.loads(job.recommend_json or "{}"),
    }


@router.post("/{job_id}/quiz")
def gen_quiz(job_id: int, req: QuizRequest, db: Session = Depends(get_db)):
    job = db.query(RoadmapJob).filter(RoadmapJob.id == job_id).first()
    if not job or job.status != "done":
        raise HTTPException(status_code=400, detail="线路图未生成完成")
    llm_cfg = resolve_llm_config(db)
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    result = json.loads(job.result_json or "{}")
    overview = result.get("overview", "")
    modules = result.get("modules", [])
    mod_lines = "\n".join(
        f"- {m['name']}: " + ", ".join(e.get("title") or ("P" + str(e.get("page"))) for e in m["episodes"])
        for m in modules
    )
    count = max(3, min(20, int(req.count or 5)))
    sys = (
        "你是学习水平诊断出题人。根据教程合集的模块划分，出 " + str(count) + " 道诊断题，"
        "用来判断用户是零基础/有基础/想深入。题型为单选，4 个选项，包含正确答案和解析。\n"
        '严格输出 JSON 数组：[{"question":"题干","options":["A","B","C","D"],'
        '"answer":"A","explanation":"解析","tests":"考察的模块"}]'
    )
    msgs = [
        {"role": "system", "content": sys},
        {"role": "user", "content": "合集：" + job.title + "\n" + overview + "\n模块：\n" + mod_lines},
    ]
    quiz = llm.chat_json(msgs, temperature=0.3)
    job.quiz_json = json.dumps(quiz, ensure_ascii=False)
    db.commit()
    return {"quiz": quiz}


@router.post("/{job_id}/recommend")
def recommend(job_id: int, req: RecommendRequest, db: Session = Depends(get_db)):
    job = db.query(RoadmapJob).filter(RoadmapJob.id == job_id).first()
    if not job or job.status != "done":
        raise HTTPException(status_code=400, detail="线路图未生成完成")
    llm_cfg = resolve_llm_config(db)
    llm = build_llm(llm_cfg["provider"], llm_cfg["api_key"], llm_cfg["model"], llm_cfg["base_url"])
    result = json.loads(job.result_json or "{}")
    answered = {a["page"]: bool(a.get("correct")) for a in (req.answers or [])}
    sys = (
        "你是学习规划师。根据用户对诊断题的作答情况，推荐他从哪些集开始学、哪些集可跳过。\n"
        "作答记录：{" + json.dumps(answered, ensure_ascii=False) + "}\n"
        '严格输出 JSON：{"level":"零基础/有基础/想深入","start_from":[1,3],"skip":[5],"advice":"一句话建议"}'
    )
    msgs = [
        {"role": "system", "content": sys},
        {"role": "user", "content": "合集：" + job.title + "\n模块：" + json.dumps(result.get("modules", []), ensure_ascii=False)},
    ]
    rec = llm.chat_json(msgs, temperature=0.2)
    job.recommend_json = json.dumps(rec, ensure_ascii=False)
    db.commit()
    return {"recommend": rec}
