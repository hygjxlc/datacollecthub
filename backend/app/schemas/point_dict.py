from pydantic import BaseModel, ConfigDict


class PointDictCreate(BaseModel):
    device_no: str
    channel_no: str
    name: str
    unit: str | None = None
    scale_slope: float | None = None
    scale_offset: float | None = None
    data_type: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    description: str | None = None


class PointDictUpdate(BaseModel):
    device_no: str | None = None
    channel_no: str | None = None
    name: str | None = None
    unit: str | None = None
    scale_slope: float | None = None
    scale_offset: float | None = None
    data_type: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    description: str | None = None


class PointDictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str | None = None
    device_no: str
    channel_no: str
    name: str
    unit: str | None = None
    scale_slope: float | None = None
    scale_offset: float | None = None
    data_type: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    description: str | None = None
    creator_id: str | None = None
    creator_name: str | None = None
    created_at: str
    updated_at: str
