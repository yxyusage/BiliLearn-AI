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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
