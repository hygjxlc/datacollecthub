"""F8 集成接口服务（SRS 5.7）：无认证只读，供 FDL 引擎拉取元数据、下载与打包导出。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found, unprocessable
from app.models import DataFile
from app.services.archive import build_file_metadata, build_files_zip
from app.services.audit import write_audit

MODALITIES = {"SCADA", "VIB", "AUD", "IR", "CAM", "VID", "TXT", "RPT"}
MAX_LIMIT = 10000


def _norm_time(value: str) -> str:
    """时间参数归一化：存储格式为空格分隔（设备本地时间），统一为 'T' 分隔比较。"""
    return value.replace(" ", "T")


class IntegrationService:
    def __init__(self, db: Session, storage):
        self.db = db
        self.storage = storage

    def query_ids(self, params: dict) -> dict:
        """条件查询文件 ID 列表（架构 6.3）：动态条件构建，翻页不重不漏。"""
        modalities = None
        raw = params.get("modalities")
        if raw is not None:
            modalities = [m.strip() for m in raw.split(",") if m.strip()]
            if not modalities:
                raise unprocessable("modalities 不能为空")
            invalid = [m for m in modalities if m not in MODALITIES]
            if invalid:
                raise unprocessable(f"非法模态: {invalid[0]}")
        try:
            limit = min(max(int(params.get("limit", 1000)), 1), MAX_LIMIT)
            offset = max(int(params.get("offset", 0)), 0)
        except ValueError:
            raise unprocessable("limit/offset 必须为整数")

        query = select(DataFile)
        if params.get("uploaded_after"):
            query = query.where(
                DataFile.created_at >= _norm_time(params["uploaded_after"]))
        if params.get("uploaded_before"):
            query = query.where(
                DataFile.created_at <= _norm_time(params["uploaded_before"]))
        if params.get("occurred_after"):
            query = query.where(
                func.replace(DataFile.start_time, " ", "T")
                >= _norm_time(params["occurred_after"]))
        if params.get("occurred_before"):
            query = query.where(
                func.replace(DataFile.start_time, " ", "T")
                <= _norm_time(params["occurred_before"]))
        if modalities:
            query = query.where(DataFile.modality.in_(modalities))

        total = self.db.execute(
            select(func.count()).select_from(query.subquery())).scalar_one()
        rows = self.db.execute(
            query.order_by(DataFile.id).offset(offset).limit(limit)).scalars().all()
        items = [{"id": r.id} for r in rows]
        write_audit(self.db, action="query", entity_type="datafile",
                    source="integration",
                    params_summary="&".join(f"{k}={v}" for k, v in sorted(params.items())))
        self.db.commit()
        return {"total": total, "items": items, "next_offset": offset + len(items)}

    def get_file(self, file_id: str) -> dict:
        """按 ID 读取：文件级 + 批次级 + 台账三字段合并视图 + presigned 下载链接（SRS 5.7.2）。"""
        df = self.db.get(DataFile, file_id)
        if df is None:
            raise not_found("文件不存在")
        metadata = build_file_metadata(self.db, df)
        url = self.storage.presign_get(df.object_key, 3600)
        write_audit(self.db, action="read", entity_type="datafile", entity_id=df.id,
                    source="integration", params_summary=f"file_id={file_id}")
        self.db.commit()
        return {"metadata": metadata, "download_url": url, "expires_in": 3600}

    def get_file_download(self, file_id: str) -> tuple[str, str]:
        """按 ID 打包导出：zip 内每文件独立文件夹，含原始数据 + 元数据 JSON
        （与认证下载结构一致，SRS 5.7.2）。返回 (临时文件路径, 下载文件名)。"""
        df = self.db.get(DataFile, file_id)
        if df is None:
            raise not_found("文件不存在")
        try:
            path, name = build_files_zip(self.db, self.storage, [df])
        except FileNotFoundError as e:
            raise not_found(f"存储对象缺失：{e}")
        write_audit(self.db, action="read", entity_type="datafile", entity_id=df.id,
                    source="integration", params_summary=f"file_id={file_id}")
        self.db.commit()
        return path, name
