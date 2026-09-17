from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MODALITIES = Literal["SCADA", "VIB", "AUD", "IR", "CAM", "VID", "TXT", "RPT"]
# 平台 8 类模态代码（enums.Modality / SRS 4.6，与 DataFile.modality 同域——batch_modal_config
# 实例按批次模态聚合值匹配字典，Phase 0 执行修正：§2.2 原书"TC609 模态代码"与平台域不符）
SEVERITIES = Literal["报警", "故障", "事故"]
VALUE_TYPES = Literal["float", "int", "str", "bool", "json"]


# ---------- fault_type_def ----------

class FaultTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(min_length=1, max_length=128)
    severity: SEVERITIES = "故障"
    is_active: int = Field(default=1, ge=0, le=1)
    sort_no: int = Field(default=0)
    description: str | None = Field(default=None, max_length=512)


class FaultTypeUpdate(BaseModel):
    """code 不入可更新集——发布后不可改名（改名=换 EVT_ID 语义段）。"""
    name: str | None = Field(default=None, min_length=1, max_length=128)
    severity: SEVERITIES | None = None
    is_active: int | None = Field(default=None, ge=0, le=1)
    sort_no: int | None = None
    description: str | None = Field(default=None, max_length=512)


class FaultTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    severity: str
    is_active: int
    sort_no: int
    description: str | None = None
    creator_id: str | None = None
    created_at: str
    updated_at: str


# ---------- modal_param_def ----------

class ModalParamCreate(BaseModel):
    modality: MODALITIES
    param_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    value_type: VALUE_TYPES
    required: int = Field(default=0, ge=0, le=2)
    min_value: float | None = None
    max_value: float | None = None
    enum_values: list | None = None
    description: str | None = Field(default=None, max_length=256)
    sort_no: int = Field(default=0)


class ModalParamUpdate(BaseModel):
    """modality/param_key 不入可更新集——权威键名发布后不可改名（渲染器按名读取）。"""
    label: str | None = Field(default=None, min_length=1, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    value_type: VALUE_TYPES | None = None
    required: int | None = Field(default=None, ge=0, le=2)
    min_value: float | None = None
    max_value: float | None = None
    enum_values: list | None = None
    description: str | None = Field(default=None, max_length=256)
    sort_no: int | None = None


class ModalParamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    modality: str
    param_key: str
    label: str
    unit: str | None = None
    value_type: str
    required: int
    min_value: float | None = None
    max_value: float | None = None
    enum_values: list | None = None
    description: str | None = None
    sort_no: int
    created_at: str
    updated_at: str
