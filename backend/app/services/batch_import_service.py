"""多批次批量导入：manifest 校验（全有或全无）+ 逐批次解压入库 + 模板生成。

zip 约定：manifest.csv（顶层，UTF-8 BOM）+ 每批次一个第一层子目录。
object_key 保留批次目录内相对路径：<场站>/<设备>/<模态>/<年>/<月>/<相对路径>。
"""
import csv
import io
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.models import Batch, BatchImport, DataFile
from app.schemas.batch_import import BatchImportOut
from app.services.audit import write_audit
from app.services.common import utcnow
from app.services.upload_service import infer_modality
from app.storage.minio import ObjectStorage

FIXED_MANIFEST_COLUMNS = ["目录", "batch_no", "device_no", "device_model", "station",
                          "license", "sensitivity", "owner_contact", "is_synthetic",
                          "operating_condition", "故障发生时间", "事件描述", "weather",
                          "所属场站"]
REQUIRED_MANIFEST_COLUMNS = ["目录", "device_no", "license", "sensitivity",
                             "is_synthetic", "所属场站"]
LICENSE_VALUES = {"内部专用", "CC-BY", "MIT"}
SENSITIVITY_VALUES = {"公开", "内部", "机密"}
STATE_TYPE_VALUES = {"风电", "光伏", "火电", "其它"}
OPERATING_CONDITION_VALUES = {"正常", "故障", "检修"}
# 旧模板兼容：字段由“数据对应设备:状态类型”更名为“所属场站”，旧列名仍可解析
STATE_COLUMN = "所属场站"
STATE_COLUMN_LEGACY = "数据对应设备:状态类型"
SAMPLE_ROW = {"目录": "F01_20250901", "batch_no": "B2026-001", "device_no": "F01",
              "device_model": "金风 GW82/1500", "station": "辉腾梁风电场",
              "license": "内部专用", "sensitivity": "内部",
              "owner_contact": "张工 138****", "is_synthetic": "0",
              "operating_condition": "正常", "故障发生时间": "", "事件描述": "",
              "weather": "晴", "所属场站": "风电"}


def _col_value(row: dict, *names: str) -> str:
    """按候选列名顺序取首个非空值（兼容更名前的旧列名）。"""
    for n in names:
        v = row.get(n)
        if v:
            return v
    return ""


def _zip_batch_dirs(zf: zipfile.ZipFile) -> tuple[set[str], dict[str, int]]:
    """返回 (第一层子目录集合, 各目录文件条目数)；兼容无显式目录条目的 zip。"""
    dirs = set()
    file_counts: dict[str, int] = {}
    for name in zf.namelist():
        is_dir = name.endswith("/")
        clean = name.rstrip("/")
        seg = clean.split("/")[0]
        if "/" in clean or is_dir:
            dirs.add(seg)
            if not is_dir:
                file_counts[seg] = file_counts.get(seg, 0) + 1
    dirs = {d for d in dirs if d and d != "manifest.csv"}
    return dirs, file_counts


def run_import_job(job_id: str, storage: ObjectStorage) -> None:
    """后台任务入口：独立会话，异常兜底置 failed。"""
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        BatchImportService(db).run_import(job_id, storage)
    finally:
        db.close()


