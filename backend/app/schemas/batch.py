from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.enums import EquipmentStateType


class BatchCreate(BaseModel):
    batch_no: str
    device_no: str
    device_model: str | None = None
    station: str | None = None
    license: str | None = None
    sensitivity: str | None = None
    owner_contact: str | None = None
    is_synthetic: int = 0
    operating_condition: str | None = None
    weather: str | None = None
    equipment_state_type: EquipmentStateType
    extras: dict | None = None


class BatchUpdate(BaseModel):
    batch_no: str | None = None
    device_no: str | None = None
    device_model: str | None = None
    station: str | None = None
    license: str | None = None
    sensitivity: str | None = None
    owner_contact: str | None = None
    is_synthetic: int | None = None
    operating_condition: str | None = None
    weather: str | None = None
    equipment_state_type: EquipmentStateType | None = None
    extras: dict | None = None

    @field_validator("equipment_state_type", mode="before")
    @classmethod
    def _empty_state_to_none(cls, v):
        return None if v == "" else v


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_no: str
    device_no: str
    device_model: str | None = None
    station: str | None = None
    license: str | None = None
    sensitivity: str | None = None
    owner_contact: str | None = None
    is_synthetic: int
    operating_condition: str | None = None
    weather: str | None = None
    equipment_state_type: str | None = None
    extras: dict | None = None
    modalities: list[str] = []   # 只读聚合：批次下文件 modality 去重（按模态规范顺序）
    organization_id: str | None = None
    creator_id: str | None = None
    file_count: int = 0          # 列表页聚合（文件数）
    total_size: int = 0          # 列表页聚合（数据量，字节）
    created_at: str
    updated_at: str
