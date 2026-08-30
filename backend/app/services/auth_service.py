from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import ChangePasswordRequest, LoginResponse, UserOut


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def login(self, username: str, password: str) -> LoginResponse:
        user = self.db.execute(
            select(User).where(User.username == username)).scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            raise unauthorized("用户名或密码错误")
        if user.is_active != 1:
            raise unauthorized("账号已停用")
        return LoginResponse(
            access_token=create_access_token(user),
            user=UserOut.model_validate(user),
        )

    def change_password(self, user: User, body: ChangePasswordRequest) -> None:
        if not verify_password(body.old_password, user.password_hash):
            raise bad_request("原密码错误")
        user.password_hash = hash_password(body.new_password)
        self.db.commit()
