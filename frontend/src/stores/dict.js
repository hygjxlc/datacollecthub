import { defineStore } from "pinia";
import api from "../api";

// 8 类模态枚举（SRS 4.6，与数据收集要求清单第二节一致）
export const MODALITIES = [
  { value: "SCADA", label: "工艺参数" },
  { value: "VIB", label: "振动信号" },
  { value: "AUD", label: "声纹/音频" },
  { value: "IR", label: "红外热像" },
  { value: "CAM", label: "可见光照片" },
  { value: "VID", label: "视频" },
  { value: "TXT", label: "文本" },
  { value: "RPT", label: "报表" },
];

export const MODALITY_LABELS = Object.fromEntries(
  MODALITIES.map((m) => [m.value, m.label])
);

export const LICENSES = ["内部专用", "CC-BY", "MIT"];
export const SENSITIVITIES = ["公开", "内部", "机密"];

export const useDictStore = defineStore("dict", {
  state: () => ({
    organizations: [],
  }),
  actions: {
    async loadOrganizations() {
      const { data } = await api.get("/admin/organizations");
      this.organizations = data.items;
    },
  },
});
