from pydantic import BaseModel, ConfigDict


class NameplateCreate(BaseModel):
    device_no: str
    organization_id: str | None = None   # 所属单位：仅管理员可指定（普通用户忽略，落本单位）
    device_model: str | None = None
    rated_power: float | None = None
    rated_wind_speed: float | None = None
    rotor_diameter: float | None = None
    hub_height: float | None = None
    bearing_model: str | None = None
    gearbox_ratio: float | None = None
    generator_model: str | None = None
    manufacturer: str | None = None
    commission_date: str | None = None
    design_life_years: int | None = None
    extras: dict | None = None


class NameplateUpdate(BaseModel):
    device_no: str | None = None
    device_model: str | None = None
    rated_power: float | None = None
    rated_wind_speed: float | None = None
    rotor_diameter: float | None = None
    hub_height: float | None = None
    bearing_model: str | None = None
    gearbox_ratio: float | None = None
    generator_model: str | None = None
    manufacturer: str | None = None
    commission_date: str | None = None
    design_life_years: int | None = None
    extras: dict | None = None


class NameplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str | None = None
    device_no: str
    device_model: str | None = None
    rated_power: float | None = None
    rated_wind_speed: float | None = None
    rotor_diameter: float | None = None
    hub_height: float | None = None
    bearing_model: str | None = None
    gearbox_ratio: float | None = None
    generator_model: str | None = None
    manufacturer: str | None = None
    commission_date: str | None = None
    design_life_years: int | None = None
    extras: dict | None = None
    creator_id: str | None = None
    creator_name: str | None = None
    created_at: str
    updated_at: str
