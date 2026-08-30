from tests.conftest import auth

EV_PAYLOAD = {
    "event_time": "2025-06-15 14:23:08", "timezone": "+08:00",
    "device_no": "F01", "event_type": "齿轮箱/轴承/磨损",
    "severity": "报警", "description": "齿轮箱轴承温度持续升高至 85℃，触发报警停机",
    "related_file_ids": ["file-1"],
}


def test_create_event_ok(client, user_token, own_file):
    r = client.post("/api/v1/events", json=EV_PAYLOAD, headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["organization_id"] == "org-1"
    assert r.json()["related_files"] == ["file-1"]
    assert r.json()["related_file_count"] == 1


def test_create_returns_creator_name(client, user_token, own_file):
    # 方案 A：台账记录暴露创建者姓名
    r = client.post("/api/v1/events", json=EV_PAYLOAD, headers=auth(user_token))
    assert r.json()["creator_name"] == "张工"


def test_create_with_structured_fields(client, user_token, own_file):
    # 事件结构化字段：根因/处置/效果/工况（SFT 指令对素材）
    r = client.post("/api/v1/events", json={
        **EV_PAYLOAD,
        "root_cause": "高速轴轴承润滑脂老化干磨",
        "treatment": "停机组 → 更换 SKF-32222 轴承 → 重新对中",
        "treatment_result": "更换后 24h 温升恢复正常",
        "operating_condition": "满发工况，环境温度 32℃，风速 8.5m/s",
    }, headers=auth(user_token))
    assert r.status_code == 200
    body = r.json()
    assert body["root_cause"] == "高速轴轴承润滑脂老化干磨"
    assert body["treatment"] == "停机组 → 更换 SKF-32222 轴承 → 重新对中"
    assert body["treatment_result"] == "更换后 24h 温升恢复正常"
    assert body["operating_condition"] == "满发工况，环境温度 32℃，风速 8.5m/s"


def test_create_structured_fields_default_none(client, user_token, own_file):
    # 4 字段全部可选：不传则返回 None
    r = client.post("/api/v1/events", json=EV_PAYLOAD, headers=auth(user_token))
    assert r.status_code == 200
    body = r.json()
    assert body["root_cause"] is None
    assert body["treatment"] is None
    assert body["treatment_result"] is None
    assert body["operating_condition"] is None


def test_update_structured_fields(client, user_token, event):
    r = client.put("/api/v1/events/ev-1", json={
        "root_cause": "轴承润滑脂老化", "treatment": "更换轴承",
    }, headers=auth(user_token))
    assert r.status_code == 200
    body = r.json()
    assert body["root_cause"] == "轴承润滑脂老化"
    assert body["treatment"] == "更换轴承"


def test_list_structured_fields_none_for_legacy(client, user_token, event):
    # 历史数据无结构化字段 → Out 为 None（前端显示空）
    r = client.get("/api/v1/events", headers=auth(user_token))
    assert r.json()["items"][0]["root_cause"] is None
    assert r.json()["items"][0]["treatment_result"] is None


def test_list_returns_creator_name(client, user_token, event):
    # fixture ev-1 creator_id=user-1（张工）
    r = client.get("/api/v1/events", headers=auth(user_token))
    assert r.json()["items"][0]["creator_name"] == "张工"


def test_create_duplicate_related_file_dedup(client, user_token, own_file):
    r = client.post("/api/v1/events",
                    json={**EV_PAYLOAD, "related_file_ids": ["file-1", "file-1"]},
                    headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["related_files"] == ["file-1"]


def test_create_invalid_severity_422(client, user_token):
    r = client.post("/api/v1/events", json={**EV_PAYLOAD, "severity": "紧急"},
                    headers=auth(user_token))
    assert r.status_code == 422


def test_create_related_file_not_found_404(client, user_token):
    r = client.post("/api/v1/events",
                    json={**EV_PAYLOAD, "related_file_ids": ["file-x"]},
                    headers=auth(user_token))
    assert r.status_code == 404


def test_create_related_file_cross_org_404(client, user_token, files_fixture):
    # file-3 属 org-2（batch-2），跨单位关联 → 404
    r = client.post("/api/v1/events",
                    json={**EV_PAYLOAD, "related_file_ids": ["file-3"]},
                    headers=auth(user_token))
    assert r.status_code == 404


def test_get_event_with_related_files(client, user_token, event):
    r = client.get("/api/v1/events/ev-1", headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["related_files"] == ["file-1"]
    assert r.json()["related_file_count"] == 1


def test_list_filters(client, user_token, event):
    ev2 = {"event_time": "2025-07-01 09:30:00", "timezone": "+08:00",
           "device_no": "F02", "event_type": "变桨/电机/失效",
           "severity": "故障", "description": "变桨电机失效"}
    assert client.post("/api/v1/events", json=ev2,
                       headers=auth(user_token)).status_code == 200
    # 按设备过滤
    r = client.get("/api/v1/events?device_no=F02", headers=auth(user_token))
    assert [i["event_type"] for i in r.json()["items"]] == ["变桨/电机/失效"]
    # 按级别过滤
    r = client.get("/api/v1/events?severity=报警", headers=auth(user_token))
    assert [i["severity"] for i in r.json()["items"]] == ["报警"]
    # 按时间范围过滤（闭区间）
    r = client.get("/api/v1/events?start=2025-07-01 00:00:00&end=2025-07-01 23:59:59",
                   headers=auth(user_token))
    assert [i["device_no"] for i in r.json()["items"]] == ["F02"]
    # 无结果
    r = client.get("/api/v1/events?device_no=F99", headers=auth(user_token))
    assert r.json()["items"] == []


def test_same_org_other_user_can_edit(client, other_user_token, event):
    # 台账共享维护：同单位 li 可编辑（不校验 owner）
    r = client.put("/api/v1/events/ev-1", json={"description": "li 补充"},
                   headers=auth(other_user_token))
    assert r.status_code == 200
    assert r.json()["description"] == "li 补充"


def test_update_event_and_related_files(client, user_token, event, files_fixture):
    # 更新描述 + 关联换成 file-2
    r = client.put("/api/v1/events/ev-1",
                   json={"description": "更新描述", "related_file_ids": ["file-2"]},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["description"] == "更新描述"
    assert r.json()["related_files"] == ["file-2"]
    assert r.json()["related_file_count"] == 1


def test_cross_org_404(client, user_token, other_org_event):
    assert client.get("/api/v1/events/ev-9",
                      headers=auth(user_token)).status_code == 404
    assert client.put("/api/v1/events/ev-9", json={"description": "x"},
                      headers=auth(user_token)).status_code == 404
    assert client.delete("/api/v1/events/ev-9",
                         headers=auth(user_token)).status_code == 404


def test_delete_event_cascade(client, db, user_token, event):
    from app.models import EventFile

    assert client.delete("/api/v1/events/ev-1",
                         headers=auth(user_token)).status_code == 200
    assert client.get("/api/v1/events/ev-1",
                      headers=auth(user_token)).status_code == 404
    assert db.get(EventFile, "ef-1") is None      # ondelete CASCADE


def test_unauthorized_401(client):
    assert client.get("/api/v1/events").status_code == 401


def test_update_related_files_writes_audit_old_new(client, db, user_token, event,
                                                    files_fixture):
    import json

    from app.models import AuditLog
    from sqlalchemy import select as sa_select

    client.put("/api/v1/events/ev-1",
               json={"related_file_ids": ["file-2"]}, headers=auth(user_token))
    log = db.execute(sa_select(AuditLog).where(
        AuditLog.entity_type == "event", AuditLog.action == "update"
    )).scalars().all()[-1]
    changes = json.loads(log.field_changes)
    assert changes["related_file_ids"] == {
        "old": ["file-1"], "new": ["file-2"]}


def test_update_same_related_files_no_audit(client, db, user_token, event):
    from app.models import AuditLog
    from sqlalchemy import select as sa_select

    before = db.execute(sa_select(AuditLog).where(
        AuditLog.entity_type == "event", AuditLog.action == "update"
    )).scalars().all()
    r = client.put("/api/v1/events/ev-1",
                   json={"related_file_ids": ["file-1"]}, headers=auth(user_token))
    assert r.status_code == 200
    after = db.execute(sa_select(AuditLog).where(
        AuditLog.entity_type == "event", AuditLog.action == "update"
    )).scalars().all()
    assert len(after) == len(before)


def test_list_excludes_other_org_events(client, user_token, other_org_event):
    r = client.get("/api/v1/events", headers=auth(user_token))
    assert all(i["organization_id"] != "org-2" for i in r.json()["items"])
    assert not any(i["id"] == "ev-9" for i in r.json()["items"])
