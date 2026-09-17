from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FaultTypeDef(Base):
    """故障类型字典表（批次事件组化改造 §2.5）。

    对齐三级标签树第三级（故障类型）语义，admin 统一维护、普通用户只读；
    code 一经发布不可改名（入 EVT_ID 类型段），仅可停用（is_active=0）。
    """

    __tablename__ = "fault_type_def"
    __table_args__ = (UniqueConstraint("code", name="uq_fault_type_def_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)   # 英文 ID（大写下划线）
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # 中文层级串（齿轮箱-轴承-磨损）
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="故障")  # 默认严重度
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(512))
    creator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
