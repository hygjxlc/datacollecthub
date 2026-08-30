"""台账模型冒烟测试：建表、插入、唯一约束、级联删除。"""
from sqlalchemy.exc import IntegrityError

from tests.conftest import utcnow


def test_ledger_tables_created(client):
    from sqlalchemy import inspect

    from app.core.db import engine
    from app.models import Event, EventFile, Nameplate, PointDict

    # client fixture 已执行 create_all：新表应真实存在
    assert all(inspect(engine).has_table(t) for t in
               ["nameplate", "point_dict", "event", "event_file"])
    assert Nameplate.__tablename__ == "nameplate"
    assert PointDict.__tablename__ == "point_dict"
    assert Event.__tablename__ == "event"
    assert EventFile.__tablename__ == "event_file"


def test_nameplate_insert_and_unique(client, db, org, user_zhang):
    from app.models import Nameplate

    n = Nameplate(id="np-1", organization_id="org-1", device_no="F01",
                  device_model="金风 GW82/1500", rated_power=1500.0,
                  rotor_diameter=82.0, extras={"备注": "试验样机"},
                  creator_id="user-1", created_at=utcnow(), updated_at=utcnow())
    db.add(n)
    db.commit()
    assert db.get(Nameplate, "np-1").rated_power == 1500.0
    assert db.get(Nameplate, "np-1").extras == {"备注": "试验样机"}
    # 同单位同设备重复 → 唯一约束
    db.add(Nameplate(id="np-2", organization_id="org-1", device_no="F01",
                     creator_id="user-1", created_at=utcnow(), updated_at=utcnow()))
    try:
        db.commit()
        raise AssertionError("应触发唯一约束")
    except IntegrityError:
        db.rollback()


def test_point_dict_insert_and_unique(client, db, org):
    from app.models import PointDict

    db.add(PointDict(id="pd-1", organization_id="org-1", device_no="F01",
                     channel_no="CH1", name="齿轮箱轴承温度", unit="℃",
                     scale_slope=1.0, scale_offset=0.0, data_type="float",
                     created_at=utcnow(), updated_at=utcnow()))
    db.commit()
    assert db.get(PointDict, "pd-1").channel_no == "CH1"
    db.add(PointDict(id="pd-2", organization_id="org-1", device_no="F01",
                     channel_no="CH1", name="重复", created_at=utcnow(),
                     updated_at=utcnow()))
    try:
        db.commit()
        raise AssertionError("应触发唯一约束")
    except IntegrityError:
        db.rollback()


def test_event_cascade_delete_files(client, db, org, own_file):
    from app.models import Event, EventFile

    e = Event(id="ev-1", organization_id="org-1", event_time="2025-06-15 14:23:08",
              timezone="+08:00", device_no="F01", event_type="齿轮箱/轴承/磨损",
              severity="报警", description="温度升至 85℃ 触发报警",
              creator_id="user-1", created_at=utcnow(), updated_at=utcnow())
    db.add(e)
    db.add(EventFile(id="ef-1", event_id="ev-1", datafile_id="file-1"))
    db.commit()
    assert db.get(EventFile, "ef-1") is not None
    db.delete(e)
    db.commit()
    assert db.get(EventFile, "ef-1") is None      # ondelete CASCADE
