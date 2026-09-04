<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  EQUIPMENT_STATE_TYPES,
  LICENSES,
  OPERATING_CONDITION_TYPES,
  SENSITIVITIES,
} from "../../stores/dict";
import api from "../../api";

// 批次说明表表单（《数据收集要求清单》6.1 字段）
const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  requireStateType: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue", "submit"]);

const form = reactive({
  batch_no: props.modelValue.batch_no || "",
  device_no: props.modelValue.device_no || "",
  device_model: props.modelValue.device_model || "",
  station: props.modelValue.station || "",
  license: props.modelValue.license || "内部专用",
  sensitivity: props.modelValue.sensitivity || "内部",
  owner_contact: props.modelValue.owner_contact || "",
  is_synthetic: props.modelValue.is_synthetic ?? 0,
  operating_condition: props.modelValue.operating_condition || "正常",
  fault_time: props.modelValue.fault_time || "",
  fault_desc: props.modelValue.fault_desc || "",
  weather: props.modelValue.weather || "",
  equipment_state_type: props.modelValue.equipment_state_type || "",
});

// 运行工况下拉：存量自由文本（如 正常，风速 8m/s）不在枚举内时保留一项可回显
const conditionOptions = computed(() => {
  const options = [...OPERATING_CONDITION_TYPES];
  const cur = form.operating_condition;
  if (cur && !OPERATING_CONDITION_TYPES.includes(cur)) options.push(cur);
  return options;
});

// 扩展字段动态键值对（每行稳定 id，供 v-for key）
let extrasSeq = 0;
const extrasList = reactive(
  Object.entries(props.modelValue.extras || {}).map(([key, value]) => ({
    id: extrasSeq++,
    key, value: String(value ?? ""),
  }))
);
function addExtra() {
  extrasList.push({ id: extrasSeq++, key: "", value: "" });
}
function removeExtra(index) {
  extrasList.splice(index, 1);
}

// 批次编号是否由系统按规则自动生成（管理员配置后前端只读）
const autoBatchNo = ref(false);
onMounted(async () => {
  try {
    const { data } = await api.get("/batch-no-rule");
    autoBatchNo.value = !!data.template;
  } catch { /* 读取失败保持手动模式（拦截器已提示） */ }
});

function submit() {
  if (!autoBatchNo.value && !form.batch_no) return;
  if (!form.device_no) return;
  if (props.requireStateType && !form.equipment_state_type) {
    ElMessage.warning("请选择 所属场站");
    return;
  }
  if (form.operating_condition === "故障") {
    if (!form.fault_time) {
      ElMessage.warning("运行工况为故障时，请填写故障发生时间");
      return;
    }
    if (!(form.fault_desc || "").trim()) {
      ElMessage.warning("运行工况为故障时，请填写事件描述");
      return;
    }
  }
  const payload = { ...form };
  payload.equipment_state_type = payload.equipment_state_type || null;
  // 故障联动：非故障工况不带故障信息（后端同样强制清理）
  if (payload.operating_condition !== "故障") {
    payload.fault_time = null;
    payload.fault_desc = null;
  } else {
    payload.fault_time = payload.fault_time || null;
    payload.fault_desc = (payload.fault_desc || "").trim() || null;
  }
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
  payload.extras = Object.keys(extras).length ? extras : null;
  if (autoBatchNo.value) delete payload.batch_no;
  emit("update:modelValue", payload);
  emit("submit", payload);
}
</script>

<template>
  <el-form label-width="130px" @submit.prevent="submit">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="批次编号" :required="!autoBatchNo">
          <el-input v-model="form.batch_no" name="batch_no" :disabled="autoBatchNo"
                    :placeholder="autoBatchNo ? '由系统按编号规则自动生成' : '如 B2025-001'" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="设备/机组编号" required>
          <el-input v-model="form.device_no" name="device_no" placeholder="如 F01" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="所属场站" :required="requireStateType">
          <el-select v-model="form.equipment_state_type" name="equipment_state_type"
                     placeholder="风电/光伏/火电/其它">
            <el-option v-for="t in EQUIPMENT_STATE_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="设备型号">
          <el-input v-model="form.device_model" name="device_model" placeholder="如 金风 GW82/1500" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="场站名称">
          <el-input v-model="form.station" name="station" placeholder="场站名（object_key 段）" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="许可证">
          <el-select v-model="form.license" name="license">
            <el-option v-for="l in LICENSES" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="敏感级别">
          <el-select v-model="form.sensitivity" name="sensitivity">
            <el-option v-for="s in SENSITIVITIES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="负责人及联系方式">
          <el-input v-model="form.owner_contact" name="owner_contact" placeholder="如 张工 138****" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="是否合成/仿真数据">
          <el-switch v-model="form.is_synthetic" :active-value="1" :inactive-value="0"
                     active-text="是" inactive-text="否" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="运行工况">
          <el-select v-model="form.operating_condition" name="operating_condition">
            <el-option v-for="c in conditionOptions" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
      </el-col>
      <template v-if="form.operating_condition === '故障'">
        <el-col :span="12">
          <el-form-item label="故障发生时间" required>
            <el-date-picker v-model="form.fault_time" name="fault_time" type="datetime"
                            value-format="YYYY-MM-DD HH:mm:ss" placeholder="选择故障发生时间"
                            style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="事件描述" required>
            <el-input v-model="form.fault_desc" name="fault_desc" type="textarea" :rows="2"
                      placeholder="描述故障事件（如：齿轮箱轴承温度超限，触发报警停机）" />
          </el-form-item>
        </el-col>
      </template>
      <el-col :span="12">
        <el-form-item label="天气条件">
          <el-input v-model="form.weather" name="weather" placeholder="如 晴，风速 8m/s" />
        </el-form-item>
      </el-col>
    </el-row>
    <el-divider content-position="left">扩展字段（可选，下载元数据 JSON 一并导出）</el-divider>
    <el-row v-for="(row, i) in extrasList" :key="row.id" :gutter="8">
      <el-col :span="9">
        <el-input v-model="row.key" placeholder="键名（如 采集周期）" />
      </el-col>
      <el-col :span="13">
        <el-input v-model="row.value" placeholder="值" />
      </el-col>
      <el-col :span="2">
        <el-button text type="danger" @click="removeExtra(i)">删除</el-button>
      </el-col>
    </el-row>
    <el-button link type="primary" @click="addExtra">+ 添加扩展字段</el-button>
    <slot />
  </el-form>
</template>
