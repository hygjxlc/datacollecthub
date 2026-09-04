import csv
import io
import zipfile

from tests.conftest import auth

RULE = {"template": "B-{YYYY}-{SEQ:3}"}
MANIFEST = ("目录,batch_no,device_no,device_model,station,license,sensitivity,"
            "owner_contact,is_synthetic,operating_condition,故障发生时间,事件描述,"
            "weather,所属场站\r\n")


def build_zip(rows, files):
    """rows: list[str]（CSV 数据行）；files: dict[zip 内路径 -> bytes]。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.csv", b"\xef\xbb\xbf" + (MANIFEST + "\r\n".join(rows)).encode("utf-8"))
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


ROW1 = ("F01_20250901,B2025-101,F01,金风 GW82/1500,wind,内部专用,内部,张工,"
        "0,正常,,,晴,风电")
ROW2 = ("F02_20250901,B2025-102,F02,金风 GW82/1500,wind,内部专用,内部,张工,"
        "0,正常,,,晴,光伏")


def create_job(client, user_token, storage, zip_bytes):
    """POST 创建任务（响应体为 pending）→ GET 返回终态。

    TestClient 会在响应返回前同步执行完 background task，
    因此一次 GET 即可拿到导入终态（生产环境由前端轮询）。
    """
    storage.objects["batch-imports/test/import.zip"] = zip_bytes
    r = client.post("/api/v1/batch-imports", json={"object_key": "batch-imports/test/import.zip"},
                    headers=auth(user_token))
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    r2 = client.get(f"/api/v1/batch-imports/{job_id}", headers=auth(user_token))
    assert r2.status_code == 200, r2.text
    return r2.json()


def test_template_download(client, user_token):
    r = client.get("/api/v1/batch-imports/template", headers=auth(user_token))
    assert r.status_code == 200
    assert r.content.startswith(b"\xef\xbb\xbf")          # UTF-8 BOM
    text = r.content.decode("utf-8-sig")
    assert "所属场站" in text
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 1
    assert rows[0]["所属场站"] == "风电"
    assert rows[0]["故障发生时间"] == ""


def test_import_success(client, user_token, storage, db):
    zip_bytes = build_zip(
        [ROW1, ROW2],
        {"F01_20250901/1.dat": b"data1", "F01_20250901/振动/2.bin": b"data2",
         "F02_20250901/3.jpg": b"data3"})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "succeeded", job["report"]
    assert job["total_batches"] == 2 and job["done_batches"] == 2
    assert job["report"]["success"] == ["B2025-101", "B2025-102"]
    # 批次与文件落库
    from app.models import Batch, DataFile

    assert db.query(Batch).filter_by(batch_no="B2025-101").count() == 1
    files = db.query(DataFile).filter_by(batch_no="B2025-101").all()
    assert {f.filename for f in files} == {"1.dat", "2.bin"}
    assert {f.modality for f in files} == {"SCADA", "VIB"}
    assert files[0].object_key.startswith("wind/F01/")
    # zip 临时对象已清理
    assert "batch-imports/test/import.zip" not in storage.objects


def test_import_additional_columns_to_extras(client, user_token, storage, db):
    header = MANIFEST.replace("weather,所属场站", "weather,所属场站,采集周期")
    row = ("F01_20250901,B2025-103,F01,,wind,内部专用,内部,,0,,,,,风电,10min")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.csv", b"\xef\xbb\xbf" + (header + row).encode("utf-8"))
        zf.writestr("F01_20250901/1.dat", b"data1")
    storage.objects["batch-imports/test/e.zip"] = buf.getvalue()
    r = client.post("/api/v1/batch-imports",
                    json={"object_key": "batch-imports/test/e.zip"}, headers=auth(user_token))
    job = client.get(f"/api/v1/batch-imports/{r.json()['id']}",
                     headers=auth(user_token)).json()
    assert job["status"] == "succeeded", job["report"]
    from app.models import Batch

    b = db.query(Batch).filter_by(batch_no="B2025-103").one()
    assert b.extras == {"采集周期": "10min"}
    assert b.equipment_state_type == "风电"


def test_import_precheck_failure_all_or_nothing(client, user_token, storage, db):
    """第 2 行缺设备编号 → 预检失败，不创建任何批次。"""
    bad = ("F02_20250901,B2025-102,,,wind,内部专用,内部,,0,,,,,光伏")
    zip_bytes = build_zip([ROW1, bad],
                          {"F01_20250901/1.dat": b"data1", "F02_20250901/3.jpg": b"data3"})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "failed"
    assert any("设备/机组编号" in e for e in job["report"]["errors"])
    from app.models import Batch

    assert db.query(Batch).count() == 0


def test_import_undeclared_dir_error(client, user_token, storage):
    zip_bytes = build_zip([ROW1],
                          {"F01_20250901/1.dat": b"data1", "GHOST/9.dat": b"ghost"})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "failed"
    assert any("GHOST" in e for e in job["report"]["errors"])


def test_import_empty_dir_error(client, user_token, storage):
    """清单声明的批次目录无任何文件 → 预检失败（目录非空约束）。"""
    zip_bytes = build_zip([ROW1], {"F01_20250901/": b""})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "failed"
    assert any("空批次目录" in e for e in job["report"]["errors"])


def test_import_invalid_enum_error(client, user_token, storage):
    bad = ROW1.replace("风电", "核电")
    zip_bytes = build_zip([bad], {"F01_20250901/1.dat": b"data1"})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "failed"
    assert any("核电" in e for e in job["report"]["errors"])


def test_import_fault_requires_fault_columns(client, user_token, storage):
    """运行工况=故障 但缺事件描述 → 预检失败（全有或全无）。"""
    bad = ROW1.replace("0,正常,,,晴,风电", "0,故障,2026-09-04 08:00:00,,晴,风电")
    zip_bytes = build_zip([bad], {"F01_20250901/1.dat": b"data1"})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "failed"
    assert any("事件描述" in e for e in job["report"]["errors"])


def test_import_fault_fields_persisted(client, user_token, storage, db):
    """故障行填全时间+描述 → 入库。"""
    row = ROW1.replace("0,正常,,,晴,风电",
                       "0,故障,2026-09-04 08:00:00,齿轮箱轴承温度超限停机,晴,风电")
    zip_bytes = build_zip([row], {"F01_20250901/1.dat": b"data1"})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "succeeded", job["report"]
    from app.models import Batch

    b = db.query(Batch).filter_by(batch_no="B2025-101").one()
    assert b.operating_condition == "故障"
    assert b.fault_time == "2026-09-04 08:00:00"
    assert b.fault_desc == "齿轮箱轴承温度超限停机"


def test_import_invalid_condition_error(client, user_token, storage):
    bad = ROW1.replace("0,正常,,,晴,风电", "0,停运,,,晴,风电")
    zip_bytes = build_zip([bad], {"F01_20250901/1.dat": b"data1"})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "failed"
    assert any("运行工况非法" in e for e in job["report"]["errors"])


def test_import_legacy_state_column_still_parsed(client, user_token, storage, db):
    """旧模板列名“数据对应设备:状态类型”仍可解析（新列名兼容回退）。"""
    header = MANIFEST.replace("weather,所属场站", "weather,数据对应设备:状态类型")
    row = ROW1.replace("0,正常,,,晴,风电", "0,正常,,,晴,光伏")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.csv", b"\xef\xbb\xbf" + (header + row).encode("utf-8"))
        zf.writestr("F01_20250901/1.dat", b"data1")
    storage.objects["batch-imports/test/legacy.zip"] = buf.getvalue()
    r = client.post("/api/v1/batch-imports",
                    json={"object_key": "batch-imports/test/legacy.zip"},
                    headers=auth(user_token))
    job = client.get(f"/api/v1/batch-imports/{r.json()['id']}",
                     headers=auth(user_token)).json()
    assert job["status"] == "succeeded", job["report"]
    from app.models import Batch

    b = db.query(Batch).filter_by(batch_no="B2025-101").one()
    assert b.equipment_state_type == "光伏"
    assert b.extras is None          # 旧列名不落入 extras


def test_import_missing_manifest(client, user_token, storage):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("F01_20250901/1.dat", b"data1")
    storage.objects["batch-imports/test/no-manifest.zip"] = buf.getvalue()
    r = client.post("/api/v1/batch-imports",
                    json={"object_key": "batch-imports/test/no-manifest.zip"},
                    headers=auth(user_token))
    job = client.get(f"/api/v1/batch-imports/{r.json()['id']}",
                     headers=auth(user_token)).json()
    assert job["status"] == "failed"
    assert any("manifest.csv" in e for e in job["report"]["errors"])


def test_import_batch_no_auto_when_rule_enabled(client, admin_token, user_token, storage, db):
    client.put("/api/v1/admin/batch-no-rule", json=RULE, headers=auth(admin_token))
    row = ("F01_20250901,,F01,,wind,内部专用,内部,,0,,,,,风电")
    zip_bytes = build_zip([row], {"F01_20250901/1.dat": b"data1"})
    job = create_job(client, user_token, storage, zip_bytes)
    assert job["status"] == "succeeded", job["report"]
    from datetime import datetime, timezone

    from app.models import Batch
    year = datetime.now(timezone.utc).year
    assert db.query(Batch).filter_by(batch_no=f"B-{year}-001").count() == 1


def test_import_idempotent_rerun_skipped(client, user_token, storage, db):
    zip_bytes = build_zip([ROW1], {"F01_20250901/1.dat": b"data1"})
    storage.objects["batch-imports/test/imp.zip"] = zip_bytes
    r1 = client.post("/api/v1/batch-imports", json={"object_key": "batch-imports/test/imp.zip"},
                     headers=auth(user_token)).json()
    job1 = client.get(f"/api/v1/batch-imports/{r1['id']}",
                      headers=auth(user_token)).json()
    assert job1["status"] == "succeeded"
    storage.objects["batch-imports/test/imp.zip"] = zip_bytes   # 首轮已删除，补回重跑
    r2 = client.post("/api/v1/batch-imports", json={"object_key": "batch-imports/test/imp.zip"},
                     headers=auth(user_token)).json()
    job2 = client.get(f"/api/v1/batch-imports/{r2['id']}",
                      headers=auth(user_token)).json()
    assert job2["status"] == "succeeded"
    assert any("B2025-101" in s for s in job2["report"].get("skipped", []))
    from app.models import Batch

    assert db.query(Batch).filter_by(batch_no="B2025-101").count() == 1
