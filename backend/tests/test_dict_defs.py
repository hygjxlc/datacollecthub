"""字典定义域测试（Phase 0：fault_type_def / modal_param_def）。

契约来源：docs/design/DataCollectHub_批次事件组化改造设计.md §2.2 / §2.5 / §六——
fault_type_def：admin 统一维护（code 一经发布不可改名，仅可停用 is_active=0）；登录用户只读。
modal_param_def：全局共享（TC609 模态代码 + 权威键名，同 modality 内 param_key 唯一）。
路由：GET /api/v1/fault-types（登录，仅 active）；/api/v1/admin/fault-types（admin 全量 CRUD）；
GET /api/v1/modal-params（登录）；/api/v1/admin/modal-params（admin 写）。
"""

from tests.conftest import auth

FAULT = {"code": "GEARBOX_BEARING_WEAR", "name": "齿轮箱-轴承-磨损",
         "severity": "故障", "sort_no": 1, "description": "高速轴轴承磨损"}
MODAL = {"modality": "VIB", "param_key": "sample_rate_hz", "label": "采样率",
         "unit": "Hz", "value_type": "int", "required": 1,
         "min_value": 1000, "max_value": 1000000}


# ---------- fault_type_def ----------

def test_fault_types_list_requires_auth_401(client):
    r = client.get("/api/v1/fault-types")
    assert r.status_code == 401


