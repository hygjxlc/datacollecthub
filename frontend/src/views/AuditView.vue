<script setup>
import { onMounted, reactive, ref } from "vue";
import api from "../api";

// 审计日志（架构 3.1 /audit 页面，GET /admin/audit-logs）
const rows = ref([]);
const total = ref(0);
const loading = ref(false);
const page = ref(1);
const pageSize = ref(20);

const ACTIONS = ["create", "update", "delete", "query", "download", "read"];
const SOURCES = ["web", "integration"];

const ACTION_LABELS = {
  create: "创建", update: "更新", delete: "删除",
  query: "查询", download: "下载", read: "读取",
};

const filters = reactive({ source: "", action: "" });

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get("/admin/audit-logs", {
      params: {
        page: page.value, page_size: pageSize.value,
        source: filters.source || undefined,
        action: filters.action || undefined,
      },
    });
    rows.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

function handleSearch() {
  page.value = 1;
  load();
}

onMounted(load);
</script>

<template>
  <div class="page">
    <h3 class="title">审计日志</h3>

    <el-card class="card">
      <el-form inline @submit.prevent="handleSearch">
        <el-form-item label="来源">
          <el-select v-model="filters.source" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="s in SOURCES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="filters.action" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="a in ACTIONS" :key="a" :label="ACTION_LABELS[a]" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit">查询</el-button>
          <el-button @click="filters.source = ''; filters.action = ''; handleSearch()">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column prop="username" label="操作人" width="120" />
      <el-table-column label="动作" width="90">
        <template #default="{ row }">{{ ACTION_LABELS[row.action] || row.action }}</template>
      </el-table-column>
      <el-table-column prop="entity_type" label="对象类型" width="110" />
      <el-table-column prop="entity_id" label="对象 ID" width="150" show-overflow-tooltip />
      <el-table-column prop="source" label="来源" width="110" />
      <el-table-column label="变更/参数" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.field_changes || row.params_summary || "-" }}
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="total"
      :page-size="pageSize"
      v-model:current-page="page"
      @current-change="load"
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
</style>
