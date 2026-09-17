"""幂等基线数据种子（部署后首个管理员 + E2E 测试基线账号）。

用法：`python seed.py`（backend 容器启动时自动执行；重复执行安全——按 username
存在性跳过，不覆盖已有账号）。账号约定与 tests/conftest.py、E2E 测试方案 2.3 一致：

    admin/admin123（管理员）            zhang/pass123（辉腾梁风电场）
    li/pass123（辉腾梁风电场）          wang/pass123（大丰光伏电站）
"""

import os
import uuid

# 必须在 import app 之前设置（config.settings 在 import 时实例化；容器内由环境变量注入）
os.environ.setdefault("DATABASE_URL", "sqlite:///./datacollecthub.db")

from sqlalchemy import select  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (FaultTypeDef, ModalParamDef, Organization,  # noqa: E402
                        User)
from app.services.common import utcnow  # noqa: E402

ORG_DEFS = [
    {"name": "辉腾梁风电场", "type": "场站"},
    {"name": "大丰光伏电站", "type": "电厂"},
]

USERS = [
    {"username": "admin", "display_name": "管理员", "password": "admin123",
     "role": "admin", "org": None},
    {"username": "zhang", "display_name": "张工", "password": "pass123",
     "role": "user", "org": "辉腾梁风电场"},
    {"username": "li", "display_name": "李工", "password": "pass123",
     "role": "user", "org": "辉腾梁风电场"},
    {"username": "wang", "display_name": "王工", "password": "pass123",
     "role": "user", "org": "大丰光伏电站"},
]


# 故障类型字典种子（批次事件组化改造 §2.5，2026-09-09 Phase 0 首批导入）：
# UNCLASSIFIED 缺省落位 + 三级标签树/治理区既有故障类型 ≥10 类（任务书 2026ZD0126800 口径：
# 轴承磨损/齿轮裂纹/叶片不平衡/发电机过温/变桨异常/逆变器失效/锅炉受热面泄漏 7 类全含，
# 另 4 类锚自治理区 finetune 样例/留痕样例/课题一典型故障清单）。name=中文层级串（可维护），
# code 不可改名（入 EVT_ID 类型段）；sort_no 按列表序。
FAULT_TYPE_SEEDS = [
    {"code": "UNCLASSIFIED", "name": "待分类", "severity": "故障",
     "description": "未细分故障的缺省落位：阻断转 confirmed，治理侧三源交叉后修正为具体类型（§3.1 规则 2）"},
    {"code": "GEARBOX_BEARING_WEAR", "name": "齿轮箱-轴承-磨损", "severity": "故障",
     "description": "高速轴轴承磨损；治理区既有 EVT 前缀同构（EVT_GEARBOX_BEARING_WEAR_001）"},
    {"code": "GEARBOX_BEARING_CAGE_FRACTURE", "name": "齿轮箱-轴承-保持架断裂", "severity": "故障",
     "description": "三级标签树同层节点（留痕样例 L2.1.4 仲裁值，区别于轴承磨损）"},
    {"code": "GEARBOX_GEAR_CRACK", "name": "齿轮箱-齿轮-裂纹", "severity": "故障",
     "description": "任务书故障模式清单『齿轮裂纹』；治理区既有 EVT（FT_SAMPLE_GEARBOX_GEAR_CRACK_*）"},
    {"code": "MAIN_BEARING_CRACK", "name": "主轴-轴承-裂纹", "severity": "故障",
     "description": "任务书典型故障『风机主轴承裂纹』（课题一创新点梳理）"},
    {"code": "GENERATOR_BEARING_OVERTEMP", "name": "发电机-轴承-过热", "severity": "故障",
     "description": "任务书『发电机过温』；治理区既有 EVT（FT_SAMPLE_GENERATOR_BEARING_OVERTEMP_*）"},
    {"code": "BLADE_IMBALANCE", "name": "叶片-不平衡", "severity": "故障",
     "description": "任务书『叶片不平衡』；治理区既有 EVT（FT_SAMPLE_BLADE_IMBALANCE_*）"},
    {"code": "PITCH_SYSTEM_FAULT", "name": "变桨系统-异常", "severity": "故障",
     "description": "任务书故障模式清单『变桨异常』"},
    {"code": "PV_MODULE_HOT_SPOT", "name": "光伏组件-热斑", "severity": "故障",
     "description": "任务书典型故障『光伏组件热斑』（课题一创新点梳理）"},
    {"code": "INVERTER_FAILURE", "name": "逆变器-失效", "severity": "故障",
     "description": "任务书故障模式清单『逆变器失效』"},
    {"code": "BATTERY_INTERNAL_SHORT_CIRCUIT", "name": "储能电池-内部短路", "severity": "故障",
     "description": "任务书典型故障『储能电池内部短路』（课题一创新点梳理）"},
    {"code": "BOILER_HEATING_SURFACE_LEAK", "name": "锅炉-受热面-泄漏", "severity": "故障",
     "description": "任务书故障模式清单『锅炉受热面泄漏』（火电侧）"},
]

