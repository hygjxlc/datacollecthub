from pydantic import BaseModel, ConfigDict


class DataFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str | None = None
    batch_no: str | None = None
    object_key: str
    filename: str
    file_size: int
    checksum: str | None = None
    modality: str
    device_no: str | None = None
    station: str | None = None
    license: str | None = None
    sensitivity: str | None = None
    is_synthetic: int | None = None
    operating_condition: str | None = None
    weather: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    timezone: str | None = None
    sample_period: str | None = None
    data_amount: str | None = None
    record_count: str | None = None
    duration: str | None = None
    uploader_id: str | None = None
    upload_status: str
    created_at: str
    updated_at: str


class DataFileUpdate(BaseModel):
    """F5 元数据手动补填（全部文件级字段）。"""

    start_time: str | None = None
    end_time: str | None = None
    timezone: str | None = None
    sample_period: str | None = None
    data_amount: str | None = None
    record_count: str | None = None
    duration: str | None = None


class BatchDownloadReq(BaseModel):
    """批量打包下载（TC-DOWNLOAD）：一次最多 20 个文件。"""

    ids: list[str]
