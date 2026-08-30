import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

# 必须在 import app 之前设置环境变量（config.settings 在 import 时实例化）
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_dch.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


_FAKE_STORAGE = None   # client fixture 与 storage fixture 共享同一注入实例


@pytest.fixture()
def client():
    global _FAKE_STORAGE
    from app.main import app
    from app.core.db import Base, engine
    from app.storage.minio import FakeStorage, get_storage

    Base.metadata.drop_all(engine)   # 每个测试重建
    Base.metadata.create_all(engine)
    # 默认注入 FakeStorage：任何路由触发 get_storage 都不会去连真实 MinIO
    _FAKE_STORAGE = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: _FAKE_STORAGE
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_storage, None)
    _FAKE_STORAGE = None


@pytest.fixture()
def db():
    from app.core.db import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def org(db):
    """辉腾梁风电场（org-1）。"""
    from app.models import Organization

    o = Organization(id="org-1", name="辉腾梁风电场", type="场站",
                     created_at=utcnow(), updated_at=utcnow())
    db.add(o)
    db.commit()
    return o


@pytest.fixture()
def user_zhang(db, org):
    """普通用户 zhang（org-1，密码 pass123）。"""
    from app.models import User
    from app.core.security import hash_password

    u = User(id="user-1", username="zhang", display_name="张工",
             password_hash=hash_password("pass123"), role="user",
             organization_id="org-1", is_active=1, created_at=utcnow())
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def user_li(db, org):
    """普通用户 li（org-1，与 zhang 同单位，用于归属校验）。"""
    from app.models import User
    from app.core.security import hash_password

    u = User(id="user-2", username="li", display_name="李工",
             password_hash=hash_password("pass123"), role="user",
             organization_id="org-1", is_active=1, created_at=utcnow())
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def admin(db):
    """系统管理员。"""
    from app.models import User
    from app.core.security import hash_password

    u = User(id="admin-1", username="admin", display_name="管理员",
             password_hash=hash_password("admin123"), role="admin",
             organization_id=None, is_active=1, created_at=utcnow())
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def user_token(user_zhang):
    from app.core.security import create_access_token

    return create_access_token(user_zhang)


@pytest.fixture()
def other_user_token(user_li):
    from app.core.security import create_access_token

    return create_access_token(user_li)


@pytest.fixture()
def admin_token(admin):
    from app.core.security import create_access_token

    return create_access_token(admin)


@pytest.fixture()
def batch(db, org, user_zhang):
    """zhang 创建的批次（org-1，station 用场站简码 wind）。"""
    from app.models import Batch

    b = Batch(id="batch-1", batch_no="B2025-001", device_no="F01",
              device_model="金风 GW82/1500", station="wind",
              license="内部专用", sensitivity="内部", owner_contact="张工",
              is_synthetic=0, operating_condition="正常", weather="晴",
              organization_id="org-1", creator_id="user-1",
              created_at=utcnow(), updated_at=utcnow())
    db.add(b)
    db.commit()
    return b


@pytest.fixture()
def own_file(db, batch, user_zhang, storage):
    """zhang 上传的文件（org-1/batch-1，SCADA 模态，元数据部分未填）。"""
    from app.models import DataFile

    df = DataFile(id="file-1", batch_id="batch-1", batch_no="B2025-001",
                  object_key="wind/F01/scada/2025/06/SCADA_F01_20250615_1423.dat",
                  filename="SCADA_F01_20250615_1423.dat", file_size=5242880,
                  modality="SCADA", device_no="F01", station="wind",
                  license="内部专用", sensitivity="内部", is_synthetic=0,
                  operating_condition="正常", weather="晴",
                  start_time="2025-06-15 14:23:08",
                  timezone=None, sample_period="1s",
                  uploader_id="user-1", upload_status="已完成",
                  created_at="2026-08-27T10:00:00Z",
                  updated_at="2026-08-27T10:00:00Z")
    db.add(df)
    db.commit()
    storage.objects[df.object_key] = b"file-content"   # 预置对象供删除/保留断言
    return df


@pytest.fixture()
def files_fixture(db, own_file, other_org_batch):
    """检索/集成接口数据集：file-1 SCADA + file-2 AUD（本单位）+ file-3 CAM（他单位）。"""
    from app.models import DataFile

    df2 = DataFile(id="file-2", batch_id="batch-1", batch_no="B2025-001",
                   object_key="wind/F01/aud/2025/06/AUD_F01_20250615_1430.wav",
                   filename="AUD_F01_20250615_1430.wav", file_size=1024000,
                   modality="AUD", device_no="F01", station="wind",
                   license="内部专用", sensitivity="内部", is_synthetic=0,
                   uploader_id="user-1", upload_status="已完成",
                   start_time="2025-06-16 14:30:00", timezone=None,
                   created_at="2026-08-27T11:00:00Z",
                   updated_at="2026-08-27T11:00:00Z")
    df3 = DataFile(id="file-3", batch_id="batch-2", batch_no="B2025-002",
                   object_key="dafeng/F01/cam/2025/07/CAM_F01_20250701_0920.jpg",
                   filename="CAM_F01_20250701_0920.jpg", file_size=2048000,
                   modality="CAM", device_no="F01", station="dafeng",
                   license="内部专用", sensitivity="内部", is_synthetic=0,
                   uploader_id=None, upload_status="已完成",
                   created_at="2026-08-27T12:00:00Z",
                   updated_at="2026-08-27T12:00:00Z")
    db.add_all([df2, df3])
    db.commit()
    return [own_file, df2, df3]


