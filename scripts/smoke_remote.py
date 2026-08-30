# -*- coding: utf-8 -*-
"""DataCollectHub 外网冒烟测试：前端页 / 登录 / 台账三接口 / 集成接口隔离。

用法：python smoke_remote.py（在任意有网络的本机执行）
"""
import json
import sys
import urllib.request

BASE = "http://49.233.255.243:19001"


def call(method: str, path: str, body=None, token=None, raw=False):
    req = urllib.request.Request(BASE + path, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode("utf-8")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            return resp.status, (data if raw else json.loads(data or b"{}"))
    except urllib.error.HTTPError as e:
        data = e.read()
        try:
            parsed = json.loads(data or b"{}")
        except Exception:
            parsed = data[:200]
        return e.code, parsed


def main():
    failures = []

    # 1. 前端首页
    st, _ = call("GET", "/", raw=True)
    ok = st == 200
    print(f"[{'PASS' if ok else 'FAIL'}] 前端首页 GET / -> {st}")
    if not ok:
        failures.append("前端首页")

    # 2. 登录
    st, data = call("POST", "/api/v1/auth/login",
                    body={"username": "zhang", "password": "pass123"})
    token = data.get("access_token") if isinstance(data, dict) else None
    ok = st == 200 and token
    print(f"[{'PASS' if ok else 'FAIL'}] 登录 zhang -> {st} token={'OK' if token else 'NO'}")
    if not ok:
        failures.append("登录")
        print("    无法继续，中止")
        sys.exit(1)

    # 3. 台账三接口（任务 1-4 新增功能）
    for path, name in [
        ("/api/v1/nameplates", "铭牌台账"),
        ("/api/v1/point-dicts", "测点字典"),
        ("/api/v1/events", "事件记录"),
    ]:
        st, data = call("GET", path, token=token)
        ok = st == 200 and isinstance(data, dict) and "items" in data
        print(f"[{'PASS' if ok else 'FAIL'}] {name} GET {path} -> {st} items={len(data.get('items', [])) if isinstance(data, dict) else '?'}")
        if not ok:
            failures.append(name)

    # 4. 联动导出元数据接口（任务 6）
    st, data = call("GET", "/api/v1/files?batch_no=", token=token)
    print(f"[{'PASS' if st == 200 else 'FAIL'}] 文件列表 GET /api/v1/files -> {st}")

    # 5. 集成接口对外 404（内网隔离第一层，任务 8 冒烟项）
    st, _ = call("GET", "/api/v1/integration/files/ids")
    ok = st == 404
    print(f"[{'PASS' if ok else 'FAIL'}] 集成接口对外隔离 GET /api/v1/integration/files/ids -> {st}（预期 404）")
    if not ok:
        failures.append("集成接口隔离")

    # 6. 设备台账按设备过滤（跨接口一致性：F01 设备号查询）
    st, data = call("GET", "/api/v1/events?device_no=F01", token=token)
    print(f"[{'PASS' if st == 200 else 'FAIL'}] 事件按设备过滤 GET /api/v1/events?device_no=F01 -> {st}")

    print()
    if failures:
        print(f"冒烟失败项：{failures}")
        sys.exit(1)
    print("全部冒烟通过 [OK]")


if __name__ == "__main__":
    main()
