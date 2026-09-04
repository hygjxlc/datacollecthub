import enum


class Modality(str, enum.Enum):
    """8 类数据模态（数据收集要求清单模态代码）。"""

    SCADA = "SCADA"
    VIB = "VIB"
    AUD = "AUD"
    IR = "IR"
    CAM = "CAM"
    VID = "VID"
    TXT = "TXT"
    RPT = "RPT"


class EquipmentStateType(str, enum.Enum):
    WIND = "风电"
    THERMAL = "火电"
    SOLAR = "光伏"
    OTHER = "其它"


class Role(str, enum.Enum):
    user = "user"
    admin = "admin"


class License(str, enum.Enum):
    INTERNAL = "内部专用"
    CC_BY = "CC-BY"
    MIT = "MIT"


class Sensitivity(str, enum.Enum):
    PUBLIC = "公开"
    INTERNAL = "内部"
    CONFIDENTIAL = "机密"


class OrgType(str, enum.Enum):
    STATION = "场站"
    PLANT = "电厂"
    OPS = "运维单位"


class UploadStatus(str, enum.Enum):
    UPLOADING = "上传中"
    DONE = "已完成"
