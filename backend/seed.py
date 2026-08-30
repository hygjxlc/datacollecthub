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
from app.models import Organization, User  # noqa: E402
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
        db.commit()
        print(f"seed 完成：新建 {created} 个账号（已存在的自动跳过）")


if __name__ == "__main__":
    main()
