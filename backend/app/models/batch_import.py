from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BatchImport(Base):
    """批量导入任务：zip 包（第一层子目录=一个批次）→ 多批次+文件入库。"""

    __tablename__ = "batch_import"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # pending/running/succeeded/failed
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"))
    creator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"))
    total_batches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done_batches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
