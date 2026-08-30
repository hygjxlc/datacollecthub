import { defineStore } from "pinia";
import api from "../api";

export const useBatchStore = defineStore("batch", {
  state: () => ({
    list: [],
    total: 0,
    current: null,
    files: { items: [], total: 0 },
  }),
  actions: {
    async fetchList(params = {}) {
      const { data } = await api.get("/batches", { params });
      this.list = data.items;
      this.total = data.total;
      return data;
    },
    async fetchDetail(id) {
      const { data } = await api.get(`/batches/${id}`);
      this.current = data;
      return data;
    },
    async fetchFiles(batchNo, params = {}) {
      // 批次详情页文件清单：按批次号快照过滤（F6 快照字段）
      const { data } = await api.get("/files", {
        params: { batch_no: batchNo, page_size: 100, ...params },
      });
      this.files = data;
      return data;
    },
  },
});
