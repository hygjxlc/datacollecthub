"""批次登记表 Excel 导出（架构 6.2 F7）：列结构与《数据收集要求清单》第六节一致。"""

import io

from openpyxl import Workbook
from openpyxl.styles import Font

MODALITY_LABELS = {"SCADA": "工艺参数", "VIB": "振动信号", "AUD": "声纹/音频",
                   "IR": "红外热像", "CAM": "可见光照片", "VID": "视频",
                   "TXT": "文本", "RPT": "报表"}

BATCH_HEADERS = ["批次编号", "设备/机组编号", "设备型号", "场站名称", "许可证",
                 "敏感级别", "负责人及联系方式", "是否合成/仿真数据", "运行工况",
                 "故障发生时间", "事件描述", "天气条件", "所属场站"]

FILE_HEADERS = ["文件名", "模态类型", "采集开始时间", "采集结束时间",
                "采样周期", "数据量", "条数/时长"]


def _fmt_time(value: str | None, timezone: str | None) -> str:
    if not value:
        return ""
    return f"{value} {timezone}" if timezone else value


def build_excel(batch, files) -> bytes:
    """两 sheet 登记表：Sheet1 批次说明表（一行），Sheet2 文件清单表（每文件一行）。"""
    wb = Workbook()
    header_font = Font(bold=True)

    ws1 = wb.active
    ws1.title = "批次说明表"
    ws1.append(BATCH_HEADERS)
    ws1.append([batch.batch_no, batch.device_no, batch.device_model or "",
                batch.station or "", batch.license or "", batch.sensitivity or "",
                batch.owner_contact or "", "是" if batch.is_synthetic else "否",
                batch.operating_condition or "", batch.fault_time or "",
                batch.fault_desc or "", batch.weather or "",
                batch.equipment_state_type or ""])
    for cell in ws1[1]:
        cell.font = header_font

    ws2 = wb.create_sheet("文件清单表")
    ws2.append(FILE_HEADERS)
    for cell in ws2[1]:
        cell.font = header_font
    for f in files:
        ws2.append([f.filename, MODALITY_LABELS.get(f.modality, f.modality),
                    _fmt_time(f.start_time, f.timezone),
                    _fmt_time(f.end_time, f.timezone),
                    f.sample_period or "", f"{f.file_size} B",
                    f.record_count or f.duration or ""])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