class BatchImportService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- 模板 ----------

    def build_template_csv(self) -> bytes:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=FIXED_MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerow(SAMPLE_ROW)
        return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")

    # ---------- 任务管理 ----------

    def create_job(self, object_key: str, user) -> BatchImport:
        now = utcnow()
        job = BatchImport(id=str(uuid.uuid4()), status="pending",
                          object_key=object_key,
                          organization_id=user.organization_id,
                          creator_id=user.id, total_batches=0, done_batches=0,
                          report=None, created_at=now, updated_at=now)
        self.db.add(job)
        self.db.commit()
        return job

    def get_job(self, job_id: str, user) -> BatchImport:
        job = self.db.get(BatchImport, job_id)
        if job is None:
            raise not_found("导入任务不存在")
        from app.repositories.base import assert_org_visible
        assert_org_visible(job, user)
        return job

    def list_jobs(self, user, page: int = 1, page_size: int = 20) -> dict:
        from app.repositories.base import filter_by_org

        query = filter_by_org(select(BatchImport), BatchImport,
                              user.organization_id, user.role == "admin")
        total = len(self.db.execute(query).scalars().all())
        rows = self.db.execute(query.order_by(BatchImport.created_at.desc())
                               .offset((page - 1) * page_size)
                               .limit(page_size)).scalars().all()
        return {"items": [BatchImportOut.model_validate(r) for r in rows],
                "total": total, "page": page, "page_size": page_size}

    # ---------- 解析与预检 ----------

    def parse_manifest(self, content: bytes) -> tuple[list[dict], list[str], list[str]]:
        """返回 (rows, extra_columns, errors)；rows 内 _line 为清单行号（2 起）。"""
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return [], [], ["manifest.csv 必须为 UTF-8 编码"]
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames or []
        effective = [STATE_COLUMN if c == STATE_COLUMN_LEGACY else c for c in fieldnames]
        errors = [f"缺少必需列：{c}" for c in REQUIRED_MANIFEST_COLUMNS
                  if c not in effective]
        # 旧列名（数据对应设备:状态类型）已并入固定列集合，不视为附加列
        extra_columns = [c for c in fieldnames
                         if c and c not in FIXED_MANIFEST_COLUMNS
                         and c != STATE_COLUMN_LEGACY]
        rows = []
        for line, raw in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in raw.items() if v is not None}
            row["_line"] = line
            rows.append(row)
        return rows, extra_columns, errors

    def precheck(self, rows, dirs, file_counts, rule) -> list[str]:
        errors = []
        declared = []
        seen_batch_nos = set()
        for row in rows:
            line = row["_line"]
            dir_name = row.get("目录", "")
            if not dir_name:
                errors.append(f"第 {line} 行：目录不能为空")
                continue
            declared.append(dir_name)
            if dir_name not in dirs:
                errors.append(f"第 {line} 行：目录 {dir_name} 不存在于 zip 中")
            elif file_counts.get(dir_name, 0) == 0:
                errors.append(f"第 {line} 行：目录 {dir_name} 为空批次目录")
            if not row.get("device_no"):
                errors.append(f"第 {line} 行：设备/机组编号不能为空")
            if row.get("license") not in LICENSE_VALUES:
                errors.append(f"第 {line} 行：许可证非法（{row.get('license')}）")
            if row.get("sensitivity") not in SENSITIVITY_VALUES:
                errors.append(f"第 {line} 行：敏感级别非法（{row.get('sensitivity')}）")
            if row.get("is_synthetic") not in {"0", "1"}:
                errors.append(f"第 {line} 行：是否合成/仿真数据须为 0/1")
            state = _col_value(row, STATE_COLUMN, STATE_COLUMN_LEGACY)
            if state not in STATE_TYPE_VALUES:
                errors.append(f"第 {line} 行：所属场站非法（{state}）")
            # 新旧列名并存且值不一致 → 冲突，提示仅保留一列
            if (row.get(STATE_COLUMN) and row.get(STATE_COLUMN_LEGACY)
                    and row.get(STATE_COLUMN) != row.get(STATE_COLUMN_LEGACY)):
                errors.append(f"第 {line} 行：{STATE_COLUMN} 与旧列名 "
                              f"{STATE_COLUMN_LEGACY} 值冲突，请仅保留一列")
            cond = row.get("operating_condition", "")
            if cond and cond not in OPERATING_CONDITION_VALUES:
                errors.append(
                    f"第 {line} 行：运行工况非法（{cond}），仅支持 正常/故障/检修")
            fault_time = _col_value(row, "故障发生时间")
            fault_desc = _col_value(row, "事件描述")
            if cond == "故障":
                if not fault_time:
                    errors.append(f"第 {line} 行：运行工况为故障时必填故障发生时间")
                if not fault_desc:
                    errors.append(f"第 {line} 行：运行工况为故障时必填事件描述")
            elif fault_time or fault_desc:
                errors.append(
                    f"第 {line} 行：仅运行工况为故障时可填写故障发生时间/事件描述")
            batch_no = row.get("batch_no", "")
            if rule is None:
                if not batch_no:
                    errors.append(f"第 {line} 行：batch_no 必填（未启用编号自动生成规则）")
            if batch_no:
                if batch_no in seen_batch_nos:
                    errors.append(f"第 {line} 行：batch_no {batch_no} 在清单内重复")
                seen_batch_nos.add(batch_no)
        for d in dirs - set(declared):
            errors.append(f"zip 中的目录 {d} 未在清单中声明")
        return errors

    # ---------- 导入 ----------

    def run_import(self, job_id: str, storage: ObjectStorage) -> None:
        job = self.db.get(BatchImport, job_id)
        if job is None:
            return
        job.status = "running"
        job.updated_at = utcnow()
        self.db.commit()
        report = {"success": [], "skipped": [], "failures": []}
        tmp_dir = tempfile.mkdtemp(prefix="batch-import-")
        try:
            try:
                stream = storage.get_object_stream(job.object_key)
            except KeyError:
                job.status = "failed"
                report["errors"] = ["zip 对象不存在或已过期，请重新上传"]
                job.report = report
                job.updated_at = utcnow()
                self.db.commit()
                return
            zip_path = Path(tmp_dir) / "import.zip"
            with open(zip_path, "wb") as dst:
                shutil.copyfileobj(stream, dst, 1024 * 1024)
            with zipfile.ZipFile(zip_path) as zf:
                dirs, file_counts = _zip_batch_dirs(zf)
                manifest_name = "manifest.csv"
                if manifest_name not in zf.namelist():
                    job.status = "failed"
                    report["errors"] = ["zip 缺少 manifest.csv"]
                    job.report = report
                    job.updated_at = utcnow()
                    self.db.commit()
                    return
                rows, extra_columns, errors = self.parse_manifest(
                    zf.read(manifest_name))
                if not errors:
                    from app.services.batch_no_service import BatchNoService
                    rule = BatchNoService(self.db).get_rule()
                    errors = self.precheck(rows, dirs, file_counts, rule)
                job.total_batches = len(rows)
                self.db.commit()          # 先落库：批次失败 rollback 时进度总数不丢失
                if errors:
                    job.status = "failed"
                    report["errors"] = errors          # 全有或全无：不创建任何批次
                    job.report = report
                    job.updated_at = utcnow()
                    self.db.commit()
                    return
                for row in rows:
                    try:
                        self._import_one(zf, row, extra_columns, job, storage,
                                         report)
                    except Exception as exc:
                        self.db.rollback()
                        report["failures"].append(
                            f"第 {row['_line']} 行（{row.get('目录')}）：{exc}")
                    job.done_batches += 1
                    job.updated_at = utcnow()
                    self.db.commit()
            job.status = "succeeded"
            job.report = report
            job.updated_at = utcnow()
            self.db.commit()
        except Exception as exc:                       # 兜底：意外异常置 failed
            self.db.rollback()
            job.status = "failed"
            report["errors"] = [f"导入异常：{exc}"]
            job.report = report
            job.updated_at = utcnow()
            self.db.commit()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            storage.delete_object(job.object_key)      # 完成后删除 zip 临时对象

    def _import_one(self, zf, row, extra_columns, job, storage, report) -> None:
        from app.services.batch_no_service import BatchNoService

        dir_name = row["目录"]
        rule = BatchNoService(self.db).get_rule()
        if rule is not None:
            batch_no = BatchNoService(self.db).generate(rule.template, row["device_no"])
        else:
            batch_no = row["batch_no"]
            if self.db.execute(select(Batch).where(
                    Batch.batch_no == batch_no)).scalar_one_or_none():
                report["skipped"].append(f"{batch_no}（已存在，跳过）")
                return
        extras = {c: row.get(c) for c in extra_columns if row.get(c) != ""} or None
        now = utcnow()
        batch = Batch(id=str(uuid.uuid4()), batch_no=batch_no,
                      device_no=row["device_no"], device_model=row.get("device_model") or None,
                      station=row.get("station") or None, license=row.get("license"),
                      sensitivity=row.get("sensitivity"),
                      owner_contact=row.get("owner_contact") or None,
                      is_synthetic=int(row.get("is_synthetic") or 0),
                      operating_condition=row.get("operating_condition") or None,
                      fault_time=row.get("故障发生时间") or None,
                      fault_desc=row.get("事件描述") or None,
                      weather=row.get("weather") or None,
                      equipment_state_type=_col_value(
                          row, STATE_COLUMN, STATE_COLUMN_LEGACY),
                      extras=extras,
                      organization_id=job.organization_id, creator_id=job.creator_id,
                      created_at=now, updated_at=now)
        self.db.add(batch)
        write_audit(self.db, action="import", entity_type="batch", entity_id=batch.id,
                    source="import")
        now_dt = datetime.now(timezone.utc)
        station = (batch.station or "").replace(" ", "")
        prefix = dir_name + "/"
        for name in zf.namelist():
            if not name.startswith(prefix) or name.endswith("/"):
                continue
            relpath = name[len(prefix):]
            filename = Path(relpath).name
            modality = infer_modality(filename)
            object_key = (f"{station}/{batch.device_no}/{modality.lower()}/"
                          f"{now_dt.year:04d}/{now_dt.month:02d}/{relpath}")
            if self.db.execute(select(DataFile).where(
                    DataFile.object_key == object_key)).scalar_one_or_none():
                continue                                   # 原始区永不覆盖
            content = zf.read(name)                        # 一次读取，同时取 size
            storage.put_object(object_key, content)        # 写入 MinIO
            self.db.add(DataFile(
                id=str(uuid.uuid4()), batch_id=batch.id, batch_no=batch.batch_no,
                object_key=object_key, filename=filename,
                file_size=len(content),
                modality=modality, device_no=batch.device_no,
                station=batch.station, license=batch.license,
                sensitivity=batch.sensitivity, is_synthetic=batch.is_synthetic,
                operating_condition=batch.operating_condition,
                weather=batch.weather, uploader_id=job.creator_id,
                upload_status="已完成", created_at=now, updated_at=now))
        report["success"].append(batch_no)
