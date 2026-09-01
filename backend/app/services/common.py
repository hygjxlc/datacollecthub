from datetime import datetime, timezone


def utcnow() -> str:
    """ISO-8601 UTC 秒级字符串（架构约定：时间统一 TEXT 存储）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# 8 类模态规范顺序（schemas/enums.py Modality 定义序），聚合展示按此排序
MODALITY_ORDER = ["SCADA", "VIB", "AUD", "IR", "CAM", "VID", "TXT", "RPT"]


def sort_modalities(modalities: list[str]) -> list[str]:
    """去重并按模态规范顺序排序；未知代码排最后。"""
    order = {m: i for i, m in enumerate(MODALITY_ORDER)}
    return sorted(set(modalities), key=lambda m: order.get(m, len(order)))
