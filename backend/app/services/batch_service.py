import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, not_found, unprocessable
from app.models import Batch, DataFile
from app.repositories.base import assert_org_visible, assert_owner, filter_by_org
from app.schemas.batch import BatchCreate, BatchOut, BatchUpdate
from app.services.audit import write_audit
from app.services.common import sort_modalities, utcnow

_BATCH_FIELDS = ("batch_no", "device_no", "device_model", "station", "license",
                 "sensitivity", "owner_contact", "is_synthetic",
                 "operating_condition", "weather")


class BatchService:
    def __init__(self, db: Session):
        self.db = db

    def list_batches(self, user, page: int = 1, page_size: int = 20) -> dict:
        query = filter_by_org(select(Batch), Batch, user.organization_id,
                              user.role == "admin")
        total = len(self.db.execute(query).scalars().all())
        rows = self.db.execute(
            query.order_by(Batch.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)).scalars().all()
        # 批量聚合文件数与数据量（架构 3.1 列表页列）
        batch_ids = [b.id for b in rows]
        agg = {}
        if batch_ids:
            agg_rows = self.db.execute(
                select(DataFile.batch_id, func.count(), func.coalesce(
                    func.sum(DataFile.file_size), 0),
                    func.group_concat(func.distinct(DataFile.modality)))
                .where(DataFile.batch_id.in_(batch_ids))
                .group_by(DataFile.batch_id)).all()
            agg = {r[0]: (r[1], r[2], r[3]) for r in agg_rows}
        items = []
        for b in rows:
            out = BatchOut.model_validate(b)
            count, size, mods = agg.get(b.id, (0, 0, ""))
            out.file_count, out.total_size = count, size
            out.modalities = sort_modalities(
                [m for m in (mods or "").split(",") if m])
            items.append(out)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def get_batch(self, batch_id: str, user) -> Batch:
        batch = self.db.get(Batch, batch_id)
        if batch is None:
            raise not_found("批次不存在")
        assert_org_visible(batch, user)
        return batch

    def get_batch_out(self, batch_id: str, user) -> BatchOut:
        """详情页输出：modalities 单独聚合填充。"""
        batch = self.get_batch(batch_id, user)
        mods = self.db.execute(select(DataFile.modality).where(
            DataFile.batch_id == batch.id).distinct()).scalars().all()
        out = BatchOut.model_validate(batch)
        out.modalities = sort_modalities(mods)
        return out

    def create_batch(self, body: BatchCreate, user) -> BatchOut:
        if self.db.execute(select(Batch).where(
                Batch.batch_no == body.batch_no)).scalar_one_or_none():
            raise unprocessable("批次编号已存在")
        now = utcnow()
        batch = Batch(id=str(uuid.uuid4()), batch_no=body.batch_no,
                      device_no=body.device_no, device_model=body.device_model,
                      station=body.station, license=body.license,
                      sensitivity=body.sensitivity, owner_contact=body.owner_contact,
                      is_synthetic=body.is_synthetic,
                      operating_condition=body.operating_condition,
                      weather=body.weather,
                      equipment_state_type=body.equipment_state_type,
                      organization_id=user.organization_id, creator_id=user.id,
                      created_at=now, updated_at=now)
        self.db.add(batch)
        write_audit(self.db, user=user, action="create", entity_type="batch",
                    entity_id=batch.id)
        self.db.commit()
        return BatchOut.model_validate(batch)

    def update_batch(self, batch_id: str, body: BatchUpdate, user) -> BatchOut:
        batch = self.get_batch(batch_id, user)
        assert_owner(batch, user)
        changes = {}
        for field, value in body.model_dump(exclude_unset=True).items():
            old = getattr(batch, field)
            if old != value:
                changes[field] = {"old": old, "new": value}
                setattr(batch, field, value)
        if changes:
            batch.updated_at = utcnow()
            write_audit(self.db, user=user, action="update", entity_type="batch",
                        entity_id=batch.id, field_changes=changes)
            self.db.commit()
        return BatchOut.model_validate(batch)

    def delete_batch(self, batch_id: str, user) -> None:
        batch = self.get_batch(batch_id, user)
        assert_owner(batch, user)
        file_count = self.db.execute(
            select(DataFile).where(DataFile.batch_id == batch.id).limit(1)).scalar_one_or_none()
        if file_count is not None:
            raise bad_request("批次内存在数据文件，仅空批次可删除")
        self.db.delete(batch)
        write_audit(self.db, user=user, action="delete", entity_type="batch",
                    entity_id=batch.id)
        self.db.commit()
