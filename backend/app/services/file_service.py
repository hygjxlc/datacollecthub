"""F5 元数据编辑/审计、F7 检索与下载（架构 5.2/6.1/6.2）。"""

from sqlalchemy.orm import Session

from app.core.errors import not_found, unprocessable
from app.models import Batch, DataFile
from app.repositories.base import assert_owner
from app.repositories.file_repo import visible_files_query
from app.schemas.datafile import DataFileOut, DataFileUpdate
from app.services.archive import build_files_zip
from app.services.audit import write_audit
from app.services.common import utcnow


class FileService:
    def __init__(self, db: Session, storage):
        self.db = db
        self.storage = storage

    def get_file(self, file_id: str, user) -> DataFile:
        """按 ID 读取 + 跨单位隐藏（404，不泄露他单位资源存在性）。"""
        df = self.db.get(DataFile, file_id)
        if df is None:
            raise not_found("文件不存在")
        if user.role != "admin":
            batch = self.db.get(Batch, df.batch_id) if df.batch_id else None
            if batch is None or batch.organization_id != user.organization_id:
                raise not_found("资源不存在")
        return df

    def update(self, file_id: str, body: DataFileUpdate, user) -> DataFileOut:
        df = self.get_file(file_id, user)
        assert_owner(df, user, owner_field="uploader_id")
        changes = {}
        for field, value in body.model_dump(exclude_unset=True).items():
            old = getattr(df, field)
            if old != value:
                changes[field] = {"old": old, "new": value}
                setattr(df, field, value)
        # 时区必填：合并后采集起止时间有值而 timezone 为空 → 422（SRS 4.4）
        if (df.start_time or df.end_time) and not df.timezone:
            raise unprocessable("时区必填：采集起止时间有值时需提供 timezone")
        if changes:
            df.updated_at = utcnow()
            write_audit(self.db, user=user, action="update", entity_type="datafile",
                        entity_id=df.id, field_changes=changes)
            self.db.commit()
        return DataFileOut.model_validate(df)

    def delete(self, file_id: str, user) -> None:
        df = self.get_file(file_id, user)
        assert_owner(df, user, owner_field="uploader_id")
        self.storage.delete_object(df.object_key)
        self.db.delete(df)
        write_audit(self.db, user=user, action="delete", entity_type="datafile",
                    entity_id=df.id)
        self.db.commit()

    def search(self, user, *, modality: str | None = None,
               batch_no: str | None = None, device_no: str | None = None,
               station: str | None = None, start_after: str | None = None,
               start_before: str | None = None, is_synthetic: int | None = None,
               page: int = 1, page_size: int = 20) -> dict:
        """组合筛选 + 单位过滤 + 分页（架构 6.2，F7）。"""
        query = visible_files_query(user)
        if modality:
            query = query.where(DataFile.modality == modality)
        if batch_no:
            query = query.where(DataFile.batch_no == batch_no)
        if device_no:
            query = query.where(DataFile.device_no == device_no)
        if station:
            query = query.where(DataFile.station == station)
        if start_after:
            query = query.where(DataFile.start_time >= start_after)
        if start_before:
            query = query.where(DataFile.start_time <= start_before)
        if is_synthetic is not None:
            query = query.where(DataFile.is_synthetic == is_synthetic)
        total = len(self.db.execute(query).scalars().all())
        rows = self.db.execute(
            query.order_by(DataFile.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)).scalars()
        return {"items": [DataFileOut.model_validate(r) for r in rows],
                "total": total, "page": page, "page_size": page_size}

    def get_download_url(self, file_id: str, user) -> dict:
        df = self.get_file(file_id, user)
        url = self.storage.presign_get(df.object_key, 3600)
        write_audit(self.db, user=user, action="download", entity_type="datafile",
                    entity_id=df.id)
        self.db.commit()
        return {"download_url": url, "expires_in": 3600}

    def build_download_zip(self, ids: list[str], user) -> tuple[str, str]:
        """批量打包下载（TC-DOWNLOAD）：每文件独立文件夹，内含原始数据 + 元数据 JSON。

        返回 (临时文件路径, 下载文件名)；失败时删除临时文件。
        """
        if not ids:
            raise unprocessable("请选择至少一个文件")
        if len(ids) > 20:
            raise unprocessable("一次最多打包 20 个文件，请分批下载")
        files = [self.get_file(fid, user) for fid in ids]  # 任一不可见 → 404
        for df in files:
            write_audit(self.db, user=user, action="download",
                        entity_type="datafile", entity_id=df.id)
        self.db.commit()
        try:
            return build_files_zip(self.db, self.storage, files)
        except FileNotFoundError as e:
            raise not_found(f"存储对象缺失：{e}")
