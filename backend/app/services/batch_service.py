import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, not_found, unprocessable
from app.models import Batch, BatchModalConfig, DataFile, FaultTypeDef, Nameplate
from app.repositories.base import assert_org_visible, assert_owner, filter_by_org
from app.schemas.batch import BatchCreate, BatchOut, BatchUpdate
from app.services.audit import write_audit
from app.services.common import sort_modalities, utcnow
from app.services.modal_config_service import ModalConfigService

_BATCH_FIELDS = ("batch_no", "device_no", "device_model", "station", "license",
                 "sensitivity", "owner_contact", "is_synthetic",
                 "operating_condition", "fault_time", "fault_desc", "weather",
                 "equipment_state_type", "event_type", "fault_type", "severity",
                 "t_start", "t_end", "event_status", "evt_id")

# 事件三态主轴（§3.1 规则 1）：正常/故障/维修；operating_condition 仅作兼容推断源
EVENT_TYPES = ("正常", "故障", "维修")
CONDITION_MAP = {"故障": "故障", "检修": "维修"}  # 退役轴推断：故障→故障、检修→维修、其它→正常
SEVERITY_VALUES = ("报警", "故障", "事故")
EVENT_STATUS_VALUES = ("draft", "confirmed")
# 事件申报联动字段（中文列名同样禁止用作 extras 键，防语义重复）
FAULT_COLUMNS = {"故障发生时间", "事件描述", "事件类型", "故障类型", "严重度",
                 "异常开始", "异常结束", "事件状态"}
_FAULT_TIMES_KEYS = frozenset({"fault_time", "fault_desc", "event_type", "fault_type",
                               "severity", "t_start", "t_end",
                               "event_status"} | FAULT_COLUMNS)
_EVENT_FIELDS = frozenset({"event_type", "operating_condition", "fault_type",
                           "severity", "fault_time", "fault_desc",
                           "t_start", "t_end", "event_status"})
_EVENT_NORM_FIELDS = ("event_type", "fault_type", "severity", "fault_time",
                      "fault_desc", "t_start", "t_end", "event_status")

_MAX_EXTRAS_KEYS = 20
_MAX_EXTRAS_KEY_LEN = 64
_ALLOWED_EXTRAS_VALUE_TYPES = (str, int, float, bool, type(None))
_FIXED_BATCH_FIELDS = frozenset(_BATCH_FIELDS)


def validate_extras(extras: dict | None) -> dict | None:
    """扩展字段校验：固定字段不重名、仅 JSON 基本类型、键长与数量上限。

    键名统一 trim；空 dict 归一为 None（与未设置同义）；拒绝 NaN/Inf 等非有限数字。
    """
    if extras is None:
        return None
    if not isinstance(extras, dict):
        raise unprocessable("扩展字段必须为键值对对象")
    if len(extras) > _MAX_EXTRAS_KEYS:
        raise unprocessable(f"扩展字段最多 {_MAX_EXTRAS_KEYS} 个键")
    cleaned: dict = {}
    for key, value in extras.items():
        if not isinstance(key, str):
            raise unprocessable("扩展字段键名必须为非空字符串")
        key = key.strip()
        if not key:
            raise unprocessable("扩展字段键名必须为非空字符串")
        if len(key) > _MAX_EXTRAS_KEY_LEN:
            raise unprocessable(f"扩展字段键名 {key} 超过 {_MAX_EXTRAS_KEY_LEN} 字符")
        if key in _FIXED_BATCH_FIELDS or key in _FAULT_TIMES_KEYS:
            raise unprocessable(f"扩展字段键 {key} 与固定字段重名")
        if key in cleaned:
            raise unprocessable(f"扩展字段键 {key} 重复")
        if isinstance(value, float) and not math.isfinite(value):
            raise unprocessable(f"扩展字段 {key} 的值必须是有限数字")
        if not isinstance(value, _ALLOWED_EXTRAS_VALUE_TYPES):
            raise unprocessable(f"扩展字段 {key} 的值仅支持字符串/数字/布尔/空值")
        cleaned[key] = value
    return cleaned if cleaned else None


def evt_type_code(event_type: str, fault_type: str | None) -> str:
    """EVT_ID 类型段（§四）：正常/维修固定 NORMAL/MAINT，故障=fault_type.code。"""
    return {"正常": "NORMAL", "维修": "MAINT"}.get(event_type) or (fault_type or "UNCLASSIFIED")


