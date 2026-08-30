"""清理前端部署临时文件（精确命名，仅删除本目录已知临时文件）。"""
import os

BASE = "/home/hyg2026/datacollecthub"
for name in ("deploy-frontend.tar", "deploy-frontend.tar.gz", "gunzip_file.py"):
    p = os.path.join(BASE, name)
    if os.path.isfile(p):
        os.remove(p)
        print(f"removed {p}")
    else:
        print(f"skip {p} (not exists)")
print("cleanup done")
