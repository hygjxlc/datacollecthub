from tests.conftest import auth

PD_PAYLOAD = {
    "device_no": "F01", "channel_no": "CH3", "name": "风速", "unit": "m/s",
    "scale_slope": 0.1, "scale_offset": 0.0, "data_type": "float",
    "range_min": 0.0, "range_max": 60.0, "description": "机舱风速计",
}


def test_create_point_dict_ok(client, user_token):
    r = client.post("/api/v1/point-dicts", json=PD_PAYLOAD, headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["organization_id"] == "org-1"


def test_create_returns_creator_name(client, user_token):
    # 方案 A：台账记录暴露创建者姓名，便于单位内人员质疑时联系创建人
    r = client.post("/api/v1/point-dicts", json=PD_PAYLOAD, headers=auth(user_token))
    assert r.json()["creator_id"] == "user-1"
    assert r.json()["creator_name"] == "张工"


def test_list_returns_creator_name(client, user_token):
    client.post("/api/v1/point-dicts", json=PD_PAYLOAD, headers=auth(user_token))
    r = client.get("/api/v1/point-dicts?device_no=F01", headers=auth(user_token))
    assert r.json()["items"][0]["creator_name"] == "张工"


def test_list_creator_name_none_for_legacy(client, user_token, point_dict):
    # 历史数据无 creator_id → creator_name 为 None（前端显示 "-"）
    r = client.get("/api/v1/point-dicts?device_no=F01", headers=auth(user_token))
    assert r.json()["items"][0]["creator_name"] is None


def test_create_duplicate_channel_422(client, user_token, point_dict):
    r = client.post("/api/v1/point-dicts",
                    json={"device_no": "F01", "channel_no": "CH1", "name": "重复"},
                    headers=auth(user_token))
    assert r.status_code == 422


def test_list_by_device(client, user_token, point_dict):
    r = client.get("/api/v1/point-dicts?device_no=F01", headers=auth(user_token))
    assert {i["channel_no"] for i in r.json()["items"]} == {"CH1", "CH2"}


def test_list_by_device_empty(client, user_token):
    r = client.get("/api/v1/point-dicts?device_no=F99", headers=auth(user_token))
    assert r.json()["items"] == []


def test_device_nos_merged(client, user_token, point_dict, batch):
    # 本单位设备编号 = Batch 与 PointDict 来源合并
    r = client.get("/api/v1/point-dicts/device-nos", headers=auth(user_token))
    assert set(r.json()["items"]) == {"F01"}


def test_update_and_delete(client, user_token, point_dict):
    r = client.put("/api/v1/point-dicts/pd-1", json={"scale_slope": 2.0},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["scale_slope"] == 2.0
    assert client.delete("/api/v1/point-dicts/pd-1",
                         headers=auth(user_token)).status_code == 200
    assert client.get("/api/v1/point-dicts/pd-1",
                      headers=auth(user_token)).status_code == 404


def test_cross_org_404(client, user_token, other_org_point_dict):
    assert client.get("/api/v1/point-dicts/pd-9",
                      headers=auth(user_token)).status_code == 404


def test_unauthorized_401(client):
    assert client.get("/api/v1/point-dicts").status_code == 401


def test_update_device_no_conflict_422(client, user_token, point_dict):
    # pd-1 是 (F01, CH1)；point_dict fixture 还含 (F01, CH2)；改 device_no 到已有组合 → 422
    # 先将 pd-1 改为 (F02, CH1) 占用组合，再尝试把 pd-2 改为 (F02, CH1) 应 422
    assert client.put("/api/v1/point-dicts/pd-1",
                      json={"device_no": "F02"}, headers=auth(user_token)).status_code == 200
    r = client.put("/api/v1/point-dicts/pd-2",
                   json={"device_no": "F02", "channel_no": "CH1"},
                   headers=auth(user_token))
    assert r.status_code == 422


def test_update_both_fields_no_false_conflict(client, user_token, point_dict):
    # 回归：库中已有 (F02, CH1)（由 pd-1 改出），pd-2 原为 (F01, CH2)
    # 同时改 device_no→F02、channel_no→CH3：最终组合 (F02, CH3) 无冲突，不应误判 422
    assert client.put("/api/v1/point-dicts/pd-1",
                      json={"device_no": "F02"}, headers=auth(user_token)).status_code == 200
    r = client.put("/api/v1/point-dicts/pd-2",
                   json={"device_no": "F02", "channel_no": "CH3"},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["channel_no"] == "CH3"


def test_cross_org_put_delete_404(client, user_token, other_org_point_dict):
    assert client.put("/api/v1/point-dicts/pd-9", json={"unit": "x"},
                      headers=auth(user_token)).status_code == 404
    assert client.delete("/api/v1/point-dicts/pd-9",
                         headers=auth(user_token)).status_code == 404


def test_device_nos_union_disjoint(client, user_token, batch, db):
    # Batch 独有 F01（batch fixture）+ PointDict 独有 F02：并集 {F01, F02}
    from app.models import PointDict
    from tests.conftest import utcnow

    db.add(PointDict(id="pd-5", organization_id="org-1", device_no="F02",
                     channel_no="CH1", name="辐照度", unit="W/m2",
                     created_at=utcnow(), updated_at=utcnow()))
    db.commit()
    r = client.get("/api/v1/point-dicts/device-nos", headers=auth(user_token))
    assert set(r.json()["items"]) == {"F01", "F02"}


def test_create_writes_audit(client, db, user_token):
    import json

    from sqlalchemy import select

    from app.models import AuditLog

    client.post("/api/v1/point-dicts",
                json={"device_no": "F02", "channel_no": "CH9", "name": "x"},
                headers=auth(user_token))
    log = db.execute(select(AuditLog).where(
        AuditLog.entity_type == "point_dict", AuditLog.action == "create"
    )).scalars().one()
    assert log.entity_id is not None
