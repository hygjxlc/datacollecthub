<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../api";
import { useBatchStore } from "../stores/batch";
import { useAuthStore } from "../stores/auth";
import { MODALITY_LABELS } from "../stores/dict";
import PermissionWrapper from "../components/common/PermissionWrapper.vue";
import BatchForm from "../components/batch/BatchForm.vue";
import FileListTable from "../components/file/FileListTable.vue";

// 批次详情：批次说明 + 文件清单（F6 快照）+ 上传入口 + 导出登记表（F7）
const route = useRoute();
const router = useRouter();
const store = useBatchStore();
const batchId = route.params.id;

const editing = ref(false);
const saving = ref(false);
const exporting = ref(false);

const batch = computed(() => store.current);

const ledger = ref({ nameplate: null, points: [] });

async function loadLedger() {
  if (!store.current?.device_no) return;
  try {
    const np = await api.get(`/nameplates/by-device/${encodeURIComponent(store.current.device_no)}`);
    ledger.value.nameplate = np.data.items[0] || null;
  } catch { /* 铭牌查询失败不阻断（拦截器已提示） */ }
  try {
    const pd = await api.get(`/point-dicts?device_no=${encodeURIComponent(store.current.device_no)}`);
    ledger.value.points = pd.data.items;
  } catch { /* 测点字典查询失败不阻断（拦截器已提示） */ }
}

async function load() {
  await store.fetchDetail(batchId);
  syncExtras();
  await Promise.allSettled([loadFiles(), loadLedger()]);
}

// 扩展字段：用户自己添加多个键值对（参考单批次表单交互）
const auth = useAuthStore();
const canEditExtras = computed(
  () => auth.isAdmin || (!!batch.value?.creator_id && batch.value.creator_id === auth.user?.id)
);
let extrasSeq = 0;
const extrasList = reactive([]);
const savingExtras = ref(false);

function syncExtras() {
  extrasList.splice(0, extrasList.length,
    ...Object.entries(batch.value?.extras || {}).map(([k, v]) => ({
      id: extrasSeq++, key: k, value: String(v ?? ""),
    })));
}

function addExtra() {
  extrasList.push({ id: extrasSeq++, key: "", value: "" });
}

async function saveExtras() {
  const extras = Object.create(null);
  for (const row of extrasList) {
    const k = (row.key || "").trim();
    if (!k) continue;
    if (Object.hasOwn(extras, k)) {
      ElMessage.warning(`扩展字段键名重复：${k}`);
      return;
    }
    extras[k] = row.value;
  }
  savingExtras.value = true;
  try {
    await api.put(`/batches/${batchId}`, {
      extras: Object.keys(extras).length ? extras : null,
    });
    ElMessage.success("扩展字段已保存");
    await load();
  } finally {
    savingExtras.value = false;
  }
}

async function loadFiles() {
  if (store.current?.batch_no) {
    await store.fetchFiles(store.current.batch_no);
  }
}

