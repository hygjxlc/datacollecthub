from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.models import User
from app.schemas.dict_defs import FaultTypeCreate, FaultTypeOut, FaultTypeUpdate
from app.services.dict_def_service import FaultTypeService

router = APIRouter(prefix="/api/v1", tags=["故障类型字典"])

# 设计（§六 routers/fault_types.py）：fault_type_def 字典 admin CRUD（require_admin）
# + 只读列表（登录）——批次表单/Event 确认下拉数据源


@router.get("/fault-types")
def list_fault_types(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """只读列表（登录）：仅 active，供批次申报下拉与治理侧引用。"""
    return {"items": FaultTypeService(db).list_active()}


admin_router = APIRouter(prefix="/api/v1/admin", tags=["故障类型字典(admin)"])


@admin_router.get("/fault-types")
def list_fault_types_all(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """admin 管理列表：含停用行（is_active=0 展示与再启用）。"""
    return {"items": FaultTypeService(db).list_all()}


@admin_router.post("/fault-types", response_model=FaultTypeOut)
def create_fault_type(body: FaultTypeCreate, user: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    return FaultTypeService(db).create(body, user)


@admin_router.put("/fault-types/{fault_type_id}", response_model=FaultTypeOut)
def update_fault_type(fault_type_id: str, body: FaultTypeUpdate,
                      _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return FaultTypeService(db).update(fault_type_id, body)
