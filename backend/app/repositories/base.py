from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import forbidden, not_found


def creator_name_map(db: Session, creator_ids) -> dict[str, str]:
    """creator_id → display_name 批量映射（台账列表"创建者"列）。

    历史数据 creator_id 为 NULL（或用户已删除）时映射缺失，
    调用方以 None 展示（前端显示 "-"）。
    """
    ids = {c for c in creator_ids if c}
    if not ids:
        return {}
    from app.models import User
    rows = db.execute(select(User.id, User.display_name)
                      .where(User.id.in_(ids))).all()
    return {r[0]: r[1] for r in rows if r[1]}


def filter_by_org(query: Select, model, org_id: str | None, is_admin: bool) -> Select:
    """单位过滤（架构 5.3 第 3 级）：普通用户强制本单位；admin 不过滤。"""
    if is_admin:
        return query
    return query.where(model.organization_id == org_id)


def assert_org_visible(obj, user) -> None:
    """跨单位隐藏：非管理员访问他单位资源 → 404（不泄露资源存在性）。"""
    if user.role != "admin" and obj.organization_id != user.organization_id:
        raise not_found("资源不存在")


def assert_owner(obj, user, owner_field: str = "creator_id") -> None:
    """归属校验：非归属者且非管理员 → 403（SRS 3.2 权限矩阵）。

    owner_field：批次用 creator_id，文件用 uploader_id。
    """
    if user.role != "admin" and getattr(obj, owner_field, None) != user.id:
        raise forbidden("仅上传者可操作")
