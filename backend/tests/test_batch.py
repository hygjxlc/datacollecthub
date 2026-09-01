import json

from tests.conftest import auth

BATCH_PAYLOAD = {
    "batch_no": "B2025-001",
    "device_no": "F01",
    "device_model": "金风 GW82/1500",
    "station": "wind",
    "license": "内部专用",
    "sensitivity": "内部",
    "owner_contact": "张工",
    "is_synthetic": 0,
    "operating_condition": "正常",
    "weather": "晴",
    "equipment_state_type": "风电",
}


def test_create_batch_ok(client, user_token):
    r = client.post("/api/v1/batches", json=BATCH_PAYLOAD, headers=auth(user_token))
    assert r.status_code == 200
    body = r.json()
    assert body["batch_no"] == "B2025-001"
    assert body["organization_id"] == "org-1"      # 单位取自当前用户
    assert body["creator_id"] == "user-1"          # 创建者取自当前用户


def test_create_duplicate_batch_no_422(client, user_token, batch):
    r = client.post("/api/v1/batches", json=BATCH_PAYLOAD, headers=auth(user_token))
    assert r.status_code == 422


def test_list_only_own_org(client, user_token, batch, other_org_batch):
    r = client.get("/api/v1/batches", headers=auth(user_token))
    assert r.status_code == 200
    ids = {b["id"] for b in r.json()["items"]}
    assert ids == {"batch-1"}                       # org-2 的批次不可见（TC-BATCH-003）


def test_admin_list_all(client, admin_token, batch, other_org_batch):
    r = client.get("/api/v1/batches", headers=auth(admin_token))
    assert {b["id"] for b in r.json()["items"]} == {"batch-1", "batch-2"}


def test_cross_org_detail_404(client, user_token, other_org_batch):
    r = client.get("/api/v1/batches/batch-2", headers=auth(user_token))
    assert r.status_code == 404                       # 跨单位隐藏（不泄露存在性）


def test_get_own_batch_ok(client, user_token, batch):
    r = client.get("/api/v1/batches/batch-1", headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["device_no"] == "F01"


def test_edit_only_creator_403(client, other_user_token, batch):
    r = client.put("/api/v1/batches/batch-1", json={"weather": "多云"},
                   headers=auth(other_user_token))
    assert r.status_code == 403                       # li 与 zhang 同单位但非创建者


def test_admin_can_edit_any(client, admin_token, batch):
    r = client.put("/api/v1/batches/batch-1", json={"weather": "多云"},
                   headers=auth(admin_token))
    assert r.status_code == 200


def test_update_writes_audit_field_changes(client, user_token, batch, db):
    from app.models import AuditLog

    client.put("/api/v1/batches/batch-1", json={"weather": "多云"}, headers=auth(user_token))
    log = db.query(AuditLog).filter_by(entity_type="batch", entity_id="batch-1",
                                       action="update").one()
    changes = json.loads(log.field_changes)
    assert changes["weather"] == {"old": "晴", "new": "多云"}
    assert log.username == "zhang"


def test_create_writes_audit(client, user_token, db):
    from app.models import AuditLog

    client.post("/api/v1/batches", json=BATCH_PAYLOAD, headers=auth(user_token))
    log = db.query(AuditLog).filter_by(entity_type="batch", action="create").one()
    assert log.entity_id
    assert log.username == "zhang"


def test_delete_empty_batch_by_creator_ok(client, user_token, batch):
    r = client.delete("/api/v1/batches/batch-1", headers=auth(user_token))
    assert r.status_code == 200
    assert client.get("/api/v1/batches/batch-1", headers=auth(user_token)).status_code == 404


def test_delete_nonempty_batch_rejected(client, user_token, batch, db):
    from app.models import DataFile
    from tests.conftest import utcnow

    df = DataFile(id="file-1", batch_id="batch-1", batch_no="B2025-001",
                  object_key="wind/f01/scada/2025/06/f.dat", filename="f.dat",
                  file_size=100, modality="SCADA", uploader_id="user-1",
                  upload_status="已完成", created_at=utcnow(), updated_at=utcnow())
    db.add(df)
    db.commit()
    r = client.delete("/api/v1/batches/batch-1", headers=auth(user_token))
    assert r.status_code == 400


def test_delete_batch_by_non_creator_403(client, other_user_token, batch):
    assert client.delete("/api/v1/batches/batch-1",
                         headers=auth(other_user_token)).status_code == 403


def test_list_batches_has_file_count(client, user_token, batch, own_file):
    """架构 3.1：批次列表需文件数与数据量（file_count）。"""
    r = client.get("/api/v1/batches", headers=auth(user_token))
    assert r.status_code == 200
    item = next(b for b in r.json()["items"] if b["id"] == "batch-1")
    assert item["file_count"] == 1
    assert item["total_size"] == 5242880
