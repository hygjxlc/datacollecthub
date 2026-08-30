"""point_dict 表补 creator_id 列（方案 A 台账创建者追溯）。

用法：
    python migrate_point_dict_creator.py <db_path>

- 迁移前自动备份 <db_path> -> <db_path>.bak-<时间戳>
- 幂等：列已存在则跳过
- 兼容：库中无 point_dict 表（新库由 create_all 建全量表）则跳过
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
        if "point_dict" not in tables:
            print(f"[SKIP] 库中无 point_dict 表（{db_path}），新库将由 create_all 建全量结构")
            return
        cols = [r[1] for r in con.execute("PRAGMA table_info(point_dict)")]
        if "creator_id" in cols:
            print(f"[SKIP] {db_path} point_dict 已有 creator_id 列")
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{db_path}.bak-{stamp}"
        shutil.copy2(db_path, bak)
        con.execute("ALTER TABLE point_dict ADD COLUMN creator_id VARCHAR(36)")
        con.commit()
        print(f"[OK] {db_path} point_dict 已加 creator_id 列（备份 {bak}）")
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    migrate(sys.argv[1])
