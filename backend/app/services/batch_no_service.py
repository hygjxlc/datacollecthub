"""批次/事件编号自动生成：模板解析 + 原子计数器。

- 模板占位符：{YYYY} {YY} {MM} {DD} {SEQ:n} {DEVICE_NO}（事件模板另支持
  {TYPE_CODE} 类型段，仅 evt_template 可用），必须含 {SEQ:n}，且 {SEQ:n}
  必须是模板中最后一个占位符（其后允许普通字面文本）。
- counter_key = 模板中除 {SEQ} 外全部占位符渲染当前值后的字符串：
  含日期占位符 → 按对应日期维度自动重置序号；含 {DEVICE_NO} → 按设备隔离序号；
  事件模板含 {TYPE_CODE} → 类型段×设备×年独立 001 起。
- 首次使用某 counter_key 时，扫描存量编号（批次 batch_no / 事件 evt_id）中
  该前缀编号的最大序号作为起始值。
- 原子自增用 SQLite INSERT ON CONFLICT DO UPDATE ... RETURNING value。
- 规则为全局单行配置，固定主键 "singleton"，save_rule 用原子 upsert 保证并发下单行。
"""
import re
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import conflict, unprocessable
from app.models import Batch, BatchNoCounter, BatchNoRule
from app.services.common import utcnow

_PLACEHOLDER_RE = re.compile(r"\{([A-Z_]+)(?::(\d+))?\}")
_ALLOWED_PLACEHOLDERS = {"YYYY", "YY", "MM", "DD", "SEQ", "DEVICE_NO"}
# 事件编号默认模板：EVT_{类型段}_{设备}_{年}_{序号}（未配置 evt_template 时生效）
DEFAULT_EVT_TEMPLATE = "EVT_{TYPE_CODE}_{DEVICE_NO}_{YYYY}_{SEQ:3}"
_MAX_SEQ_DIGITS = 8
_GENERATE_RETRIES = 3


