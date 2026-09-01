from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_admin
from app.models import User
from app.schemas.admin import (BatchNoRuleIn, BatchNoRuleOut, OrgCreate, OrgOut,
                               OrgUpdate, ResetPasswordOut, UserCreate, UserOut,
                               UserUpdate)
from app.services.admin_service import AdminService
from app.services.batch_no_service import BatchNoService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------- 单位 ----------

@router.get("/organizations")
def list_orgs(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"items": AdminService(db).list_orgs()}


@router.post("/organizations", response_model=OrgOut)
def create_org(body: OrgCreate, _: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    return AdminService(db).create_org(body)


@router.put("/organizations/{org_id}", response_model=OrgOut)
def update_org(org_id: str, body: OrgUpdate, _: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    return AdminService(db).update_org(org_id, body)


@router.delete("/organizations/{org_id}")
def delete_org(org_id: str, _: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    AdminService(db).delete_org(org_id)
    return {"status": "ok"}


# ---------- 用户 ----------

@router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"items": AdminService(db).list_users()}


@router.post("/users", response_model=UserOut)
def create_user(body: UserCreate, _: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    return AdminService(db).create_user(body)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, _: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    return AdminService(db).update_user(user_id, body)


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordOut)
def reset_password(user_id: str, _: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    return ResetPasswordOut(new_password=AdminService(db).reset_password(user_id))


@router.delete("/users/{user_id}")
def delete_user(user_id: str, _: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    AdminService(db).delete_user(user_id)
    return {"status": "ok"}


# ---------- 审计日志（架构 3.1 /audit 页面） ----------

@router.get("/audit-logs")
def list_audit_logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    source: str | None = None, action: str | None = None,
                    _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return AdminService(db).list_audit_logs(page, page_size, source, action)


# ---------- 批次编号规则（全局单行，admin 配置） ----------

@router.get("/batch-no-rule", response_model=BatchNoRuleOut)
def get_batch_no_rule(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rule = BatchNoService(db).get_rule()
    return (BatchNoRuleOut(template=rule.template, updated_by=rule.updated_by,
                           updated_at=rule.updated_at) if rule else BatchNoRuleOut())


@router.put("/batch-no-rule", response_model=BatchNoRuleOut)
def put_batch_no_rule(body: BatchNoRuleIn, user: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    rule = BatchNoService(db).save_rule(body.template, user)
    return BatchNoRuleOut(template=rule.template, updated_by=rule.updated_by,
                          updated_at=rule.updated_at)
