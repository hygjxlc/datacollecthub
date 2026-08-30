"""清理部署临时文件（精确命名，仅删除本目录 3 个已知临时文件）。"""
import os

BASE = "/home/hyg2026/datacollecthub"
for name in ("deploy-images.tar", "deploy-images.tar.gz", "unpack_images.py"):
    p = os.path.join(BASE, name)
    if os.path.isfile(p):
        os.remove(p)
        print(f"removed {p}")
    else:
        print(f"skip {p} (not exists)")
print("cleanup done")
