# -*- coding: utf-8 -*-
"""部署后冒烟验证：三台账 creator_name + 事件结构化 4 字段。

用法：
    python smoke_structured.py

- 调用公网 API http://49.233.255.243:19001
- 验证：nameplates/point-dicts/events 响应含 creator_name 键
- 验证：创建事件带 4 结构化字段 → 响应回显；随后删除该测试事件
- 任一步失败以非零码退出（EXIT=1）
"""
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.environ.get("SMOKE_BASE", "http://49.233.255.243:19001")
USER = os.environ.get("SMOKE_USER", "zhang")
PASS = os.environ.get("SMOKE_PASS", "pass123")


def call(method, path, token=None, payload=None, expect=200):
    req = urllib.request.Request(f"{BASE}/api/v1{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=15) as r:
            code, body = r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        code, body = e.code, json.loads(e.read() or b"{}")
    assert code == expect, f"{method} {path} -> {code}: {body}"
    return body


def main() -> None:
    token = call("POST", "/auth/login",
                 payload={"username": USER, "password": PASS})["access_token"]

    # 方案 A：三台账响应含 creator_name 键
    for ep in ("/nameplates", "/point-dicts", "/events"):
        body = call("GET", ep, token=token)
        assert "items" in body, f"{ep} 无 items"
        if body["items"]:
            assert "creator_name" in body["items"][0], f"{ep} 缺 creator_name 键"

    # 事件结构化 4 字段：创建 → 回显 → 删除
    payload = {
        "event_time": "2026-08-29 10:00:00", "timezone": "+08:00",
        "device_no": "SMOKE-STRUCT", "event_type": "冒烟/结构化/验证",
        "severity": "报警", "description": "冒烟测试事件（自动清理）",
        "root_cause": "测试根因", "treatment": "测试处置",
        "treatment_result": "测试效果", "operating_condition": "测试工况",
    }
    created = call("POST", "/events", token=token, payload=payload)
    assert created["root_cause"] == "测试根因"
    assert created["treatment"] == "测试处置"
    assert created["treatment_result"] == "测试效果"
    assert created["operating_condition"] == "测试工况"
    call("DELETE", f"/events/{created['id']}", token=token)
    print("[OK] smoke_structured 全部通过")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
