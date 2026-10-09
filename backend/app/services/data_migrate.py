"""学习存档的导出与合并导入。

- 导出：数据库快照 + Markdown 笔记 + 关键帧截图 → 一个 zip，换电脑直接带走；
- 导入：把一个 `bililearn.db`（或本地导出的 zip）合并进当前数据库。
  同一个 BV 号 + 同一分 P 已存在则跳过，只补充新的笔记与学习记录；
  设置与 API Key 不会被覆盖。
"""
import datetime
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.orm import Session

from ..config import DATA_DIR, DB_PATH
from ..models import (
    CollectionJob,
    ConfusionPoint,
    Note,
    ReviewMaterial,
    ReviewPlan,
    RoadmapJob,
    SubtitleCache,
    WrongAnswer,
)
from . import storage

ARCHIVE_FORMAT = 1

MERGE_TABLES = (
    "notes",
    "wrong_answers",
    "review_plan",
    "confusion_points",
    "collection_jobs",
    "review_materials",
    "roadmap_jobs",
    "subtitle_cache",
)

# 表名 → (模型, 统计键)
RELATED_TABLES = (
    ("wrong_answers", WrongAnswer, "wrong_added"),
    ("review_plan", ReviewPlan, "plans_added"),
    ("confusion_points", ConfusionPoint, "confusions_added"),
)


# ------------------------------------------------------------------ 导出

