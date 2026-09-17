<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  EQUIPMENT_STATE_TYPES,
  EVENT_TYPES,
  LICENSES,
  SENSITIVITIES,
  SEVERITY_VALUES,
} from "../../stores/dict";
import api from "../../api";

// 批次说明表表单（《数据收集要求清单》6.1）：基本信息 + 事件组申报区 + 扩展字段
// 事件组三态主轴（设计 §3.1/§6.1 决策 5）：event_type 取代"运行工况"下拉，故障联动轴一轴化
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
  event_type: props.modelValue.event_type || "正常",   // 三态必填，UI 默认"正常"
  fault_type: props.modelValue.fault_type || "",
  severity: props.modelValue.severity || "",
  t_start: props.modelValue.t_start || "",
  t_end: props.modelValue.t_end || "",
  fault_time: props.modelValue.fault_time || "",
  fault_desc: props.modelValue.fault_desc || "",
  weather: props.modelValue.weather || "",
  equipment_state_type: props.modelValue.equipment_state_type || "",
});

// 设备台账下拉（设计 §2.6）：数据源 = /nameplates（可检索）；存量设备号不在台账
// 可见列表时保留一项兜底回显（升级前普通用户自建台账/单位外可见性）
const deviceOptions = ref([]);
const deviceLoading = ref(false);
async function loadDevices() {
  deviceLoading.value = true;
  try {
    const { data } = await api.get("/nameplates", { params: { page_size: 500 } });
    const rows = data.items || [];
    const known = new Set(rows.map((r) => r.device_no));
    if (form.device_no && !known.has(form.device_no)) {
      rows.unshift({ device_no: form.device_no, device_model: "" });   // 存量回显项
    }
    deviceOptions.value = rows;
  } catch { /* 台账读取失败保持可检索空列表（拦截器已提示） */ }
  finally {
    deviceLoading.value = false;
  }
}
function onDeviceChange(no) {
  const row = deviceOptions.value.find((r) => r.device_no === no);
  if (row?.device_model) form.device_model = row.device_model;   // 台账铭牌带出型号
}

// 故障类型字典下拉（公共只读接口仅返回激活行；UNCLASSIFIED 种子随行返回）
const faultOptions = ref([]);
async function loadFaultTypes() {
  try {
    const { data } = await api.get("/fault-types");
    faultOptions.value = data.items || [];
  } catch { /* 故障类型读取失败：不阻断提交（缺省 UNCLASSIFIED，后端兜底） */ }
}

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

// 故障分支的 fault_type 中文名映射（下拉显示 name、提交 code）
const faultTypeLabel = computed(() => {
  const hit = faultOptions.value.find((r) => r.code === form.fault_type);
  return hit ? `${hit.name}（${hit.code}）` : form.fault_type || "";
});
// 故障描述占位文案随态变化：故障=事件描述/维修=维修内容/正常=基线说明（§3.1 规则 3/4）
const faultDescPlaceholder = computed(
  () => ({
    故障: "描述故障事件（如：齿轮箱轴承温度超限，触发报警停机）",
    维修: "维修内容（如：更换齿轮箱轴承）",
    正常: "基线说明（可选，如：正常巡检、机组状态良好）",
  })[form.event_type]
);

// 批次编号是否由系统按规则自动生成（管理员配置后前端只读）
const autoBatchNo = ref(false);
onMounted(async () => {
  try {
    const { data } = await api.get("/batch-no-rule");
    autoBatchNo.value = !!data.template;
  } catch { /* 读取失败保持手动模式（拦截器已提示） */ }
  await Promise.allSettled([loadDevices(), loadFaultTypes()]);
});

