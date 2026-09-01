<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";

// 批次编号规则：全局单行配置，保存后新建批次编号强制自动生成
const template = ref("");
const updatedAt = ref("");
const saving = ref(false);
const PLACEHOLDERS = [
  { p: "{YYYY}", d: "四位年份" }, { p: "{YY}", d: "两位年份" },
  { p: "{MM}", d: "月份（01-12）" }, { p: "{DD}", d: "日（01-31）" },
  { p: "{SEQ:n}", d: "序号（n 位补零，必含）" }, { p: "{DEVICE_NO}", d: "设备/机组编号" },
];

function preview(input) {
  return (input || "").replace(/\{YYYY\}/g, "2026").replace(/\{YY\}/g, "26")
    .replace(/\{MM\}/g, "09").replace(/\{DD\}/g, "01")
    .replace(/\{DEVICE_NO\}/g, "F01")
    .replace(/\{SEQ:(\d+)\}/g, (_, n) => "1".padStart(Number(n), "0"));
}
const previewText = computed(() => preview(template.value));

async function load() {
  const { data } = await api.get("/admin/batch-no-rule");
  template.value = data.template || "";
  updatedAt.value = data.updated_at || "";
}
async function save() {
  saving.value = true;
  try {
    const { data } = await api.put("/admin/batch-no-rule", { template: template.value });
    updatedAt.value = data.updated_at;
    ElMessage.success("批次编号规则已保存");
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="page">
    <h3>批次编号规则</h3>
    <el-card class="card">
      <el-alert type="info" show-icon :closable="false" class="tip"
                title="保存后，所有单位新建批次的编号由系统按模板自动生成，前端不可手动修改。" />
      <el-form label-width="120px">
        <el-form-item label="编号模板" required>
          <el-input v-model="template" name="batch_no_template" class="tpl-input"
                    placeholder="如 B-{YYYY}-{SEQ:3}" />
        </el-form-item>
        <el-form-item label="实时预览">
          <el-tag size="large" type="success">{{ previewText || "—" }}</el-tag>
        </el-form-item>
        <el-form-item label="占位符说明">
          <el-table :data="PLACEHOLDERS" size="small" class="ph-table">
            <el-table-column prop="p" label="占位符" width="150" />
            <el-table-column prop="d" label="含义" />
          </el-table>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存规则</el-button>
          <span v-if="updatedAt" class="updated">最近修改：{{ updatedAt }}</span>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.card { max-width: 720px; }
.tip { margin-bottom: 16px; }
.tpl-input { max-width: 360px; }
.ph-table { max-width: 480px; }
.updated { margin-left: 12px; color: #909399; font-size: 13px; }
</style>
