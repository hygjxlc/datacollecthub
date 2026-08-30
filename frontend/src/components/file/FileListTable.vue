<script setup>
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../../api";
import { MODALITY_LABELS } from "../../stores/dict";
import PermissionWrapper from "../common/PermissionWrapper.vue";
import FileMetaForm from "./FileMetaForm.vue";

// 文件清单表：编辑/删除按钮按归属渲染（TC-PERM-002，后端仍强制校验）
const props = defineProps({
  files: { type: Array, default: () => [] },
});
const emit = defineEmits(["changed"]);

const editing = ref(null);
const saving = ref(false);

// v-model 需成员表达式，对话框显隐由 computed 代理
const editDialog = computed({
  get: () => !!editing.value,
  set: (v) => { if (!v) editing.value = null; },
});

// 当前编辑文件的同批次其他文件（供元数据表单"复制自同批次文件"下拉）
const siblings = computed(() => {
  const cur = editing.value;
  if (!cur) return [];
  return props.files.filter((f) => f.id !== cur.id && f.batch_id === cur.batch_id);
});

function fmtSize(bytes) {
  if (!bytes) return "-";
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function fmtTime(value) {
  return value || "-";
}

async function saveMeta(payload) {
  saving.value = true;
  try {
    await api.put(`/files/${editing.value.id}`, payload);
    ElMessage.success("元数据已保存");
    editing.value = null;
    emit("changed");
  } finally {
    saving.value = false;
  }
}

async function handleDelete(file) {
  await ElMessageBox.confirm(`确认删除文件 ${file.filename}？原始对象将一并删除。`,
                             "删除确认", { type: "warning" });
  await api.delete(`/files/${file.id}`);
  ElMessage.success("已删除");
  emit("changed");
}

async function handleDownload(file) {
  // 单文件下载 = 打包（原始数据 + 元数据 JSON 同文件夹），与批量下载结构一致
  const resp = await api.post(
    "/files/batch-download", { ids: [file.id] }, { responseType: "blob" });
  const cd = resp.headers["content-disposition"] || "";
  const m = /filename\*?=(?:UTF-8''|["']?)([^;"']+)/i.exec(cd);
  const name = m ? m[1] : `${file.filename}.zip`;
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div>
    <el-table :data="files" border>
      <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
      <el-table-column label="模态" width="110">
        <template #default="{ row }">{{ MODALITY_LABELS[row.modality] || row.modality }}</template>
      </el-table-column>
      <el-table-column label="采集开始时间" min-width="170">
        <template #default="{ row }">{{ fmtTime(row.start_time) }}</template>
      </el-table-column>
      <el-table-column prop="sample_period" label="采样周期" width="100" />
      <el-table-column label="大小" width="100">
        <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="handleDownload(row)">下载</el-button>
          <PermissionWrapper :owner-id="row.uploader_id">
            <el-button link type="primary" @click="editing = row">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </PermissionWrapper>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editDialog" :title="`编辑元数据 - ${editing?.filename}`" width="720px">
      <FileMetaForm v-if="editing" :model-value="editing" :siblings="siblings" @submit="saveMeta">
        <div class="dialog-footer">
          <el-button @click="editing = null">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
        </div>
      </FileMetaForm>
    </el-dialog>
  </div>
</template>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
