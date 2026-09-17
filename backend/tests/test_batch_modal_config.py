"""批次=事件组 Phase 2 测试（设计 §七 Phase 2：modal_param_def/batch_modal_config 实例 + 校验 + 待补标注）。

覆盖（设计 §九 测试 2 + Phase 2 验收点）：
- PUT /batches/{id}/modal-config：未知键/必填缺失/类型/范围/enum/NaN → 422（§3.3 规则 1-4）
- 类型清洗与幂等 upsert（(batch_id, modality) 1:1 全量替换）
- 权限：登录 401 / 同单位非创建者 403 / 跨单位 404 / admin 放行
- Out 聚合：batch_modal_configs + modal_pending_modalities（§3.4 "模态参数待补"标注）
- 删批次后 config 随批清空
- 验收点：红外（IR）批次缺 emissivity → 422；全 required=1 补齐 → 待补解除
"""
from datetime import datetime, timezone

from tests.conftest import auth

# conftest modal_defs fixture 的必填键语义（mp-0..12，与 seed.py §8.3 初稿同源）：
# IR required=1：emissivity/ambient_temp_c/rh_pct（reflected_temp_c/distance_m=2 条件必填）
# VIB required=1：sample_rate_hz（int）/channel_map（json）；AUD mic_pad_db（int enum）测试行
IR_REQ1 = {"emissivity": 0.95, "ambient_temp_c": 25.0, "rh_pct": 40.0}
VIB_REQ1 = {"sample_rate_hz": 25600, "channel_map": {"CH1": "pd-1"}}
_BATCH_NO = "P2-MC-001"      # 每测试重建库，批号不跨测试复用


def _batch(client, token) -> dict:
    r = client.post("/api/v1/batches",
                    json={"batch_no": _BATCH_NO, "device_no": "F01",
                          "equipment_state_type": "风电"},
                    headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _put(client, token, batch_id, modality, params):
    return client.put(f"/api/v1/batches/{batch_id}/modal-config",
                      json={"modality": modality, "params": params},
                      headers=auth(token))


def _detail(client, token, batch_id) -> dict:
    r = client.get(f"/api/v1/batches/{batch_id}", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _config_map(client, token, batch_id) -> dict:
    return {c["modality"]: c for c in _detail(client, token, batch_id)["batch_modal_configs"]}


def _add_file(db, batch_id: str, modality: str, fid: str) -> None:
    """直插 DataFile 行（pending 判定按批次模态聚合，绕过上传链路）。"""
    from app.models import DataFile

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.add(DataFile(id=fid, batch_id=batch_id, batch_no=_BATCH_NO,
                    object_key=f"wind/F01/{modality.lower()}/2025/06/{fid}.dat",
                    filename=f"{fid}.dat", file_size=1024, modality=modality,
                    device_no="F01", station="wind", uploader_id="user-1",
                    upload_status="已完成", created_at=now, updated_at=now))
    db.commit()


# ---------- A. 校验核心（§3.3 规则 1-4） ----------

def test_put_ir_missing_emissivity_422(client, user_token, nameplate, modal_defs):
    """验收点：红外（IR）批次补录缺 emissivity（required=1）→ 422。"""
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR",
             {"ambient_temp_c": 25.0, "rh_pct": 40.0})
    assert r.status_code == 422
    assert "emissivity" in r.text


def test_put_ir_empty_params_422(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR", {})
    assert r.status_code == 422
    assert "发射率" in r.text and "emissivity" in r.text


def test_put_required_null_means_missing_422(client, user_token, nameplate, modal_defs):
    """显式 null = 未填：required=1 键给 null → 422（前端清空输入会传 null）。"""
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR",
             {"emissivity": None, "ambient_temp_c": 25.0, "rh_pct": 40.0})
    assert r.status_code == 422
    assert "emissivity" in r.text


def test_put_unknown_key_422(client, user_token, nameplate, modal_defs):
    """拼写错误键（不存在于字典）→ 422（规则 1）。"""
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR",
             {"emissivity": 0.95, "ambient_temp_c": 25.0, "rh_pct": 40.0,
              "emisivity": 0.9})
    assert r.status_code == 422
    assert "emisivity" in r.text


