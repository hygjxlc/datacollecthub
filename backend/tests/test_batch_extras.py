from tests.conftest import auth

BASE = {
    "batch_no": "B2025-010", "device_no": "F01", "license": "内部专用",
    "sensitivity": "内部", "is_synthetic": 0, "equipment_state_type": "风电",
}


def test_create_batch_with_extras(client, user_token):
    r = client.post("/api/v1/batches", json={**BASE, "extras": {"采集周期": "10min"}},
                    headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["extras"] == {"采集周期": "10min"}


def test_update_extras(client, user_token, batch):
    r = client.put("/api/v1/batches/batch-1", json={"extras": {"塔高": 80}},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["extras"] == {"塔高": 80}


def test_update_extras_clear_with_empty_dict(client, user_token, batch):
    r = client.put("/api/v1/batches/batch-1", json={"extras": {}},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["extras"] is None


def test_extras_key_conflict_with_fixed_field_422(client, user_token):
    r = client.post("/api/v1/batches", json={**BASE, "extras": {"device_no": "x"}},
                    headers=auth(user_token))
    assert r.status_code == 422


def test_extras_nested_value_rejected_422(client, user_token):
    for bad in [{"a": {"b": 1}}, {"a": [1, 2]}]:
        r = client.post("/api/v1/batches", json={**BASE, "extras": bad},
                        headers=auth(user_token))
        assert r.status_code == 422


def test_extras_too_many_keys_422(client, user_token):
    extras = {f"k{i}": str(i) for i in range(21)}
    r = client.post("/api/v1/batches", json={**BASE, "extras": extras},
                    headers=auth(user_token))
    assert r.status_code == 422


def test_extras_key_too_long_422(client, user_token):
    r = client.post("/api/v1/batches", json={**BASE, "extras": {"x" * 65: "v"}},
                    headers=auth(user_token))
    assert r.status_code == 422


def test_metadata_json_contains_extras(client, db, batch, own_file):
    from app.models import DataFile
    from app.services.archive import build_file_metadata

    batch.extras = {"采集周期": "10min"}
    db.commit()
    meta = build_file_metadata(db, db.get(DataFile, "file-1"))
    assert meta["batch"]["extras"] == {"采集周期": "10min"}


def test_extras_key_with_spaces_rejected_422(client, user_token):
    r = client.post("/api/v1/batches", json={**BASE, "extras": {" device_no ": "x"}},
                    headers=auth(user_token))
    assert r.status_code == 422


def test_extras_nan_rejected_422(client, user_token):
    # httpx 的 json= 参数不允许 NaN，改用原始 JSON 字符串发送，确保 NaN 真正到达后端校验
    import json

    body = json.dumps({**BASE, "extras": {"a": float("nan")}})
    r = client.post("/api/v1/batches", content=body,
                    headers={**auth(user_token), "Content-Type": "application/json"})
    assert r.status_code == 422
