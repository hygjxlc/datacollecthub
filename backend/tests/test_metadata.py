"""任务 5：F5 元数据编辑/审计、F6 快照继承（已有 upload 测试覆盖）、F7 检索/Excel 导出/下载。"""

import json

from app.models import AuditLog

from tests.conftest import auth


def test_update_metadata_requires_timezone(client, user_token, own_file):
    r = client.put(f"/api/v1/files/{own_file.id}",
                   json={"start_time": "2025-06-15 14:23:08", "sample_period": "1s"},
                   headers=auth(user_token))
    assert r.status_code == 422          # timezone 留空 = 时间不可用，拒绝


def test_update_own_file_writes_audit(client, user_token, own_file, db):
    r = client.put(f"/api/v1/files/{own_file.id}",
                   json={"timezone": "+08:00", "sample_period": "25.6kHz"},
                   headers=auth(user_token))
    assert r.status_code == 200
    log = db.query(AuditLog).filter_by(
        entity_type="datafile", entity_id=own_file.id, action="update").one()
    assert json.loads(log.field_changes)["sample_period"]["old"] == "1s"


def test_update_others_file_403(client, other_user_token, own_file):
    r = client.put(f"/api/v1/files/{own_file.id}",
                   json={"timezone": "+08:00"}, headers=auth(other_user_token))
    assert r.status_code == 403


def test_delete_others_file_403_and_object_kept(client, other_user_token, own_file, storage):
    assert client.delete(f"/api/v1/files/{own_file.id}",
                         headers=auth(other_user_token)).status_code == 403
    assert storage.exists(own_file.object_key) is True


def test_delete_own_file_removes_object(client, user_token, own_file, storage):
    r = client.delete(f"/api/v1/files/{own_file.id}", headers=auth(user_token))
    assert r.status_code == 200
    assert storage.exists(own_file.object_key) is False


def test_search_filters(client, user_token, files_fixture):
    r = client.get("/api/v1/files",
                   params={"modality": "SCADA", "batch_no": "B2025-001"},
                   headers=auth(user_token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all(f["modality"] == "SCADA" for f in body["items"])
    # 他单位文件不可见
    assert all(f["id"] != "file-3" for f in body["items"])


def test_search_hides_other_org(client, user_token, files_fixture):
    r = client.get("/api/v1/files", headers=auth(user_token))
    assert r.status_code == 200
    assert {f["id"] for f in r.json()["items"]} == {"file-1", "file-2"}


def test_get_download_url(client, user_token, own_file):
    r = client.get(f"/api/v1/files/{own_file.id}/download", headers=auth(user_token))
    assert r.status_code == 200
    body = r.json()
    assert body["download_url"].startswith("http")
    assert body["expires_in"] == 3600


def test_export_two_sheets(client, user_token, batch_with_file):
    r = client.get(f"/api/v1/batches/{batch_with_file.id}/export",
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
