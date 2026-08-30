import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found, unprocessable
from app.models import Batch, PointDict
from app.repositories.base import (assert_org_visible, creator_name_map,
                                   filter_by_org)
from app.schemas.point_dict import PointDictCreate, PointDictOut, PointDictUpdate
from app.services.audit import write_audit
from app.services.common import utcnow


class PointDictService:
    """测点字典：同单位共享维护。"""

    def __init__(self, db: Session):
        self.db = db

    def _to_out(self, obj: PointDict, names: dict | None = None) -> PointDictOut:
        """组装响应：附带创建者姓名（列表批量传入映射，单条单独查）。"""
        if names is None:
            names = creator_name_map(self.db, [obj.creator_id])
        data = PointDictOut.model_validate(obj).model_dump()
        data["creator_name"] = names.get(obj.creator_id)
        return PointDictOut(**data)

    def _get_obj(self, point_dict_id: str, user) -> PointDict:
        obj = self.db.get(PointDict, point_dict_id)
        if obj is None:
            raise not_found("测点字典不存在")
        assert_org_visible(obj, user)
        return obj

    def list_by_device(self, device_no: str | None, user) -> list[PointDictOut]:
        query = filter_by_org(select(PointDict), PointDict, user.organization_id,
                              user.role == "admin")
        if device_no:
            query = query.where(PointDict.device_no == device_no)
        rows = self.db.execute(query.order_by(PointDict.device_no,
                                              PointDict.channel_no)).scalars().all()
        names = creator_name_map(self.db, {r.creator_id for r in rows})
        return [self._to_out(r, names) for r in rows]

    def list_device_nos(self, user) -> list[str]:
        """本单位已出现的设备编号：Batch 与 PointDict 来源合并去重。"""
        q1 = filter_by_org(select(Batch.device_no), Batch, user.organization_id,
                           user.role == "admin")
        q2 = filter_by_org(select(PointDict.device_no), PointDict,
                           user.organization_id, user.role == "admin")
        return sorted({r[0] for r in self.db.execute(q1.union(q2)).all() if r[0]})

    def get(self, point_dict_id: str, user) -> PointDictOut:
        return self._to_out(self._get_obj(point_dict_id, user))

    def _conflict(self, org_id: str | None, device_no: str, channel_no: str,
                  exclude_id: str | None = None) -> bool:
        query = select(PointDict).where(PointDict.device_no == device_no,
                                        PointDict.channel_no == channel_no,
                                        PointDict.organization_id == org_id)
        if exclude_id:
            query = query.where(PointDict.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def create(self, body: PointDictCreate, user) -> PointDictOut:
        if self._conflict(user.organization_id, body.device_no, body.channel_no):
            raise unprocessable("该设备该通道号已存在")
        now = utcnow()
        obj = PointDict(id=str(uuid.uuid4()), organization_id=user.organization_id,
                        creator_id=user.id, created_at=now, updated_at=now,
                        **body.model_dump())
        self.db.add(obj)
        write_audit(self.db, user=user, action="create", entity_type="point_dict",
                    entity_id=obj.id)
        self.db.commit()
        return self._to_out(obj)

    def update(self, point_dict_id: str, body: PointDictUpdate, user) -> PointDictOut:
        obj = self._get_obj(point_dict_id, user)
        payload = body.model_dump(exclude_unset=True)
        # 先按目标组合做一次冲突检查（双字段同时变更时避免旧值干扰）
        target_device = payload.get("device_no", obj.device_no)
        target_channel = payload.get("channel_no", obj.channel_no)
        if (target_device, target_channel) != (obj.device_no, obj.channel_no) and \
                self._conflict(obj.organization_id, target_device, target_channel, obj.id):
            raise unprocessable("该设备该通道号已存在")
        changes = {}
        for field, value in payload.items():
            old = getattr(obj, field)
            if old != value:
                changes[field] = {"old": old, "new": value}
                setattr(obj, field, value)
        if changes:
            obj.updated_at = utcnow()
            write_audit(self.db, user=user, action="update", entity_type="point_dict",
                        entity_id=obj.id, field_changes=changes)
            self.db.commit()
        return self._to_out(obj)

    def delete(self, point_dict_id: str, user) -> None:
        obj = self._get_obj(point_dict_id, user)
        self.db.delete(obj)
        write_audit(self.db, user=user, action="delete", entity_type="point_dict",
                    entity_id=obj.id)
        self.db.commit()
