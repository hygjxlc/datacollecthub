"""批次=事件组 Phase 1 测试（设计 §七 Phase 1：三态申报/兼容推断/EVT_ID/台账校验）。

覆盖（设计 §九 测试 1/3/5 + Phase 1 验收点）：
- event_type 三态申报与字段清空规则（§3.1 规则 1-4）
- operating_condition 兼容推断（故障→故障/检修→维修，§3.1 规则 1）
- fault_type 字典白名单 + 停用态拒绝 + severity 缺省取字典行默认（§3.1 规则 2/5）
- t_start/t_end 成对校验（§3.1 规则 6）
- EVT_ID：默认模板/类型段值/段值×设备×年独立计数/存量种子衔接（§四）
- update：draft 改类型重算 EVT_ID；含 DataFile 禁改（§四 变更规则）
- evt_template 规则：admin 双模板配置与校验（{TYPE_CODE} 仅 evt 可用）
- device_no 台账校验：create 422 + manifest 导入行级失败（§3.5）
- nameplate 写权限收紧 require_admin + admin 指定单位归属（§2.6 执行补充）
"""
import csv
import io
import zipfile
from datetime import datetime, timezone

from tests.conftest import auth

_YEAR = datetime.now(timezone.utc).year
# conftest client 预插的字典行（ft-0 UNCLASSIFIED/故障、ft-1 GEARBOX_BEARING_WEAR/故障、
# ft-2 GENERATOR_BEARING_OVERTEMP/报警、ft-3 DISABLED_TEST_FAULT/停用）
EVT_RULE = {"template": "B-{YYYY}-{SEQ:3}", "evt_template": "E-{TYPE_CODE}-{SEQ:3}"}


def _base(device_no: str = "F01", **kw) -> dict:
    payload = {"batch_no": f"E2E-{_YEAR}-001", "device_no": device_no,
               "equipment_state_type": "风电"}
    payload.update(kw)
    return payload


def _fault(**kw) -> dict:
    payload = {"event_type": "故障", "fault_time": "2026-09-04 08:30:00",
               "fault_desc": "齿轮箱轴承温度超限停机"}
    payload.update(kw)
    return payload


