import io

from openpyxl import load_workbook

from tests.conftest import auth

STATE_PAYLOAD = {
    "batch_no": "B2025-009", "device_no": "F01", "device_model": "金风 GW82/1500",
    "station": "wind", "license": "内部专用", "sensitivity": "内部",
    "owner_contact": "张工", "is_synthetic": 0,
    "operating_condition": "正常", "weather": "晴", "equipment_state_type": "风电",
}


def test_create_batch_missing_state_type_422(client, user_token):
    r = client.post("/api/v1/batches", json={"batch_no": "B2025-009",
                                             "device_no": "F01"},
                    headers=auth(user_token))
    assert r.status_code == 422


def test_create_batch_invalid_state_type_422(client, user_token):
    payload = {**STATE_PAYLOAD, "equipment_state_type": "核电"}
    assert client.post("/api/v1/batches", json=payload,
                       headers=auth(user_token)).status_code == 422


def test_create_batch_with_state_type_ok(client, user_token):
    r = client.post("/api/v1/batches", json=STATE_PAYLOAD, headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["equipment_state_type"] == "风电"


def test_update_state_type(client, user_token, batch):
    r = client.put("/api/v1/batches/batch-1", json={"equipment_state_type": "光伏"},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["equipment_state_type"] == "光伏"


def test_list_modalities_aggregate_sorted(client, user_token, batch, files_fixture, db):
    """file-1 SCADA + file-2 AUD，另加 file-vib VIB → 按模态规范顺序去重排序。"""
    from app.models import DataFile
    from tests.conftest import utcnow

    db.add(DataFile(id="file-vib", batch_id="batch-1", batch_no="B2025-001",
                    object_key="wind/F01/vib/2025/06/vib.dat", filename="vib.dat",
                    file_size=100, modality="VIB", uploader_id="user-1",
                    upload_status="已完成", created_at=utcnow(), updated_at=utcnow()))
    db.commit()
    r = client.get("/api/v1/batches", headers=auth(user_token))
    item = next(b for b in r.json()["items"] if b["id"] == "batch-1")
    assert item["modalities"] == ["SCADA", "VIB", "AUD"]


def test_detail_modalities(client, user_token, batch, own_file):
    r = client.get("/api/v1/batches/batch-1", headers=auth(user_token))
    assert r.json()["modalities"] == ["SCADA"]


def test_empty_batch_modalities(client, user_token, batch):
    r = client.get("/api/v1/batches/batch-1", headers=auth(user_token))
    assert r.json()["modalities"] == []


def test_metadata_json_contains_state_type_and_modalities(client, db, own_file):
    from app.models import DataFile
    from app.services.archive import build_file_metadata

    meta = build_file_metadata(db, db.get(DataFile, "file-1"))
    assert meta["batch"]["equipment_state_type"] is None
    assert meta["batch"]["modalities"] == ["SCADA"]


def test_update_without_state_type_keeps_value(client, user_token, batch):
    r = client.put("/api/v1/batches/batch-1", json={"weather": "阴"},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["weather"] == "阴"
    assert r.json()["equipment_state_type"] is None   # 未传字段保持原值（null）


def test_update_empty_string_state_normalized_to_none(client, user_token, batch):
    r = client.put("/api/v1/batches/batch-1", json={"equipment_state_type": ""},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["equipment_state_type"] is None


def test_export_excel_contains_state_type_column(client, user_token, batch):
    r = client.get("/api/v1/batches/batch-1/export", headers=auth(user_token))
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.content))["批次说明表"]
    headers = [c.value for c in ws[1]]
    assert "数据对应设备:状态类型" in headers


def test_update_other_field_keeps_state_type(client, user_token, batch):
    """先置状态类型为风电，再 PUT 其他字段，断言状态类型不被覆盖。"""
    client.put("/api/v1/batches/batch-1", json={"equipment_state_type": "风电"},
               headers=auth(user_token))
    r = client.put("/api/v1/batches/batch-1", json={"weather": "阴"},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["equipment_state_type"] == "风电"


def test_list_modalities_distinct_dedup(client, user_token, batch, own_file, db):
    """同批次两个 SCADA 文件 → 列表聚合去重后只出现一次 SCADA。"""
    from app.models import DataFile
    from tests.conftest import utcnow

    db.add(DataFile(id="file-scada2", batch_id="batch-1", batch_no="B2025-001",
                    object_key="wind/F01/scada/2025/06/scada2.dat", filename="scada2.dat",
                    file_size=100, modality="SCADA", uploader_id="user-1",
                    upload_status="已完成", created_at=utcnow(), updated_at=utcnow()))
    db.commit()
    r = client.get("/api/v1/batches", headers=auth(user_token))
    item = next(b for b in r.json()["items"] if b["id"] == "batch-1")
    assert item["modalities"] == ["SCADA"]   # 去重后仅一个
