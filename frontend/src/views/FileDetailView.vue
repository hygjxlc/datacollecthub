<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import api from "../api";
import { MODALITY_LABELS } from "../stores/dict";
import PermissionWrapper from "../components/common/PermissionWrapper.vue";
import FileMetaForm from "../components/file/FileMetaForm.vue";

// 文件详情：全部字段 + 下载 presign + F5 元数据补填（时区必填 TC-META-002）
const route = useRoute();
const router = useRouter();
const fileId = route.params.id;

const file = ref(null);
const siblings = ref([]);
const editing = ref(false);
const saving = ref(false);

function fmtSize(bytes) {
  if (!bytes) return "-";
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

async function load() {
  const { data } = await api.get(`/files/${fileId}`);
  file.value = data;
  // 同批次其他文件（供元数据表单"复制自同批次文件"下拉；检索按单位过滤，同单位可见）
  if (data.batch_no) {
    const res = await api.get("/files", { params: { batch_no: data.batch_no, page_size: 100 } });
    siblings.value = res.data.items.filter((f) => f.id !== fileId);
  }
}

async function handleDownload() {
  // 单文件下载 = 打包（原始数据 + 元数据 JSON 同文件夹），与批量下载结构一致
  const resp = await api.post(
    "/files/batch-download", { ids: [fileId] }, { responseType: "blob" });
  const cd = resp.headers["content-disposition"] || "";
  const m = /filename\*?=(?:UTF-8''|["']?)([^;"']+)/i.exec(cd);
  const name = m ? m[1] : `${file.value.filename}.zip`;
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function handleSave(payload) {
  saving.value = true;
  try {
    const { data } = await api.put(`/files/${fileId}`, payload);
    file.value = data;
    editing.value = false;
    ElMessage.success("元数据已保存");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page" v-if="file">
    <el-page-header class="header" @back="router.push('/files')">
      <template #content><h3>{{ file.filename }}</h3></template>
    </el-page-header>

    <el-card class="card">
      <template #header>
        <div class="card-header">
          <span>文件信息</span>
          <div>
            <el-button type="primary" @click="handleDownload">下载</el-button>
            <PermissionWrapper :owner-id="file.uploader_id">
              <el-button @click="editing = true">补填元数据</el-button>
            </PermissionWrapper>
          </div>
        </div>
      </template>

      <el-descriptions :column="3" border>
        <el-descriptions-item label="文件名">{{ file.filename }}</el-descriptions-item>
        <el-descriptions-item label="模态">
          {{ MODALITY_LABELS[file.modality] || file.modality }}
        </el-descriptions-item>
        <el-descriptions-item label="大小">{{ fmtSize(file.file_size) }}</el-descriptions-item>
        <el-descriptions-item label="批次编号">{{ file.batch_no || "-" }}</el-descriptions-item>
        <el-descriptions-item label="设备编号">{{ file.device_no || "-" }}</el-descriptions-item>
        <el-descriptions-item label="场站名称">{{ file.station || "-" }}</el-descriptions-item>
        <el-descriptions-item label="object_key">{{ file.object_key }}</el-descriptions-item>
        <el-descriptions-item label="校验和">{{ file.checksum || "-" }}</el-descriptions-item>
        <el-descriptions-item label="上传状态">{{ file.upload_status }}</el-descriptions-item>
        <el-descriptions-item label="采集开始时间">{{ file.start_time || "-" }}</el-descriptions-item>
        <el-descriptions-item label="采集结束时间">{{ file.end_time || "-" }}</el-descriptions-item>
        <el-descriptions-item label="采样周期">{{ file.sample_period || "-" }}</el-descriptions-item>
        <el-descriptions-item label="数据量">{{ file.data_amount || "-" }}</el-descriptions-item>
        <el-descriptions-item label="条数">{{ file.record_count || "-" }}</el-descriptions-item>
        <el-descriptions-item label="时长">{{ file.duration || "-" }}</el-descriptions-item>
        <el-descriptions-item label="许可证">{{ file.license || "-" }}</el-descriptions-item>
        <el-descriptions-item label="敏感级别">{{ file.sensitivity || "-" }}</el-descriptions-item>
        <el-descriptions-item label="是否合成">
          {{ file.is_synthetic == null ? "-" : file.is_synthetic ? "是" : "否" }}
        </el-descriptions-item>
        <el-descriptions-item label="运行工况">{{ file.operating_condition || "-" }}</el-descriptions-item>
        <el-descriptions-item label="天气条件">{{ file.weather || "-" }}</el-descriptions-item>
        <el-descriptions-item label="上传时间">{{ file.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-dialog v-model="editing" title="补填元数据" width="720px">
      <FileMetaForm v-if="editing" :model-value="file" :siblings="siblings" @submit="handleSave">
        <div class="footer">
          <el-button @click="editing = false">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
        </div>
      </FileMetaForm>
    </el-dialog>
  </div>
</template>

<style scoped>
.header {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
