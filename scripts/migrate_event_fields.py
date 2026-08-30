"""event 表补 4 个结构化字段列（事件记录升级：根因/处置/效果/工况）。

用法：
    python migrate_event_fields.py <db_path>

- 迁移前自动备份 <db_path> -> <db_path>.bak-<时间戳>
- 幂等：列已存在则跳过
- 兼容：库中无 event 表（新库由 create_all 建全量表）则跳过
"""
import shutil
import sqlite3
import sys
from datetime import datetime

COLUMNS = [
    ("root_cause", "TEXT"),
    ("treatment", "TEXT"),
    ("treatment_result", "TEXT"),
    ("operating_condition", "TEXT"),
]


def migrate(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        if "event" not in tables:
            print(f"[SKIP] 库中无 event 表（{db_path}），新库将由 create_all 建全量结构")
            return
        cols = [r[1] for r in con.execute("PRAGMA table_info(event)")]
        missing = [(name, typ) for name, typ in COLUMNS if name not in cols]
        if not missing:
            print(f"[SKIP] {db_path} event 已含全部结构化字段列")
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{db_path}.bak-{stamp}"
        shutil.copy2(db_path, bak)
        for name, typ in missing:
            con.execute(f"ALTER TABLE event ADD COLUMN {name} {typ}")
        con.commit()
        names = ", ".join(n for n, _ in missing)
        print(f"[OK] {db_path} event 已加列：{names}（备份 {bak}）")
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    migrate(sys.argv[1])
