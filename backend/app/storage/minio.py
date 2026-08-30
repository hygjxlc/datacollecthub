"""对象存储抽象层（架构 5.1/5.2）。

- `MinioStorage`：生产实现。multipart 采用「分片独立对象 + compose 合并」方式，
  全程使用 MinIO SDK 公开 API（presigned PUT / compose_object / remove_objects），
  无服务端上传状态；「上传中」状态仅存在于前端 localStorage。
- `FakeStorage`：测试实现，dict 内存语义等价。
"""

import io
import uuid
from datetime import timedelta
from typing import BinaryIO, Protocol
from urllib.parse import urlparse

from minio import Minio
from minio.commonconfig import ComposeSource
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from app.core.config import Settings, settings


class NoSuchUploadError(Exception):
    """上传会话不存在或已过期。"""


class ObjectStorage(Protocol):
    def create_multipart(self, object_key: str) -> str: ...
    def presign_part(self, object_key: str, upload_id: str, part_number: int) -> str: ...
    def complete_multipart(self, object_key: str, upload_id: str,
                           parts: list[dict]) -> None: ...
    def presign_get(self, object_key: str, expires_seconds: int) -> str: ...
    def delete_object(self, object_key: str) -> None: ...
    def exists(self, object_key: str) -> bool: ...
    def get_object_stream(self, object_key: str) -> BinaryIO: ...


def part_object_key(object_key: str, upload_id: str, part_number: int) -> str:
    return f"{object_key}.parts/{upload_id}/{part_number:05d}"


class MinioStorage:
    def __init__(self, cfg: Settings = settings):
        self._client = Minio(cfg.minio_endpoint,
                             access_key=cfg.minio_access_key,
                             secret_key=cfg.minio_secret_key, secure=False)
        self._bucket = cfg.minio_bucket
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
        # presign 专用 client：URL 的 host 用公共端点（浏览器/FDL 可达），签名与之一致。
        # 后端实际请求仍走内网 client（minio:9000），两者互不影响（架构 5.4/7.1）。
        # region 从内网 client 查询后传入：SDK 构造函数带 region 时 presign 的
        # _get_region 直接返回，不会向公共端点发起 GetBucketLocation（容器内不可达）。
        p = urlparse(cfg.minio_public_endpoint)
        port = p.port or (443 if p.scheme == "https" else 80)
        region = self._client._get_region(self._bucket)
        self._public_client = Minio(f"{p.hostname}:{port}",
                                    access_key=cfg.minio_access_key,
                                    secret_key=cfg.minio_secret_key,
                                    secure=(p.scheme == "https"),
                                    region=region)

    def create_multipart(self, object_key: str) -> str:
        return str(uuid.uuid4())

    def presign_part(self, object_key: str, upload_id: str, part_number: int) -> str:
        return self._public_client.presigned_put_object(
            self._bucket, part_object_key(object_key, upload_id, part_number))

    def complete_multipart(self, object_key: str, upload_id: str,
                           parts: list[dict]) -> None:
        keys = [part_object_key(object_key, upload_id, p["part_number"])
                for p in sorted(parts, key=lambda x: x["part_number"])]
        if not keys:
            raise NoSuchUploadError("空分片列表")
        # minio SDK 要求 ComposeSource 对象（传字符串 key 会报
        # "sources[0] must be ComposeSource type"）
        sources = [ComposeSource(self._bucket, k) for k in keys]
        # 分片对象缺失时 compose 会抛错，由调用方捕获转 400
        self._client.compose_object(self._bucket, object_key, sources)
        errors = self._client.remove_objects(
            self._bucket, [DeleteObject(k) for k in keys])
        for err in errors:
            if err is not None:
                raise NoSuchUploadError("分片清理失败")

    def presign_get(self, object_key: str, expires_seconds: int) -> str:
        # minio SDK 要求 timedelta（传 int 会在真实 MinIO 下报 AttributeError）
        return self._public_client.presigned_get_object(
            self._bucket, object_key,
            expires=timedelta(seconds=expires_seconds))

    def delete_object(self, object_key: str) -> None:
        self._client.remove_object(self._bucket, object_key)

    def exists(self, object_key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except Exception:
            return False

    def get_object_stream(self, object_key: str):
        """流式读取对象；缺失时抛 KeyError（供 zip 打包逐文件失败处理）。"""
        try:
            return self._client.get_object(self._bucket, object_key)
        except S3Error:
            raise KeyError(object_key)


class FakeStorage:
    """内存实现：multipart 语义与 MinioStorage 等价（compose = 分片拼接）。"""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.multiparts: dict[str, tuple[str, dict[int, bytes]]] = {}

    def create_multipart(self, object_key: str) -> str:
        upload_id = f"upload-{uuid.uuid4()}"
        self.multiparts[upload_id] = (object_key, {})
        return upload_id

    def presign_part(self, object_key: str, upload_id: str, part_number: int) -> str:
        return (f"http://fake-minio/{part_object_key(object_key, upload_id, part_number)}"
                f"?uploadId={upload_id}&partNumber={part_number}")

    def complete_multipart(self, object_key: str, upload_id: str,
                           parts: list[dict]) -> None:
        mp = self.multiparts.pop(upload_id, None)
        if mp is None or mp[0] != object_key:
            raise NoSuchUploadError("上传会话不存在或已过期")
        self.objects[object_key] = b""

    def presign_get(self, object_key: str, expires_seconds: int) -> str:
        return f"http://fake-minio/{object_key}?X-Amz-Expires={expires_seconds}"

    def delete_object(self, object_key: str) -> None:
        self.objects.pop(object_key, None)

    def exists(self, object_key: str) -> bool:
        return object_key in self.objects

    def get_object_stream(self, object_key: str):
        if object_key not in self.objects:
            raise KeyError(object_key)
        return io.BytesIO(self.objects[object_key])


_default_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    """FastAPI 依赖：测试通过 dependency_overrides 注入 FakeStorage。"""
    global _default_storage
    if _default_storage is None:
        _default_storage = MinioStorage()
    return _default_storage
