from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Batch(Base):
    """批次表（架构设计 4.3）：同一设备、同一模态组、同一采集参数、同一时段连续采集。"""

    __tablename__ = "batch"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    device_no: Mapped[str] = mapped_column(String(64), nullable=False)
    device_model: Mapped[str | None] = mapped_column(String(128))
    station: Mapped[str | None] = mapped_column(String(128))      # 场站名（object_key 段）
    license: Mapped[str | None] = mapped_column(String(32))       # 内部专用/CC-BY/MIT
    sensitivity: Mapped[str | None] = mapped_column(String(16))   # 公开/内部/机密
    owner_contact: Mapped[str | None] = mapped_column(String(64))
    is_synthetic: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operating_condition: Mapped[str | None] = mapped_column(String(256))
    weather: Mapped[str | None] = mapped_column(String(128))
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"))
    creator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
