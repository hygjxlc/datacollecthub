from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db import Base, engine
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import batch_no as batch_no_router
from app.routers import batches as batches_router
from app.routers import events as events_router
from app.routers import files as files_router
from app.routers import integration as integration_router
from app.routers import nameplates as nameplates_router
from app.routers import point_dicts as point_dicts_router
from app.routers import uploads as uploads_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # MVP 用 create_all 建表；Alembic 迁移在任务 3 引入
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DataCollectHub", lifespan=lifespan)

app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(batch_no_router.router)
app.include_router(batches_router.router)
app.include_router(uploads_router.router)
app.include_router(files_router.router)
app.include_router(integration_router.router)
app.include_router(nameplates_router.router)
app.include_router(point_dicts_router.router)
app.include_router(events_router.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
