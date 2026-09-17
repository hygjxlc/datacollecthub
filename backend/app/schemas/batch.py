from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.dict_defs import MODALITIES
from app.schemas.enums import EquipmentStateType


class ModalConfigIn(BaseModel):
    """模态采集参数实例写入（PUT /batches/{id}/modal-config，§2.3/§3.3）。

    params 键必须为 modal_param_def 权威键且属于该 modality，值按字典
    value_type/范围/enum 校验——schema 层不锁键（由服务层按字典行裁决）。
    """

    modality: MODALITIES
    params: dict


class ModalConfigOut(BaseModel):
    """批次×模态参数实例只读视图（嵌套于 BatchOut.batch_modal_configs）。"""

    model_config = ConfigDict(from_attributes=True)

    modality: str
    params: dict
    created_at: str
    updated_at: str


class BatchCreate(BaseModel):
    batch_no: str | None = None
    device_no: str
    device_model: str | None = None
    station: str | None = None
    license: str | None = None
    sensitivity: str | None = None
    owner_contact: str | None = None
    is_synthetic: int = 0
    operating_condition: str | None = None   # 退役轴：仅兼容推断源（不落库）
    event_type: str | None = None            # 三态主轴：正常/故障/维修（缺省按 operating_condition 推断→正常）
    fault_type: str | None = None
    severity: str | None = None
    t_start: str | None = None
    t_end: str | None = None
    event_status: str | None = None
    fault_time: str | None = None
    fault_desc: str | None = None
    weather: str | None = None
    equipment_state_type: EquipmentStateType
    extras: dict | None = None


class BatchUpdate(BaseModel):
    batch_no: str | None = None
    device_no: str | None = None
    device_model: str | None = None
    station: str | None = None
    license: str | None = None
    sensitivity: str | None = None
    owner_contact: str | None = None
    is_synthetic: int | None = None
    operating_condition: str | None = None
    event_type: str | None = None
    fault_type: str | None = None
    severity: str | None = None
    t_start: str | None = None
    t_end: str | None = None
    event_status: str | None = None
    fault_time: str | None = None
    fault_desc: str | None = None
    weather: str | None = None
    equipment_state_type: EquipmentStateType | None = None
    extras: dict | None = None

    @field_validator("equipment_state_type", "fault_time", "fault_desc",
                     "event_type", "fault_type", "severity", "t_start", "t_end",
                     "event_status", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        return None if v == "" else v


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_no: str
    device_no: str
    device_model: str | None = None
    station: str | None = None
    license: str | None = None
    sensitivity: str | None = None
    owner_contact: str | None = None
    is_synthetic: int
    operating_condition: str | None = None
    event_type: str | None = None
    fault_type: str | None = None
    severity: str | None = None
    t_start: str | None = None
    t_end: str | None = None
    event_status: str | None = None
    evt_id: str | None = None
    fault_time: str | None = None
    fault_desc: str | None = None
    weather: str | None = None
    equipment_state_type: str | None = None
    extras: dict | None = None
    modalities: list[str] = []   # 只读聚合：批次下文件 modality 去重（按模态规范顺序）
    batch_modal_configs: list[ModalConfigOut] = []  # 只读聚合：已配置模态参数实例（§2.3）
    modal_pending_modalities: list[str] = []  # §3.4 待补标注：含 required=1 字典键而未配全的模态
    organization_id: str | None = None
    creator_id: str | None = None
    file_count: int = 0          # 列表页聚合（文件数）
    total_size: int = 0          # 列表页聚合（数据量，字节）
    created_at: str
    updated_at: str
