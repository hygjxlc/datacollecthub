"""MinioStorage presign 端点契约（架构 5.4/7.1）：

presigned URL 的 host 必须是 `MINIO_PUBLIC_ENDPOINT`（浏览器/FDL 可达的公共端点），
而非后端内网端点（minio:9000）——否则分片直传与下载在部署态不可用。
"""

from minio import Minio as MinioClient

from app.core.config import Settings


def _build_storage(monkeypatch, public_endpoint: str):
    # Minio() 构造不发网络请求；presign 会调 _get_region（发请求）→ monkeypatch 掉
    monkeypatch.setattr(MinioClient, "bucket_exists", lambda self, bucket: True)
    monkeypatch.setattr(MinioClient, "make_bucket", lambda self, bucket: None)
    monkeypatch.setattr(MinioClient, "_get_region", lambda self, bucket: "us-east-1")
    from app.storage.minio import MinioStorage

    cfg = Settings(minio_endpoint="minio:9000",
                   minio_access_key="minioadmin",
                   minio_secret_key="minioadmin",
                   minio_bucket="energydata-raw",
                   minio_public_endpoint=public_endpoint)
    return MinioStorage(cfg)


def test_presign_part_uses_public_endpoint(monkeypatch):
    storage = _build_storage(monkeypatch, "http://localhost:9000")
    url = storage.presign_part("wind/f01/scada/2025/06/a.dat", "upload-1", 1)
    assert url.startswith("http://localhost:9000/energydata-raw/")
    assert "minio:9000" not in url


def test_presign_get_uses_public_endpoint(monkeypatch):
    storage = _build_storage(monkeypatch, "https://data.example.com")
    url = storage.presign_get("wind/f01/scada/2025/06/a.dat", 3600)
    assert url.startswith("https://data.example.com/energydata-raw/")
    assert "X-Amz-Expires=3600" in url


def test_public_endpoint_default_port(monkeypatch):
    # 无显式端口时按 scheme 补默认端口（SDK 对 80/443 会省略输出）
    storage = _build_storage(monkeypatch, "http://data.example.com")
    url = storage.presign_get("k", 3600)
    assert url.startswith("http://data.example.com/")
    assert "minio:9000" not in url


def test_public_client_inherits_region(monkeypatch):
    # 构造函数 region 参数使 presign 的 _get_region 直接返回，
    # 不向公共端点发 GetBucketLocation（容器内公共端点不可达）
    storage = _build_storage(monkeypatch, "http://localhost:9000")
    assert storage._public_client._base_url.region == "us-east-1"
