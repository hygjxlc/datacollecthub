"""deploy-images.tar -> deploy-images.tar.gz（gzip 纯压缩，避免双层 tar 导致 docker load 失败）。"""
import gzip
import shutil

with open("deploy-images.tar", "rb") as src, gzip.open("deploy-images.tar.gz", "wb", compresslevel=9) as dst:
    shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
print("packed deploy-images.tar.gz")
