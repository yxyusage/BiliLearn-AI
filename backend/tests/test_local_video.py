"""本地视频笔记：路径校验与音频时长探测的离线测试（不依赖网络与大模型）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import HTTPException

from backend.app.routers.local import ALLOWED_EXTS, _clean_path, _probe_duration


def test_allowed_extensions():
    for ext in (".mp4", ".mkv", ".flv", ".m4a", ".mp3"):
        assert ext in ALLOWED_EXTS
    assert ".txt" not in ALLOWED_EXTS
    print("allowed-exts OK")


def test_clean_path_rejects():
    cases = [
        ("", 400),          # 空路径
        ("   ", 400),
        ("E:/definitely-not-here-9f3a.mp4", 404),   # 文件不存在
    ]
    for raw, code in cases:
        try:
            _clean_path(raw)
            raise AssertionError("应当被拒绝：" + repr(raw))
        except HTTPException as exc:
            assert exc.status_code == code, (raw, exc.status_code)
    # 存在的文件但扩展名不支持
    try:
        _clean_path(str(Path(__file__).resolve()))
        raise AssertionError("应当拒绝不支持的扩展名")
    except HTTPException as exc:
        assert exc.status_code == 400
    print("clean-path OK")


def test_probe_duration_missing_file():
    # 探测失败时返回 0，不抛异常（不阻断后续流程）
    assert _probe_duration("E:/definitely-not-here-9f3a.mp4") == 0.0
    print("probe-duration OK")


def test_cleanup_keeps_referenced_files():
    """清理缓存副本时必须保留仍被笔记引用的文件。"""
    from backend.app import models
    from backend.app.database import Base, SessionLocal, engine, run_migrations
    from backend.app.routers.local import UPLOAD_DIR, cleanup_uploads

    Base.metadata.create_all(bind=engine)
    run_migrations()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    keep = UPLOAD_DIR / "_keep_me_test.wav"
    drop = UPLOAD_DIR / "_drop_me_test.wav"
    keep.write_bytes(b"RIFF0000WAVE")
    drop.write_bytes(b"RIFF0000WAVE")

    db = SessionLocal()
    note = models.Note(
        bvid="local-cleanup-test", page=1, title="清理测试", subject="general",
        status="done", source="local", local_path=str(keep),
    )
    db.add(note)
    db.commit()
    try:
        cleanup_uploads(db)
        assert keep.exists(), "被笔记引用的缓存文件不应被删除"
        assert not drop.exists(), "未被引用的缓存文件应被删除"
    finally:
        db.delete(note)
        db.commit()
        db.close()
        for path in (keep, drop):
            if path.exists():
                path.unlink()
    print("cleanup OK")


if __name__ == "__main__":
    test_allowed_extensions()
    test_clean_path_rejects()
    test_probe_duration_missing_file()
    test_cleanup_keeps_referenced_files()
    print("ALL_LOCAL_VIDEO_TESTS_PASSED")
