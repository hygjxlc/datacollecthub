"""batch 表补「批次扩展键值对」列（extras）。

用法：
    python migrate_batch_extras.py <db_path>

- 迁移前自动备份 <db_path> -> <db_path>.bak-<时间戳>
- 幂等：列已存在则跳过
- 兼容：库中无 batch 表（新库由 create_all 建全量结构）则跳过
"""
import shutil
import sqlite3
import sys
from datetime import datetime


def migrate(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        if "batch" not in tables:
            print(f"[SKIP] 库中无 batch 表（{db_path}），新库将由 create_all 建全量结构")
            return
        cols = [r[1] for r in con.execute("PRAGMA table_info(batch)")]
        if "extras" in cols:
            print(f"[SKIP] {db_path} batch 已含 extras 列")
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{db_path}.bak-{stamp}"
        shutil.copy2(db_path, bak)
        con.execute("ALTER TABLE batch ADD COLUMN extras JSON")
        con.commit()
        print(f"[OK] {db_path} batch 已加列：extras（备份 {bak}）")
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    migrate(sys.argv[1])
