import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found, unprocessable
from app.models import FaultTypeDef, ModalParamDef, User
from app.schemas.dict_defs import (FaultTypeCreate, FaultTypeOut, FaultTypeUpdate,
                                   ModalParamCreate, ModalParamOut, ModalParamUpdate)
from app.services.common import utcnow


class FaultTypeService:
    """故障类型字典（fault_type_def）：admin 统一维护，登录用户只读（§2.5）。"""

    def __init__(self, db: Session):
        self.db = db

    def list_active(self) -> list[FaultTypeOut]:
        """只读列表：仅 is_active=1（批次表单/Event 确认下拉数据源）。"""
        rows = self.db.execute(select(FaultTypeDef)
                               .where(FaultTypeDef.is_active == 1)
                               .order_by(FaultTypeDef.sort_no, FaultTypeDef.code)).scalars()
        return [FaultTypeOut.model_validate(r) for r in rows]

    def list_all(self) -> list[FaultTypeOut]:
        """admin 管理列表：含停用行。"""
        rows = self.db.execute(select(FaultTypeDef)
                               .order_by(FaultTypeDef.sort_no, FaultTypeDef.code)).scalars()
        return [FaultTypeOut.model_validate(r) for r in rows]

    def create(self, body: FaultTypeCreate, user: User) -> FaultTypeOut:
        if self.db.execute(select(FaultTypeDef).where(
                FaultTypeDef.code == body.code)).scalar_one_or_none():
            raise unprocessable("故障类型 code 已存在")
        now = utcnow()
        row = FaultTypeDef(id=str(uuid.uuid4()), code=body.code, name=body.name,
                           severity=body.severity, is_active=body.is_active,
                           sort_no=body.sort_no, description=body.description,
                           creator_id=user.id, created_at=now, updated_at=now)
        self.db.add(row)
        self.db.commit()
        return FaultTypeOut.model_validate(row)

    def update(self, fault_type_id: str, body: FaultTypeUpdate) -> FaultTypeOut:
        row = self.db.get(FaultTypeDef, fault_type_id)
        if row is None:
            raise not_found("故障类型不存在")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = utcnow()
        self.db.commit()
        return FaultTypeOut.model_validate(row)


class ModalParamService:
    """模态采集参数 Schema 字典（modal_param_def）：全局共享，admin 维护（§2.2）。"""

    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[ModalParamOut]:
        rows = self.db.execute(select(ModalParamDef)
                               .order_by(ModalParamDef.modality,
                                         ModalParamDef.sort_no,
                                         ModalParamDef.param_key)).scalars()
        return [ModalParamOut.model_validate(r) for r in rows]

    def create(self, body: ModalParamCreate) -> ModalParamOut:
        if self.db.execute(select(ModalParamDef).where(
                ModalParamDef.modality == body.modality,
                ModalParamDef.param_key == body.param_key)).scalar_one_or_none():
            raise unprocessable("该模态下参数键已存在")
        self._check_range(body.min_value, body.max_value)
        now = utcnow()
        row = ModalParamDef(id=str(uuid.uuid4()), modality=body.modality,
                            param_key=body.param_key, label=body.label, unit=body.unit,
                            value_type=body.value_type, required=body.required,
                            min_value=body.min_value, max_value=body.max_value,
                            enum_values=body.enum_values, description=body.description,
                            sort_no=body.sort_no, created_at=now, updated_at=now)
        self.db.add(row)
        self.db.commit()
        return ModalParamOut.model_validate(row)

    def update(self, param_id: str, body: ModalParamUpdate) -> ModalParamOut:
        row = self.db.get(ModalParamDef, param_id)
        if row is None:
            raise not_found("模态参数定义不存在")
        data = body.model_dump(exclude_unset=True)
        self._check_range(data.get("min_value", row.min_value),
                          data.get("max_value", row.max_value))
        for field, value in data.items():
            setattr(row, field, value)
        row.updated_at = utcnow()
        self.db.commit()
        return ModalParamOut.model_validate(row)

    @staticmethod
    def _check_range(min_value: float | None, max_value: float | None) -> None:
        if min_value is not None and max_value is not None and min_value > max_value:
            raise unprocessable("min_value 不能大于 max_value")