@pytest.fixture()
def many_files(db, batch):
    """30 个文件：供集成接口分页不重不漏测试（>单页容量）。"""
    from app.models import DataFile

    rows = []
    for i in range(30):
        rows.append(DataFile(
            id=f"file-many-{i:03d}", batch_id="batch-1", batch_no="B2025-001",
            object_key=f"wind/F01/scada/2025/06/SCADA_F01_20250615_{i:04d}.dat",
            filename=f"SCADA_F01_20250615_{i:04d}.dat", file_size=1048576,
            modality="SCADA", device_no="F01", station="wind",
            license="内部专用", sensitivity="内部", is_synthetic=0,
            uploader_id="user-1", upload_status="已完成",
            created_at=f"2026-08-2{i % 10}T10:00:00Z",
            updated_at=f"2026-08-2{i % 10}T10:00:00Z"))
    db.add_all(rows)
    db.commit()
    return rows


@pytest.fixture()
def batch_with_file(db, batch, own_file):
    """含文件 file-1 的批次（供 Excel 导出测试）。"""
    from app.models import Batch

    return db.get(Batch, batch.id)


@pytest.fixture()
def storage(client):
    """FakeStorage 句柄（注入由 client fixture 统一完成）。"""
    return _FAKE_STORAGE


@pytest.fixture()
def other_org_batch(db):
    """大丰光伏（org-2）的批次，用于跨单位 404 校验。"""
    from app.models import Batch, Organization

    org2 = Organization(id="org-2", name="大丰光伏电站", type="场站",
                        created_at=utcnow(), updated_at=utcnow())
    db.add(org2)
    db.commit()
    b = Batch(id="batch-2", batch_no="B2025-002", device_no="F01",
              device_model="", station="dafeng",
              license="内部专用", sensitivity="内部", owner_contact="王工",
              is_synthetic=0, operating_condition="", weather="",
              organization_id="org-2", creator_id=None,
              created_at=utcnow(), updated_at=utcnow())
    db.add(b)
    db.commit()
    return b


@pytest.fixture()
def nameplate(db, org, user_zhang):
    """F01 铭牌（org-1）。"""
    from app.models import Nameplate

    n = Nameplate(id="np-1", organization_id="org-1", device_no="F01",
                  device_model="金风 GW82/1500", rated_power=1500.0,
                  rated_wind_speed=10.5, rotor_diameter=82.0, hub_height=70.0,
                  bearing_model="SKF 240/600", gearbox_ratio=104.5,
                  generator_model="天元 1.5MW", manufacturer="金风科技",
                  commission_date="2015-06-30", design_life_years=20,
                  extras={"机型": "GW82/1500"},
                  creator_id="user-1", created_at=utcnow(), updated_at=utcnow())
    db.add(n)
    db.commit()
    return n


@pytest.fixture()
def other_org_nameplate(db, other_org_batch):
    """org-2 的 F01 铭牌（跨单位 404 校验）。"""
    from app.models import Nameplate

    n = Nameplate(id="np-2", organization_id="org-2", device_no="F01",
                  device_model="远景 EN-110", creator_id=None,
                  created_at=utcnow(), updated_at=utcnow())
    db.add(n)
    db.commit()
    return n


@pytest.fixture()
def point_dict(db, org):
    """F01 测点字典 2 条（org-1，供任务 3/6 测试使用）。"""
    from app.models import PointDict

    rows = [
        PointDict(id="pd-1", organization_id="org-1", device_no="F01",
                  channel_no="CH1", name="齿轮箱轴承温度", unit="℃",
                  scale_slope=1.0, scale_offset=0.0, data_type="float",
                  range_min=-40.0, range_max=150.0, description="主轴测点",
                  created_at=utcnow(), updated_at=utcnow()),
        PointDict(id="pd-2", organization_id="org-1", device_no="F01",
                  channel_no="CH2", name="有功功率", unit="kW",
                  scale_slope=10.0, scale_offset=0.0, data_type="float",
                  created_at=utcnow(), updated_at=utcnow()),
    ]
    db.add_all(rows)
    db.commit()
    return rows


@pytest.fixture()
def event(db, org, own_file):
    """F01 报警事件（org-1，关联 file-1，供任务 4/6 测试使用）。"""
    from app.models import Event, EventFile

    e = Event(id="ev-1", organization_id="org-1", event_time="2025-06-15 14:23:08",
              timezone="+08:00", device_no="F01", event_type="齿轮箱/轴承/磨损",
              severity="报警", description="齿轮箱轴承温度持续升高至 85℃，触发报警停机",
              creator_id="user-1", created_at=utcnow(), updated_at=utcnow())
    db.add(e)
    db.add(EventFile(id="ef-1", event_id="ev-1", datafile_id="file-1"))
    db.commit()
    return e


@pytest.fixture()
def other_org_point_dict(db, other_org_batch):
    """org-2 的测点字典（跨单位 404 校验）。"""
    from app.models import PointDict

    p = PointDict(id="pd-9", organization_id="org-2", device_no="F01",
                  channel_no="CH1", name="辐照度", unit="W/m2",
                  created_at=utcnow(), updated_at=utcnow())
    db.add(p)
    db.commit()
    return p


@pytest.fixture()
def other_org_event(db, other_org_batch):
    """org-2 的事件（跨单位 404 校验）。"""
    from app.models import Event

    e = Event(id="ev-9", organization_id="org-2", event_time="2025-07-01 09:00:00",
              timezone="+08:00", device_no="F01", event_type="光伏/逆变器/停机",
              severity="故障", description="他单位事件",
              creator_id=None, created_at=utcnow(), updated_at=utcnow())
    db.add(e)
    db.commit()
    return e
