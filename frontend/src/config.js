// 系统可配置项（按需修改，改后重新构建前端生效）
// 采样周期默认单位按模态映射（8 类模态，SRS 4.6；TXT/RPT 无默认单位）
export const SAMPLE_PERIOD_UNITS = {
  SCADA: "s",   // 工艺参数
  VIB: "kHz",   // 振动信号
  AUD: "kHz",   // 声纹/音频
  IR: "min",    // 红外热像
  CAM: "min",   // 可见光照片
  VID: "s",     // 视频
  TXT: "",      // 文本
  RPT: "",      // 报表
};
// 采样周期单位下拉备选项（用户可改选）
export const SAMPLE_UNIT_OPTIONS = ["s", "ms", "min", "h", "kHz", "Hz", "fps", "帧", "次", "天"];
