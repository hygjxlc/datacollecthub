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
    assert r.json()["extras"] == {}


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


def test_metadata_json_contains_extras(client, db, batch):
    from app.models import Batch
    from app.schemas.batch import BatchOut

    out = BatchOut.model_validate(db.get(Batch, "batch-1")).model_dump()
    assert "extras" in out