def _create(client, token, payload) -> dict:
    r = client.post("/api/v1/batches", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


# ---------- A. 三态申报与默认 ----------

def test_create_default_normal_with_evt_id(client, user_token, nameplate):
    b = _create(client, user_token, _base())
    assert b["event_type"] == "正常"
    assert b["operating_condition"] is None      # 退役列：新申报不再写入
    assert b["fault_type"] is None and b["severity"] is None
    assert b["fault_time"] is None
    assert b["event_status"] == "draft"
    assert b["evt_id"] == f"EVT_NORMAL_F01_{_YEAR}_001"


def test_create_fault_explicit_type_dict_defaults(client, user_token, nameplate):
    b = _create(client, user_token, _base(**_fault(fault_type="GEARBOX_BEARING_WEAR")))
    assert b["event_type"] == "故障"
    assert b["fault_type"] == "GEARBOX_BEARING_WEAR"
    assert b["severity"] == "故障"                # 缺省取字典行默认（ft-1=故障）
    assert b["evt_id"] == f"EVT_GEARBOX_BEARING_WEAR_F01_{_YEAR}_001"


def test_create_fault_severity_overrides_dict_default(client, user_token, nameplate):
    b = _create(client, user_token, _base(**_fault(
        fault_type="GEARBOX_BEARING_WEAR", severity="报警")))
    assert b["severity"] == "报警"


def test_create_fault_severity_taken_from_dict_row(client, user_token, nameplate):
    """字典行 severity=报警（ft-2）→ 缺省取报警（差异行）。"""
    b = _create(client, user_token, _base(**_fault(
        fault_type="GENERATOR_BEARING_OVERTEMP")))
    assert b["severity"] == "报警"


def test_create_fault_invalid_severity_422(client, user_token, nameplate):
    r = client.post("/api/v1/batches", json=_base(**_fault(severity="严重")),
                    headers=auth(user_token))
    assert r.status_code == 422


def test_create_fault_missing_time_422(client, user_token, nameplate):
    payload = _base(**{"event_type": "故障", "fault_desc": "轴承过热"})
    r = client.post("/api/v1/batches", json=payload, headers=auth(user_token))
    assert r.status_code == 422
    assert "故障发生时间" in r.text


def test_create_fault_missing_desc_422(client, user_token, nameplate):
    payload = _base(**{"event_type": "故障", "fault_time": "2026-09-04 08:00:00"})
    r = client.post("/api/v1/batches", json=payload, headers=auth(user_token))
    assert r.status_code == 422
    assert "事件描述" in r.text


def test_create_fault_unknown_fault_type_422(client, user_token, nameplate):
    r = client.post("/api/v1/batches", json=_base(**_fault(fault_type="NOPE_FAULT")),
                    headers=auth(user_token))
    assert r.status_code == 422
    assert "NOPE_FAULT" in r.text


def test_create_fault_disabled_fault_type_422(client, user_token, nameplate):
    r = client.post("/api/v1/batches", json=_base(**_fault(
        fault_type="DISABLED_TEST_FAULT")), headers=auth(user_token))
    assert r.status_code == 422
    assert "停用" in r.text


def test_create_fault_default_unclassified(client, user_token, nameplate):
    b = _create(client, user_token, _base(**_fault()))
    assert b["fault_type"] == "UNCLASSIFIED"
    assert b["severity"] == "故障"                # UNCLASSIFIED 行默认
    assert b["evt_id"] == f"EVT_UNCLASSIFIED_F01_{_YEAR}_001"


def test_create_maint_clears_fault_fields(client, user_token, nameplate):
    payload = _base(event_type="维修", fault_time="2026-09-04 08:00:00",
                    fault_type="GEARBOX_BEARING_WEAR", severity="报警",
                    fault_desc="更换齿轮箱轴承", t_start="2026-09-04 09:00:00",
                    t_end="2026-09-04 11:00:00")
    b = _create(client, user_token, payload)
    assert b["event_type"] == "维修"
    assert b["fault_type"] is None and b["severity"] is None
    assert b["fault_time"] is None
    assert b["fault_desc"] == "更换齿轮箱轴承"     # 维修内容允许申报
    assert b["evt_id"] == f"EVT_MAINT_F01_{_YEAR}_001"


def test_create_normal_clears_fault_fields(client, user_token, nameplate):
    payload = _base(event_type="正常", fault_time="2026-09-04 08:00:00",
                    fault_type="GEARBOX_BEARING_WEAR", severity="故障",
                    fault_desc="基线说明")
    b = _create(client, user_token, payload)
    assert b["event_type"] == "正常"
    assert b["fault_type"] is None and b["severity"] is None
    assert b["fault_time"] is None
    assert b["fault_desc"] == "基线说明"           # 正常态基线说明允许申报
    assert b["evt_id"] == f"EVT_NORMAL_F01_{_YEAR}_001"


def test_create_invalid_event_type_422(client, user_token, nameplate):
    r = client.post("/api/v1/batches", json=_base(event_type="严重"),
                    headers=auth(user_token))
    assert r.status_code == 422


# ---------- B. operating_condition 兼容推断（退役轴） ----------

def test_infer_fault_from_legacy_condition(client, user_token, nameplate):
    """旧客户端仅传 operating_condition=故障 + 时间/描述 → 不 422（§八 零破坏）。"""
    payload = _base(operating_condition="故障", fault_time="2026-09-04 08:00:00",
                    fault_desc="旧客户端故障申报")
    b = _create(client, user_token, payload)
    assert b["event_type"] == "故障"
    assert b["fault_type"] == "UNCLASSIFIED"
    assert b["severity"] == "故障"
    assert b["evt_id"] == f"EVT_UNCLASSIFIED_F01_{_YEAR}_001"


def test_infer_maint_from_legacy_repair(client, user_token, nameplate):
    payload = _base(operating_condition="检修", fault_desc="年度检修")
    b = _create(client, user_token, payload)
    assert b["event_type"] == "维修"
    assert b["fault_time"] is None
    assert b["evt_id"] == f"EVT_MAINT_F01_{_YEAR}_001"


def test_infer_normal_from_legacy_condition(client, user_token, nameplate):
    b = _create(client, user_token, _base(operating_condition="正常"))
    assert b["event_type"] == "正常"


def test_explicit_event_type_wins_over_legacy_condition(client, user_token, nameplate):
    """显式 event_type=正常 与旧轴 operating_condition=故障 冲突 → 显式优先。"""
    payload = _base(event_type="正常", operating_condition="故障",
                    fault_time="2026-09-04 08:00:00", fault_desc="x")
    b = _create(client, user_token, payload)
    assert b["event_type"] == "正常"
    assert b["fault_time"] is None


# ---------- C. 异常区间成对校验 ----------

def test_create_partial_range_422(client, user_token, nameplate):
    r = client.post("/api/v1/batches", json=_base(t_start="2026-09-04 08:00:00"),
                    headers=auth(user_token))
    assert r.status_code == 422
    assert "异常区间" in r.text


def test_create_range_start_after_end_422(client, user_token, nameplate):
    r = client.post("/api/v1/batches", json=_base(
        t_start="2026-09-04 10:00:00", t_end="2026-09-04 08:00:00"),
        headers=auth(user_token))
    assert r.status_code == 422


def test_create_range_pair_ok(client, user_token, nameplate):
    b = _create(client, user_token, _base(
        t_start="2026-09-04 08:00:00", t_end="2026-09-04 08:30:00"))
    assert b["t_start"] == "2026-09-04 08:00:00"
    assert b["t_end"] == "2026-09-04 08:30:00"


# ---------- D. EVT_ID 生成与独立计数 ----------

def test_evt_seq_independent_per_type_device(client, user_token, nameplate,
                                             second_device):
    g1 = _create(client, user_token, _base(**_fault(fault_type="GEARBOX_BEARING_WEAR")))
    n1 = _create(client, user_token, _base(batch_no="E2E-N-1"))
    g2 = _create(client, user_token, _base(batch_no="E2E-N-2", **_fault(
        fault_type="GEARBOX_BEARING_WEAR")))
    g3 = _create(client, user_token, _base(batch_no="E2E-N-3", device_no="F02",
                                           **_fault(fault_type="GEARBOX_BEARING_WEAR")))
    assert g1["evt_id"] == f"EVT_GEARBOX_BEARING_WEAR_F01_{_YEAR}_001"
    assert n1["evt_id"] == f"EVT_NORMAL_F01_{_YEAR}_001"      # 与故障互不干扰
    assert g2["evt_id"] == f"EVT_GEARBOX_BEARING_WEAR_F01_{_YEAR}_002"  # 同类连续
    assert g3["evt_id"] == f"EVT_GEARBOX_BEARING_WEAR_F02_{_YEAR}_001"  # 设备独立


def test_evt_seed_from_existing(client, user_token, db, nameplate):
    """存量直插 EVT_NORMAL_F01_..._005 → 首个自动编号衔接 006（迁移回填兼容）。"""
    from app.models import Batch
    from tests.conftest import utcnow

    ts = utcnow()
    db.add(Batch(id="b-legacy-1", batch_no="B2026-LEGACY", device_no="F01",
                 is_synthetic=0, evt_id=f"EVT_NORMAL_F01_{_YEAR}_005",
                 event_type="正常", event_status="draft",
                 created_at=ts, updated_at=ts))
    db.commit()
    b = _create(client, user_token, _base(batch_no="E2E-N-9"))
    assert b["evt_id"] == f"EVT_NORMAL_F01_{_YEAR}_006"


# ---------- E. update：重算与禁改 ----------

def test_update_type_recalc_evt_id(client, user_token, nameplate):
    b = _create(client, user_token, _base())
    assert b["evt_id"] == f"EVT_NORMAL_F01_{_YEAR}_001"
    r = client.put(f"/api/v1/batches/{b['id']}",
                   json=_fault(), headers=auth(user_token))
    assert r.status_code == 200, r.text
    b2 = r.json()
    assert b2["event_type"] == "故障" and b2["fault_type"] == "UNCLASSIFIED"
    assert b2["evt_id"] == f"EVT_UNCLASSIFIED_F01_{_YEAR}_001"   # 新段值重新起号


def test_update_fault_type_recalc_evt_id(client, user_token, nameplate):
    b = _create(client, user_token, _base(**_fault()))
    assert b["evt_id"] == f"EVT_UNCLASSIFIED_F01_{_YEAR}_001"
    r = client.put(f"/api/v1/batches/{b['id']}",
                   json={"fault_type": "GEARBOX_BEARING_WEAR"}, headers=auth(user_token))
    assert r.status_code == 200, r.text
    assert r.json()["evt_id"] == f"EVT_GEARBOX_BEARING_WEAR_F01_{_YEAR}_001"


def test_update_other_field_keeps_evt_id(client, user_token, nameplate):
    b = _create(client, user_token, _base())
    r = client.put(f"/api/v1/batches/{b['id']}", json={"weather": "阴"},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["evt_id"] == b["evt_id"]


def test_update_maint_recalc_and_clear(client, user_token, nameplate):
    b = _create(client, user_token, _base(**_fault()))
    r = client.put(f"/api/v1/batches/{b['id']}",
                   json={"event_type": "维修", "fault_desc": "更换轴承"},
                   headers=auth(user_token))
    b2 = r.json()
    assert b2["fault_type"] is None and b2["fault_time"] is None
    assert b2["evt_id"] == f"EVT_MAINT_F01_{_YEAR}_001"


def test_update_type_blocked_when_has_files_422(client, user_token, batch_with_file):
    """批次含 DataFile → 禁止改类型（§四 变更规则：防 ID 与引用失联）。"""
    r = client.put("/api/v1/batches/batch-1", json={"event_type": "故障",
                                                    "fault_time": "2026-09-04 08:00:00",
                                                    "fault_desc": "x"},
                   headers=auth(user_token))
    assert r.status_code == 422
    assert "文件" in r.text
    # 改 fault_type（携带完整故障申报 → 类型变更）同样被拦
    r2 = client.put("/api/v1/batches/batch-1",
                    json=_fault(fault_type="GEARBOX_BEARING_WEAR"),
                    headers=auth(user_token))
    assert r2.status_code == 422


def test_update_same_type_keeps_evt_id(client, user_token, nameplate):
    b = _create(client, user_token, _base(**_fault(fault_type="GEARBOX_BEARING_WEAR")))
    r = client.put(f"/api/v1/batches/{b['id']}", json={"severity": "报警"},
                   headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["evt_id"] == b["evt_id"]      # 类型未变不重算


# ---------- F. 事件编码规则（evt_template） ----------

def test_admin_save_evt_template_ok(client, admin_token, user_token):
    r = client.put("/api/v1/admin/batch-no-rule", json=EVT_RULE,
                   headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["evt_template"] == EVT_RULE["evt_template"]
    r2 = client.get("/api/v1/batch-no-rule", headers=auth(user_token))
    assert r2.json()["evt_template"] == EVT_RULE["evt_template"]


def test_admin_save_evt_wo_template_ok(client, admin_token):
    r = client.put("/api/v1/admin/batch-no-rule", json={"template": "B-{YYYY}-{SEQ:3}"},
                   headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["evt_template"] is None       # 未配置 → 服务层用默认模板


def test_evt_template_must_contain_type_code_422(client, admin_token):
    r = client.put("/api/v1/admin/batch-no-rule",
                   json={"template": "B-{YYYY}-{SEQ:3}",
                         "evt_template": "EVT-{SEQ:3}"},
                   headers=auth(admin_token))
    assert r.status_code == 422
    assert "TYPE_CODE" in r.text


def test_batch_template_forbid_type_code_422(client, admin_token):
    r = client.put("/api/v1/admin/batch-no-rule",
                   json={"template": "B-{TYPE_CODE}-{SEQ:3}"},
                   headers=auth(admin_token))
    assert r.status_code == 422
    assert "TYPE_CODE" in r.text


def test_create_uses_configured_evt_template(client, admin_token, user_token,
                                             nameplate):
    client.put("/api/v1/admin/batch-no-rule", json=EVT_RULE, headers=auth(admin_token))
    b = _create(client, user_token, _base(**_fault(fault_type="GEARBOX_BEARING_WEAR")))
    assert b["evt_id"] == "E-GEARBOX_BEARING_WEAR-001"


def test_evt_seq_reuse_template_rule_ok(client, admin_token, user_token, nameplate):
    """同规则行同时驱动 batch_no 与 evt 计数器，互不串扰。"""
    client.put("/api/v1/admin/batch-no-rule", json=EVT_RULE, headers=auth(admin_token))
    b = _create(client, user_token, _base(batch_no="IGNORED", **_fault()))
    assert b["batch_no"].startswith(f"B-{_YEAR}-")
    assert b["evt_id"] == "E-UNCLASSIFIED-001"


# ---------- G. 台账校验 ----------

def test_create_device_not_in_ledger_422(client, user_token):
    """F99 不在本单位 nameplate → 422（§3.5）。"""
    r = client.post("/api/v1/batches", json=_base(device_no="F99"),
                    headers=auth(user_token))
    assert r.status_code == 422
    assert "设备不在台账中" in r.text


def test_create_cross_org_device_422(client, user_token, other_org_nameplate):
    """org-2 的 F01 台账对 org-1 用户不可见 → 同样 422。"""
    r = client.post("/api/v1/batches", json=_base(), headers=auth(user_token))
    assert r.status_code == 422
    assert "设备不在台账中" in r.text


def test_import_device_not_in_ledger_row_failure(client, user_token, storage, db):
    """manifest 导入：F01 成功、F99 行级失败计入报告（§2.6 导入失败行）。"""
    from app.models import Batch
    from app.models.nameplate import Nameplate

    db.add(Nameplate(id="np-imp", organization_id="org-1", device_no="F01",
                     created_at="2026-09-01T00:00:00Z",
                     updated_at="2026-09-01T00:00:00Z"))
    db.commit()
    header = ("目录,batch_no,device_no,device_model,station,license,sensitivity,"
              "owner_contact,is_synthetic,operating_condition,故障发生时间,事件描述,"
              "weather,所属场站\r\n")
    rows = ("IMP1,B2026-IMP-1,F01,,wind,内部专用,内部,,0,正常,,,晴,风电\r\n"
            "IMP2,B2026-IMP-2,F99,,wind,内部专用,内部,,0,正常,,,晴,风电\r\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.csv", b"\xef\xbb\xbf" + (header + rows).encode("utf-8"))
        zf.writestr("IMP1/1.dat", b"data1")
        zf.writestr("IMP2/2.dat", b"data2")
    storage.objects["batch-imports/test/ledger.zip"] = buf.getvalue()
    r = client.post("/api/v1/batch-imports",
                    json={"object_key": "batch-imports/test/ledger.zip"},
                    headers=auth(user_token))
    job = client.get(f"/api/v1/batch-imports/{r.json()['id']}",
                     headers=auth(user_token)).json()
    assert job["status"] == "succeeded", job["report"]
    assert job["report"]["success"] == ["B2026-IMP-1"]
    assert any("设备不在台账中" in e for e in job["report"]["failures"])
    assert db.query(Batch).filter_by(batch_no="B2026-IMP-2").count() == 0


def test_import_template_contains_event_columns(client, user_token):
    """manifest 模板：新申报列就位、旧列名兼容（设计 §六 manifest 行）。"""
    r = client.get("/api/v1/batch-imports/template", headers=auth(user_token))
    assert r.status_code == 200
    text = r.content.decode("utf-8-sig")
    for col in ("事件类型", "故障类型", "严重度", "异常开始", "异常结束",
                "故障发生时间", "事件描述"):
        assert col in text


# ---------- H. nameplate 写权限收紧（§2.6） ----------

def test_user_create_nameplate_403(client, user_token):
    r = client.post("/api/v1/nameplates", json={"device_no": "F01"},
                    headers=auth(user_token))
    assert r.status_code == 403


def test_user_update_nameplate_403(client, user_token, nameplate):
    r = client.put("/api/v1/nameplates/np-1", json={"device_model": "X"},
                   headers=auth(user_token))
    assert r.status_code == 403


def test_admin_create_nameplate_with_org(client, admin_token, org):
    """admin 建台账可显式指定所属单位（§2.6 执行补充：归属缺口补全）。"""
    r = client.post("/api/v1/nameplates",
                    json={"device_no": "F05", "organization_id": "org-1"},
                    headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["organization_id"] == "org-1"


def test_admin_create_nameplate_unknown_org_422(client, admin_token):
    r = client.post("/api/v1/nameplates",
                    json={"device_no": "F06", "organization_id": "org-999"},
                    headers=auth(admin_token))
    assert r.status_code == 422
