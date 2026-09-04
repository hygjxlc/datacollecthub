<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import api from "../api";
import { useBatchStore } from "../stores/batch";
import { MODALITY_LABELS } from "../stores/dict";
import PermissionWrapper from "../components/common/PermissionWrapper.vue";

// 批次列表：文件数/数据量聚合（41ec700 后端补丁）+ 按归属渲染删除（TC-PERM-002）
const store = useBatchStore();
const router = useRouter();
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);

function fmtSize(bytes) {
  if (!bytes) return "-";
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

async function load() {
  loading.value = true;
  try {
    await store.fetchList({ page: page.value, page_size: pageSize.value });
  } finally {
    loading.value = false;
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(
    `确认删除批次 ${row.batch_no}？批次下全部文件对象将一并删除。`,
    "删除确认", { type: "warning" });
  await api.delete(`/batches/${row.id}`);
  load();
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <h3>批次管理</h3>
      <div>
        <el-button @click="router.push('/batch-imports')">批量导入</el-button>
        <el-button type="primary" @click="router.push('/batches/new')">新建批次</el-button>
      </div>
    </div>

    <el-table :data="store.list" border v-loading="loading">
      <el-table-column prop="batch_no" label="批次编号" min-width="130" />
      <el-table-column prop="device_no" label="设备/机组编号" width="130" />
      <el-table-column prop="equipment_state_type" label="所属场站" width="90">
        <template #default="{ row }">{{ row.equipment_state_type || "-" }}</template>
      </el-table-column>
      <el-table-column label="涵盖模态" min-width="150">
        <template #default="{ row }">
          <template v-if="row.modalities?.length">
            <el-tag v-for="m in row.modalities" :key="m" size="small" class="mod-tag">
              {{ MODALITY_LABELS[m] || m }}
            </el-tag>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="station" label="场站名称" min-width="110" show-overflow-tooltip />
      <el-table-column prop="file_count" label="文件数" width="80" align="right" />
      <el-table-column label="数据量" width="110" align="right">
        <template #default="{ row }">{{ fmtSize(row.total_size) }}</template>
      </el-table-column>
      <el-table-column label="是否合成" width="90">
        <template #default="{ row }">{{ row.is_synthetic ? "是" : "否" }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/batches/${row.id}`)">详情</el-button>
          <el-button link type="success"
                     @click="router.push({ path: '/batches/new', query: { copy_from: row.id } })">复制新建</el-button>
          <PermissionWrapper :owner-id="row.creator_id">
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </PermissionWrapper>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="store.total"
      :page-size="pageSize"
      v-model:current-page="page"
      @current-change="load"
    />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.mod-tag {
  margin-right: 4px;
}
</style>