async function handleEdit(payload) {
  saving.value = true;
  try {
    await api.put(`/batches/${batchId}`, payload);
    ElMessage.success("批次已更新");
    editing.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function handleDelete() {
  await ElMessageBox.confirm(
    `确认删除批次 ${batch.value.batch_no}？批次下全部文件对象将一并删除。`,
    "删除确认", { type: "warning" });
  await api.delete(`/batches/${batchId}`);
  router.push("/batches");
}

// 导出登记表：带 Authorization 的 blob 下载（F7 两 sheet Excel）
async function handleExport() {
  exporting.value = true;
  try {
    const { data } = await api.get(`/batches/${batchId}/export`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${batch.value.batch_no}_登记表.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page" v-if="batch">
    <el-page-header class="header" @back="router.push('/batches')">
      <template #content>
        <h3>批次 {{ batch.batch_no }}</h3>
      </template>
    </el-page-header>

    <el-card class="card">
      <template #header>
        <div class="card-header">
          <span>批次说明表</span>
          <div>
            <el-button type="primary" @click="router.push(`/batches/${batchId}/upload`)">
              上传文件
            </el-button>
            <el-button :loading="exporting" @click="handleExport">导出登记表</el-button>
            <PermissionWrapper :owner-id="batch.creator_id">
              <el-button @click="editing = true">编辑</el-button>
              <el-button type="danger" @click="handleDelete">删除批次</el-button>
            </PermissionWrapper>
          </div>
        </div>
      </template>

      <el-descriptions :column="3" border>
        <el-descriptions-item label="批次编号">{{ batch.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="设备/机组编号">
          {{ batch.device_no }}
          <el-tooltip :content="ledger.nameplate ? '已录铭牌台账' : '未录铭牌台账'">
            <el-tag :type="ledger.nameplate ? 'success' : 'info'" size="small" style="margin-left: 8px">
              铭牌 {{ ledger.nameplate ? "✓" : "✗" }}
            </el-tag>
          </el-tooltip>
          <el-tooltip :content="ledger.points.length ? `已录测点字典 ${ledger.points.length} 条` : '未录测点字典'">
            <el-tag :type="ledger.points.length ? 'success' : 'info'" size="small" style="margin-left: 4px">
              测点字典 {{ ledger.points.length ? `✓(${ledger.points.length})` : "✗" }}
            </el-tag>
          </el-tooltip>
        </el-descriptions-item>
        <el-descriptions-item label="所属场站">
          {{ batch.equipment_state_type || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="涵盖模态数据">
          <template v-if="batch.modalities?.length">
            <el-tag v-for="m in batch.modalities" :key="m" size="small" style="margin-right: 4px">
              {{ MODALITY_LABELS[m] || m }}
            </el-tag>
          </template>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="设备型号">{{ batch.device_model || "-" }}</el-descriptions-item>
        <el-descriptions-item label="场站名称">{{ batch.station || "-" }}</el-descriptions-item>
        <el-descriptions-item label="许可证">{{ batch.license || "-" }}</el-descriptions-item>
        <el-descriptions-item label="敏感级别">{{ batch.sensitivity || "-" }}</el-descriptions-item>
        <el-descriptions-item label="负责人及联系方式">
          {{ batch.owner_contact || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="是否合成/仿真数据">
          {{ batch.is_synthetic ? "是" : "否" }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ batch.created_at }}</el-descriptions-item>
        <el-descriptions-item label="运行工况">{{ batch.operating_condition || "-" }}</el-descriptions-item>
        <el-descriptions-item v-if="batch.operating_condition === '故障'" label="故障发生时间">
          {{ batch.fault_time || "-" }}
        </el-descriptions-item>
        <el-descriptions-item v-if="batch.operating_condition === '故障'" label="事件描述">
          {{ batch.fault_desc || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="天气条件">{{ batch.weather || "-" }}</el-descriptions-item>
        <el-descriptions-item label="文件数 / 数据量">
          {{ batch.file_count }} 个文件
        </el-descriptions-item>
      </el-descriptions>
      <el-divider content-position="left">扩展字段</el-divider>
      <div class="extras">
        <el-row v-for="(row, i) in extrasList" :key="row.id" :gutter="8" class="extra-row">
          <el-col :span="8">
            <el-input v-model="row.key" placeholder="键名（如 采集周期）" :disabled="!canEditExtras" />
          </el-col>
          <el-col :span="14">
            <el-input v-model="row.value" placeholder="值" :disabled="!canEditExtras" />
          </el-col>
          <el-col v-if="canEditExtras" :span="2">
            <el-button text type="danger" @click="extrasList.splice(i, 1)">删除</el-button>
          </el-col>
        </el-row>
        <div v-if="!extrasList.length" class="extra-empty">-</div>
        <div v-if="canEditExtras" class="extra-actions">
          <el-button link type="primary" @click="addExtra">+ 添加扩展字段</el-button>
          <el-button type="primary" size="small" :loading="savingExtras" @click="saveExtras">
            保存扩展字段
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="card">
      <template #header><span>文件清单（F6 批次快照）</span></template>
      <FileListTable :files="store.files.items" @changed="loadFiles" />
    </el-card>

    <el-dialog v-model="editing" title="编辑批次" width="800px">
      <BatchForm v-if="editing" :model-value="batch" @submit="handleEdit">
        <div class="footer">
          <el-button @click="editing = false">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
        </div>
      </BatchForm>
    </el-dialog>
  </div>
</template>

<style scoped>
.header {
  margin-bottom: 16px;
}
.card {
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
.extra-row {
  margin-bottom: 8px;
}
.extra-empty {
  color: #909399;
  margin-bottom: 8px;
}
.extra-actions {
  margin-top: 4px;
}
</style>
