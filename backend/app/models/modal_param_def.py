from sqlalchemy import JSON, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ModalParamDef(Base):
    """单模态采集参数 Schema 字典表（批次事件组化改造 §2.2）。

    全局共享（参数语义为行业公共知识，不按组织隔离）；键名 = 渲染器与规则库按名读取的
    权威键（入 batch_modal_config.params），同 modality 内 param_key 唯一、发布后不可改名。
    """

    __tablename__ = "modal_param_def"
    __table_args__ = (UniqueConstraint("modality", "param_key",
                                       name="uq_modal_param_def"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    modality: Mapped[str] = mapped_column(String(16), nullable=False)  # 平台模态代码（enums.Modality）
    param_key: Mapped[str] = mapped_column(String(64), nullable=False)  # 权威键名（emissivity 等）
    label: Mapped[str] = mapped_column(String(64), nullable=False)     # 中文名（发射率）
    unit: Mapped[str | None] = mapped_column(String(32))
    value_type: Mapped[str] = mapped_column(String(16), nullable=False)  # float/int/str/bool/json
    required: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 可选/1 必填/2 条件必填
    min_value: Mapped[float | None] = mapped_column(Float)
    max_value: Mapped[float | None] = mapped_column(Float)
    enum_values: Mapped[list | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(String(256))
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
