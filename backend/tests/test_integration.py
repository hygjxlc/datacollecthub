"""任务 6：F8 集成接口（无认证只读 / 条件查询 ID / 按 ID 读取 / 打包下载 / 审计）。"""

import io
import json
import zipfile

from app.models import AuditLog


def test_no_auth_required(client):
    assert client.get("/api/v1/integration/files/ids").status_code == 200


def test_filter_by_uploaded_time(client, files_fixture):
    r = client.get("/api/v1/integration/files/ids",
                   params={"uploaded_after": "2026-08-27T00:00:00Z"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_filter_by_occurred_time(client, files_fixture):
    # occurred_* 作用于 start_time；start_time 为空的文件不命中
    r = client.get("/api/v1/integration/files/ids",
                   params={"occurred_after": "2025-06-15T14:00:00",
                           "occurred_before": "2025-06-15T16:00:00"})
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert set(ids) == {"file-1"}


def test_modalities_multi(client, files_fixture):
    assert client.get("/api/v1/integration/files/ids",
                      params={"modalities": "SCADA,VIB,AUD"}).status_code == 200


def test_modalities_invalid_422(client):
    assert client.get("/api/v1/integration/files/ids",
                      params={"modalities": "XXX"}).status_code == 422


def test_pagination_no_dup(client, many_files):
    seen, offset = set(), 0
    body = client.get("/api/v1/integration/files/ids",
                      params={"limit": 1000, "offset": offset}).json()
    total = body["total"]
    while True:
        body = client.get("/api/v1/integration/files/ids",
                          params={"limit": 1000, "offset": offset}).json()
        assert body["total"] == total          # 翻页期间总数不变
        for it in body["items"]:
            assert it["id"] not in seen
            seen.add(it["id"])
        if body["next_offset"] >= body["total"]:
            break
        offset = body["next_offset"]
    assert len(seen) == total


def test_get_by_id_returns_metadata_and_url(client, files_fixture, storage):
    r = client.get("/api/v1/integration/files/file-1")
    assert r.status_code == 200
    body = r.json()
    assert body["metadata"]["file"]["filename"] == "SCADA_F01_20250615_1423.dat"
    assert body["metadata"]["batch"]["batch_no"] == "B2025-001"   # 文件级+批次级合并
    assert body["download_url"].startswith("http")
    assert body["expires_in"] == 3600


def test_get_missing_404(client):
    assert client.get("/api/v1/integration/files/no-such-id").status_code == 404


def test_download_zip_with_metadata(client, files_fixture):
    """集成导出：zip 内文件夹结构 + 原始数据 + 元数据 JSON（与认证下载一致）。"""
    r = client.get("/api/v1/integration/files/file-1/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert set(zf.namelist()) == {
        "SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat",
        "SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat.json",
    }
    assert zf.read("SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat") == b"file-content"
    meta = json.loads(zf.read("SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat.json"))
    assert meta["file"]["filename"] == "SCADA_F01_20250615_1423.dat"
    assert meta["batch"]["batch_no"] == "B2025-001"


def test_download_missing_404(client):
    assert client.get("/api/v1/integration/files/no-such-id/download").status_code == 404


def test_write_methods_not_allowed(client):
    assert client.post("/api/v1/integration/files/ids").status_code == 405


def test_integration_call_audited(client, db, files_fixture):
    client.get("/api/v1/integration/files/ids", params={"modalities": "SCADA"})
    log = db.query(AuditLog).filter_by(
        source="integration").order_by(AuditLog.created_at.desc()).first()
    assert log is not None
    assert "SCADA" in log.params_summary


def test_get_file_metadata_with_ledger(client, files_fixture, nameplate,
                                       point_dict, event):
    """集成查询 metadata 与打包 JSON 同结构（含台账 3 字段）。"""
    resp = client.get("/api/v1/integration/files/file-1")
    assert resp.status_code == 200
    meta = resp.json()["metadata"]
    assert meta["file"]["filename"] == "SCADA_F01_20250615_1423.dat"
    assert meta["batch"]["batch_no"] == "B2025-001"
    assert meta["nameplate"]["device_no"] == "F01"
    assert len(meta["point_dicts"]) == 2
    assert len(meta["related_events"]) == 1
