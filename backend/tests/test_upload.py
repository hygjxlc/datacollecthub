from tests.conftest import auth

FILENAME = "SCADA_F01_20250615_1423.dat"


def _init(client, token, batch_id="batch-1", filename=FILENAME, size=5242880):
    return client.post(f"/api/v1/batches/{batch_id}/files/upload/init",
                       json={"filename": filename, "file_size": size},
                       headers=auth(token))


def _complete(client, token, upload_id, object_key, batch_id="batch-1",
              filename=FILENAME, size=5242880):
    return client.post(f"/api/v1/batches/{batch_id}/files/upload/{upload_id}/complete",
                       json={"object_key": object_key, "filename": filename,
                             "file_size": size,
                             "parts": [{"part_number": 1, "etag": "fake-etag"}]},
                       headers=auth(token))


def test_init_returns_upload_id_and_parts(client, user_token, batch, storage):
    r = _init(client, user_token)
    assert r.status_code == 200
    body = r.json()
    assert body["upload_id"]
    assert body["object_key"].startswith("wind/F01/scada/")
    assert len(body["parts"]) == 1          # 5MB ≤ 10MB → 1 片（TC-UP-001）
    assert body["parts"][0]["part_number"] == 1
    assert body["parts"][0]["url"].startswith("http")


def test_init_large_file_multi_parts(client, user_token, batch, storage):
    r = _init(client, user_token, size=25 * 1024 * 1024)
    assert r.status_code == 200
    assert len(r.json()["parts"]) == 3      # 25MB → 3 片


def test_init_cross_org_batch_404(client, user_token, other_org_batch, storage):
    r = _init(client, user_token, batch_id="batch-2")
    assert r.status_code == 404             # 跨单位批次不可见


def test_init_duplicate_object_key_422(client, user_token, batch, storage, db):
    from app.models import DataFile
    from tests.conftest import utcnow

    key = f"wind/F01/scada/2026/08/{FILENAME}"
    db.add(DataFile(id="file-x", batch_id="batch-1", object_key=key,
                    filename=FILENAME, file_size=1, modality="SCADA",
                    uploader_id="user-1", upload_status="已完成",
                    created_at=utcnow(), updated_at=utcnow()))
    db.commit()
    r = _init(client, user_token)
    assert r.status_code == 422             # object_key 唯一，永不覆盖（TC-UP-005）


def test_complete_creates_datafile_with_inherited_batch(client, user_token, batch, storage):
    init_body = _init(client, user_token).json()
    r = _complete(client, user_token, init_body["upload_id"], init_body["object_key"])
    assert r.status_code == 200
    df = r.json()
    assert df["modality"] == "SCADA"        # 扩展名推断
    assert df["object_key"] == init_body["object_key"]
    assert df["batch_no"] == "B2025-001"
    # 批次字段快照继承（TC-META-001 / F6）
    assert df["device_no"] == "F01"
    assert df["station"] == "wind"
    assert df["license"] == "内部专用"
    assert df["sensitivity"] == "内部"
    assert df["is_synthetic"] == 0
    assert df["operating_condition"] == "正常"
    assert df["weather"] == "晴"
    assert df["uploader_id"] == "user-1"
    assert df["upload_status"] == "已完成"
    assert df["timezone"] is None           # 上传时留空，由 F5 补填（架构 4.4）
    assert storage.exists(init_body["object_key"]) is True


def test_complete_unknown_upload_id_400(client, user_token, batch, storage):
    r = _complete(client, user_token, "no-such-upload",
                  f"wind/F01/scada/2026/08/{FILENAME}")
    assert r.status_code == 400


def test_complete_writes_audit(client, user_token, batch, storage, db):
    from app.models import AuditLog

    init_body = _init(client, user_token).json()
    _complete(client, user_token, init_body["upload_id"], init_body["object_key"])
    log = db.query(AuditLog).filter_by(entity_type="datafile", action="create").one()
    assert log.username == "zhang"
