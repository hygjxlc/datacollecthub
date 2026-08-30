from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PointDict(Base):
    """测点字典：SCADA 通道号 → 物理量/单位/缩放系数（physical = raw * slope + offset）。
    （注：organization_id 可空，单位删除后置 NULL 时唯一约束失效，由应用层保证台账归属）"""

    __tablename__ = "point_dict"
    __table_args__ = (UniqueConstraint("organization_id", "device_no", "channel_no",
                                       name="ux_pointdict_org_device_channel"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"))
    device_no: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_no: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)    # 物理量名称
    unit: Mapped[str | None] = mapped_column(String(32))
    scale_slope: Mapped[float | None] = mapped_column(Float)
    scale_offset: Mapped[float | None] = mapped_column(Float)
    data_type: Mapped[str | None] = mapped_column(String(16))         # float/int/string/boolean
    range_min: Mapped[float | None] = mapped_column(Float)
    range_max: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(String(512))
    creator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
