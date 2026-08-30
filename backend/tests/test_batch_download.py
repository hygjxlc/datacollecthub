"""批量打包下载接口测试（TC-DOWNLOAD）。"""
import io
import json
import zipfile

from tests.conftest import auth


def test_batch_download_zip(client, files_fixture, user_token, storage):
    # file-2 对象在 FakeStorage 预置（fixture 仅预置 file-1）
    storage.objects["wind/F01/aud/2025/06/AUD_F01_20250615_1430.wav"] = b"aud-content"
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ["file-1", "file-2"]}, headers=auth(user_token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    # 每文件独立文件夹（文件名去扩展名），内含原始数据 + <文件名>.json 元数据
    assert set(zf.namelist()) == {
        "SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat",
        "SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat.json",
        "AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav",
        "AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav.json",
    }
    assert zf.read("SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat") == b"file-content"
    assert zf.read("AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav") == b"aud-content"
    meta = json.loads(zf.read("SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat.json"))
    assert meta["file"]["filename"] == "SCADA_F01_20250615_1423.dat"
    assert meta["file"]["modality"] == "SCADA"
    assert meta["file"]["sample_period"] == "1s"
    assert meta["file"]["start_time"] == "2025-06-15 14:23:08"
    assert meta["file"]["uploader"] == "张工"
    assert meta["batch"]["batch_no"] == "B2025-001"
    assert meta["batch"]["organization"] == "辉腾梁风电场"
    assert meta["batch"]["creator"] == "张工"


def test_batch_download_single_zip_name(client, files_fixture, user_token):
    # 单文件打包：下载文件名 = 原始文件名去扩展名 .zip
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ["file-1"]}, headers=auth(user_token))
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "SCADA_F01_20250615_1423.zip" in cd


def test_batch_download_cross_org_404(client, files_fixture, user_token):
    # file-3 属他单位（org-2），按 get_file 语义 404 且不打包任何文件
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ["file-1", "file-3"]}, headers=auth(user_token))
    assert resp.status_code == 404


def test_batch_download_invalid_id_404(client, files_fixture, user_token):
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ["file-1", "no-such-id"]}, headers=auth(user_token))
    assert resp.status_code == 404


def test_batch_download_empty_ids_422(client, user_token):
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": []}, headers=auth(user_token))
    assert resp.status_code == 422


def test_batch_download_over_limit_422(client, user_token):
    ids = [f"file-{i}" for i in range(21)]
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ids}, headers=auth(user_token))
    assert resp.status_code == 422


def test_batch_download_duplicate_names_prefixed(db, client, files_fixture, user_token, storage):
    # 同名文件：第二个同名对象 → 文件夹加序号前缀，文件与 JSON 保持原名
    storage.objects["wind/F01/aud/2025/06/AUD_F01_20250615_1430.wav"] = b"aud-content"
    storage.objects["wind/F01/aud/2025/06/dup_AUD_F01_20250615_1430.wav"] = b"dup-content"
    from app.models import DataFile

    df4 = DataFile(id="file-4", batch_id="batch-1", batch_no="B2025-001",
                   object_key="wind/F01/aud/2025/06/dup_AUD_F01_20250615_1430.wav",
                   filename="AUD_F01_20250615_1430.wav", file_size=1024000,
                   modality="AUD", device_no="F01", station="wind",
                   license="内部专用", sensitivity="内部", is_synthetic=0,
                   uploader_id="user-1", upload_status="已完成",
                   created_at="2026-08-27T13:00:00Z",
                   updated_at="2026-08-27T13:00:00Z")
    db.add(df4)
    db.commit()
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ["file-2", "file-4"]}, headers=auth(user_token))
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert "AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav" in zf.namelist()
    assert "2-AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav" in zf.namelist()
    assert "2-AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav.json" in zf.namelist()
    assert zf.read("2-AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav") == b"dup-content"


def test_batch_download_zip_with_ledger(client, files_fixture, user_token, storage,
                                        nameplate, point_dict, event):
    """有台账时：元数据 JSON 附带 nameplate/point_dicts/related_events。"""
    storage.objects["wind/F01/aud/2025/06/AUD_F01_20250615_1430.wav"] = b"aud-content"
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ["file-1"]}, headers=auth(user_token))
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    meta = json.loads(zf.read("SCADA_F01_20250615_1423/SCADA_F01_20250615_1423.dat.json"))
    assert meta["nameplate"]["device_no"] == "F01"
    assert meta["nameplate"]["rated_power"] == 1500.0
    assert meta["nameplate"]["extras"] == {"机型": "GW82/1500"}
    assert [p["channel_no"] for p in meta["point_dicts"]] == ["CH1", "CH2"]
    assert meta["point_dicts"][0]["name"] == "齿轮箱轴承温度"
    assert len(meta["related_events"]) == 1
    assert meta["related_events"][0]["severity"] == "报警"
    assert meta["related_events"][0]["event_type"] == "齿轮箱/轴承/磨损"
    assert meta["related_events"][0]["related_files"] == []   # 不递归组装


def test_batch_download_zip_without_ledger(client, files_fixture, user_token, storage):
    """无台账时：三字段为 null/空数组，不阻断下载。"""
    storage.objects["wind/F01/aud/2025/06/AUD_F01_20250615_1430.wav"] = b"aud-content"
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ["file-2"]}, headers=auth(user_token))
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    meta = json.loads(zf.read("AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav.json"))
    assert meta["nameplate"] is None
    assert meta["point_dicts"] == []
    assert meta["related_events"] == []


def test_batch_download_orphan_ledger_not_attached(client, files_fixture, admin_token,
                                                   storage, db):
    """无批次文件 + 孤儿台账（organization_id IS NULL）不得误关联。"""
    from sqlalchemy import update as sa_update
    from app.models import DataFile, Nameplate
    from tests.conftest import utcnow

    # 将 file-2 置为无批次文件（batch_id=None），命中 org_id=None 的导出路径；
    # 无批次文件对普通用户不可见（get_file 归属校验 404），故用 admin 打包下载触发。
    db.execute(sa_update(DataFile).where(DataFile.id == "file-2")
               .values(batch_id=None))
    db.commit()

    # 构造孤儿铭牌：organization_id 为 NULL、device_no 与 file 相同
    db.add(Nameplate(id="np-orphan", organization_id=None, device_no="F01",
                     device_model="孤儿机型", creator_id=None,
                     created_at=utcnow(), updated_at=utcnow()))
    db.commit()
    storage.objects["wind/F01/aud/2025/06/AUD_F01_20250615_1430.wav"] = b"aud-content"
    resp = client.post("/api/v1/files/batch-download",
                       json={"ids": ["file-2"]}, headers=auth(admin_token))
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    meta = json.loads(zf.read("AUD_F01_20250615_1430/AUD_F01_20250615_1430.wav.json"))
    assert meta["nameplate"] is None
    assert meta["point_dicts"] == []
