from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.services.batch_no_service import BatchNoService

router = APIRouter(prefix="/api/v1/batch-no-rule", tags=["batch-no-rule"])


@router.get("")
def get_batch_no_rule(_: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """公开读取：返回批次/事件编号模板（未配置为 null），供申报表单渲染只读编号。"""
    rule = BatchNoService(db).get_rule()
    return {"template": rule.template if rule else None,
            "evt_template": rule.evt_template if rule else None}
