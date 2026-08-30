import json
import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.services.common import utcnow


def write_audit(db: Session, *, user=None, action: str, entity_type: str,
                entity_id: str | None = None, field_changes: dict | None = None,
                source: str = "web", params_summary: str | None = None) -> None:
    """审计留痕（与业务同事务提交；集成调用 user=None）。"""
    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        field_changes=json.dumps(field_changes, ensure_ascii=False) if field_changes else None,
        source=source,
        params_summary=params_summary,
        created_at=utcnow(),
    )
    db.add(log)
