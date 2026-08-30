from sqlalchemy import JSON, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Nameplate(Base):
    """设备铭牌台账：每设备一条，供物理规则库参数标定。
    （注：organization_id 可空，单位删除后置 NULL 时唯一约束失效，由应用层保证台账归属）"""

    __tablename__ = "nameplate"
    __table_args__ = (UniqueConstraint("organization_id", "device_no",
                                       name="ux_nameplate_org_device"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"))
    device_no: Mapped[str] = mapped_column(String(64), nullable=False)
    device_model: Mapped[str | None] = mapped_column(String(128))
    rated_power: Mapped[float | None] = mapped_column(Float)          # kW
    rated_wind_speed: Mapped[float | None] = mapped_column(Float)     # m/s
    rotor_diameter: Mapped[float | None] = mapped_column(Float)       # m
    hub_height: Mapped[float | None] = mapped_column(Float)           # m
    bearing_model: Mapped[str | None] = mapped_column(String(128))
    gearbox_ratio: Mapped[float | None] = mapped_column(Float)
    generator_model: Mapped[str | None] = mapped_column(String(128))
    manufacturer: Mapped[str | None] = mapped_column(String(128))
    commission_date: Mapped[str | None] = mapped_column(String(10))   # YYYY-MM-DD
    design_life_years: Mapped[int | None] = mapped_column(Integer)
    extras: Mapped[dict | None] = mapped_column(JSON)                 # 规则库扩展键值对
    creator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
