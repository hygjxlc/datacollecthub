from pydantic import BaseModel, ConfigDict


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
    organization_id: str | None = None
    creator_id: str | None = None
    file_count: int = 0          # 列表页聚合（文件数）
    total_size: int = 0          # 列表页聚合（数据量，字节）
    created_at: str
    updated_at: str
