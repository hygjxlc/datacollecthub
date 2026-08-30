from tests.conftest import auth


def test_login_ok(client, user_zhang):
    r = client.post("/api/v1/auth/login", json={"username": "zhang", "password": "pass123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "zhang"
    assert body["user"]["role"] == "user"
    assert body["user"]["organization_id"] == "org-1"


def test_login_wrong_password_401(client, user_zhang):
    r = client.post("/api/v1/auth/login", json={"username": "zhang", "password": "bad"})
    assert r.status_code == 401


def test_login_unknown_user_401(client, user_zhang):
    r = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_login_inactive_user_401(client, db, user_zhang):
    user_zhang.is_active = 0
    db.commit()
    r = client.post("/api/v1/auth/login", json={"username": "zhang", "password": "pass123"})
    assert r.status_code == 401


def test_me_requires_token(client, user_zhang):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(client, user_token):
    r = client.get("/api/v1/auth/me", headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["username"] == "zhang"


def test_stale_token_rejected_after_deactivate(client, db, user_token):
    # TC-AUTH-004：停用后携带旧 JWT 的后续请求同样被拒（后端校验 is_active）
    from app.models import User

    db.query(User).filter_by(username="zhang").update({"is_active": 0})
    db.commit()
    r = client.get("/api/v1/auth/me", headers=auth(user_token))
    assert r.status_code == 401


def test_change_password_then_old_fails(client, user_token):
    r = client.put("/api/v1/auth/password",
                   json={"old_password": "pass123", "new_password": "newpass456"},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert client.post("/api/v1/auth/login",
                       json={"username": "zhang", "password": "pass123"}).status_code == 401
    assert client.post("/api/v1/auth/login",
                       json={"username": "zhang", "password": "newpass456"}).status_code == 200
