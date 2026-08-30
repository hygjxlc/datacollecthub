import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, unprocessable
from app.models import Batch, DataFile
from app.schemas.datafile import DataFileOut
from app.schemas.upload import UploadCompleteRequest, UploadInitRequest, UploadInitResponse
from app.services.audit import write_audit
from app.services.batch_service import BatchService
from app.services.common import utcnow
from app.storage.minio import NoSuchUploadError

PART_SIZE = 10 * 1024 * 1024   # 10MB/片（架构 5.1）

EXT_TO_MODALITY = {".dat": "SCADA", ".bin": "VIB", ".wav": "AUD", ".flac": "AUD",
                   ".mp3": "AUD", ".irx": "IR", ".png": "IR", ".jpg": "CAM",
                   ".mp4": "VID", ".pdf": "TXT", ".doc": "TXT", ".docx": "TXT",
                   ".csv": "SCADA", ".xlsx": "RPT"}


def infer_modality(filename: str) -> str:
    return EXT_TO_MODALITY.get(Path(filename).suffix.lower(), "SCADA")


def build_object_key(station: str, device_no: str, filename: str,
                     now: datetime | None = None) -> str:
    """<场站>/<设备>/<模态>/<年>/<月>/<文件名>（架构 4.4，原始区永不修改）。"""
    now = now or datetime.now(timezone.utc)
    modality = infer_modality(filename)
    return f"{station}/{device_no}/{modality.lower()}/{now.year:04d}/{now.month:02d}/{filename}"


class UploadService:
    def __init__(self, db: Session, storage):
        self.db = db
        self.storage = storage

    def init_upload(self, batch_id: str, body: UploadInitRequest, user,
                    ) -> UploadInitResponse:
        if body.file_size <= 0:
            raise unprocessable("file_size 必须为正数")
        batch = BatchService(self.db).get_batch(batch_id, user)
        station = (batch.station or batch.organization.name).replace(" ", "")
        object_key = build_object_key(station, batch.device_no, body.filename)
        if self.db.execute(select(DataFile).where(
                DataFile.object_key == object_key)).scalar_one_or_none():
            raise unprocessable("同名文件已存在，原始区永不覆盖，请修改文件名后重试")
        upload_id = self.storage.create_multipart(object_key)
        part_count = max(1, math.ceil(body.file_size / PART_SIZE))
        parts = [{"part_number": i,
                  "url": self.storage.presign_part(object_key, upload_id, i)}
                 for i in range(1, part_count + 1)]
        return UploadInitResponse(upload_id=upload_id, object_key=object_key,
                                  part_size=PART_SIZE, parts=parts)

    def complete_upload(self, batch_id: str, upload_id: str,
                        body: UploadCompleteRequest, user) -> DataFileOut:
        batch = BatchService(self.db).get_batch(batch_id, user)
        if self.db.execute(select(DataFile).where(
                DataFile.object_key == body.object_key)).scalar_one_or_none():
            raise unprocessable("同名文件已存在，原始区永不覆盖")
        try:
            self.storage.complete_multipart(
                body.object_key, upload_id,
                [p.model_dump() for p in body.parts])
        except NoSuchUploadError as exc:
            raise bad_request(str(exc))
        except Exception as exc:
            raise bad_request(f"分片合入失败：{exc}")
        now = utcnow()
        df = DataFile(
            id=str(uuid.uuid4()),
            batch_id=batch.id,
            batch_no=batch.batch_no,                       # F6 批次字段快照继承
            object_key=body.object_key,
            filename=body.filename,
            file_size=body.file_size,
            checksum=body.checksum,
            modality=infer_modality(body.filename),
            device_no=batch.device_no,
            station=batch.station,
            license=batch.license,
            sensitivity=batch.sensitivity,
            is_synthetic=batch.is_synthetic,
            operating_condition=batch.operating_condition,
            weather=batch.weather,
            uploader_id=user.id,
            upload_status="已完成",
            created_at=now, updated_at=now,
        )
        self.db.add(df)
        write_audit(self.db, user=user, action="create", entity_type="datafile",
                    entity_id=df.id)
        self.db.commit()
        return DataFileOut.model_validate(df)
