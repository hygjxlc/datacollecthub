import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import not_found, unprocessable
from app.models import Batch, DataFile, Event, EventFile
from app.repositories.base import (assert_org_visible, creator_name_map,
                                   filter_by_org)
from app.schemas.event import EventCreate, EventOut, EventUpdate
from app.services.audit import write_audit
from app.services.common import utcnow

SEVERITIES = {"报警", "故障", "事故"}


class EventService:
    """事件记录：多模态事件组数据集锚点，同单位共享维护。"""

    def __init__(self, db: Session):
        self.db = db

    def _to_out(self, e: Event, names: dict | None = None) -> EventOut:
        """组装响应：附带关联文件 ID 列表与计数、创建者姓名。"""
        if names is None:
            names = creator_name_map(self.db, [e.creator_id])
        file_ids = [r[0] for r in self.db.execute(
            select(EventFile.datafile_id).where(EventFile.event_id == e.id)
            .order_by(EventFile.datafile_id)).all()]
        data = EventOut.model_validate(e).model_dump()
        data["related_files"] = file_ids
        data["related_file_count"] = len(file_ids)
        data["creator_name"] = names.get(e.creator_id)
        return EventOut(**data)

    def list_events(self, device_no: str | None, start: str | None,
                    end: str | None, severity: str | None, user) -> list[EventOut]:
        query = filter_by_org(select(Event), Event, user.organization_id,
                              user.role == "admin")
        if device_no:
            query = query.where(Event.device_no == device_no)
        if severity:
            query = query.where(Event.severity == severity)
        if start:
            query = query.where(Event.event_time >= start)
        if end:
            query = query.where(Event.event_time <= end)
        rows = self.db.execute(query.order_by(Event.event_time.desc())).scalars().all()
        names = creator_name_map(self.db, {e.creator_id for e in rows})
        return [self._to_out(e, names) for e in rows]

    def get(self, event_id: str, user) -> EventOut:
        obj = self.db.get(Event, event_id)
        if obj is None:
            raise not_found("事件不存在")
        assert_org_visible(obj, user)
        return self._to_out(obj)

    def _assert_file_visible(self, df: DataFile, user) -> None:
        """关联文件必须属于当前单位（DataFile 无 organization_id，经 batch 判断）。"""
        if user.role == "admin":
            return
        batch = self.db.get(Batch, df.batch_id) if df.batch_id else None
        if batch is None or batch.organization_id != user.organization_id:
            raise not_found(f"关联文件不存在：{df.id}")

    def _set_files(self, event: Event, file_ids: list[str], user) -> None:
        """全量替换关联：校验 + 去重 + 先删后插（UNIQUE 约束下幂等）。"""
        for fid in dict.fromkeys(file_ids):
            df = self.db.get(DataFile, fid)
            if df is None:
                raise not_found(f"关联文件不存在：{fid}")
            self._assert_file_visible(df, user)
        self.db.execute(delete(EventFile).where(EventFile.event_id == event.id))
        for fid in dict.fromkeys(file_ids):
            self.db.add(EventFile(id=str(uuid.uuid4()), event_id=event.id,
                                  datafile_id=fid))

    def create(self, body: EventCreate, user) -> EventOut:
        if body.severity not in SEVERITIES:
            raise unprocessable("严重级别必须为：报警/故障/事故")
        now = utcnow()
        payload = body.model_dump(exclude={"related_file_ids"})
        obj = Event(id=str(uuid.uuid4()), organization_id=user.organization_id,
                    creator_id=user.id, created_at=now, updated_at=now, **payload)
        self.db.add(obj)
        self._set_files(obj, body.related_file_ids or [], user)
        write_audit(self.db, user=user, action="create", entity_type="event",
                    entity_id=obj.id)
        self.db.commit()
        return self._to_out(obj)

    def update(self, event_id: str, body: EventUpdate, user) -> EventOut:
        obj = self.db.get(Event, event_id)
        if obj is None:
            raise not_found("事件不存在")
        assert_org_visible(obj, user)
        changes = {}
        file_ids = None
        for field, value in body.model_dump(exclude_unset=True).items():
            if field == "related_file_ids":
                file_ids = value or []
                continue
            if field == "severity" and value not in SEVERITIES:
                raise unprocessable("严重级别必须为：报警/故障/事故")
            old = getattr(obj, field)
            if old != value:
                changes[field] = {"old": old, "new": value}
                setattr(obj, field, value)
        if file_ids is not None:
            new_ids = list(dict.fromkeys(file_ids))
            old_ids = [r[0] for r in self.db.execute(
                select(EventFile.datafile_id).where(EventFile.event_id == obj.id)
                .order_by(EventFile.datafile_id)).all()]
            if sorted(old_ids) != sorted(new_ids):
                self._set_files(obj, new_ids, user)
                changes["related_file_ids"] = {"old": old_ids, "new": new_ids}
        if changes:
            obj.updated_at = utcnow()
            write_audit(self.db, user=user, action="update", entity_type="event",
                        entity_id=obj.id, field_changes=changes)
        self.db.commit()
        return self._to_out(obj)

    def delete(self, event_id: str, user) -> None:
        obj = self.db.get(Event, event_id)
        if obj is None:
            raise not_found("事件不存在")
        assert_org_visible(obj, user)
        self.db.delete(obj)          # event_file 由 ondelete CASCADE 清理
        write_audit(self.db, user=user, action="delete", entity_type="event",
                    entity_id=obj.id)
        self.db.commit()
