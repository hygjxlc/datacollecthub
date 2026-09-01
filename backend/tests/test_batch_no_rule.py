from datetime import datetime, timezone

from tests.conftest import auth

RULE = {"template": "B-{YYYY}-{SEQ:3}"}
STATE = {"equipment_state_type": "风电"}


def test_put_rule_non_admin_403(client, user_token):
    r = client.put("/api/v1/admin/batch-no-rule", json=RULE, headers=auth(user_token))
    assert r.status_code == 403


def test_put_rule_invalid_template_422(client, admin_token):
    for bad in ["B-{YYYY}", "B-{UNKNOWN}-{SEQ:3}", "B-{SEQ}-{YYYY}",
                "B-{YYYY}-{SEQ:0}", "B-{YYYY}-{SEQ:12}"]:
        r = client.put("/api/v1/admin/batch-no-rule", json={"template": bad},
                       headers=auth(admin_token))
        assert r.status_code == 422, bad


def test_put_and_get_rule(client, admin_token, user_token):
    r = client.put("/api/v1/admin/batch-no-rule", json=RULE, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["template"] == RULE["template"]
    r2 = client.get("/api/v1/admin/batch-no-rule", headers=auth(admin_token))
    assert r2.json()["template"] == RULE["template"]
    r3 = client.get("/api/v1/batch-no-rule", headers=auth(user_token))
    assert r3.json() == {"template": RULE["template"]}


def test_get_rule_unset_returns_null_template(client, user_token):
    r = client.get("/api/v1/batch-no-rule", headers=auth(user_token))
    assert r.json() == {"template": None}


def test_create_auto_generated_sequential(client, admin_token, user_token):
    client.put("/api/v1/admin/batch-no-rule", json=RULE, headers=auth(admin_token))
    year = datetime.now(timezone.utc).year
    r1 = client.post("/api/v1/batches", json={"batch_no": "IGNORED", "device_no": "F01",
                                              **STATE}, headers=auth(user_token))
    assert r1.status_code == 200
    assert r1.json()["batch_no"] == f"B-{year}-001"   # 前端值被忽略，强制自动
    r2 = client.post("/api/v1/batches", json={"device_no": "F01", **STATE},
                     headers=auth(user_token))
    assert r2.json()["batch_no"] == f"B-{year}-002"


def test_without_rule_batch_no_required_422(client, user_token):
    r = client.post("/api/v1/batches", json={"device_no": "F01", **STATE},
                    headers=auth(user_token))
    assert r.status_code == 422


def test_seed_from_existing_batches(client, admin_token, user_token):
    """存量 B-2026-005 存在 → 启用规则后首个自动编号为 006。"""
    year = datetime.now(timezone.utc).year
    client.post("/api/v1/batches", json={"batch_no": f"B-{year}-005",
                                         "device_no": "F01", **STATE},
                headers=auth(user_token))
    client.put("/api/v1/admin/batch-no-rule", json=RULE, headers=auth(admin_token))
    r = client.post("/api/v1/batches", json={"device_no": "F01", **STATE},
                    headers=auth(user_token))
    assert r.json()["batch_no"] == f"B-{year}-006"


def test_device_no_placeholder_independent_seq(client, admin_token, user_token):
    client.put("/api/v1/admin/batch-no-rule",
               json={"template": "{DEVICE_NO}-{YYYY}-{SEQ:2}"}, headers=auth(admin_token))
    r1 = client.post("/api/v1/batches", json={"device_no": "F01", **STATE},
                     headers=auth(user_token))
    r2 = client.post("/api/v1/batches", json={"device_no": "F02", **STATE},
                     headers=auth(user_token))
    assert r1.json()["batch_no"].startswith("F01-") and r1.json()["batch_no"].endswith("-01")
    assert r2.json()["batch_no"].startswith("F02-") and r2.json()["batch_no"].endswith("-01")


def test_render_and_counter_key_unit(db):
    from app.services.batch_no_service import BatchNoService

    svc = BatchNoService(db)
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    tpl = "B-{YYYY}-{MM}-{DD}-{SEQ:3}"
    assert svc.render(tpl, device_no="F01", now=now, seq=7) == "B-2026-09-01-007"
    assert svc.counter_key(tpl, device_no="F01", now=now) == "B-2026-09-01-"
    tpl2 = "D-{DEVICE_NO}-{YY}-{SEQ:2}"
    assert svc.render(tpl2, device_no="F01", now=now, seq=3) == "D-F01-26-03"
    assert svc.counter_key(tpl2, device_no="F01", now=now) == "D-F01-26-"
