from pydantic import BaseModel, ConfigDict


class EventCreate(BaseModel):
    event_time: str
    timezone: str = "+08:00"
    device_no: str
    event_type: str
    severity: str
    description: str | None = None
    root_cause: str | None = None
    treatment: str | None = None
    treatment_result: str | None = None
    operating_condition: str | None = None
    related_file_ids: list[str] = []


class EventUpdate(BaseModel):
    event_time: str | None = None
    timezone: str | None = None
    device_no: str | None = None
    event_type: str | None = None
    severity: str | None = None
    description: str | None = None
    root_cause: str | None = None
    treatment: str | None = None
    treatment_result: str | None = None
    operating_condition: str | None = None
    related_file_ids: list[str] | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str | None = None
    event_time: str
    timezone: str
    device_no: str
    event_type: str
    severity: str
    description: str | None = None
    root_cause: str | None = None
    treatment: str | None = None
    treatment_result: str | None = None
    operating_condition: str | None = None
    creator_id: str | None = None
    creator_name: str | None = None
    created_at: str
    updated_at: str
    related_files: list[str] = []        # 关联文件 ID 列表（详情组装）
    related_file_count: int = 0
