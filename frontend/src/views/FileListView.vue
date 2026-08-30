<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import api from "../api";
import { MODALITIES, MODALITY_LABELS } from "../stores/dict";

// 文件检索：组合筛选（F7 架构 6.2）+ 分页 + 跨单位隐藏 + 批量下载（TC-DOWNLOAD）
const router = useRouter();
const loading = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const selection = ref([]);
const downloading = ref(false);

const filters = reactive({
  modality: "",
  batch_no: "",
  device_no: "",
  station: "",
  start_after: "",
  start_before: "",
  is_synthetic: "",
});

function fmtSize(bytes) {
  if (!bytes) return "-";
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

async function search() {
  loading.value = true;
  try {
    const params = {
      page: page.value, page_size: pageSize.value,
      modality: filters.modality || undefined,
      batch_no: filters.batch_no || undefined,
      device_no: filters.device_no || undefined,
      station: filters.station || undefined,
      start_after: filters.start_after || undefined,
      start_before: filters.start_before || undefined,
      is_synthetic: filters.is_synthetic === "" ? undefined : filters.is_synthetic,
    };
    const { data } = await api.get("/files", { params });
    rows.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

function reset() {
  Object.assign(filters, {
    modality: "", batch_no: "", device_no: "", station: "",
    start_after: "", start_before: "", is_synthetic: "",
  });
  page.value = 1;
  search();
}

onMounted(search);

function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// 逐个下载：每个文件单独打包（原始数据 + 元数据 JSON），同源 blob 触发保存
async function batchDownload() {
  if (!selection.value.length) return;
  downloading.value = true;
  try {
    for (const row of selection.value) {
      const resp = await api.post(
        "/files/batch-download", { ids: [row.id] }, { responseType: "blob" });
      const cd = resp.headers["content-disposition"] || "";
      const m = /filename\*?=(?:UTF-8''|["']?)([^;"']+)/i.exec(cd);
      const name = m ? m[1] : `${row.filename}.zip`;
      const url = URL.createObjectURL(resp.data);
      triggerDownload(url, name);
      URL.revokeObjectURL(url);
      await new Promise((r) => setTimeout(r, 300));
    }
    ElMessage.success(`已下载 ${selection.value.length} 个文件（含元数据）`);
  } finally {
    downloading.value = false;
  }
}

// 打包下载：后端 zip 流式生成（TC-DOWNLOAD，一次最多 20 个）
async function batchZip() {
  if (!selection.value.length) return;
  if (selection.value.length > 20) {
    ElMessage.warning("一次最多打包 20 个文件，请分批下载");
    return;
  }
  downloading.value = true;
  try {
    const resp = await api.post(
      "/files/batch-download",
      { ids: selection.value.map((r) => r.id) },
      { responseType: "blob" });
    const cd = resp.headers["content-disposition"] || "";
    const m = /filename\*?=(?:UTF-8''|["']?)([^;"']+)/i.exec(cd);
    const name = m ? m[1] : `datacollecthub-${Date.now()}.zip`;
    const url = URL.createObjectURL(resp.data);
    triggerDownload(url, name);
    URL.revokeObjectURL(url);
    ElMessage.success("已打包下载");
  } finally {
    downloading.value = false;
  }
}
</script>

<template>
  <div class="page">
    <h3 class="title">文件检索</h3>

    <el-card class="card">
      <el-form inline @submit.prevent="page = 1; search()">
        <el-form-item label="模态">
          <el-select v-model="filters.modality" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="m in MODALITIES" :key="m.value"
                       :label="m.label" :value="m.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次编号">
          <el-input v-model="filters.batch_no" name="batch_no" clearable placeholder="如 B2025-001" />
        </el-form-item>
        <el-form-item label="设备编号">
          <el-input v-model="filters.device_no" name="device_no" clearable placeholder="如 F01" />
        </el-form-item>
        <el-form-item label="场站">
          <el-input v-model="filters.station" name="station" clearable placeholder="场站名" />
        </el-form-item>
        <el-form-item label="开始时间起">
          <el-input v-model="filters.start_after" clearable placeholder="2025-06-15 14:23:08" />
        </el-form-item>
        <el-form-item label="开始时间止">
          <el-input v-model="filters.start_before" clearable placeholder="2025-06-16 14:23:08" />
        </el-form-item>
        <el-form-item label="是否合成">
          <el-select v-model="filters.is_synthetic" clearable placeholder="全部" style="width: 100px">
            <el-option label="是" :value="1" />
            <el-option label="否" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="toolbar">
      <span class="selected">已选 {{ selection.length }} 项</span>
      <el-button size="small" :disabled="!selection.length || downloading"
                 @click="batchDownload">逐个下载</el-button>
      <el-button size="small" type="primary" :disabled="!selection.length || downloading"
                 @click="batchZip">打包下载（zip）</el-button>
    </div>

    <el-table :data="rows" border v-loading="loading" @selection-change="selection = $event">
      <el-table-column type="selection" width="46" />
      <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
      <el-table-column label="模态" width="110">
        <template #default="{ row }">{{ MODALITY_LABELS[row.modality] || row.modality }}</template>
      </el-table-column>
      <el-table-column prop="batch_no" label="批次编号" width="130" />
      <el-table-column prop="device_no" label="设备编号" width="110" />
      <el-table-column label="采集开始时间" min-width="170">
        <template #default="{ row }">
          {{ row.start_time || "-" }}
        </template>
      </el-table-column>
      <el-table-column label="大小" width="100" align="right">
        <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/files/${row.id}`)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="total"
      :page-size="pageSize"
      v-model:current-page="page"
      @current-change="search"
    />
  </div>
</template>

<style scoped>
.title {
  margin-bottom: 16px;
}
.card {
  margin-bottom: 16px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.selected {
  margin-right: 8px;
  font-size: 14px;
  color: #606266;
}
</style>
