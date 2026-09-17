from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.db import Base, engine
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import batch_imports as batch_imports_router
from app.routers import batch_no as batch_no_router
from app.routers import batches as batches_router
from app.routers import events as events_router
from app.routers import fault_types as fault_types_router
from app.routers import files as files_router
from app.routers import integration as integration_router
from app.routers import modal_params as modal_params_router
from app.routers import nameplates as nameplates_router
from app.routers import point_dicts as point_dicts_router
from app.routers import uploads as uploads_router


def _ensure_sqlite_columns() -> None:
    """幂等补列：create_all 不迁移已存在的旧表（MVP 未接 Alembic）。

    Phase 1 事件组化：新增 7 列并对存量 operating_condition 一次性回填推断 event_type；
    evt_id 唯一约束走独立索引（SQLite ADD COLUMN 无法带 UNIQUE）。
    """
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(batch)"))}
        if "fault_time" not in cols:
            conn.execute(text("ALTER TABLE batch ADD COLUMN fault_time VARCHAR(32)"))
        if "fault_desc" not in cols:
            conn.execute(text("ALTER TABLE batch ADD COLUMN fault_desc TEXT"))
        if "event_type" not in cols:
            conn.execute(text(
                "ALTER TABLE batch ADD COLUMN event_type VARCHAR(16) NOT NULL DEFAULT '正常'"))
            # 退役轴回填推断（仅加列时执行一次，此后新申报由服务层维护）
            conn.execute(text(
                "UPDATE batch SET event_type = '故障' WHERE operating_condition = '故障'"))
            conn.execute(text(
                "UPDATE batch SET event_type = '维修' WHERE operating_condition = '检修'"))
        if "fault_type" not in cols:
            conn.execute(text("ALTER TABLE batch ADD COLUMN fault_type VARCHAR(64)"))
        if "severity" not in cols:
            conn.execute(text("ALTER TABLE batch ADD COLUMN severity VARCHAR(16)"))
        if "t_start" not in cols:
            conn.execute(text("ALTER TABLE batch ADD COLUMN t_start VARCHAR(32)"))
        if "t_end" not in cols:
            conn.execute(text("ALTER TABLE batch ADD COLUMN t_end VARCHAR(32)"))
        if "event_status" not in cols:
            conn.execute(text(
                "ALTER TABLE batch ADD COLUMN event_status VARCHAR(16) NOT NULL DEFAULT 'draft'"))
        if "evt_id" not in cols:
            conn.execute(text("ALTER TABLE batch ADD COLUMN evt_id VARCHAR(64)"))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_batch_evt_id ON batch(evt_id)"))
        rule_cols = {row[1] for row in conn.execute(
            text("PRAGMA table_info(batch_no_rule)"))}
        if "evt_template" not in rule_cols:
            conn.execute(text(
                "ALTER TABLE batch_no_rule ADD COLUMN evt_template VARCHAR(256)"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    # MVP 用 create_all 建表；Alembic 迁移在任务 3 引入
    Base.metadata.create_all(engine)
    _ensure_sqlite_columns()
    yield


app = FastAPI(title="DataCollectHub", lifespan=lifespan)

app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(batch_no_router.router)
app.include_router(batch_imports_router.router)
app.include_router(batches_router.router)
app.include_router(uploads_router.router)
app.include_router(files_router.router)
app.include_router(integration_router.router)
app.include_router(nameplates_router.router)
app.include_router(point_dicts_router.router)
app.include_router(events_router.router)
app.include_router(fault_types_router.router)
app.include_router(fault_types_router.admin_router)
app.include_router(modal_params_router.router)
app.include_router(modal_params_router.admin_router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
