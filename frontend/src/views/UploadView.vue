<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useBatchStore } from "../stores/batch";
import UploadPanel from "../components/upload/UploadPanel.vue";

// 上传页：分片直传 MinIO + 断点续传（TC-UP-004），完成后回到批次详情页刷新清单
const route = useRoute();
const router = useRouter();
const store = useBatchStore();
const batchId = route.params.id;

const batch = ref(null);

async function load() {
  batch.value = await store.fetchDetail(batchId);
}

// 全部文件上传完成后回到批次详情页（文件清单随之刷新）
function onUploaded() {
  router.push(`/batches/${batchId}`);
}

onMounted(load);
</script>

<template>
  <div class="page">
    <el-page-header class="header" @back="router.push(`/batches/${batchId}`)">
      <template #content>
        <h3 v-if="batch">上传文件 — 批次 {{ batch.batch_no }}（{{ batch.device_no }}）</h3>
      </template>
    </el-page-header>

    <el-card class="card">
      <UploadPanel :batch-id="batchId" :device-no="batch?.device_no" @uploaded="onUploaded" />
    </el-card>
  </div>
</template>

<style scoped>
.header {
  margin-bottom: 16px;
}
.card {
  max-width: 800px;
}
</style>