# 模态参数 Schema 字典种子（模态数据标注_口径与讨论记录.md §8.3 初稿 12 行，2026-09-09 Phase 0）：
# modality 用平台模态代码（enums.Modality 同域）；required：1 必填 / 2 条件必填 / 0 可选（含『建议』）。
MODAL_PARAM_SEEDS = [
    {"modality": "IR", "param_key": "emissivity", "label": "发射率", "unit": None,
     "value_type": "float", "required": 1, "min_value": 0.05, "max_value": 1.0,
     "description": "定标温度修正（格式未内置时）"},
    {"modality": "IR", "param_key": "ambient_temp_c", "label": "环境温度", "unit": "℃",
     "value_type": "float", "required": 1, "min_value": -40, "max_value": 80, "description": None},
    {"modality": "IR", "param_key": "reflected_temp_c", "label": "反射温度", "unit": "℃",
     "value_type": "float", "required": 2, "min_value": -40, "max_value": 120,
     "description": "金属高反射面必填"},
    {"modality": "IR", "param_key": "rh_pct", "label": "相对湿度", "unit": "%",
     "value_type": "float", "required": 1, "min_value": 0, "max_value": 100, "description": None},
    {"modality": "IR", "param_key": "distance_m", "label": "测温距离", "unit": "m",
     "value_type": "float", "required": 2, "min_value": 0, "max_value": 500,
     "description": "影响大气透射"},
    {"modality": "VIB", "param_key": "sample_rate_hz", "label": "采样率", "unit": "Hz",
     "value_type": "int", "required": 1, "min_value": 1000, "max_value": 1000000,
     "description": "FFT x 轴定标（渲染硬依赖）"},
    {"modality": "VIB", "param_key": "channel_map", "label": "通道接线映射", "unit": None,
     "value_type": "json", "required": 1, "min_value": None, "max_value": None,
     "description": "本次接线配置（通道→point_dict 引用）"},
    {"modality": "VIB", "param_key": "sensor_sensitivity", "label": "灵敏度（换装覆盖）", "unit": "mV/g",
     "value_type": "float", "required": 2, "min_value": 0.1, "max_value": 100000,
     "description": "仅换装时填，默认取 PointDict"},
    {"modality": "VIB", "param_key": "range_max", "label": "满量程", "unit": "g",
     "value_type": "float", "required": 0, "min_value": None, "max_value": None,
     "description": "削顶判据"},
    {"modality": "AUD", "param_key": "recorder_model", "label": "采集仪/麦克风型号", "unit": None,
     "value_type": "str", "required": 0, "min_value": None, "max_value": None,
     "description": "便携装备识别（建议填写）"},
    {"modality": "AUD", "param_key": "noise_level_db", "label": "环境噪声级", "unit": "dB",
     "value_type": "float", "required": 0, "min_value": 0, "max_value": 140,
     "description": "SNR 质量标注（建议填写）"},
    {"modality": "VID", "param_key": "camera_note", "label": "拍摄位置/视角备注", "unit": None,
     "value_type": "str", "required": 0, "min_value": None, "max_value": None,
     "description": "巡检机位（固定 camera_id 在 Nameplate）"},
]


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        orgs = {o.name: o for o in db.execute(select(Organization)).scalars()}
        for org_def in ORG_DEFS:
            if org_def["name"] not in orgs:
                orgs[org_def["name"]] = Organization(
                    id=str(uuid.uuid4()), name=org_def["name"], type=org_def["type"],
                    created_at=utcnow(), updated_at=utcnow())
                db.add(orgs[org_def["name"]])
        db.flush()

        existing = {u.username for u in db.execute(select(User)).scalars()}
        created = 0
        for u in USERS:
            if u["username"] in existing:
                continue
            db.add(User(id=str(uuid.uuid4()), username=u["username"], display_name=u["display_name"],
                        password_hash=hash_password(u["password"]), role=u["role"],
                        organization_id=orgs[u["org"]].id if u["org"] else None,
                        is_active=1, created_at=utcnow()))
            created += 1
        existing_faults = {f.code for f in db.execute(select(FaultTypeDef)).scalars()}
        fault_created = 0
        for i, s in enumerate(FAULT_TYPE_SEEDS):
            if s["code"] in existing_faults:
                continue
            now = utcnow()
            db.add(FaultTypeDef(id=str(uuid.uuid4()), code=s["code"], name=s["name"],
                                severity=s["severity"], is_active=1, sort_no=i,
                                description=s["description"], creator_id=None,
                                created_at=now, updated_at=now))
            fault_created += 1

        existing_params = {(p.modality, p.param_key)
                           for p in db.execute(select(ModalParamDef)).scalars()}
        param_created = 0
        for i, s in enumerate(MODAL_PARAM_SEEDS):
            if (s["modality"], s["param_key"]) in existing_params:
                continue
            now = utcnow()
            db.add(ModalParamDef(id=str(uuid.uuid4()), modality=s["modality"],
                                 param_key=s["param_key"], label=s["label"], unit=s["unit"],
                                 value_type=s["value_type"], required=s["required"],
                                 min_value=s["min_value"], max_value=s["max_value"],
                                 enum_values=None, description=s["description"],
                                 sort_no=i,
                                 created_at=now, updated_at=now))
            param_created += 1
        db.commit()
        print(f"seed 完成：新建 {created} 个账号、{fault_created} 个故障类型、"
              f"{param_created} 个模态参数（已存在的自动跳过）")


if __name__ == "__main__":
    main()
