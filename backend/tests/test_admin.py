from tests.conftest import auth


# ---------- 单位管理 ----------

def test_admin_create_org(client, admin_token):
    r = client.post("/api/v1/admin/organizations",
                    json={"name": "大丰光伏电站", "type": "场站",
                          "contact_person": "王工", "contact_phone": "13800000000"},
                    headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "大丰光伏电站"
    assert body["id"]


def test_admin_list_orgs(client, admin_token, org):
    r = client.get("/api/v1/admin/organizations", headers=auth(admin_token))
    assert r.status_code == 200
    assert [o["name"] for o in r.json()["items"]] == ["辉腾梁风电场"]


def test_admin_update_org(client, admin_token, org):
    r = client.put(f"/api/v1/admin/organizations/{org.id}",
                   json={"contact_person": "赵工"}, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["contact_person"] == "赵工"


def test_non_admin_forbidden(client, user_token):
    assert client.get("/api/v1/admin/organizations", headers=auth(user_token)).status_code == 403
    assert client.get("/api/v1/admin/users", headers=auth(user_token)).status_code == 403


# ---------- 用户管理 ----------

def test_admin_create_user(client, admin_token, org):
    r = client.post("/api/v1/admin/users",
                    json={"username": "wang", "display_name": "王工", "password": "pass456",
                          "role": "user", "organization_id": org.id},
                    headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["username"] == "wang"
    # 新用户可直接登录
    assert client.post("/api/v1/auth/login",
                       json={"username": "wang", "password": "pass456"}).status_code == 200


def test_create_user_duplicate_username_422(client, admin_token, user_zhang):
    r = client.post("/api/v1/admin/users",
                    json={"username": "zhang", "display_name": "重复", "password": "x12345",
                          "role": "user", "organization_id": "org-1"},
                    headers=auth(admin_token))
    assert r.status_code == 422


def test_create_user_unknown_org_404(client, admin_token):
    r = client.post("/api/v1/admin/users",
                    json={"username": "wang", "display_name": "王工", "password": "pass456",
                          "role": "user", "organization_id": "no-such-org"},
                    headers=auth(admin_token))
    assert r.status_code == 404


def test_admin_list_users(client, admin_token, user_zhang, admin):
    r = client.get("/api/v1/admin/users", headers=auth(admin_token))
    assert r.status_code == 200
    usernames = {u["username"] for u in r.json()["items"]}
    assert usernames == {"zhang", "admin"}


def test_reset_password_then_old_fails(client, admin_token, user_zhang):
    r = client.post(f"/api/v1/admin/users/{user_zhang.id}/reset-password",
                    headers=auth(admin_token))
    assert r.status_code == 200
    new_password = r.json()["new_password"]
    assert new_password
    assert client.post("/api/v1/auth/login",
                       json={"username": "zhang", "password": "pass123"}).status_code == 401
    assert client.post("/api/v1/auth/login",
                       json={"username": "zhang", "password": new_password}).status_code == 200


def test_deactivate_user_old_token_rejected(client, admin_token, user_token):
    r = client.put("/api/v1/admin/users/user-1", json={"is_active": 0},
                   headers=auth(admin_token))
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(user_token)).status_code == 401


def test_delete_user_ok(client, admin_token, user_zhang):
    r = client.delete("/api/v1/admin/users/user-1", headers=auth(admin_token))
    assert r.status_code == 200
    assert client.post("/api/v1/auth/login",
                       json={"username": "zhang", "password": "pass123"}).status_code == 401


# ---------- 审计日志查看（架构 3.1 /audit 页面） ----------

def test_list_audit_logs_admin_only(client, user_token, admin_token, batch, db):
    from app.models import AuditLog
    from tests.conftest import utcnow

    db.add(AuditLog(id="log-1", user_id="user-1", username="zhang",
                    action="create", entity_type="batch", entity_id="batch-1",
                    source="web", created_at=utcnow()))
    db.commit()
    assert client.get("/api/v1/admin/audit-logs",
                      headers=auth(user_token)).status_code == 403
    r = client.get("/api/v1/admin/audit-logs", headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert {"id", "action", "entity_type", "source", "created_at"} <= set(body["items"][0])


def test_list_audit_logs_filters(client, admin_token, batch, db):
    from app.models import AuditLog
    from tests.conftest import utcnow

    db.add_all([
        AuditLog(id="log-2", user_id=None, username=None, action="query",
                 entity_type="datafile", source="integration",
                 params_summary="modalities=SCADA", created_at=utcnow()),
        AuditLog(id="log-3", user_id="user-1", username="zhang", action="create",
                 entity_type="batch", entity_id="batch-1", source="web",
                 created_at=utcnow()),
    ])
    db.commit()
    r = client.get("/api/v1/admin/audit-logs",
                   params={"source": "integration", "action": "query"},
                   headers=auth(admin_token))
    assert r.status_code == 200
    assert all(i["source"] == "integration" for i in r.json()["items"])
