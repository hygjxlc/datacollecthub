from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import DataFile, User
from app.schemas.batch import BatchCreate, BatchOut, BatchUpdate
from app.services.batch_service import BatchService
from app.storage.exporter import build_excel

router = APIRouter(prefix="/api/v1/batches", tags=["batches"])


@router.get("")
def list_batches(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BatchService(db).list_batches(user, page, page_size)


@router.post("", response_model=BatchOut)
def create_batch(body: BatchCreate, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return BatchService(db).create_batch(body, user)


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: str, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    return BatchService(db).get_batch(batch_id, user)


@router.put("/{batch_id}", response_model=BatchOut)
def update_batch(batch_id: str, body: BatchUpdate, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return BatchService(db).update_batch(batch_id, body, user)


@router.delete("/{batch_id}")
def delete_batch(batch_id: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    BatchService(db).delete_batch(batch_id, user)
    return {"status": "ok"}


@router.get("/{batch_id}/export")
def export_batch(batch_id: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """批次登记表 Excel 导出（Sheet1 批次说明表 + Sheet2 文件清单表）。"""
    batch = BatchService(db).get_batch(batch_id, user)
    files = db.execute(select(DataFile).where(
        DataFile.batch_id == batch.id).order_by(DataFile.filename)).scalars().all()
    content = build_excel(batch, files)
    filename = f"{batch.batch_no}_登记表.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f"attachment; filename=\"{batch.batch_no}_registry.xlsx\"; "
                 f"filename*=UTF-8''{quote(filename)}"})
