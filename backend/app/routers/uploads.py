from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.datafile import DataFileOut
from app.schemas.upload import UploadCompleteRequest, UploadInitRequest, UploadInitResponse
from app.services.upload_service import UploadService
from app.storage.minio import get_storage

router = APIRouter(prefix="/api/v1/batches", tags=["uploads"])


@router.post("/{batch_id}/files/upload/init", response_model=UploadInitResponse)
def init_upload(batch_id: str, body: UploadInitRequest,
                user: User = Depends(get_current_user), db: Session = Depends(get_db),
                storage=Depends(get_storage)):
    return UploadService(db, storage).init_upload(batch_id, body, user)


@router.post("/{batch_id}/files/upload/{upload_id}/complete", response_model=DataFileOut)
def complete_upload(batch_id: str, upload_id: str, body: UploadCompleteRequest,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db),
                    storage=Depends(get_storage)):
    return UploadService(db, storage).complete_upload(batch_id, upload_id, body, user)
