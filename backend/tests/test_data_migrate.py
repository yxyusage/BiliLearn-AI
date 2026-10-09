"""数据导入/导出回归测试：合并导入要能补新笔记，且重复导入不产生重复。

覆盖点：
1. 导入一个新笔记 → notes_added = 1，并带上错题/复习计划/合集任务；
2. 再导入同一份数据 → 全部跳过，不再新增；
3. 同一 BV + 同一分 P 不会被重复导入。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models  # noqa: F401  导入以注册表结构
from backend.app.database import Base, SessionLocal, engine, run_migrations
from backend.app.models import CollectionJob, Note
from backend.app.services import data_migrate, storage

TEST_BVID = "BVTESTMIGRATE1"


def _make_source_db(path: Path) -> None:
    """构造一个来源库（结构与当前版本一致，含 1 篇笔记 + 关联记录）。"""
    src_engine = create_engine("sqlite:///" + str(path))
    Base.metadata.create_all(bind=src_engine)
    Session = sessionmaker(bind=src_engine, future=True)
    session = Session()
    try:
        note = Note(
            bvid=TEST_BVID,
            page=1,
            title="导入测试笔记",
            subject="general",
            status="done",
            summary="摘要",
            note_json='{"title": "导入测试笔记", "summary": "摘要", "chapters": []}',
            markdown="# 导入测试笔记",
        )
        session.add(note)
        session.flush()
        job = CollectionJob(
            bvid=TEST_BVID, title="导入测试合集", subject="general", status="done",
            total=1, done_count=1, failed_count=0,
            result_json='[{"page": 1, "note_id": %d, "status": "done", "title": "导入测试笔记", "error": ""}]' % note.id,
        )
        session.add(job)
        session.flush()
        note.batch_id = job.id
        session.add(models.WrongAnswer(
            note_id=note.id, subject="general", qtype="single", question="导入测试题",
            user_answer="A", correct_answer="B", explanation="解析", status="active", wrong_count=1,
        ))
        session.add(models.ReviewPlan(note_id=note.id, content="复习导入测试", due_date="2026-01-01"))
        session.add(models.RoadmapJob(bvid=TEST_BVID, title="导入测试线路图", status="done"))
        session.commit()
    finally:
        session.close()
        src_engine.dispose()


def _cleanup():
    db = SessionLocal()
    try:
        for note in db.query(Note).filter(Note.bvid == TEST_BVID).all():
            storage.cleanup_note_files(note.id, note.title)
            db.delete(note)
        db.query(models.WrongAnswer).filter(models.WrongAnswer.question == "导入测试题").delete(synchronize_session=False)
        db.query(models.ReviewPlan).filter(models.ReviewPlan.content == "复习导入测试").delete(synchronize_session=False)
        for job in db.query(CollectionJob).filter(CollectionJob.bvid == TEST_BVID).all():
            db.delete(job)
        for job in db.query(models.RoadmapJob).filter(models.RoadmapJob.bvid == TEST_BVID).all():
            db.delete(job)
        db.commit()
    finally:
        db.close()


def test_import_merge_and_dedupe():
    Base.metadata.create_all(bind=engine)
    run_migrations()
    _cleanup()

    src_dir = Path(__file__).resolve().parent / "_tmp_migrate"
    src_dir.mkdir(exist_ok=True)
    src_db = src_dir / "source.db"
    if src_db.exists():
        src_db.unlink()
    _make_source_db(src_db)

    db = SessionLocal()
    try:
        first = data_migrate.import_database(src_db, db, notes_src_dir=None)
        assert first["notes_added"] == 1, first
        assert first["wrong_added"] == 1, first
        assert first["plans_added"] == 1, first
        assert first["collections_added"] == 1, first
        assert first["roadmaps_added"] == 1, first
        # Markdown 应当按新笔记 id 重新落盘
        note = db.query(Note).filter(Note.bvid == TEST_BVID).first()
        assert note is not None
        assert storage.markdown_path(note.id, note.title).exists(), "Markdown 未落盘"

        second = data_migrate.import_database(src_db, db, notes_src_dir=None)
        assert second["notes_added"] == 0, second
        assert second["notes_skipped"] == 1, second
        assert second["collections_added"] == 0, second
        assert second["roadmaps_added"] == 0, second
        assert db.query(Note).filter(Note.bvid == TEST_BVID).count() == 1
    finally:
        db.close()
        _cleanup()
        try:
            src_db.unlink()
            src_dir.rmdir()
        except OSError:
            pass
    print("data migrate OK")


if __name__ == "__main__":
    test_import_merge_and_dedupe()
    print("ALL_DATA_MIGRATE_TESTS_PASSED")
