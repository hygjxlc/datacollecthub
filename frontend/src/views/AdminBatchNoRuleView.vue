<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";

// 事件编码规则（决策 4：批次编号规则更名）：批次编码模板（batch_no）+ 事件编码模板（evt_id）双配置
// evt 模板支持 {TYPE_CODE}（=故障类型 code；正常/维修为 NORMAL/MAINT），缺省内置默认模板
const DEFAULT_EVT_TEMPLATE = "EVT_{TYPE_CODE}_{DEVICE_NO}_{YYYY}_{SEQ:3}";

const template = ref("");
const evtTemplate = ref("");
const updatedAt = ref("");
const saving = ref(false);
// 占位符按适用模板分组：{TYPE_CODE} 仅事件模板（批次模板含之会被后端 422 拒绝）
const PLACEHOLDERS = [
  { p: "{YYYY}", d: "四位年份", scope: "批次 + 事件" },
  { p: "{YY}", d: "两位年份", scope: "批次 + 事件" },
  { p: "{MM}", d: "月份（01-12）", scope: "批次 + 事件" },
  { p: "{DD}", d: "日（01-31）", scope: "批次 + 事件" },
  { p: "{SEQ:n}", d: "序号（n 位补零，必含）", scope: "批次 + 事件" },
  { p: "{DEVICE_NO}", d: "设备/机组编号", scope: "批次 + 事件" },
  { p: "{TYPE_CODE}", d: "事件类型段：故障类型 code；正常=NORMAL、维修=MAINT（事件模板必含）", scope: "仅事件" },
];

function preview(input, typeCode) {
  const now = new Date();
  const yyyy = String(now.getFullYear());
  const yy = yyyy.slice(-2);
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  return (input || "").replace(/\{YYYY\}/g, yyyy).replace(/\{YY\}/g, yy)
    .replace(/\{MM\}/g, mm).replace(/\{DD\}/g, dd)
    .replace(/\{DEVICE_NO\}/g, "F01").replace(/\{TYPE_CODE\}/g, typeCode)
    .replace(/\{SEQ:(\d+)\}/g, (_, n) => "1".padStart(Number(n), "0"));
}
const batchPreviewText = computed(() => preview(template.value, "NORMAL"));
// 事件模板未配置时按后端默认模板预览（缺省字段提示不变，交互所见即所得）
const evtPreviewText = computed(() => preview(evtTemplate.value || DEFAULT_EVT_TEMPLATE,
                                              "GEARBOX_BEARING_WEAR"));

async function load() {
  const { data } = await api.get("/admin/batch-no-rule");
  template.value = data.template || "";
  evtTemplate.value = data.evt_template || "";
  updatedAt.value = data.updated_at || "";
}
async function save() {
  saving.value = true;
  try {
    const { data } = await api.put("/admin/batch-no-rule", {
      template: template.value,
      evt_template: evtTemplate.value || null,
    });
    updatedAt.value = data.updated_at;
    ElMessage.success("事件编码规则已保存");
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="page">
    <h3>事件编码规则</h3>
    <el-card class="card">
      <el-alert type="info" show-icon :closable="false" class="tip"
                title="保存后，所有单位新建事件（批次）的编码由系统按模板自动生成，前端不可手动修改。" />
      <el-form label-width="160px">
        <el-form-item label="批次编码模板（batch_no）" required>
          <el-input v-model="template" name="batch_no_template" class="tpl-input"
                    placeholder="如 B-{YYYY}-{SEQ:3}，不可含 {TYPE_CODE}" />
        </el-form-item>
        <el-form-item label="实时预览">
          <el-tag size="large" type="success">{{ batchPreviewText || "—" }}</el-tag>
        </el-form-item>
        <el-form-item label="事件编码模板（evt_id）">
          <el-input v-model="evtTemplate" name="evt_template" class="tpl-input"
                    placeholder="留空使用默认模板 EVT_{TYPE_CODE}_{DEVICE_NO}_{YYYY}_{SEQ:3}" />
          <div class="tpl-hint">
            {TYPE_CODE}=故障类型 code（正常=NORMAL、维修=MAINT）；事件模板必含 {TYPE_CODE} 与 {SEQ:n}，
            序号按 类型段值×设备×年 独立 001 起
          </div>
        </el-form-item>
        <el-form-item label="实时预览">
          <el-tag size="large" type="success">{{ evtPreviewText || "—" }}</el-tag>
        </el-form-item>
        <el-form-item label="占位符说明">
          <el-table :data="PLACEHOLDERS" size="small" class="ph-table">
            <el-table-column prop="p" label="占位符" width="130" />
            <el-table-column prop="d" label="含义" />
            <el-table-column prop="scope" label="适用模板" width="110" />
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
.card { max-width: 760px; }
.tip { margin-bottom: 16px; }
.tpl-input { max-width: 460px; }
.tpl-hint { color: #909399; font-size: 12px; line-height: 1.6; margin-top: 4px; }
.ph-table { max-width: 640px; }
.updated { margin-left: 12px; color: #909399; font-size: 13px; }
</style>
