from sqlalchemy import JSON, ForeignKey, Integer, String, Text
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
    operating_condition: Mapped[str | None] = mapped_column(String(256))  # 退役轴：仅兼容推断（不落库）
    # 事件组化三态主轴（§3.1 规则 1-7）：event_type 必填三态，故障联动字典字段
    event_type: Mapped[str] = mapped_column(String(16), nullable=False, default="正常")
    fault_type: Mapped[str | None] = mapped_column(String(64))   # 故障类型字典 code（故障时缺省 UNCLASSIFIED）
    severity: Mapped[str | None] = mapped_column(String(16))     # 报警/故障/事故（缺省取字典行默认）
    t_start: Mapped[str | None] = mapped_column(String(32))      # 异常区间开始（成对可选）
    t_end: Mapped[str | None] = mapped_column(String(32))        # 异常区间结束（成对可选）
    event_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    evt_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # 事件组 ID：类型段×设备×年 001 起
    fault_time: Mapped[str | None] = mapped_column(String(32))   # 故障发生时间（事件类型=故障 必填）
    fault_desc: Mapped[str | None] = mapped_column(Text)         # 事件描述（故障必填；维修内容/正常基线说明）
    weather: Mapped[str | None] = mapped_column(String(128))
    equipment_state_type: Mapped[str | None] = mapped_column(String(16))  # 风电/光伏/火电/其它
    extras: Mapped[dict | None] = mapped_column(JSON)              # 批次扩展键值对（自由扩充）
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"))
    creator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
