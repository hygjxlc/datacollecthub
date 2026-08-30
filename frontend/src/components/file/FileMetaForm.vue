<script setup>
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { SAMPLE_PERIOD_UNITS, SAMPLE_UNIT_OPTIONS } from "../../config";

// 文件级元数据表单（F5 手动补填；国内采集时区固定 +08:00，不在表单内填写）
// 内建"复制自同批次文件"下拉：siblings 为同批次其他文件（由父组件传入）
const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  siblings: { type: Array, default: () => [] },
});
const emit = defineEmits(["submit"]);

// 采样周期拆分为数值 + 单位（存储仍为拼接字符串 "25.6kHz"，后端零改动）
function splitPeriod(value) {
  const m = /^(\d*\.?\d+)\s*(\D.*)?$/.exec(value || "");
  if (!m) return { value: value || "", unit: "" };
  return { value: m[1], unit: (m[2] || "").trim() };
}
function periodUnitOf(file) {
  return SAMPLE_PERIOD_UNITS[file && file.modality] || "";
}

const initial = splitPeriod(props.modelValue.sample_period);
const form = reactive({
  start_time: props.modelValue.start_time || "",
  end_time: props.modelValue.end_time || "",
  sample_value: initial.value,
  sample_unit: initial.unit || periodUnitOf(props.modelValue),
  data_amount: props.modelValue.data_amount || "",
  record_count: props.modelValue.record_count || "",
  duration: props.modelValue.duration || "",
});

const hasTime = computed(() => !!(form.start_time || form.end_time));

const copySource = ref(null);

// 复制源：同批次其他文件中已有元数据者（6 字段任一有值即可作为源）
const copySources = computed(() =>
  props.siblings.filter((f) =>
    f.start_time || f.end_time || f.sample_period ||
    f.data_amount || f.record_count || f.duration));

function handleCopyFrom(id) {
  const source = props.siblings.find((f) => f.id === id);
  if (!source) return;
  const sp = splitPeriod(source.sample_period);
  Object.assign(form, {
    start_time: source.start_time || "",
    end_time: source.end_time || "",
    sample_value: sp.value,
    sample_unit: sp.unit || periodUnitOf(source),
    data_amount: source.data_amount || "",
    record_count: source.record_count || "",
    duration: source.duration || "",
  });
  ElMessage.success("已填充元数据，请核对修改后保存");
}

function submit() {
  emit("submit", {
    start_time: form.start_time || null,
    end_time: form.end_time || null,
    // 国内采集时区固定 +08:00（SRS 4.4：时区缺失 = 时间不可用）
    timezone: hasTime.value ? "+08:00" : null,
    sample_period: form.sample_value ? `${form.sample_value}${form.sample_unit}` : null,
    data_amount: form.data_amount || null,
    record_count: form.record_count || null,
    duration: form.duration || null,
  });
}
</script>

<template>
  <el-form label-width="120px" @submit.prevent="submit">
    <div class="copy-from">
      <span class="copy-label">复制自同批次文件</span>
      <el-select v-model="copySource" placeholder="选择已录入元数据的文件" clearable filterable
                 style="width: 340px" no-data-text="同批次暂无已填元数据的文件"
                 @change="handleCopyFrom">
        <el-option v-for="f in copySources" :key="f.id"
                   :label="`${f.filename}（${f.start_time || '未填时间'}）`" :value="f.id" />
      </el-select>
    </div>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="采集开始时间">
          <el-date-picker v-model="form.start_time" name="start_time" type="datetime"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          placeholder="选择采集开始时间" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="采集结束时间">
          <el-date-picker v-model="form.end_time" name="end_time" type="datetime"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          placeholder="选择采集结束时间" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="采样周期">
          <el-input v-model="form.sample_value" name="sample_value" placeholder="如 25.6"
                    style="width: 140px" />
          <el-select v-model="form.sample_unit" name="sample_unit" placeholder="单位"
                     style="width: 110px; margin-left: 8px">
            <el-option v-for="u in SAMPLE_UNIT_OPTIONS" :key="u" :label="u" :value="u" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="数据量">
          <el-input v-model="form.data_amount" name="data_amount" placeholder="如 2.1 GB" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="条数">
          <el-input v-model="form.record_count" name="record_count" placeholder="如 3600 条" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="时长">
          <el-input v-model="form.duration" name="duration" placeholder="如 1h" />
        </el-form-item>
      </el-col>
    </el-row>
    <slot />
  </el-form>
</template>

<style scoped>
.copy-from {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px 120px;
}
.copy-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}
</style>
