"""服务器端 TC-INT-006 等价验证：backend 容器内直连集成接口，预期输出 200。"""
import urllib.request

status = urllib.request.urlopen(
    "http://localhost:8080/api/v1/integration/files/ids"
).status
print(status)
assert status == 200, f"expected 200, got {status}"
print("[OK] TC-INT-006 container-internal check passed")
