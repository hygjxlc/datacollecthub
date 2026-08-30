from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DataFile(Base):
    """数据文件表（架构设计 4.4）：object_key 全局唯一，原始区永不覆盖。"""

    __tablename__ = "data_file"
    __table_args__ = (UniqueConstraint("object_key", name="ux_datafile_object_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("batch.id", ondelete="SET NULL"))
    batch_no: Mapped[str | None] = mapped_column(String(64))          # 批次字段快照（F6 继承）
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[str | None] = mapped_column(String(128))
    modality: Mapped[str] = mapped_column(String(16), nullable=False)  # 8 类模态代码
    # 批次级字段快照（上传时拷贝，不随批次修改追溯）
    device_no: Mapped[str | None] = mapped_column(String(64))
    station: Mapped[str | None] = mapped_column(String(128))
    license: Mapped[str | None] = mapped_column(String(32))
    sensitivity: Mapped[str | None] = mapped_column(String(16))
    is_synthetic: Mapped[int | None] = mapped_column(Integer)
    operating_condition: Mapped[str | None] = mapped_column(String(256))
    weather: Mapped[str | None] = mapped_column(String(128))
    # 文件级元数据（F5 手动补填）
    start_time: Mapped[str | None] = mapped_column(String(32))        # 设备本地时间
    end_time: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str | None] = mapped_column(String(32))          # 缺失 = 时间不可用
    sample_period: Mapped[str | None] = mapped_column(String(64))
    data_amount: Mapped[str | None] = mapped_column(String(32))
    record_count: Mapped[str | None] = mapped_column(String(32))
    duration: Mapped[str | None] = mapped_column(String(32))
    uploader_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"))
    upload_status: Mapped[str] = mapped_column(String(16), nullable=False, default="已完成")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
