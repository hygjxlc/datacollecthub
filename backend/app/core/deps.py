from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import forbidden, unauthorized
from app.core.security import decode_token
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """认证依赖（架构 5.3 四级校验第 1 级）：每次请求查库校验 is_active，停用即时生效。"""
    if creds is None:
        raise unauthorized("未认证")
    try:
        payload = decode_token(creds.credentials)
    except Exception:
        raise unauthorized("凭证无效或过期")
    user = db.get(User, payload["sub"])
    if user is None or user.is_active != 1:
        raise unauthorized("用户不存在或已停用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """管理员依赖（第 2 级）。"""
    if user.role != "admin":
        raise forbidden("需要管理员权限")
    return user
