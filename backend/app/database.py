"""SQLite 数据库连接与会话管理。"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def run_migrations() -> None:
    """轻量迁移：为旧库补充新增列。"""
    from sqlalchemy import text

    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(wrong_answers)"))]
        if cols and "feedback" not in cols:
            conn.execute(text("ALTER TABLE wrong_answers ADD COLUMN feedback TEXT DEFAULT ''"))
            conn.commit()
        note_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(notes)"))]
        if note_cols and "batch_id" not in note_cols:
            conn.execute(text("ALTER TABLE notes ADD COLUMN batch_id INTEGER DEFAULT 0"))
            conn.commit()
        if note_cols and "formulas" not in note_cols:
            conn.execute(text("ALTER TABLE notes ADD COLUMN formulas TEXT DEFAULT ''"))
            conn.commit()
        if note_cols and "keyframes" not in note_cols:
            conn.execute(text("ALTER TABLE notes ADD COLUMN keyframes TEXT DEFAULT ''"))
            conn.commit()
        for col, ddl in (
            ("qtype", "ALTER TABLE wrong_answers ADD COLUMN qtype TEXT DEFAULT ''"),
            ("status", "ALTER TABLE wrong_answers ADD COLUMN status TEXT DEFAULT 'active'"),
            ("wrong_count", "ALTER TABLE wrong_answers ADD COLUMN wrong_count INTEGER DEFAULT 1"),
            ("updated_at", "ALTER TABLE wrong_answers ADD COLUMN updated_at TIMESTAMP"),
        ):
            if cols and col not in cols:
                conn.execute(text(ddl))
                conn.commit()
        # v1.6.0：notes.dictations（英语听写）与 review_plan SM-2 状态列
        if note_cols and "dictations" not in note_cols:
            conn.execute(text("ALTER TABLE notes ADD COLUMN dictations TEXT DEFAULT ''"))
            conn.commit()
        rp_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(review_plan)"))]
        for col, ddl in (
            ("repetitions", "ALTER TABLE review_plan ADD COLUMN repetitions INTEGER DEFAULT 0"),
            ("interval_days", "ALTER TABLE review_plan ADD COLUMN interval_days INTEGER DEFAULT 0"),
            ("ease_factor", "ALTER TABLE review_plan ADD COLUMN ease_factor REAL DEFAULT 2.5"),
            ("last_reviewed", "ALTER TABLE review_plan ADD COLUMN last_reviewed TEXT DEFAULT ''"),
        ):
            if rp_cols and col not in rp_cols:
                conn.execute(text(ddl))
                conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
