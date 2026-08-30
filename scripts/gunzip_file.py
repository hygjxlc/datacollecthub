"""<name>.tar.gz -> <name>.tar（服务器端解压，供 docker load 使用）。"""
import gzip
import shutil
import sys

src_name = sys.argv[1]            # 如 deploy-frontend.tar.gz
dst_name = src_name[:-3]          # 去掉 .gz
with gzip.open(src_name, "rb") as src, open(dst_name, "wb") as dst:
    shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
print(f"unpacked {dst_name}")
