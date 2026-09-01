"""批次编号自动生成：模板解析 + 原子计数器。

- 模板占位符：{YYYY} {YY} {MM} {DD} {SEQ:n} {DEVICE_NO}，必须含 {SEQ:n}。
- counter_key = 模板中除 {SEQ} 外全部占位符渲染当前值后的字符串：
  含日期占位符 → 按对应日期维度自动重置序号；含 {DEVICE_NO} → 按设备隔离序号。
- 首次使用某 counter_key 时，扫描存量批次中该前缀编号的最大序号作为起始值。
- 原子自增用 SQLite INSERT ON CONFLICT DO UPDATE ... RETURNING value。
"""
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import conflict, unprocessable
from app.models import Batch, BatchNoCounter, BatchNoRule
from app.services.common import utcnow

_PLACEHOLDER_RE = re.compile(r"\{([A-Z_]+)(?::(\d+))?\}")
_ALLOWED_PLACEHOLDERS = {"YYYY", "YY", "MM", "DD", "SEQ", "DEVICE_NO"}
_MAX_SEQ_DIGITS = 8
_GENERATE_RETRIES = 3


class BatchNoService:
    def __init__(self, db: Session):
        self.db = db

    def get_rule(self) -> BatchNoRule | None:
        return self.db.execute(select(BatchNoRule).limit(1)).scalar_one_or_none()

    @staticmethod
    def validate_template(template: str) -> None:
        if not template or not template.strip():
            raise unprocessable("编号模板不能为空")
        has_seq = False
        for m in _PLACEHOLDER_RE.finditer(template):
            name, digits = m.group(1), m.group(2)
            if name not in _ALLOWED_PLACEHOLDERS:
                raise unprocessable(
                    f"未知占位符 {name}，可用：YYYY YY MM DD SEQ:n DEVICE_NO")
            if name == "SEQ":
                has_seq = True
                if digits is None:
                    raise unprocessable("{SEQ} 必须指定位数，如 {SEQ:4}")
                if not 1 <= int(digits) <= _MAX_SEQ_DIGITS:
                    raise unprocessable(f"SEQ 位数须在 1~{_MAX_SEQ_DIGITS} 之间")
            elif digits is not None:
                raise unprocessable(f"占位符 {name} 不支持位数参数")
        if not has_seq:
            raise unprocessable("模板必须包含 {SEQ:n} 序号占位符")

    def save_rule(self, template: str, user) -> BatchNoRule:
        self.validate_template(template)
        rule = self.get_rule()
        if rule is None:
            rule = BatchNoRule(id=str(uuid.uuid4()), template=template,
                               updated_by=user.id, updated_at=utcnow())
            self.db.add(rule)
        else:
            rule.template = template
            rule.updated_by = user.id
            rule.updated_at = utcnow()
        self.db.commit()
        return rule

    def _render(self, template: str, *, device_no: str, now: datetime,
                seq: int | None) -> str:
        def repl(m):
            name, digits = m.group(1), m.group(2)
            if name == "SEQ":
                return "" if seq is None else str(seq).zfill(int(digits))
            if name == "YYYY":
                return f"{now.year:04d}"
            if name == "YY":
                return f"{now.year % 100:02d}"
            if name == "MM":
                return f"{now.month:02d}"
            if name == "DD":
                return f"{now.day:02d}"
            return device_no          # {DEVICE_NO}

        return _PLACEHOLDER_RE.sub(repl, template)

    def render(self, template: str, *, device_no: str, now: datetime, seq: int) -> str:
        return self._render(template, device_no=device_no, now=now, seq=seq)

    def counter_key(self, template: str, *, device_no: str, now: datetime) -> str:
        return self._render(template, device_no=device_no, now=now, seq=None)

    def _seed_from_existing(self, counter_key: str) -> int:
        """存量批次中该前缀编号的最大序号（后缀需全为数字），无则 0。"""
        numbers = [b for b in self.db.execute(select(Batch.batch_no)).scalars()
                   if b.startswith(counter_key) and b[len(counter_key):].isdigit()]
        return max((int(n[len(counter_key):]) for n in numbers), default=0)

    def _next_seq(self, counter_key: str) -> int:
        existing = self.db.get(BatchNoCounter, counter_key)
        if existing is None:
            seed = self._seed_from_existing(counter_key)
            sql = text(
                "INSERT INTO batch_no_counter (counter_key, value) VALUES (:k, :v) "
                "ON CONFLICT(counter_key) DO UPDATE SET value = value + 1 "
                "RETURNING value")
            return self.db.execute(sql, {"k": counter_key, "v": seed + 1}).scalar_one()
        sql = text("UPDATE batch_no_counter SET value = value + 1 "
                   "WHERE counter_key = :k RETURNING value")
        return self.db.execute(sql, {"k": counter_key}).scalar_one()

    def generate(self, template: str, device_no: str) -> str:
        now = datetime.now(timezone.utc)
        key = self.counter_key(template, device_no=device_no, now=now)
        for _ in range(_GENERATE_RETRIES):
            seq = self._next_seq(key)
            batch_no = self.render(template, device_no=device_no, now=now, seq=seq)
            exists = self.db.execute(select(Batch).where(
                Batch.batch_no == batch_no)).scalar_one_or_none()
            if exists is None:
                return batch_no
        raise conflict("批次编号生成冲突，请重试")