def normalize_event_fields(db, *, event_type=None, condition=None, fault_type=None,
                           severity=None, fault_time=None, fault_desc=None,
                           t_start=None, t_end=None, event_status=None) -> dict:
    """事件申报字段归一（§3.1 规则 1-7）：三态主轴 + 退役轴兼容推断。

    - event_type 显式值优先；缺失时按 operating_condition 推断
      （故障→故障/检修→维修/其它或空→正常），退役列不落库。
    - 故障：fault_type 字典白名单（is_active=1，缺省 UNCLASSIFIED），severity 缺省取
      字典行默认，必填 fault_time（故障发生时间）+ fault_desc（事件描述）。
    - 维修/正常：清空 fault_type/severity/fault_time；fault_desc 保留作维修内容/基线说明。
    - t_start/t_end 成对可选且 t_start ≤ t_end。
    """
    et = (event_type or "").strip()
    if not et:
        et = CONDITION_MAP.get((condition or "").strip(), "正常")
    if et not in EVENT_TYPES:
        raise unprocessable(f"事件类型非法：{et}，仅支持 正常/故障/维修")
    fault_time = (fault_time or "").strip() or None
    fault_desc = (fault_desc or "").strip() or None
    fault_type = (fault_type or "").strip() or None
    severity = (severity or "").strip() or None
    t_start = (t_start or "").strip() or None
    t_end = (t_end or "").strip() or None
    event_status = (event_status or "").strip() or None
    if event_status is not None and event_status not in EVENT_STATUS_VALUES:
        raise unprocessable("事件状态非法：仅支持 draft/confirmed")
    row = None
    if et == "故障":
        if fault_type:
            row = db.execute(select(FaultTypeDef).where(
                FaultTypeDef.code == fault_type)).scalar_one_or_none()
            if row is None:
                raise unprocessable(f"故障类型 {fault_type} 不存在，请联系管理员添加")
            if not row.is_active:
                raise unprocessable(f"故障类型 {fault_type} 已停用")
        else:
            fault_type = "UNCLASSIFIED"
            row = db.execute(select(FaultTypeDef).where(
                FaultTypeDef.code == "UNCLASSIFIED")).scalar_one_or_none()
        if not fault_time:
            raise unprocessable("事件类型为故障时必填故障发生时间")
        if not fault_desc:
            raise unprocessable("事件类型为故障时必填事件描述")
        if severity is None:
            severity = row.severity if row is not None else "故障"
        if severity not in SEVERITY_VALUES:
            raise unprocessable(f"严重度非法：{severity}，仅支持 报警/故障/事故")
    else:
        fault_type = severity = fault_time = None
    if (t_start is None) != (t_end is None):
        raise unprocessable("异常区间开始/结束时间须成对填写")
    if t_start and t_end and t_start > t_end:
        raise unprocessable("异常区间开始时间不能晚于结束时间")
    return {"event_type": et, "fault_type": fault_type, "severity": severity,
            "fault_time": fault_time, "fault_desc": fault_desc,
            "t_start": t_start, "t_end": t_end,
            "event_status": event_status or "draft"}


def assert_device_in_ledger(db, device_no: str, *, organization_id: str | None,
                            include_all: bool = False) -> None:
    """台账校验（§3.5）：设备编号须存在于可见台账，否则 422。

    单位隔离按 organization_id 过滤；include_all=True（管理员）放行任意台账。
    """
    query = select(Nameplate).where(Nameplate.device_no == device_no)
    if not include_all:
        query = query.where(Nameplate.organization_id == organization_id)
    if db.execute(query.limit(1)).scalar_one_or_none() is None:
        raise unprocessable("设备不在台账中，请联系管理员添加")


