import math
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found, unprocessable
from app.models import Batch, BatchModalConfig, ModalParamDef, User
from app.repositories.base import assert_org_visible, assert_owner
from app.schemas.batch import ModalConfigIn, ModalConfigOut
from app.services.common import utcnow


def _type_error(d) -> None:
    raise unprocessable(f"参数 {d.label}（{d.param_key}）须为 {d.value_type} 类型")


def _coerce(d, value):
    """按字典 value_type 清洗单值（§3.3 规则 3/4）。

    float/int：接受数字与可解析数字字符串（bool 拒绝——int 子类陷阱），
    清洗后转目标类型并做有限性检查（NaN/Inf → 422）；str/bool 严格同型；
    json 接受 dict/list。None（JSON null）= 未填，由调用方剔除。
    """
    if value is None:
        return None
    vtype = d.value_type
    if vtype == "float":
        if isinstance(value, bool):
            _type_error(d)
        try:
            num = float(value)
        except (TypeError, ValueError):
            _type_error(d)
        if not math.isfinite(num):
            raise unprocessable(f"参数 {d.label}（{d.param_key}）值必须是有限数字")
        return num
    if vtype == "int":
        if isinstance(value, bool):
            _type_error(d)
        try:
            num = float(value)
        except (TypeError, ValueError):
            _type_error(d)
        if not math.isfinite(num) or not num.is_integer():
            _type_error(d)
        return int(num)
    if vtype == "str":
        if not isinstance(value, str):
            _type_error(d)
        return value
    if vtype == "bool":
        if not isinstance(value, bool):
            _type_error(d)
        return value
    if vtype == "json":
        if not isinstance(value, (dict, list)):
            _type_error(d)
        return value
    return value


def _check_value(d, v) -> None:
    """范围与枚举白名单（§3.3 规则 3）：数值键按 min/max 闭区间，enum_values 白名单。"""
    if d.value_type in ("float", "int"):
        if d.min_value is not None and v < d.min_value:
            raise unprocessable(f"参数 {d.label}（{d.param_key}）不能小于 {d.min_value}")
        if d.max_value is not None and v > d.max_value:
            raise unprocessable(f"参数 {d.label}（{d.param_key}）不能大于 {d.max_value}")
    if d.enum_values and v not in d.enum_values:
        allowed = "/".join(str(x) for x in d.enum_values)
        raise unprocessable(f"参数 {d.label}（{d.param_key}）取值须为：{allowed}")


def validate_modal_params(db, *, modality: str, params: dict) -> dict:
    """模态采集参数校验与清洗（§3.3 规则 1-4，服务层权威裁决）。

    - 未知键 → 422（键必须存在于 modal_param_def 且属于该 modality）
    - required=1 缺失（含 null）→ 422；required=2 条件必填不在此强制
      （触发条件在 description，服务端不判定现场语义）
    - value_type / min-max / enum_values 不符 → 422；NaN/Inf → 422
    - 输出：清洗后 params（类型转换；null 剔除）
    """
    defs = db.execute(select(ModalParamDef)
                      .where(ModalParamDef.modality == modality)
                      .order_by(ModalParamDef.sort_no, ModalParamDef.param_key)).scalars().all()
    by_key = {d.param_key: d for d in defs}
    cleaned: dict = {}
    for key, value in params.items():
        d = by_key.get(key)
        if d is None:
            raise unprocessable(f"参数键 {key} 不在模态 {modality} 字典中")
        v = _coerce(d, value)
        if v is None:
            continue                     # null = 未填（required 缺失统一在下方查）
        _check_value(d, v)
        cleaned[key] = v
    for d in defs:
        if d.required == 1 and d.param_key not in cleaned:
            raise unprocessable(f"必填参数缺失：{d.label}（{d.param_key}）")
    return cleaned


class ModalConfigService:
    """模态采集参数实例（batch_modal_config，§2.3）：PUT upsert + Out 聚合 + 待补标注。"""

    def __init__(self, db: Session):
        self.db = db

    def put_config(self, batch_id: str, body: ModalConfigIn, user: User) -> ModalConfigOut:
        """写入/覆盖某批次的某模态参数：批次归属校验同 update_batch（创建者/admin）。"""
        batch = self.db.get(Batch, batch_id)
        if batch is None:
            raise not_found("批次不存在")
        assert_org_visible(batch, user)
        assert_owner(batch, user)
        cleaned = validate_modal_params(self.db, modality=body.modality,
                                        params=body.params)
        row = self.db.execute(select(BatchModalConfig).where(
            BatchModalConfig.batch_id == batch_id,
            BatchModalConfig.modality == body.modality)).scalar_one_or_none()
        now = utcnow()
        if row is None:
            row = BatchModalConfig(id=str(uuid.uuid4()), batch_id=batch_id,
                                   modality=body.modality, params=cleaned,
                                   created_at=now, updated_at=now)
            self.db.add(row)
        else:
            row.params = cleaned                     # 全量替换（无残留旧键）
            row.updated_at = now
        self.db.commit()
        return ModalConfigOut.model_validate(row)

    def config_map(self, batch_ids: list[str]) -> dict[str, list[ModalConfigOut]]:
        """多批次配置聚合（列表页填充防 N+1）。"""
        if not batch_ids:
            return {}
        rows = self.db.execute(select(BatchModalConfig)
                               .where(BatchModalConfig.batch_id.in_(batch_ids))
                               .order_by(BatchModalConfig.modality)).scalars().all()
        out: dict[str, list[ModalConfigOut]] = {}
        for r in rows:
            out.setdefault(r.batch_id, []).append(ModalConfigOut.model_validate(r))
        return out

    @staticmethod
    def pending_modalities(db: Session, modalities: list[str],
                           configs: dict[str, dict]) -> list[str]:
        """§3.4 待补标注：批次含 required=1 字典键的模态而未配全 → "模态参数待补"。

        - 模态未定（无文件）或该模态字典无 required=1 键 → 不标（先传文件后补参）
        - config 存在但缺 required=1 键（字典后续新增必填键）→ 重新标
        - required=2 条件必填不参与判定（服务端不判定条件）
        """
        if not modalities:
            return []
        req_keys: dict[str, list[str]] = {}
        rows = db.execute(select(ModalParamDef.modality, ModalParamDef.param_key)
                          .where(ModalParamDef.modality.in_(modalities),
                                 ModalParamDef.required == 1)).all()
        for m, key in rows:
            req_keys.setdefault(m, []).append(key)
        pending = []
        for m in modalities:                     # 调用方保证已按模态规范序
            keys = req_keys.get(m)
            if not keys:
                continue
            params = configs.get(m)
            if params is None or any(k not in params for k in keys):
                pending.append(m)
        return pending
