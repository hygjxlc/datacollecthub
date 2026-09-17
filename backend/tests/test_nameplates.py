import json

from tests.conftest import auth

NP_PAYLOAD = {
    "device_no": "F01", "device_model": "金风 GW82/1500", "rated_power": 1500.0,
    "organization_id": "org-1",   # 仅管理员可指定所属单位（§2.6 执行补充）
    "rated_wind_speed": 10.5, "rotor_diameter": 82.0, "hub_height": 70.0,
    "bearing_model": "SKF 240/600", "gearbox_ratio": 104.5,
    "generator_model": "天元 1.5MW", "manufacturer": "金风科技",
    "commission_date": "2015-06-30", "design_life_years": 20,
    "extras": {"机型": "GW82/1500"},
}


def test_create_nameplate_ok(client, admin_token, org):
    # 写权限收紧（决策 5）：台账维护仅管理员可操作
    r = client.post("/api/v1/nameplates", json=NP_PAYLOAD, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["organization_id"] == "org-1"      # 单位取自 body.organization_id
    assert r.json()["rated_power"] == 1500.0


def test_create_returns_creator_name(client, admin_token, org):
    # 方案 A：台账记录暴露创建者姓名（admin 实建）
    r = client.post("/api/v1/nameplates", json=NP_PAYLOAD, headers=auth(admin_token))
    assert r.json()["creator_name"] == "管理员"


def test_list_returns_creator_name(client, user_token, nameplate):
    # fixture np-1 creator_id=user-1（张工）
    r = client.get("/api/v1/nameplates", headers=auth(user_token))
    assert r.json()["items"][0]["creator_name"] == "张工"


def test_get_returns_creator_name(client, user_token, nameplate):
    r = client.get("/api/v1/nameplates/np-1", headers=auth(user_token))
    assert r.json()["creator_name"] == "张工"


def test_create_duplicate_device_422(client, admin_token, nameplate):
    # admin 未传 organization_id 时默认落 None，与 np-1（org-1）不冲突 → 须显式同单位
    r = client.post("/api/v1/nameplates",
                    json={"device_no": "F01", "organization_id": "org-1"},
                    headers=auth(admin_token))
    assert r.status_code == 422


def test_list_only_own_org(client, user_token, nameplate, other_org_nameplate):
    r = client.get("/api/v1/nameplates", headers=auth(user_token))
    assert {i["id"] for i in r.json()["items"]} == {"np-1"}


def test_get_by_device(client, user_token, nameplate):
    r = client.get("/api/v1/nameplates/by-device/F01", headers=auth(user_token))
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["device_model"] == "金风 GW82/1500"


def test_get_by_device_empty(client, user_token):
    r = client.get("/api/v1/nameplates/by-device/F99", headers=auth(user_token))
    assert r.json()["items"] == []


def test_update_nameplate_ok(client, admin_token, nameplate):
    r = client.put("/api/v1/nameplates/np-1", json={"rated_power": 2000.0},
                   headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["rated_power"] == 2000.0


def test_write_requires_admin(client, user_token, other_user_token, nameplate):
    # 写权限收紧（决策 5）：普通用户（含台账所属单位成员）一律 403，不再共享维护
    assert client.put("/api/v1/nameplates/np-1", json={"manufacturer": "金风"},
                      headers=auth(user_token)).status_code == 403
    assert client.delete("/api/v1/nameplates/np-1",
                         headers=auth(other_user_token)).status_code == 403


def test_cross_org_404(client, user_token, other_org_nameplate):
    # 读仍按单位隐藏（404）；写已被 require_admin 先行拦截（403）
    assert client.get("/api/v1/nameplates/np-2", headers=auth(user_token)).status_code == 404
    assert client.put("/api/v1/nameplates/np-2", json={"rated_power": 1},
                      headers=auth(user_token)).status_code == 403
    assert client.delete("/api/v1/nameplates/np-2",
                         headers=auth(user_token)).status_code == 403


def test_delete_nameplate(client, admin_token, nameplate):
    assert client.delete("/api/v1/nameplates/np-1",
                         headers=auth(admin_token)).status_code == 200
    assert client.get("/api/v1/nameplates/np-1",
                      headers=auth(admin_token)).status_code == 404


def test_unauthorized_401(client):
    assert client.get("/api/v1/nameplates").status_code == 401


def test_update_writes_audit_field_changes(client, db, admin_token, nameplate):
    from sqlalchemy import select

    from app.models import AuditLog

    client.put("/api/v1/nameplates/np-1", json={"rated_power": 2000.0},
               headers=auth(admin_token))
    log = db.execute(select(AuditLog).where(
        AuditLog.entity_type == "nameplate", AuditLog.action == "update"
    )).scalars().all()[-1]
    assert log.entity_id == "np-1"
    changes = json.loads(log.field_changes)
    assert changes == {"rated_power": {"old": 1500.0, "new": 2000.0}}


def test_create_writes_audit(client, db, admin_token, org):
    from sqlalchemy import select

    from app.models import AuditLog

    client.post("/api/v1/nameplates",
                json={"device_no": "F02", "organization_id": "org-1"},
                headers=auth(admin_token))
    log = db.execute(select(AuditLog).where(
        AuditLog.entity_type == "nameplate", AuditLog.action == "create"
    )).scalars().one()
    assert log.entity_id is not None
