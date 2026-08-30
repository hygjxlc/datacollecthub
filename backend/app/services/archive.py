"""下载打包公共逻辑：认证下载（FileService）与集成导出（IntegrationService）共用。

zip 结构（每文件独立文件夹，文件夹名 = 原始文件名去扩展名）：

    <原始文件名去扩展名>/
    ├── <原始文件名>          原始数据
    └── <原始文件名>.json     元数据描述（file 级 + batch 级）

同名文件夹冲突：第二个起加序号前缀（如 `2-<原名>`）。
"""
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (Batch, DataFile, Event, EventFile, Nameplate,
                        Organization, PointDict, User)
from app.schemas.batch import BatchOut
from app.schemas.datafile import DataFileOut
from app.schemas.event import EventOut
from app.schemas.nameplate import NameplateOut
from app.schemas.point_dict import PointDictOut


def _build_device_ledger(db: Session, device_no: str | None,
                         org_id: str | None) -> dict:
    """按设备编号查铭牌/测点字典（限定同单位）；无则 None/[]。"""
    if not device_no or org_id is None:
        return {"nameplate": None, "point_dicts": []}
    nameplate = db.execute(select(Nameplate).where(
        Nameplate.device_no == device_no,
        Nameplate.organization_id == org_id)).scalar_one_or_none()
    points = db.execute(select(PointDict).where(
        PointDict.device_no == device_no,
        PointDict.organization_id == org_id)
        .order_by(PointDict.channel_no)).scalars().all()
    return {
        "nameplate": (NameplateOut.model_validate(nameplate).model_dump()
                      if nameplate else None),
        "point_dicts": [PointDictOut.model_validate(p).model_dump() for p in points],
    }


def _build_related_events(db: Session, df: DataFile) -> list[dict]:
    """关联到该文件的事件列表（事件组数据集锚点，不递归组装 related_files）。"""
    rows = db.execute(
        select(Event).join(EventFile, EventFile.event_id == Event.id)
        .where(EventFile.datafile_id == df.id)
        .order_by(Event.event_time)).scalars().all()
    return [EventOut.model_validate(e).model_dump() for e in rows]


def build_file_metadata(db: Session, df: DataFile) -> dict:
    """文件元数据 JSON：file 级全字段（uploader 补充姓名）+ batch 级全字段
    （organization/creator 补充单位名与创建人姓名）+ 台账三字段
    （nameplate/point_dicts/related_events）。"""
    file_meta = DataFileOut.model_validate(df).model_dump()
    uploader = db.get(User, df.uploader_id) if df.uploader_id else None
    file_meta.pop("uploader_id", None)
    file_meta["uploader"] = uploader.display_name if uploader else None

    batch_meta = None
    org_id = None
    if df.batch_id:
        batch = db.get(Batch, df.batch_id)
        if batch:
            org_id = batch.organization_id
            batch_meta = BatchOut.model_validate(batch).model_dump()
            batch_meta.pop("file_count", None)      # 列表页聚合字段，打包不适用
            batch_meta.pop("total_size", None)
            batch_meta.pop("organization_id", None)
            batch_meta.pop("creator_id", None)
            org = (db.get(Organization, batch.organization_id)
                   if batch.organization_id else None)
            creator = db.get(User, batch.creator_id) if batch.creator_id else None
            batch_meta["organization"] = org.name if org else None
            batch_meta["creator"] = creator.display_name if creator else None
    ledger = _build_device_ledger(db, df.device_no, org_id)
    return {"file": file_meta, "batch": batch_meta,
            "nameplate": ledger["nameplate"],
            "point_dicts": ledger["point_dicts"],
            "related_events": _build_related_events(db, df)}


def build_files_zip(db: Session, storage, files: list[DataFile],
                    download_name: str | None = None) -> tuple[str, str]:
    """打包为 zip：每文件独立文件夹（文件名去扩展名），内含原始数据 + 元数据 JSON。

    返回 (临时文件路径, 下载文件名)；失败时删除临时文件。
    下载文件名：单文件默认 `<原始文件名去扩展名>.zip`，多文件默认
    `datacollecthub-YYYYMMDD.zip`。
    对象缺失时抛 FileNotFoundError（调用方转 404）。
    """
    if not files:
        raise ValueError("files 不能为空")
    tmp_path = tempfile.mktemp(suffix=".zip")
    try:
        used: set[str] = set()
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zf:
            for df in files:
                stem = Path(df.filename).stem
                folder = stem
                seq = 2
                while folder in used:               # 同名文件夹：加序号前缀
                    folder = f"{seq}-{stem}"
                    seq += 1
                used.add(folder)
                try:
                    src = storage.get_object_stream(df.object_key)
                except KeyError:
                    raise FileNotFoundError(df.filename)
                with zf.open(f"{folder}/{df.filename}", "w") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                meta = json.dumps(build_file_metadata(db, df),
                                  ensure_ascii=False, indent=2).encode("utf-8")
                zf.writestr(f"{folder}/{df.filename}.json", meta)
        if download_name is None:
            download_name = (f"{Path(files[0].filename).stem}.zip"
                             if len(files) == 1
                             else f"datacollecthub-{datetime.now():%Y%m%d}.zip")
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return tmp_path, download_name
