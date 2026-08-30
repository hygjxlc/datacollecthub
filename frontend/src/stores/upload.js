import { defineStore } from "pinia";

const STORAGE_KEY = "dch_upload_tasks";

// 上传任务队列：进度与断点续传状态持久化到 localStorage（架构 3.3）
export const useUploadStore = defineStore("upload", {
  state: () => ({
    tasks: JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"),
  }),
  actions: {
    save() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.tasks));
    },
    add(task) {
      this.tasks.push(task);
      this.save();
    },
    markDone(uploadId, partNumber) {
      const t = this.tasks.find((x) => x.uploadId === uploadId);
      if (t && !t.done.includes(partNumber)) {
        t.done.push(partNumber);
        this.save();
      }
    },
    updateStatus(uploadId, status) {
      const t = this.tasks.find((x) => x.uploadId === uploadId);
      if (t) {
        t.status = status;
        this.save();
      }
    },
    remove(uploadId) {
      this.tasks = this.tasks.filter((x) => x.uploadId !== uploadId);
      this.save();
    },
    forBatch(batchId) {
      return this.tasks.filter((x) => x.batchId === batchId);
    },
  },
});
