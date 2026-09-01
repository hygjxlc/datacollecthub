<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import api from "../api";
import BatchForm from "../components/batch/BatchForm.vue";

// 新建批次：批次说明表 10 字段（《数据收集要求清单》6.1）
// 复制新建（?copy_from=<批次id>）：预填除 batch_no 外全部字段，batch_no 必须新编号
const router = useRouter();
const route = useRoute();
const saving = ref(false);
const loading = ref(false);
const source = ref(null);
const sourceLabel = ref("");
const copyFromId = route.query.copy_from;

onMounted(async () => {
  if (!copyFromId) return;
  loading.value = true;
  try {
    const { data } = await api.get(`/batches/${copyFromId}`);
    sourceLabel.value = data.batch_no;
    source.value = { ...data, batch_no: "" };
  } catch {
    ElMessage.warning("复制源不存在或不可访问，请手工填写");
  } finally {
    loading.value = false;
  }
});

async function handleSubmit(payload) {
  saving.value = true;
  try {
    const { data } = await api.post("/batches", payload);
    ElMessage.success(`批次 ${data.batch_no} 创建成功`);
    router.push(`/batches/${data.id}`);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="page">
    <el-page-header class="header" @back="router.push('/batches')">
      <template #content><h3>新建批次</h3></template>
    </el-page-header>

    <el-card class="card" v-loading="loading">
      <el-alert v-if="sourceLabel" type="info" show-icon :closable="false" class="copy-tip"
                :title="`已从批次 ${sourceLabel} 复制（批次编号除外），请修改后提交`" />
      <BatchForm v-if="!loading" :model-value="source || {}" require-state-type
                 @submit="handleSubmit">
        <div class="footer">
          <el-button @click="router.push('/batches')">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">创建批次</el-button>
        </div>
      </BatchForm>
    </el-card>
  </div>
</template>

<style scoped>
.header {
  margin-bottom: 16px;
}
.copy-tip {
  margin-bottom: 16px;
}
.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