class BatchNoService:
    def __init__(self, db: Session):
        self.db = db

    def get_rule(self) -> BatchNoRule | None:
        return self.db.get(BatchNoRule, "singleton")

    @staticmethod
    def validate_template(template: str) -> None:
        """批次编号模板：禁用 {TYPE_CODE}（未知占位符路径拦截）。"""
        BatchNoService._validate(template, allow_type_code=False)

    @staticmethod
    def validate_evt_template(template: str) -> None:
        """事件编号模板：{TYPE_CODE} 类型段必含（段值×设备×年独立计数）。"""
        BatchNoService._validate(template, allow_type_code=True)

    @staticmethod
    def _validate(template: str, *, allow_type_code: bool) -> None:
        if not template or not template.strip():
            raise unprocessable("编号模板不能为空")
        matches = list(_PLACEHOLDER_RE.finditer(template))
        allowed = (_ALLOWED_PLACEHOLDERS | {"TYPE_CODE"}) if allow_type_code \
            else _ALLOWED_PLACEHOLDERS
        has_seq = False
        has_type_code = False
        for m in matches:
            name, digits = m.group(1), m.group(2)
            if name not in allowed:
                raise unprocessable(
                    f"未知占位符 {name}，可用：YYYY YY MM DD SEQ:n DEVICE_NO"
                    + (" TYPE_CODE" if allow_type_code else ""))
            if name == "SEQ":
                has_seq = True
                if digits is None:
                    raise unprocessable("{SEQ} 必须指定位数，如 {SEQ:4}")
                if not 1 <= int(digits) <= _MAX_SEQ_DIGITS:
                    raise unprocessable(f"SEQ 位数须在 1~{_MAX_SEQ_DIGITS} 之间")
            elif name == "TYPE_CODE":
                has_type_code = True
                if digits is not None:
                    raise unprocessable(f"占位符 {name} 不支持位数参数")
            elif digits is not None:
                raise unprocessable(f"占位符 {name} 不支持位数参数")
        if not has_seq:
            raise unprocessable("模板必须包含 {SEQ:n} 序号占位符")
        if allow_type_code and not has_type_code:
            raise unprocessable("事件编码模板必须包含 {TYPE_CODE} 占位符")
        # {SEQ:n} 必须是模板中最后一个占位符（其后允许普通字面文本，不允许其他占位符）
        if matches[-1].group(1) != "SEQ":
            raise unprocessable("SEQ 序号占位符必须是模板末尾的最后一个占位符")

    def save_rule(self, template: str, user, evt_template: str | None = None) -> BatchNoRule:
        self.validate_template(template)
        if evt_template is not None:
            evt_template = evt_template.strip() or None
            if evt_template is not None:
                self.validate_evt_template(evt_template)
        # 固定主键 "singleton" 的原子 upsert：并发保存时也只会保留一行规则
        sql = text(
            "INSERT INTO batch_no_rule (id, template, evt_template, updated_by, "
            "updated_at) VALUES (:id, :t, :et, :u, :at) "
            "ON CONFLICT(id) DO UPDATE SET template = :t, evt_template = :et, "
            "updated_by = :u, updated_at = :at")
        self.db.execute(sql, {"id": "singleton", "t": template, "et": evt_template,
                              "u": user.id, "at": utcnow()})
        self.db.commit()
        rule = self.db.get(BatchNoRule, "singleton")
        assert rule is not None
        return rule

    def _render(self, template: str, *, device_no: str, type_code: str | None = None,
                now: datetime, seq: int | None) -> str:
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
            if name == "TYPE_CODE":
                return type_code          # 事件模板类型段（validate 保证批次模板不含）
            return device_no              # {DEVICE_NO}

        return _PLACEHOLDER_RE.sub(repl, template)

    def render(self, template: str, *, device_no: str, now: datetime, seq: int) -> str:
        return self._render(template, device_no=device_no, now=now, seq=seq)

    def counter_key(self, template: str, *, device_no: str, now: datetime) -> str:
        return self._render(template, device_no=device_no, now=now, seq=None)

    def _seed_from_existing(self, counter_key: str, *, evt: bool = False) -> int:
        """存量编号中该前缀的最大序号（后缀需全为数字），无则 0。

        evt=False 扫批次 batch_no；evt=True 扫事件 evt_id（迁移回填兼容）。
        """
        column = Batch.evt_id if evt else Batch.batch_no
        # counter_key 可能含 _ / % / \ 等 LIKE 通配字符，需转义以保持 startswith 语义；
        # 下方编号[len(counter_key):] 切片仍使用原始 counter_key（编号未转义）。
        like_pattern = counter_key.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        numbers: list[int] = []
        for (value,) in self.db.execute(
                select(column).where(
                    column.like(f"{like_pattern}%", escape="\\"))).all():
            if value is None:
                continue
            suffix = value[len(counter_key):]
            if suffix.isascii() and suffix.isdigit():
                numbers.append(int(suffix))
        return max(numbers, default=0)

    def _next_seq(self, counter_key: str, *, evt: bool = False) -> int:
        existing = self.db.get(BatchNoCounter, counter_key)
        if existing is None:
            seed = self._seed_from_existing(counter_key, evt=evt)
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
        # 双层重试：内层处理 generate 内查重冲突（已占用编号则自增再查）；
        # 外层 create_batch 捕获 IntegrityError 重试，作为唯一索引的最终兜底。
        for _ in range(_GENERATE_RETRIES):
            seq = self._next_seq(key)
            batch_no = self.render(template, device_no=device_no, now=now, seq=seq)
            if len(batch_no) > 64:
                raise unprocessable("生成的批次编号超过 64 字符，请调整模板或设备编号")
            exists = self.db.execute(select(Batch).where(
                Batch.batch_no == batch_no)).scalar_one_or_none()
            if exists is None:
                return batch_no
        raise conflict("批次编号生成冲突，请重试")

    def generate_evt(self, template: str | None, device_no: str, type_code: str) -> str:
        """生成事件编号（EVT_ID）：模板未配置时用默认模板；
        counter_key=除 SEQ 外全占位符渲染 → 类型段×设备×年独立 001 起。
        """
        template = template or DEFAULT_EVT_TEMPLATE
        now = datetime.now(timezone.utc)
        key = self._render(template, device_no=device_no, type_code=type_code,
                           now=now, seq=None)
        for _ in range(_GENERATE_RETRIES):
            seq = self._next_seq(key, evt=True)
            evt_id = self._render(template, device_no=device_no, type_code=type_code,
                                  now=now, seq=seq)
            if len(evt_id) > 64:
                raise unprocessable("生成的事件编号超过 64 字符，请调整模板或设备编号")
            exists = self.db.execute(select(Batch).where(
                Batch.evt_id == evt_id)).scalar_one_or_none()
            if exists is None:
                return evt_id
        raise conflict("事件编号生成冲突，请重试")
