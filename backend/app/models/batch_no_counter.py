from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BatchNoCounter(Base):
    """批次编号计数器：counter_key=模板固定部分+日期维度（+设备维度），原子自增。"""

    __tablename__ = "batch_no_counter"

    counter_key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
