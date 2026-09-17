from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BatchNoRule(Base):
    """批次/事件编号规则表（全局单行，管理员配置）。

    template=批次编号模板（不含 {TYPE_CODE}）；evt_template=事件编号模板
    （{TYPE_CODE} 类型段专用，未配置时服务层用默认模板）。
    """

    __tablename__ = "batch_no_rule"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template: Mapped[str] = mapped_column(String(256), nullable=False)
    evt_template: Mapped[str | None] = mapped_column(String(256))
    updated_by: Mapped[str | None] = mapped_column(String(36))
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
