"""F8 集成接口路由（SRS 5.7）：无认证只读，仅内网可达（部署时经 nginx 例外规则）。

不挂任何认证依赖；只定义三个 GET，其余方法由 FastAPI 默认返回 405。
"""

import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.integration_service import IntegrationService
from app.storage.minio import get_storage

router = APIRouter(prefix="/api/v1/integration", tags=["integration"])


@router.get("/files/ids")
def query_file_ids(request: Request, db: Session = Depends(get_db),
                   storage=Depends(get_storage)):
    params = {k: v for k, v in request.query_params.items()}
    return IntegrationService(db, storage).query_ids(params)


@router.get("/files/{file_id}")
def get_file(file_id: str, db: Session = Depends(get_db),
             storage=Depends(get_storage)):
    return IntegrationService(db, storage).get_file(file_id)


@router.get("/files/{file_id}/download")
def download_file(file_id: str, db: Session = Depends(get_db),
                  storage=Depends(get_storage)):
    """集成打包导出：zip（原始数据 + 元数据 JSON 同文件夹），结构与认证下载一致。"""
    path, filename = IntegrationService(db, storage).get_file_download(file_id)
    return FileResponse(path, filename=filename, media_type="application/zip",
                        background=BackgroundTask(os.unlink, path))
