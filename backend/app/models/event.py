from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Event(Base):
    """事件/故障记录：多模态事件组数据集的锚点。"""

    __tablename__ = "event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"))
    event_time: Mapped[str] = mapped_column(String(32), nullable=False)  # 设备本地时间
    timezone: Mapped[str] = mapped_column(String(32), nullable=False, default="+08:00")
    device_no: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)  # 层级字符串
    severity: Mapped[str] = mapped_column(String(16), nullable=False)     # 报警/故障/事故
    description: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)           # 根因分析
    treatment: Mapped[str | None] = mapped_column(Text)            # 处置措施
    treatment_result: Mapped[str | None] = mapped_column(Text)     # 处置效果
    operating_condition: Mapped[str | None] = mapped_column(Text)  # 工况环境
    creator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class EventFile(Base):
    """事件-文件多对多关联（支持双向查询，随事件级联删除）。"""

    __tablename__ = "event_file"
    __table_args__ = (UniqueConstraint("event_id", "datafile_id",
                                       name="ux_event_file"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("event.id", ondelete="CASCADE"), nullable=False)
    datafile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_file.id", ondelete="CASCADE"), nullable=False)
