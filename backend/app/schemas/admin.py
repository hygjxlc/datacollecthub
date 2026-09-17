from pydantic import BaseModel, ConfigDict


class OrgCreate(BaseModel):
    name: str
    type: str   # 场站/电厂/运维单位
    contact_person: str | None = None
    contact_phone: str | None = None


class OrgUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    contact_person: str | None = None
    contact_phone: str | None = None


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    contact_person: str | None = None
    contact_phone: str | None = None
    created_at: str
    updated_at: str


class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str
    role: str = "user"
    organization_id: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    organization_id: str | None = None
    is_active: int | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str
    role: str
    organization_id: str | None = None
    is_active: int
    created_at: str


class ResetPasswordOut(BaseModel):
    new_password: str


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None = None
    username: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    field_changes: str | None = None
    source: str
    params_summary: str | None = None
    created_at: str


class BatchNoRuleIn(BaseModel):
    template: str
    evt_template: str | None = None   # 事件编号模板：{TYPE_CODE} 类型段仅此模板可用


class BatchNoRuleOut(BaseModel):
    template: str | None = None
    evt_template: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None