def _snapshot_db(target: Path) -> None:
    """用 sqlite3 备份 API 生成一致性快照（含还在 WAL 里的最新数据）。"""
    src = sqlite3.connect(str(DB_PATH))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def export_archive() -> Tuple[Path, Path]:
    """打包当前数据目录，返回 (zip 路径, 临时目录)，调用方负责清理临时目录。"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="bililearn-export-"))
    snapshot = tmp_dir / "bililearn.db"
    _snapshot_db(snapshot)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = tmp_dir / ("BiliLearn-学习存档-" + stamp + ".zip")
    notes_root = DATA_DIR / "notes"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(snapshot, "bililearn.db")
        if notes_root.is_dir():
            for path in sorted(notes_root.rglob("*")):
                if path.is_file():
                    zf.write(path, str(Path("notes") / path.relative_to(notes_root)))
        manifest = {
            "app": "BiliLearn-AI",
            "format": ARCHIVE_FORMAT,
            "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "data_dir": str(DATA_DIR),
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return archive, tmp_dir


# ------------------------------------------------------------------ 导入

def _read_source(path: Path) -> Dict[str, list]:
    """读取来源数据库（自动兼容旧版本缺少的列）。"""
    try:
        engine = create_engine("sqlite:///" + str(path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("无法读取该文件：" + str(exc)) from exc
    try:
        meta = MetaData()
        try:
            meta.reflect(bind=engine)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("这不是有效的 BiliLearn 数据文件") from exc
        if "notes" not in meta.tables:
            raise ValueError("这不是有效的 BiliLearn 数据文件（缺少 notes 表）")
        data: Dict[str, list] = {}
        with engine.connect() as conn:
            for name in MERGE_TABLES:
                table = meta.tables.get(name)
                if table is None:
                    continue
                data[name] = [dict(row._mapping) for row in conn.execute(select(table))]
        return data
    finally:
        engine.dispose()


def _model_payload(model, row: dict, skip=("id",)) -> dict:
    columns = {c.name for c in model.__table__.columns}
    return {k: v for k, v in row.items() if k in columns and k not in skip}


def _restore_note_files(row: dict, note: Note, notes_src_dir: Optional[Path], summary: dict) -> None:
    """把导入笔记的 Markdown 重新落盘，并按需复制关键帧/公式截图。"""
    try:
        if note.markdown:
            storage.save_markdown_file(note.id, note.title, note.markdown)
    except Exception as exc:  # noqa: BLE001
        summary["warnings"].append("Markdown 落盘失败（" + str(note.title)[:20] + "）：" + str(exc))
    if not notes_src_dir:
        return
    old_id = row.get("id")
    for kind in storage.FRAME_KINDS:
        src = notes_src_dir / (str(old_id) + "_" + kind)
        if not src.is_dir():
            continue
        try:
            shutil.copytree(src, storage.frames_dir(note.id, kind), dirs_exist_ok=True)
            summary["frames_copied"] += sum(1 for p in src.iterdir() if p.is_file())
        except Exception as exc:  # noqa: BLE001
            summary["warnings"].append("截图复制失败：" + str(exc))


def _remap_result_json(raw: str, bvid: str, note_id_map: dict, db: Session) -> str:
    """合集任务结果里的 note_id 指向来源库，导入后必须重指向本库。"""
    try:
        items = json.loads(raw or "[]")
    except Exception:  # noqa: BLE001
        return "[]"
    if not isinstance(items, list):
        return "[]"
    for item in items:
        if not isinstance(item, dict):
            continue
        old_id = item.get("note_id")
        if old_id in note_id_map:
            item["note_id"] = note_id_map[old_id]
            continue
        page = item.get("page")
        local = (
            db.query(Note)
            .filter(Note.bvid == bvid, Note.page == page, Note.status == "done")
            .order_by(Note.id.desc())
            .first()
        )
        item["note_id"] = local.id if local else 0
    return json.dumps(items, ensure_ascii=False)


def import_database(src_db: Path, db: Session, notes_src_dir: Optional[Path] = None) -> dict:
    """把来源数据库合并进当前库；返回导入统计。失败时整体回滚。"""
    summary = {
        "notes_added": 0,
        "notes_skipped": 0,
        "wrong_added": 0,
        "plans_added": 0,
        "confusions_added": 0,
        "collections_added": 0,
        "review_materials_added": 0,
        "roadmaps_added": 0,
        "subtitles_added": 0,
        "frames_copied": 0,
        "warnings": [],
    }
    src = _read_source(src_db)

    try:
        # 1) 合集任务先入库，方便把笔记的 batch_id 映射到新任务 id
        #    同一份存档重复导入时按 (bvid, 创建时间) 去重，不重复建任务
        existing_jobs = {
            (j.bvid or "", str(j.created_at)): j.id for j in db.query(CollectionJob).all()
        }
        job_id_map: Dict[int, int] = {}
        job_pending = []
        for row in src.get("collection_jobs", []):
            key = (row.get("bvid") or "", str(row.get("created_at")))
            if key in existing_jobs:
                job_id_map[row.get("id")] = existing_jobs[key]
                continue
            job = CollectionJob(**_model_payload(CollectionJob, row))
            db.add(job)
            db.flush()
            existing_jobs[key] = job.id
            job_id_map[row.get("id")] = job.id
            job_pending.append((job, row.get("result_json") or ""))
            summary["collections_added"] += 1

        # 2) 笔记：同 BV + 同分 P 已存在则跳过
        existing_keys = {(n.bvid, n.page) for n in db.query(Note.bvid, Note.page).all()}
        note_id_map: Dict[int, int] = {}
        for row in src.get("notes", []):
            bvid = row.get("bvid") or ""
            page = int(row.get("page") or 1)
            if (bvid, page) in existing_keys:
                summary["notes_skipped"] += 1
                continue
            payload = _model_payload(Note, row)
            if payload.get("batch_id"):
                payload["batch_id"] = job_id_map.get(payload["batch_id"], 0)
            if payload.get("status") in ("processing", "pending"):
                # 来源库里没跑完的笔记，导入后标记为失败，避免一直转圈
                payload["status"] = "failed"
                payload["error"] = (payload.get("error") or "") + "（导入时该笔记尚未生成完成）"
            note = Note(**payload)
            db.add(note)
            db.flush()
            note_id_map[row.get("id")] = note.id
            existing_keys.add((bvid, page))
            summary["notes_added"] += 1
            _restore_note_files(row, note, notes_src_dir, summary)
        db.flush()

        # 3) 错题 / 复习计划 / 没懂打点：只保留成功导入的笔记
        for table_name, model, key in RELATED_TABLES:
            for row in src.get(table_name, []):
                new_note_id = note_id_map.get(row.get("note_id"))
                if not new_note_id:
                    continue
                payload = _model_payload(model, row)
                payload["note_id"] = new_note_id
                db.add(model(**payload))
                summary[key] += 1

        # 4) 合集复习资料（按 任务 + 创建时间 去重）
        existing_materials = {
            (m.collection_job_id, str(m.created_at))
            for m in db.query(ReviewMaterial.collection_job_id, ReviewMaterial.created_at).all()
        }
        for row in src.get("review_materials", []):
            new_job_id = job_id_map.get(row.get("collection_job_id"))
            if not new_job_id:
                continue
            key = (new_job_id, str(row.get("created_at")))
            if key in existing_materials:
                continue
            payload = _model_payload(ReviewMaterial, row)
            payload["collection_job_id"] = new_job_id
            db.add(ReviewMaterial(**payload))
            existing_materials.add(key)
            summary["review_materials_added"] += 1

        # 5) 线路图任务（按 bvid + 创建时间 去重）
        existing_roadmaps = {
            (r.bvid or "", str(r.created_at))
            for r in db.query(RoadmapJob.bvid, RoadmapJob.created_at).all()
        }
        for row in src.get("roadmap_jobs", []):
            key = (row.get("bvid") or "", str(row.get("created_at")))
            if key in existing_roadmaps:
                continue
            db.add(RoadmapJob(**_model_payload(RoadmapJob, row)))
            existing_roadmaps.add(key)
            summary["roadmaps_added"] += 1

        # 6) 字幕缓存：key 唯一，已存在则跳过
        existing_keys = {c.key for c in db.query(SubtitleCache.key).all()}
        for row in src.get("subtitle_cache", []):
            key = row.get("key")
            if not key or key in existing_keys:
                continue
            db.add(SubtitleCache(**_model_payload(SubtitleCache, row)))
            existing_keys.add(key)
            summary["subtitles_added"] += 1

        db.flush()

        # 7) 合集任务结果里的 note_id 重指向本库笔记
        for job, raw in job_pending:
            job.result_json = _remap_result_json(raw, job.bvid, note_id_map, db)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return summary


def import_from_upload(src_file: Path, db: Session) -> dict:
    """支持裸 .db（同目录有 notes/ 会一起合并）或本地导出的 .zip 存档。"""
    if src_file.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="bililearn-import-") as tmp:
            with zipfile.ZipFile(src_file) as zf:
                for member in zf.namelist():
                    parts = Path(member).parts
                    if member.startswith("/") or ".." in parts:
                        raise ValueError("压缩包目录结构异常，已拒绝导入")
                zf.extractall(tmp)
            root = Path(tmp)
            db_file = root / "bililearn.db"
            if not db_file.exists():
                candidates = list(root.rglob("bililearn.db"))
                if not candidates:
                    raise ValueError("压缩包里没有找到 bililearn.db")
                db_file = candidates[0]
            notes_dir = db_file.parent / "notes"
            return import_database(db_file, db, notes_dir if notes_dir.is_dir() else None)
    notes_dir = src_file.parent / "notes"
    return import_database(src_file, db, notes_dir if notes_dir.is_dir() else None)
