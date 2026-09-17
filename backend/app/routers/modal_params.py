from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.models import User
from app.schemas.dict_defs import ModalParamCreate, ModalParamOut, ModalParamUpdate
from app.services.dict_def_service import ModalParamService

router = APIRouter(prefix="/api/v1", tags=["模态参数字典"])

# 设计（§2.2）：modal_param_def 全局共享 Schema 字典，admin 维护种子数据，
# 登录用户只读列表（Phase 2 schema 驱动表单 / 渲染器取权威键的数据源）


@router.get("/modal-params")
def list_modal_params(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """只读列表（登录）：全量返回（字典无停用概念，键发布后常驻）。"""
    return {"items": ModalParamService(db).list_all()}


admin_router = APIRouter(prefix="/api/v1/admin", tags=["模态参数字典(admin)"])


@admin_router.post("/modal-params", response_model=ModalParamOut)
def create_modal_param(body: ModalParamCreate, _: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    return ModalParamService(db).create(body)


@admin_router.put("/modal-params/{param_id}", response_model=ModalParamOut)
def update_modal_param(param_id: str, body: ModalParamUpdate,
                       _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return ModalParamService(db).update(param_id, body)