function submit() {
  if (!autoBatchNo.value && !form.batch_no) return;
  if (!form.device_no) return;
  if (props.requireStateType && !form.equipment_state_type) {
    ElMessage.warning("请选择 所属场站");
    return;
  }
  if (form.event_type === "故障") {
    if (!form.fault_time) {
      ElMessage.warning("事件类型为故障时，请填写事件时刻（申报）");
      return;
    }
    if (!(form.fault_desc || "").trim()) {
      ElMessage.warning("事件类型为故障时，请填写事件描述（申报）");
      return;
    }
  }
  if (!!form.t_start !== !!form.t_end) {
    ElMessage.warning("异常区间开始/结束时间须成对填写");
    return;
  }
  if (form.t_start && form.t_end && form.t_start > form.t_end) {
    ElMessage.warning("异常区间开始时间不能晚于结束时间");
    return;
  }
  const payload = { ...form };
  payload.equipment_state_type = payload.equipment_state_type || null;
  payload.fault_desc = (payload.fault_desc || "").trim() || null;
  if (payload.event_type === "故障") {
    payload.fault_type = payload.fault_type || null;   // 空=UNCLASSIFIED（待分类）
    payload.severity = payload.severity || null;       // 空=按故障类型字典默认严重度
    payload.fault_time = payload.fault_time || null;
  } else {
    // 维修/正常：故障专属字段清空（后端同样强制，§3.1 规则 3/4）
    payload.fault_type = payload.severity = payload.fault_time = null;
  }
  payload.t_start = payload.t_start || null;
  payload.t_end = payload.t_end || null;
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
    <el-divider content-position="left">基本信息</el-divider>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="批次编号" :required="!autoBatchNo">
          <el-input v-model="form.batch_no" name="batch_no" :disabled="autoBatchNo"
                    :placeholder="autoBatchNo ? '由系统按编号规则自动生成' : '如 B2025-001'" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="设备/机组编号" required>
          <el-select v-model="form.device_no" name="device_no" filterable
                     :loading="deviceLoading" placeholder="从设备台账选择（可检索）"
                     style="width: 100%" @change="onDeviceChange">
            <el-option v-for="d in deviceOptions" :key="d.device_no"
                       :label="d.device_no" :value="d.device_no" />
          </el-select>
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
        <el-form-item label="天气条件">
          <el-input v-model="form.weather" name="weather" placeholder="如 晴，风速 8m/s" />
        </el-form-item>
      </el-col>
    </el-row>

    <el-divider content-position="left">事件组申报</el-divider>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="事件类型" required>
          <el-radio-group v-model="form.event_type" name="event_type">
            <el-radio-button v-for="t in EVENT_TYPES" :key="t" :value="t">{{ t }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-col>
      <template v-if="form.event_type === '故障'">
        <el-col :span="12">
          <el-form-item label="故障类型">
            <el-select v-model="form.fault_type" name="fault_type" filterable clearable
                       placeholder="不选=待分类（UNCLASSIFIED）" style="width: 100%">
              <el-option v-for="f in faultOptions" :key="f.code" :label="f.name" :value="f.code">
                <span>{{ f.name }}</span>
                <span class="opt-code">{{ f.code }}</span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="严重度">
            <el-select v-model="form.severity" name="severity" clearable
                       placeholder="不选=按故障类型默认" style="width: 100%">
              <el-option v-for="s in SEVERITY_VALUES" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="事件时刻（申报）" required>
            <el-date-picker v-model="form.fault_time" name="fault_time" type="datetime"
                            value-format="YYYY-MM-DD HH:mm:ss" placeholder="选择事件时刻（故障发生时间）"
                            style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="事件描述（申报）" required>
            <el-input v-model="form.fault_desc" name="fault_desc" type="textarea" :rows="2"
                      :placeholder="faultDescPlaceholder" />
          </el-form-item>
        </el-col>
      </template>
      <template v-else>
        <el-col :span="24">
          <el-form-item :label="form.event_type === '维修' ? '维修内容' : '基线说明'">
            <el-input v-model="form.fault_desc" name="fault_desc" type="textarea" :rows="2"
                      :placeholder="faultDescPlaceholder" />
          </el-form-item>
        </el-col>
      </template>
      <el-col :span="12">
        <el-form-item label="异常区间开始">
          <el-date-picker v-model="form.t_start" name="t_start" type="datetime"
                          value-format="YYYY-MM-DD HH:mm:ss" placeholder="开始时间（可选，成对填写）"
                          style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="异常区间结束">
          <el-date-picker v-model="form.t_end" name="t_end" type="datetime"
                          value-format="YYYY-MM-DD HH:mm:ss" placeholder="结束时间（可选，成对填写）"
                          style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col v-if="form.event_type === '故障' && form.fault_type" :span="24">
        <div class="evt-tip">
          故障类型 code：{{ form.fault_type }}（{{ faultTypeLabel }}），将进入事件编号（EVT_ID）类型段
        </div>
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

<style scoped>
.opt-code {
  float: right;
  color: #909399;
  font-size: 12px;
}
.evt-tip {
  padding: 0 8px;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
</style>
