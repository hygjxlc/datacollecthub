from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditLog(Base):
    """审计日志表（架构设计 4.5）：字段级 old→new 变更留痕 + 集成调用留痕。"""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36))          # 集成调用为 None
    username: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # create/update/delete/query/download
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    field_changes: Mapped[str | None] = mapped_column(String(4000))  # JSON 文本 old→new
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="web")  # web/integration
    params_summary: Mapped[str | None] = mapped_column(String(512))  # 集成调用参数摘要
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
