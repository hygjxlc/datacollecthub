from pydantic import BaseModel


class UploadInitRequest(BaseModel):
    filename: str
    file_size: int


class PartInfo(BaseModel):
    part_number: int
    url: str


class UploadInitResponse(BaseModel):
    upload_id: str
    object_key: str
    part_size: int
    parts: list[PartInfo]


class PartDone(BaseModel):
    part_number: int
    etag: str | None = None


class UploadCompleteRequest(BaseModel):
    object_key: str
    filename: str
    file_size: int
    checksum: str | None = None
    parts: list[PartDone]
