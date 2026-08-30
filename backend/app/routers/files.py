import os

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.datafile import BatchDownloadReq, DataFileOut, DataFileUpdate
from app.services.file_service import FileService
from app.storage.minio import get_storage

router = APIRouter(prefix="/api/v1/files", tags=["files"])


@router.post("/batch-download")
def batch_download(body: BatchDownloadReq,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db), storage=Depends(get_storage)):
    """批量打包下载（TC-DOWNLOAD）：zip 流式生成，响应后删除临时文件。"""
    path, filename = FileService(db, storage).build_download_zip(body.ids, user)
    return FileResponse(path, filename=filename, media_type="application/zip",
                        background=BackgroundTask(os.unlink, path))


@router.get("")
def list_files(modality: str | None = None, batch_no: str | None = None,
               device_no: str | None = None, station: str | None = None,
               start_after: str | None = None, start_before: str | None = None,
               is_synthetic: int | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               user: User = Depends(get_current_user), db: Session = Depends(get_db),
               storage=Depends(get_storage)):
    return FileService(db, storage).search(
        user, modality=modality, batch_no=batch_no, device_no=device_no,
        station=station, start_after=start_after, start_before=start_before,
        is_synthetic=is_synthetic, page=page, page_size=page_size)


@router.get("/{file_id}", response_model=DataFileOut)
def get_file(file_id: str, user: User = Depends(get_current_user),
             db: Session = Depends(get_db), storage=Depends(get_storage)):
    return FileService(db, storage).get_file(file_id, user)


@router.put("/{file_id}", response_model=DataFileOut)
def update_file(file_id: str, body: DataFileUpdate,
                user: User = Depends(get_current_user), db: Session = Depends(get_db),
                storage=Depends(get_storage)):
    return FileService(db, storage).update(file_id, body, user)


@router.delete("/{file_id}")
def delete_file(file_id: str, user: User = Depends(get_current_user),
                db: Session = Depends(get_db), storage=Depends(get_storage)):
    FileService(db, storage).delete(file_id, user)
    return {"status": "ok"}


@router.get("/{file_id}/download")
def get_download_url(file_id: str, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db), storage=Depends(get_storage)):
    return FileService(db, storage).get_download_url(file_id, user)
