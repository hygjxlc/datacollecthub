from pydantic import BaseModel, ConfigDict


class BatchImportCreate(BaseModel):
    object_key: str


class BatchImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    object_key: str
    organization_id: str | None = None
    creator_id: str | None = None
    total_batches: int
    done_batches: int
    report: dict | None = None
    created_at: str
    updated_at: str
