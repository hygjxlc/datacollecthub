import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, not_found, unprocessable
from app.models import Batch, DataFile
from app.repositories.base import assert_org_visible, assert_owner, filter_by_org
from app.schemas.batch import BatchCreate, BatchOut, BatchUpdate
from app.services.audit import write_audit
from app.services.common import sort_modalities, utcnow

_BATCH_FIELDS = ("batch_no", "device_no", "device_model", "station", "license",
                 "sensitivity", "owner_contact", "is_synthetic",
                 "operating_condition", "weather", "equipment_state_type")

_MAX_EXTRAS_KEYS = 20
_MAX_EXTRAS_KEY_LEN = 64
_ALLOWED_EXTRAS_VALUE_TYPES = (str, int, float, bool, type(None))
_FIXED_BATCH_FIELDS = frozenset(_BATCH_FIELDS)


def validate_extras(extras: dict | None) -> dict | None:
    """扩展字段校验：固定字段不重名、仅 JSON 基本类型、键长与数量上限。

    键名统一 trim；空 dict 归一为 None（与未设置同义）；拒绝 NaN/Inf 等非有限数字。
    """
    if extras is None:
        return None
    if not isinstance(extras, dict):
        raise unprocessable("扩展字段必须为键值对对象")
    if len(extras) > _MAX_EXTRAS_KEYS:
        raise unprocessable(f"扩展字段最多 {_MAX_EXTRAS_KEYS} 个键")
    cleaned: dict = {}
    for key, value in extras.items():
        if not isinstance(key, str):
            raise unprocessable("扩展字段键名必须为非空字符串")
        key = key.strip()
        if not key:
            raise unprocessable("扩展字段键名必须为非空字符串")
        if len(key) > _MAX_EXTRAS_KEY_LEN:
            raise unprocessable(f"扩展字段键名 {key} 超过 {_MAX_EXTRAS_KEY_LEN} 字符")
        if key in _FIXED_BATCH_FIELDS:
            raise unprocessable(f"扩展字段键 {key} 与固定字段重名")
        if key in cleaned:
            raise unprocessable(f"扩展字段键 {key} 重复")
        if isinstance(value, float) and not math.isfinite(value):
            raise unprocessable(f"扩展字段 {key} 的值必须是有限数字")
        if not isinstance(value, _ALLOWED_EXTRAS_VALUE_TYPES):
            raise unprocessable(f"扩展字段 {key} 的值仅支持字符串/数字/布尔/空值")
        cleaned[key] = value
    return cleaned if cleaned else None


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

    def _manual_batch_no(self, batch_no: str | None) -> str:
        if not batch_no:
            raise unprocessable("批次编号必填（管理员未配置自动生成规则）")
        if self.db.execute(select(Batch).where(
                Batch.batch_no == batch_no)).scalar_one_or_none():
            raise unprocessable("批次编号已存在")
        return batch_no

    def create_batch(self, body: BatchCreate, user) -> BatchOut:
        from sqlalchemy.exc import IntegrityError

        from app.services.batch_no_service import BatchNoService
        rule = BatchNoService(self.db).get_rule()
        extras = validate_extras(body.extras)
        for _ in range(3):
            try:
                batch_no = (BatchNoService(self.db).generate(rule.template, body.device_no)
                            if rule is not None else self._manual_batch_no(body.batch_no))
                now = utcnow()
                batch = Batch(id=str(uuid.uuid4()), batch_no=batch_no,
                              device_no=body.device_no, device_model=body.device_model,
                              station=body.station, license=body.license,
                              sensitivity=body.sensitivity,
                              owner_contact=body.owner_contact,
                              is_synthetic=body.is_synthetic,
                              operating_condition=body.operating_condition,
                              weather=body.weather,
                              equipment_state_type=body.equipment_state_type,
                              extras=extras,
                              organization_id=user.organization_id, creator_id=user.id,
                              created_at=now, updated_at=now)
                self.db.add(batch)
                write_audit(self.db, user=user, action="create", entity_type="batch",
                            entity_id=batch.id)
                self.db.commit()
                return BatchOut.model_validate(batch)
            except IntegrityError:
                self.db.rollback()
        raise conflict("批次编号生成冲突，请重试")

    def update_batch(self, batch_id: str, body: BatchUpdate, user) -> BatchOut:
        batch = self.get_batch(batch_id, user)
        assert_owner(batch, user)
        data = body.model_dump(exclude_unset=True)
        if "extras" in data:
            data["extras"] = validate_extras(data["extras"])
        changes = {}
        for field, value in data.items():
            old = getattr(batch, field)
            if old != value:
                changes[field] = {"old": old, "new": value}
                setattr(batch, field, value)
        if changes:
            batch.updated_at = utcnow()
            write_audit(self.db, user=user, action="update", entity_type="batch",
                        entity_id=batch.id, field_changes=changes)
            self.db.commit()
        return self.get_batch_out(batch_id, user)

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
