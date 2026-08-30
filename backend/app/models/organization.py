from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Organization(Base):
    """单位表（架构设计 4.1）。"""

    __tablename__ = "organization"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)   # 场站/电厂/运维单位
    contact_person: Mapped[str | None] = mapped_column(String(64))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)   # ISO-8601 UTC
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
