import math
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import bad_request, not_found, unprocessable
from app.models import User
from app.schemas.batch_import import BatchImportCreate, BatchImportOut
from app.schemas.upload import (UploadCompleteRequest, UploadInitRequest,
                                UploadInitResponse)
from app.services.batch_import_service import (BatchImportService,
                                               run_import_job)
from app.services.upload_service import PART_SIZE
from app.storage.minio import NoSuchUploadError, get_storage

router = APIRouter(prefix="/api/v1/batch-imports", tags=["batch-imports"])


@router.get("/template")
def download_template(user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    content = BatchImportService(db).build_template_csv()
    return Response(content=content, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             "attachment; filename=\"manifest.csv\"; "
                             "filename*=UTF-8''manifest.csv"})


@router.post("/upload/init", response_model=UploadInitResponse)
def init_zip_upload(body: UploadInitRequest, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db), storage=Depends(get_storage)):
    if body.file_size <= 0:
        raise unprocessable("file_size 必须为正数")
    object_key = f"batch-imports/{uuid.uuid4()}/{body.filename}"
    upload_id = storage.create_multipart(object_key)
    part_count = max(1, math.ceil(body.file_size / PART_SIZE))
    parts = [{"part_number": i, "url": storage.presign_part(object_key, upload_id, i)}
             for i in range(1, part_count + 1)]
    return UploadInitResponse(upload_id=upload_id, object_key=object_key,
                              part_size=PART_SIZE, parts=parts)


@router.post("/upload/{upload_id}/complete")
def complete_zip_upload(upload_id: str, body: UploadCompleteRequest,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db), storage=Depends(get_storage)):
    try:
        storage.complete_multipart(body.object_key, upload_id,
                                   [p.model_dump() for p in body.parts])
    except NoSuchUploadError as exc:
        raise bad_request(str(exc))
    return {"object_key": body.object_key}


@router.post("", response_model=BatchImportOut)
def create_import(body: BatchImportCreate, background: BackgroundTasks,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db),
                  storage=Depends(get_storage)):
    if not storage.exists(body.object_key):
        raise not_found("zip 对象不存在或已过期，请重新上传")
    job = BatchImportService(db).create_job(body.object_key, user)
    background.add_task(run_import_job, job.id, storage)   # 异步导入（GB 级大包不阻塞请求）
    return job


@router.get("")
def list_imports(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BatchImportService(db).list_jobs(user, page, page_size)


@router.get("/{import_id}", response_model=BatchImportOut)
def get_import(import_id: str, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    return BatchImportService(db).get_job(import_id, user)
