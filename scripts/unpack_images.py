"""deploy-images.tar.gz -> deploy-images.tar（服务器端解压，供 docker load 使用）。"""
import gzip
import shutil

with gzip.open("deploy-images.tar.gz", "rb") as src, open("deploy-images.tar", "wb") as dst:
    shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
print("unpacked deploy-images.tar")
