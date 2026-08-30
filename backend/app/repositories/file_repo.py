from sqlalchemy import Select, select

from app.models import Batch, DataFile


def visible_files_query(user) -> Select:
    """本单位可见文件查询：DataFile 无 org 字段，经 Batch 判定（架构 5.3）。

    普通用户仅可见本单位批次下的文件；admin 不过滤。
    批次已删除（batch_id=NULL）的文件对普通用户不可见。
    """
    if user.role == "admin":
        return select(DataFile)
    return (select(DataFile).join(Batch, DataFile.batch_id == Batch.id)
            .where(Batch.organization_id == user.organization_id))