def test_put_cross_modality_key_422(client, user_token, nameplate, modal_defs):
    """VIB 的键塞进 IR → 422（键必须属于该 modality）。"""
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR",
             {"emissivity": 0.95, "ambient_temp_c": 25.0, "rh_pct": 40.0,
              "sample_rate_hz": 25600})
    assert r.status_code == 422
    assert "sample_rate_hz" in r.text


def test_put_range_high_422(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR", dict(IR_REQ1, emissivity=1.5))
    assert r.status_code == 422
    assert "emissivity" in r.text


def test_put_range_low_422(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR", dict(IR_REQ1, emissivity=0.02))
    assert r.status_code == 422
    assert "emissivity" in r.text


def test_put_range_boundary_values_ok(client, user_token, nameplate, modal_defs):
    """闭区间边界 0.05 / 1.0 均合法。"""
    b = _batch(client, user_token)
    for v in (0.05, 1.0):
        r = _put(client, user_token, b["id"], "IR",
                 dict(IR_REQ1, emissivity=v))
        assert r.status_code == 200, r.text


def test_put_type_mismatch_cases_422(client, user_token, nameplate, modal_defs):
    """类型不符（规则 3）：float 键给非数字串 / bool；int 键给非整 float；str 键给数字。"""
    b = _batch(client, user_token)
    cases = [
        ("IR", dict(IR_REQ1, emissivity="abc")),          # float ← 不可解析字符串
        ("IR", dict(IR_REQ1, emissivity=True)),           # float ← bool（int 子类陷阱）
        ("VIB", dict(VIB_REQ1, sample_rate_hz=1000.5)),   # int ← 非整 float
        ("AUD", {"recorder_model": 123}),                 # str ← int
    ]
    for modality, params in cases:
        assert _put(client, user_token, b["id"], modality, params).status_code == 422


def test_put_type_error_message_422(client, user_token, nameplate, modal_defs):
    r = _put(client, user_token, _batch(client, user_token)["id"], "IR",
             dict(IR_REQ1, emissivity="abc"))
    assert r.status_code == 422
    assert "发射率" in r.text and "须为" in r.text


def test_put_str_number_coerced_ok(client, user_token, nameplate, modal_defs):
    """float 键给数字字符串 → 清洗为 float（API 手调友好）。"""
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR", dict(IR_REQ1, emissivity="0.95"))
    assert r.status_code == 200, r.text
    assert _config_map(client, user_token, b["id"])["IR"]["params"]["emissivity"] == 0.95


def test_put_int_string_coerced_ok(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "VIB", dict(VIB_REQ1, sample_rate_hz="25600"))
    assert r.status_code == 200, r.text
    params = _config_map(client, user_token, b["id"])["VIB"]["params"]
    assert params["sample_rate_hz"] == 25600 and isinstance(params["sample_rate_hz"], int)


def test_put_enum_valid_and_invalid_422(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    assert _put(client, user_token, b["id"], "AUD", {"mic_pad_db": -10}).status_code == 200
    r = _put(client, user_token, b["id"], "AUD", {"mic_pad_db": 5})
    assert r.status_code == 422
    assert "mic_pad_db" in r.text


def test_put_json_param_type_422(client, user_token, nameplate, modal_defs):
    """json 键（channel_map 通道接线映射）只接受 dict/list。"""
    b = _batch(client, user_token)
    assert _put(client, user_token, b["id"], "VIB", dict(VIB_REQ1)).status_code == 200
    r = _put(client, user_token, b["id"], "VIB",
             {"sample_rate_hz": 25600, "channel_map": "CH1->pd-1"})
    assert r.status_code == 422
    assert "channel_map" in r.text


def test_put_required2_not_enforced(client, user_token, nameplate, modal_defs):
    """required=2 条件必填：服务端不判定条件 → 仅 required=1 补齐即可 200。"""
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR", IR_REQ1)
    assert r.status_code == 200, r.text


def test_put_optional_only_ok(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "VID", {"camera_note": "塔底机位朝塔顶"})
    assert r.status_code == 200, r.text


def test_put_modality_without_def_rows(client, user_token, nameplate, modal_defs):
    """SCADA 无字典行：任意键 422（未知键）；空 params 允许保存（不强制）。"""
    b = _batch(client, user_token)
    assert _put(client, user_token, b["id"], "SCADA", {"x": 1}).status_code == 422
    assert _put(client, user_token, b["id"], "SCADA", {}).status_code == 200


def test_put_nan_422(client, user_token, nameplate, modal_defs):
    """NaN（float，规则 4）→ 422（服务层防御：JSON 标准外但可被宽松解析送达）。"""
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR",
             {"emissivity": float("nan"), "ambient_temp_c": 25.0, "rh_pct": 40.0})
    assert r.status_code == 422
    assert "emissivity" in r.text


def test_put_inf_422(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    r = _put(client, user_token, b["id"], "IR",
             {"emissivity": float("inf"), "ambient_temp_c": 25.0, "rh_pct": 40.0})
    assert r.status_code == 422
    assert "emissivity" in r.text


# ---------- B. 类型清洗 / 幂等 upsert（(batch_id, modality) 1:1） ----------

def test_put_full_ok_and_detail_echo(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    assert _put(client, user_token, b["id"], "IR", IR_REQ1).status_code == 200
    cfg = _config_map(client, user_token, b["id"])["IR"]
    assert cfg["modality"] == "IR"
    assert cfg["params"] == {"emissivity": 0.95, "ambient_temp_c": 25.0, "rh_pct": 40.0}


def test_put_upsert_overwrite_and_multi_modal(client, user_token, nameplate, modal_defs):
    b = _batch(client, user_token)
    assert _put(client, user_token, b["id"], "IR", IR_REQ1).status_code == 200
    assert _put(client, user_token, b["id"], "IR",
                dict(IR_REQ1, emissivity=0.80)).status_code == 200
    assert _put(client, user_token, b["id"], "VIB", VIB_REQ1).status_code == 200
    cm = _config_map(client, user_token, b["id"])
    assert set(cm) == {"IR", "VIB"}                 # 无重复行（1:1）
    assert cm["IR"]["params"]["emissivity"] == 0.80  # 覆盖而非追加


def test_put_upsert_full_replacement(client, user_token, nameplate, modal_defs):
    """全量替换语义：后 PUT 移除的键从 params 消失（无残留旧键）。"""
    b = _batch(client, user_token)
    assert _put(client, user_token, b["id"], "VIB", VIB_REQ1).status_code == 200
    assert _put(client, user_token, b["id"], "VIB",
                dict(VIB_REQ1, range_max=10.0)).status_code == 200
    assert _put(client, user_token, b["id"], "VIB", VIB_REQ1).status_code == 200
    params = _config_map(client, user_token, b["id"])["VIB"]["params"]
    assert params == {"sample_rate_hz": 25600, "channel_map": {"CH1": "pd-1"}}


# ---------- C. 权限 ----------

def test_put_requires_token_401(client):
    """无 token → 401（依赖注入先于业务校验，无需建批——用任意 id 即可）。"""
    r = client.put("/api/v1/batches/nope-1/modal-config",
                   json={"modality": "IR", "params": {}})
    assert r.status_code == 401


def test_put_same_org_other_user_403(client, user_token, other_user_token,
                                     nameplate, modal_defs):
    """批次归属：同单位非创建者（li）→ 403（仅创建者与 admin 可补录）。"""
    b = _batch(client, user_token)
    r = _put(client, other_user_token, b["id"], "IR", IR_REQ1)
    assert r.status_code == 403


def test_put_cross_org_404(client, user_token, other_org_batch):
    """跨单位批次 → 404（org 可见性先行，不泄露存在性）。"""
    r = _put(client, user_token, other_org_batch.id, "IR", {})
    assert r.status_code == 404


def test_put_admin_can_write_others(client, admin_token, batch, modal_defs):
    """admin 可补录任意单位批次（zhang 的 batch-1）。"""
    r = _put(client, admin_token, batch.id, "IR", IR_REQ1)
    assert r.status_code == 200, r.text


def test_put_batch_missing_404(client, user_token):
    r = _put(client, user_token, "nope-1", "IR", {})
    assert r.status_code == 404


# ---------- D. 模态参数待补标注（§3.4：批次含 required=1 键模态而未配全） ----------

def test_pending_ir_file_without_config(client, user_token, db, nameplate, modal_defs):
    b = _batch(client, user_token)
    _add_file(db, b["id"], "IR", "file-ir1")
    d = _detail(client, user_token, b["id"])
    assert d["modal_pending_modalities"] == ["IR"]
    assert d["batch_modal_configs"] == []


def test_pending_cleared_after_full_required1(client, user_token, db,
                                              nameplate, modal_defs):
    """补齐全部 required=1（含不填 required=2 条件键）→ 待补解除。"""
    b = _batch(client, user_token)
    _add_file(db, b["id"], "IR", "file-ir2")
    assert _put(client, user_token, b["id"], "IR", IR_REQ1).status_code == 200
    assert _detail(client, user_token, b["id"])["modal_pending_modalities"] == []


def test_pending_empty_when_no_files(client, user_token, nameplate, modal_defs):
    """批次模态未定（无文件）→ 不标待补（允许先传文件后补参）。"""
    b = _batch(client, user_token)
    assert _detail(client, user_token, b["id"])["modal_pending_modalities"] == []


def test_pending_empty_for_modality_without_defs(client, user_token, db,
                                                 nameplate, modal_defs):
    """SCADA 文件（该模态无字典行/无 required=1）→ 不标待补。"""
    b = _batch(client, user_token)
    _add_file(db, b["id"], "SCADA", "file-scada1")
    assert _detail(client, user_token, b["id"])["modal_pending_modalities"] == []


def test_pending_reappears_when_dict_grows(client, user_token, db,
                                           nameplate, modal_defs):
    """字典新增必填键后旧 config 缺键 → 重新标待补（dict 演进场景）。"""
    from app.models import BatchModalConfig

    b = _batch(client, user_token)
    _add_file(db, b["id"], "IR", "file-ir3")
    db.add(BatchModalConfig(id="mc-1", batch_id=b["id"], modality="IR",
                            params={"emissivity": 0.9, "ambient_temp_c": 20.0},
                            created_at="2026-09-09T00:00:00Z",
                            updated_at="2026-09-09T00:00:00Z"))
    db.commit()
    assert _detail(client, user_token, b["id"])["modal_pending_modalities"] == ["IR"]


def test_list_includes_pending(client, user_token, db, nameplate, modal_defs):
    b = _batch(client, user_token)
    _add_file(db, b["id"], "IR", "file-ir4")
    r = client.get("/api/v1/batches?page_size=100", headers=auth(user_token))
    assert r.status_code == 200
    item = next(x for x in r.json()["items"] if x["id"] == b["id"])
    assert item["modal_pending_modalities"] == ["IR"]


# ---------- E. 删除级联 ----------

def test_delete_batch_clears_configs(client, user_token, db, nameplate, modal_defs):
    from sqlalchemy import func, select

    from app.models import BatchModalConfig

    b = _batch(client, user_token)
    assert _put(client, user_token, b["id"], "IR", IR_REQ1).status_code == 200
    r = client.delete(f"/api/v1/batches/{b['id']}", headers=auth(user_token))
    assert r.status_code == 200
    left = db.execute(select(func.count()).select_from(
        BatchModalConfig).where(BatchModalConfig.batch_id == b["id"])).scalar()
    assert left == 0
