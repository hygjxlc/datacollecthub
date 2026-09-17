from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BatchModalConfig(Base):
    """批次模态采集参数实例（批次事件组化改造 §2.3）。

    键=modal_param_def 权威键（发布不可改名），值按 def 校验后存储；
    (batch_id, modality) 1:1 唯一——同批同模态多次保存为覆盖（upsert）。
    """

    __tablename__ = "batch_modal_config"
    __table_args__ = (UniqueConstraint("batch_id", "modality",
                                       name="uq_batch_modal_config"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("batch.id", ondelete="CASCADE"), nullable=False)
    modality: Mapped[str] = mapped_column(String(16), nullable=False)  # 平台模态代码
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