class BatchService:
    def __init__(self, db: Session):
        self.db = db

    def list_batches(self, user, page: int = 1, page_size: int = 20) -> dict:
        query = filter_by_org(select(Batch), Batch, user.organization_id,
                              user.role == "admin")
        total = len(self.db.execute(query).scalars().all())
        rows = self.db.execute(
            query.order_by(Batch.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)).scalars().all()
        # 批量聚合文件数与数据量（架构 3.1 列表页列）
        batch_ids = [b.id for b in rows]
        agg = {}
        if batch_ids:
            agg_rows = self.db.execute(
                select(DataFile.batch_id, func.count(), func.coalesce(
                    func.sum(DataFile.file_size), 0),
                    func.group_concat(func.distinct(DataFile.modality)))
                .where(DataFile.batch_id.in_(batch_ids))
                .group_by(DataFile.batch_id)).all()
            agg = {r[0]: (r[1], r[2], r[3]) for r in agg_rows}
        items = []
        cfg_map = ModalConfigService(self.db).config_map(batch_ids)
        for b in rows:
            out = BatchOut.model_validate(b)
            count, size, mods = agg.get(b.id, (0, 0, ""))
            out.file_count, out.total_size = count, size
            out.modalities = sort_modalities(
                [m for m in (mods or "").split(",") if m])
            self._fill_modal_configs(out, cfg_map)
            items.append(out)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def get_batch(self, batch_id: str, user) -> Batch:
        batch = self.db.get(Batch, batch_id)
        if batch is None:
            raise not_found("批次不存在")
        assert_org_visible(batch, user)
        return batch

    def get_batch_out(self, batch_id: str, user) -> BatchOut:
        """详情页输出：modalities/batch_modal_configs/待补标注填充（§3.4）。"""
        batch = self.get_batch(batch_id, user)
        mods = self.db.execute(select(DataFile.modality).where(
            DataFile.batch_id == batch.id).distinct()).scalars().all()
        out = BatchOut.model_validate(batch)
        out.modalities = sort_modalities(mods)
        cfg_map = ModalConfigService(self.db).config_map([batch.id])
        self._fill_modal_configs(out, cfg_map)
        return out

    def _fill_modal_configs(self, out: BatchOut, cfg_map: dict) -> None:
        """填充批次模态参数实例与待补标注（列表/详情共用，防 N+1）。"""
        cfgs = cfg_map.get(out.id, [])
        out.batch_modal_configs = cfgs
        out.modal_pending_modalities = ModalConfigService.pending_modalities(
            self.db, out.modalities, {c.modality: c.params for c in cfgs})

    def _manual_batch_no(self, batch_no: str | None) -> str:
        if not batch_no:
            raise unprocessable("批次编号必填（管理员未配置自动生成规则）")
        if self.db.execute(select(Batch).where(
                Batch.batch_no == batch_no)).scalar_one_or_none():
            raise unprocessable("批次编号已存在")
        return batch_no

    def create_batch(self, body: BatchCreate, user) -> BatchOut:
        from sqlalchemy.exc import IntegrityError

        from app.services.batch_no_service import BatchNoService

        # 台账校验先行：不消耗编号序号（§3.5 时点裁决）
        assert_device_in_ledger(self.db, body.device_no,
                                organization_id=user.organization_id,
                                include_all=user.role == "admin")
        extras = validate_extras(body.extras)
        norm = normalize_event_fields(
            self.db, event_type=body.event_type,
            condition=body.operating_condition, fault_type=body.fault_type,
            severity=body.severity, fault_time=body.fault_time,
            fault_desc=body.fault_desc, t_start=body.t_start, t_end=body.t_end,
            event_status=body.event_status)
        rule = BatchNoService(self.db).get_rule()
        no_service = BatchNoService(self.db)
        for _ in range(3):
            try:
                batch_no = (no_service.generate(rule.template, body.device_no)
                            if rule is not None else self._manual_batch_no(body.batch_no))
                evt_id = no_service.generate_evt(
                    rule.evt_template if rule else None, body.device_no,
                    evt_type_code(norm["event_type"], norm["fault_type"]))
                now = utcnow()
                batch = Batch(id=str(uuid.uuid4()), batch_no=batch_no,
                              device_no=body.device_no, device_model=body.device_model,
                              station=body.station, license=body.license,
                              sensitivity=body.sensitivity,
                              owner_contact=body.owner_contact,
                              is_synthetic=body.is_synthetic,
                              operating_condition=None,     # 退役列：仅推断不写
                              event_type=norm["event_type"],
                              fault_type=norm["fault_type"],
                              severity=norm["severity"],
                              t_start=norm["t_start"], t_end=norm["t_end"],
                              event_status=norm["event_status"], evt_id=evt_id,
                              fault_time=norm["fault_time"],
                              fault_desc=norm["fault_desc"],
                              weather=body.weather,
                              equipment_state_type=body.equipment_state_type,
                              extras=extras,
                              organization_id=user.organization_id, creator_id=user.id,
                              created_at=now, updated_at=now)
                self.db.add(batch)
                write_audit(self.db, user=user, action="create", entity_type="batch",
                            entity_id=batch.id)
                self.db.commit()
                return BatchOut.model_validate(batch)
            except IntegrityError:
                self.db.rollback()
        raise conflict("批次编号生成冲突，请重试")

    def update_batch(self, batch_id: str, body: BatchUpdate, user) -> BatchOut:
        batch = self.get_batch(batch_id, user)
        assert_owner(batch, user)
        data = body.model_dump(exclude_unset=True)
        if "extras" in data:
            data["extras"] = validate_extras(data["extras"])
        # 事件申报字段任一变更 → 三态主轴整体重算（含兼容推断与字段清空）
        if any(k in data for k in _EVENT_FIELDS):
            # 推断优先级：payload 显式给 event_type 用显式值；仅给退役轴
            # operating_condition 时以其推断为准（现值不参与，否则推断永不生效）；
            # 两者均未给（如只改 fault_time）则沿用批次现值保持类型。
            if "event_type" in data:
                evt_param = data["event_type"]
            elif "operating_condition" in data:
                evt_param = None
            else:
                evt_param = batch.event_type
            norm = normalize_event_fields(
                self.db,
                event_type=evt_param,
                condition=data.get("operating_condition", batch.operating_condition),
                fault_type=data.get("fault_type", batch.fault_type),
                severity=data.get("severity", batch.severity),
                fault_time=data.get("fault_time", batch.fault_time),
                fault_desc=data.get("fault_desc", batch.fault_desc),
                t_start=data.get("t_start", batch.t_start),
                t_end=data.get("t_end", batch.t_end),
                event_status=data.get("event_status", batch.event_status))
            type_changed = (norm["event_type"] != batch.event_type
                            or norm["fault_type"] != batch.fault_type)
            has_files = self.db.execute(select(DataFile.id).where(
                DataFile.batch_id == batch.id).limit(1)).scalar_one_or_none() is not None
            # §四 变更规则：含文件或已确认 → 禁止改类型（防 ID 与引用失联）
            if type_changed and (has_files or batch.event_status == "confirmed"):
                why = "批次含数据文件" if has_files else "批次已确认"
                raise unprocessable(f"{why}，禁止变更事件类型")
            for field in _EVENT_NORM_FIELDS:
                data[field] = norm[field]
            data["operating_condition"] = None      # 退役列：仅推断不写
            if type_changed:
                from app.services.batch_no_service import BatchNoService
                rule = BatchNoService(self.db).get_rule()
                data["evt_id"] = BatchNoService(self.db).generate_evt(
                    rule.evt_template if rule else None, batch.device_no,
                    evt_type_code(norm["event_type"], norm["fault_type"]))
        changes = {}
        for field, value in data.items():
            old = getattr(batch, field)
            if old != value:
                changes[field] = {"old": old, "new": value}
                setattr(batch, field, value)
        if changes:
            batch.updated_at = utcnow()
            write_audit(self.db, user=user, action="update", entity_type="batch",
                        entity_id=batch.id, field_changes=changes)
            self.db.commit()
        return self.get_batch_out(batch_id, user)

    def delete_batch(self, batch_id: str, user) -> None:
        batch = self.get_batch(batch_id, user)
        assert_owner(batch, user)
        file_count = self.db.execute(
            select(DataFile).where(DataFile.batch_id == batch.id).limit(1)).scalar_one_or_none()
        if file_count is not None:
            raise bad_request("批次内存在数据文件，仅空批次可删除")
        # 模态参数实例随批删除（ORM 无关系级联，显式清理防孤儿行）
        for cfg in self.db.execute(select(BatchModalConfig).where(
                BatchModalConfig.batch_id == batch.id)).scalars():
            self.db.delete(cfg)
        self.db.delete(batch)
        write_audit(self.db, user=user, action="delete", entity_type="batch",
                    entity_id=batch.id)
        self.db.commit()
