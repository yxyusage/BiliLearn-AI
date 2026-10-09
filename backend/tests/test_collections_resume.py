"""回归测试：合集「继续生成未完成的集数」后，之前成功的各集结果必须保留。

背景：_run_job 以前从空的 results 开始累积，续跑时会把 result_json 里已有的
旧成功记录整体覆盖掉，前端「各集处理结果」就只剩本次生成的集数。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app import models  # noqa: F401  导入以注册表结构
from backend.app.database import Base, SessionLocal, engine, run_migrations
from backend.app.models import CollectionJob
from backend.app.routers import collections as C

# CI 环境没有现成数据库，这里自行建表，保证测试可以独立运行
Base.metadata.create_all(bind=engine)
run_migrations()


def _fake_process(p, job_id, llm_cfg, bvid, course_title, subject):
    """打桩：不真正生成笔记，直接返回成功。"""
    page = p["page"]
    return {"page": page, "note_id": 900 + page, "status": "done", "title": "P" + str(page), "error": ""}


def test_resume_keeps_previous_results():
    db = SessionLocal()
    job = CollectionJob(
        bvid="TESTBV_RESUME",
        title="续跑回归测试",
        subject="general",
        status="paused",
        total=3,
        done_count=1,
        failed_count=0,
        result_json=json.dumps(
            [{"page": 1, "note_id": 901, "status": "done", "title": "P1", "error": ""}],
            ensure_ascii=False,
        ),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    original = C._process_episode
    C._process_episode = _fake_process
    try:
        C._run_job(
            job_id,
            {"provider": "deepseek", "api_key": "x", "model": "m", "base_url": ""},
            [{"page": 2, "title": "P2"}, {"page": 3, "title": "P3"}],
            "TESTBV_RESUME",
            "课程",
            "general",
            2,
        )
    finally:
        C._process_episode = original

    db = SessionLocal()
    try:
        saved = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
        pages = sorted(r["page"] for r in json.loads(saved.result_json))
        assert pages == [1, 2, 3], "续跑后旧的成功结果丢失：" + str(pages)
        assert saved.done_count == 3, "done_count 不正确：" + str(saved.done_count)
        assert saved.status == "done", "任务状态不正确：" + str(saved.status)
        db.delete(saved)
        db.commit()
    finally:
        db.close()
    print("collections resume OK")


if __name__ == "__main__":
    test_resume_keeps_previous_results()
    print("ALL_COLLECTION_TESTS_PASSED")
