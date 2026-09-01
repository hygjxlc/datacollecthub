<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";
import UploadPanel from "../components/upload/UploadPanel.vue";

// 批量导入：下载模板 → 上传 zip → 后端异步导入 → 轮询进度与报告
const jobs = ref([]);
const current = ref(null);
let timer = null;

async function downloadTemplate() {
  const { data } = await api.get("/batch-imports/template", { responseType: "blob" });
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "manifest.csv";
  a.click();
  URL.revokeObjectURL(url);
}

async function onFileUploaded({ objectKey }) {
  try {
    const { data } = await api.post("/batch-imports", { object_key: objectKey });
    ElMessage.success("导入任务已提交，系统正在后台处理");
    current.value = data;
    startPolling(data.id);
  } catch { /* 拦截器已提示 */ }
}

function startPolling(id) {
  stopPolling();
  timer = setInterval(async () => {
    const { data } = await api.get(`/batch-imports/${id}`);
    current.value = data;
    if (["succeeded", "failed"].includes(data.status)) {
      stopPolling();
      loadJobs();
    }
  }, 2000);
}
function stopPolling() {
  if (timer) clearInterval(timer);
  timer = null;
}
async function loadJobs() {
  const { data } = await api.get("/batch-imports", { params: { page_size: 50 } });
  jobs.value = data.items;
}
onMounted(loadJobs);
onUnmounted(stopPolling);
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <h3>批量导入</h3>
      <el-button type="primary" @click="downloadTemplate">下载模板（manifest.csv）</el-button>
    </div>

    <el-card class="card">
      <template #header><span>导入步骤</span></template>
      <el-steps :active="current ? (current.status === 'succeeded' ? 3 : 2) : 0"
                align-center finish-status="success">
        <el-step title="下载模板" description="按清单填写各批次字段" />
        <el-step title="打包 zip" description="manifest.csv 与批次目录同层，第一层子目录=一个批次" />
        <el-step title="上传并导入" description="分片直传 MinIO，后台自动预检入库" />
        <el-step title="查看报告" description="成功清单与失败明细" />
      </el-steps>
    </el-card>

    <el-card class="card">
      <template #header><span>上传导入包</span></template>
      <UploadPanel batch-id="import" :check-point-dict="false"
                   init-url="/batch-imports/upload/init"
                   complete-url-template="/batch-imports/upload/{uploadId}/complete"
                   @file-uploaded="onFileUploaded" />
      <el-alert type="info" show-icon :closable="false" class="tip"
                title="manifest.csv 字段：目录、batch_no（启用编号规则时留空）、device_no、license、sensitivity、is_synthetic、数据对应设备:状态类型为必填；其余选填；任意附加列将作为该批次扩展字段（extras）入库。" />
    </el-card>

    <el-card v-if="current" class="card">
      <template #header><span>导入进度 — {{ current.status }}</span></template>
      <el-progress :percentage="current.total_batches
        ? Math.round((current.done_batches / current.total_batches) * 100) : 0" />
      <template v-if="current.report">
        <h4>成功批次</h4>
        <el-tag v-for="s in current.report.success" :key="s" type="success" class="tag">{{ s }}</el-tag>
        <h4 v-if="current.report.skipped?.length">跳过（已存在）</h4>
        <el-tag v-for="s in current.report.skipped" :key="s" type="warning" class="tag">{{ s }}</el-tag>
        <h4 v-if="current.report.failures?.length">失败明细</h4>
        <ul><li v-for="f in current.report.failures" :key="f">{{ f }}</li></ul>
        <h4 v-if="current.report.errors?.length">预检错误（全部未入库）</h4>
        <ul><li v-for="e in current.report.errors" :key="e">{{ e }}</li></ul>
      </template>
    </el-card>

    <el-card class="card">
      <template #header><span>历史任务</span></template>
      <el-table :data="jobs" border>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            {{ row.done_batches }} / {{ row.total_batches }} 批次
          </template>
        </el-table-column>
        <el-table-column prop="object_key" label="导入包" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card { margin-bottom: 16px; }
.tip { margin-top: 12px; }
.tag { margin-right: 8px; }
</style>
