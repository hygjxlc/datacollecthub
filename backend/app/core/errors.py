from fastapi import HTTPException


def unauthorized(detail: str = "未认证") -> HTTPException:
    return HTTPException(status_code=401, detail=detail)


def forbidden(detail: str = "无权限") -> HTTPException:
    return HTTPException(status_code=403, detail=detail)


def not_found(detail: str = "资源不存在") -> HTTPException:
    return HTTPException(status_code=404, detail=detail)


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def conflict(detail: str = "冲突") -> HTTPException:
    return HTTPException(status_code=409, detail=detail)
