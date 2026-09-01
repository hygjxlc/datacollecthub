import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


def _sqlite_version_tuple() -> tuple[int, ...]:
    """解析 sqlite3.sqlite_version（可能带后缀，如 '3.50.4'），仅取前三段数字。"""
    result = []
    for token in sqlite3.sqlite_version.split(".")[:3]:
        digits = ""
        for ch in token:
            if not ch.isdigit():
                break
            digits += ch
        result.append(int(digits) if digits else 0)
    return tuple(result)


# 批次编号自动生成依赖 INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING；
# RETURNING 需 SQLite >= 3.35，低版本在此处直接失败，避免运行期 SQL 报错难以定位。
if settings.database_url.startswith("sqlite") and _sqlite_version_tuple() < (3, 35):
    raise RuntimeError("批次编号规则需要 SQLite >= 3.35（支持 RETURNING）")


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    """SQLite WAL 五项 PRAGMA（架构设计 4.6）。"""
    if settings.database_url.startswith("sqlite"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA wal_autocheckpoint=1000")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
