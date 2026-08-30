from datetime import datetime, timezone


def utcnow() -> str:
    """ISO-8601 UTC 秒级字符串（架构约定：时间统一 TEXT 存储）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
