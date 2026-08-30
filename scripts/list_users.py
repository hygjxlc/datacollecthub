"""列出部署系统上的所有用户（通过 admin API）。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://49.233.255.243:19001/api/v1"


def call(path, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, headers=headers)
    return json.loads(urllib.request.urlopen(req).read().decode())


# 登录 admin
login = urllib.request.Request(
    BASE + "/auth/login",
    data=json.dumps({"username": "admin", "password": "admin123"}).encode(),
    headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(login).read().decode())["access_token"]

users = call("/admin/users", token)["items"]
orgs = {o["id"]: o["name"] for o in call("/admin/organizations", token)["items"]}

print(f"共 {len(users)} 个用户:")
for u in users:
    org = orgs.get(u.get("organization_id"), "-")
    print(f" - {u.get('username')} | {u.get('display_name')} | role: {u.get('role')}"
          f" | org: {org} | active: {u.get('is_active')}")
