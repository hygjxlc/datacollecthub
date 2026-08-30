import secrets
import string
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found, unprocessable
from app.core.security import hash_password
from app.models import AuditLog, Organization, User
from app.schemas.admin import (AuditLogOut, OrgCreate, OrgOut, OrgUpdate,
                               UserCreate, UserOut, UserUpdate)
from app.services.common import utcnow


class AdminService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- 单位 ----------

    def list_orgs(self) -> list[OrgOut]:
        rows = self.db.execute(select(Organization).order_by(Organization.name)).scalars()
        return [OrgOut.model_validate(o) for o in rows]

    def create_org(self, body: OrgCreate) -> OrgOut:
        if self.db.execute(select(Organization).where(
                Organization.name == body.name)).scalar_one_or_none():
            raise unprocessable("单位名称已存在")
        now = utcnow()
        org = Organization(id=str(uuid.uuid4()), name=body.name, type=body.type,
                           contact_person=body.contact_person,
                           contact_phone=body.contact_phone,
                           created_at=now, updated_at=now)
        self.db.add(org)
        self.db.commit()
        return OrgOut.model_validate(org)

    def update_org(self, org_id: str, body: OrgUpdate) -> OrgOut:
        org = self.db.get(Organization, org_id)
        if org is None:
            raise not_found("单位不存在")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(org, field, value)
        org.updated_at = utcnow()
        self.db.commit()
        return OrgOut.model_validate(org)

    def delete_org(self, org_id: str) -> None:
        org = self.db.get(Organization, org_id)
        if org is None:
            raise not_found("单位不存在")
        self.db.delete(org)   # 用户 organization_id ON DELETE SET NULL
        self.db.commit()

    # ---------- 用户 ----------

    def list_users(self) -> list[UserOut]:
        rows = self.db.execute(select(User).order_by(User.created_at)).scalars()
        return [UserOut.model_validate(u) for u in rows]

    def create_user(self, body: UserCreate) -> UserOut:
        if self.db.execute(select(User).where(
                User.username == body.username)).scalar_one_or_none():
            raise unprocessable("用户名已存在")
        if body.organization_id and self.db.get(Organization, body.organization_id) is None:
            raise not_found("单位不存在")
        user = User(id=str(uuid.uuid4()), username=body.username,
                    display_name=body.display_name,
                    password_hash=hash_password(body.password),
                    role=body.role, organization_id=body.organization_id,
                    is_active=1, created_at=utcnow())
        self.db.add(user)
        self.db.commit()
        return UserOut.model_validate(user)

    def update_user(self, user_id: str, body: UserUpdate) -> UserOut:
        user = self.db.get(User, user_id)
        if user is None:
            raise not_found("用户不存在")
        data = body.model_dump(exclude_unset=True)
        if "organization_id" in data and data["organization_id"] \
                and self.db.get(Organization, data["organization_id"]) is None:
            raise not_found("单位不存在")
        for field, value in data.items():
            setattr(user, field, value)
        self.db.commit()
        return UserOut.model_validate(user)

    def reset_password(self, user_id: str) -> str:
        """重置密码：生成 12 位随机密码并返回一次（SRS 3.3 F2）。"""
        user = self.db.get(User, user_id)
        if user is None:
            raise not_found("用户不存在")
        alphabet = string.ascii_letters + string.digits
        new_password = "".join(secrets.choice(alphabet) for _ in range(12))
        user.password_hash = hash_password(new_password)
        self.db.commit()
        return new_password

    def delete_user(self, user_id: str) -> None:
        user = self.db.get(User, user_id)
        if user is None:
            raise not_found("用户不存在")
        self.db.delete(user)
        self.db.commit()

    # ---------- 审计日志（架构 3.1 /audit 页面） ----------

    def list_audit_logs(self, page: int = 1, page_size: int = 20,
                        source: str | None = None, action: str | None = None) -> dict:
        query = select(AuditLog)
        if source:
            query = query.where(AuditLog.source == source)
        if action:
            query = query.where(AuditLog.action == action)
        total = len(self.db.execute(query).scalars().all())
        rows = self.db.execute(
            query.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)).scalars()
        return {"items": [AuditLogOut.model_validate(r) for r in rows],
                "total": total, "page": page, "page_size": page_size}
