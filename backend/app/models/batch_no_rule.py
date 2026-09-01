from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BatchNoRule(Base):
    """批次编号规则表（全局单行，管理员配置）。"""

    __tablename__ = "batch_no_rule"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template: Mapped[str] = mapped_column(String(256), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36))
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
