import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found, unprocessable
from app.models import Nameplate
from app.repositories.base import (assert_org_visible, creator_name_map,
                                   filter_by_org)
from app.schemas.nameplate import NameplateCreate, NameplateOut, NameplateUpdate
from app.services.audit import write_audit
from app.services.common import utcnow


class NameplateService:
    """设备铭牌台账：同单位共享维护（仅校验单位可见性，不校验 owner）。"""

    def __init__(self, db: Session):
        self.db = db

    def _to_out(self, obj: Nameplate, names: dict | None = None) -> NameplateOut:
        """组装响应：附带创建者姓名（列表批量传入映射，单条单独查）。"""
        if names is None:
            names = creator_name_map(self.db, [obj.creator_id])
        data = NameplateOut.model_validate(obj).model_dump()
        data["creator_name"] = names.get(obj.creator_id)
        return NameplateOut(**data)

    def _get_obj(self, nameplate_id: str, user) -> Nameplate:
        obj = self.db.get(Nameplate, nameplate_id)
        if obj is None:
            raise not_found("铭牌不存在")
        assert_org_visible(obj, user)
        return obj

    def list_nameplates(self, user) -> list[NameplateOut]:
        query = filter_by_org(select(Nameplate), Nameplate, user.organization_id,
                              user.role == "admin")
        rows = self.db.execute(query.order_by(Nameplate.device_no)).scalars().all()
        names = creator_name_map(self.db, {r.creator_id for r in rows})
        return [self._to_out(r, names) for r in rows]

    def get_by_device(self, device_no: str, user) -> list[NameplateOut]:
        query = filter_by_org(select(Nameplate).where(Nameplate.device_no == device_no),
                              Nameplate, user.organization_id, user.role == "admin")
        rows = self.db.execute(query).scalars().all()
        names = creator_name_map(self.db, {r.creator_id for r in rows})
        return [self._to_out(r, names) for r in rows]

    def get(self, nameplate_id: str, user) -> NameplateOut:
        return self._to_out(self._get_obj(nameplate_id, user))

    def _conflict(self, org_id: str | None, device_no: str,
                  exclude_id: str | None = None) -> bool:
        query = select(Nameplate).where(Nameplate.device_no == device_no,
                                        Nameplate.organization_id == org_id)
        if exclude_id:
            query = query.where(Nameplate.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def create(self, body: NameplateCreate, user) -> NameplateOut:
        # §2.6 执行补充：admin 可显式指定所属单位（校验存在），否则落 user 本单位
        org_id = user.organization_id
        if user.role == "admin" and body.organization_id:
            org_id = body.organization_id
            from app.models import Organization
            if self.db.get(Organization, org_id) is None:
                raise unprocessable("所属单位不存在")
        if self._conflict(org_id, body.device_no):
            raise unprocessable("该设备铭牌已存在")
        now = utcnow()
        data = body.model_dump()
        data.pop("organization_id", None)
        obj = Nameplate(id=str(uuid.uuid4()), organization_id=org_id,
                        creator_id=user.id, created_at=now, updated_at=now, **data)
        self.db.add(obj)
        write_audit(self.db, user=user, action="create", entity_type="nameplate",
                    entity_id=obj.id)
        self.db.commit()
        return self._to_out(obj)

    def update(self, nameplate_id: str, body: NameplateUpdate, user) -> NameplateOut:
        obj = self._get_obj(nameplate_id, user)
        changes = {}
        for field, value in body.model_dump(exclude_unset=True).items():
            if field == "device_no" and value != obj.device_no and \
                    self._conflict(obj.organization_id, value, obj.id):
                raise unprocessable("该设备铭牌已存在")
            old = getattr(obj, field)
            if old != value:
                changes[field] = {"old": old, "new": value}
                setattr(obj, field, value)
        if changes:
            obj.updated_at = utcnow()
            write_audit(self.db, user=user, action="update", entity_type="nameplate",
                        entity_id=obj.id, field_changes=changes)
            self.db.commit()
        return self._to_out(obj)

    def delete(self, nameplate_id: str, user) -> None:
        obj = self._get_obj(nameplate_id, user)
        self.db.delete(obj)
        write_audit(self.db, user=user, action="delete", entity_type="nameplate",
                    entity_id=obj.id)
        self.db.commit()