def test_fault_types_list_login_ok_empty(client, user_token):
    r = client.get("/api/v1/fault-types", headers=auth(user_token))
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_create_fault_type_admin_ok(client, admin_token):
    r = client.post("/api/v1/admin/fault-types", json=FAULT, headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == FAULT["code"]
    assert body["name"] == FAULT["name"]
    assert body["severity"] == "故障"
    assert body["is_active"] == 1
    assert body["creator_id"]  # 维护人落位（§2.5）


def test_create_fault_type_non_admin_403(client, user_token):
    r = client.post("/api/v1/admin/fault-types", json=FAULT, headers=auth(user_token))
    assert r.status_code == 403


def test_create_fault_type_duplicate_code_422(client, admin_token):
    client.post("/api/v1/admin/fault-types", json=FAULT, headers=auth(admin_token))
    r = client.post("/api/v1/admin/fault-types", json={**FAULT, "name": "别名"},
                    headers=auth(admin_token))
    assert r.status_code == 422


def test_create_fault_type_bad_code_422(client, admin_token):
    for bad in ["gearbox_wear", "齿轮箱-磨损", "GB WEAR", "GEARBOX-"]:
        r = client.post("/api/v1/admin/fault-types", json={**FAULT, "code": bad},
                        headers=auth(admin_token))
        assert r.status_code == 422, bad


def test_create_fault_type_bad_severity_422(client, admin_token):
    r = client.post("/api/v1/admin/fault-types", json={**FAULT, "severity": "严重"},
                    headers=auth(admin_token))
    assert r.status_code == 422


def test_update_fault_type_fields_ok(client, admin_token):
    created = client.post("/api/v1/admin/fault-types", json=FAULT,
                          headers=auth(admin_token)).json()
    r = client.put(f"/api/v1/admin/fault-types/{created['id']}",
                   json={"name": "齿轮箱-轴承-保持架断裂", "severity": "事故",
                         "sort_no": 5, "description": "改判"},
                   headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["name"] == "齿轮箱-轴承-保持架断裂"
    assert r.json()["severity"] == "事故"
    assert r.json()["sort_no"] == 5
    assert r.json()["code"] == FAULT["code"]   # code 不可改名


def test_update_fault_type_code_immutable(client, admin_token):
    created = client.post("/api/v1/admin/fault-types", json=FAULT,
                          headers=auth(admin_token)).json()
    r = client.put(f"/api/v1/admin/fault-types/{created['id']}",
                   json={"code": "RENAMED_CODE"}, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["code"] == FAULT["code"]


def test_update_fault_type_not_found_404(client, admin_token):
    r = client.put("/api/v1/admin/fault-types/no-such-id", json={"name": "x"},
                   headers=auth(admin_token))
    assert r.status_code == 404


def test_deactivate_fault_type_hidden_from_public(client, admin_token, user_token):
    created = client.post("/api/v1/admin/fault-types", json=FAULT,
                          headers=auth(admin_token)).json()
    client.put(f"/api/v1/admin/fault-types/{created['id']}",
               json={"is_active": 0}, headers=auth(admin_token))
    pub = client.get("/api/v1/fault-types", headers=auth(user_token)).json()
    assert pub["items"] == []                       # 停用态新申报不可选
    adm = client.get("/api/v1/admin/fault-types", headers=auth(admin_token)).json()
    assert len(adm["items"]) == 1 and adm["items"][0]["is_active"] == 0


# ---------- modal_param_def ----------

def test_modal_params_list_requires_auth_401(client):
    r = client.get("/api/v1/modal-params")
    assert r.status_code == 401


def test_modal_params_list_login_ok_empty(client, user_token):
    r = client.get("/api/v1/modal-params", headers=auth(user_token))
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_create_modal_param_admin_ok(client, admin_token):
    r = client.post("/api/v1/admin/modal-params", json=MODAL, headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["modality"] == "VIB" and body["param_key"] == "sample_rate_hz"
    assert body["value_type"] == "int" and body["required"] == 1
    assert body["min_value"] == 1000 and body["max_value"] == 1000000


def test_create_modal_param_non_admin_403(client, user_token):
    r = client.post("/api/v1/admin/modal-params", json=MODAL, headers=auth(user_token))
    assert r.status_code == 403


def test_create_modal_param_duplicate_composite_422(client, admin_token):
    client.post("/api/v1/admin/modal-params", json=MODAL, headers=auth(admin_token))
    r = client.post("/api/v1/admin/modal-params", json={**MODAL, "label": "采样率2"},
                    headers=auth(admin_token))
    assert r.status_code == 422
    # 同 key 跨 modality 允许（SCADA 与 VIB 各自键空间）
    r2 = client.post("/api/v1/admin/modal-params",
                     json={**MODAL, "modality": "SCADA", "label": "采样率"},
                     headers=auth(admin_token))
    assert r2.status_code == 200


def test_create_modal_param_bad_value_type_422(client, admin_token):
    r = client.post("/api/v1/admin/modal-params", json={**MODAL, "value_type": "number"},
                    headers=auth(admin_token))
    assert r.status_code == 422


def test_create_modal_param_bad_modality_422(client, admin_token):
    r = client.post("/api/v1/admin/modal-params", json={**MODAL, "modality": "scada"},
                    headers=auth(admin_token))
    assert r.status_code == 422


def test_create_modal_param_bad_required_422(client, admin_token):
    r = client.post("/api/v1/admin/modal-params", json={**MODAL, "required": 3},
                    headers=auth(admin_token))
    assert r.status_code == 422


def test_create_modal_param_min_gt_max_422(client, admin_token):
    r = client.post("/api/v1/admin/modal-params",
                    json={**MODAL, "min_value": 2000, "max_value": 1000},
                    headers=auth(admin_token))
    assert r.status_code == 422


def test_update_modal_param_fields_ok(client, admin_token):
    created = client.post("/api/v1/admin/modal-params", json=MODAL,
                          headers=auth(admin_token)).json()
    r = client.put(f"/api/v1/admin/modal-params/{created['id']}",
                   json={"label": "采样频率", "required": 2, "max_value": 2000000,
                         "description": "FFT x 轴定标（渲染硬依赖）"},
                   headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "采样频率" and body["required"] == 2
    assert body["max_value"] == 2000000
    assert body["modality"] == "VIB"        # 权威键不变
    assert body["param_key"] == "sample_rate_hz"


def test_update_modal_param_key_immutable(client, admin_token):
    created = client.post("/api/v1/admin/modal-params", json=MODAL,
                          headers=auth(admin_token)).json()
    r = client.put(f"/api/v1/admin/modal-params/{created['id']}",
                   json={"param_key": "sample_rate"}, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["param_key"] == "sample_rate_hz"


def test_update_modal_param_not_found_404(client, admin_token):
    r = client.put("/api/v1/admin/modal-params/no-such-id", json={"label": "x"},
                   headers=auth(admin_token))
    assert r.status_code == 404


def test_modal_param_optional_fields_nullable(client, admin_token):
    r = client.post("/api/v1/admin/modal-params",
                    json={"modality": "VID", "param_key": "camera_note",
                          "label": "拍摄位置/视角备注", "value_type": "str",
                          "description": "巡检机位备注"},
                    headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] is None and body["min_value"] is None
    assert body["enum_values"] is None and body["required"] == 0
