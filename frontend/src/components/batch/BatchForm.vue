<script setup>
import { reactive } from "vue";
import { ElMessage } from "element-plus";
import { EQUIPMENT_STATE_TYPES, LICENSES, SENSITIVITIES } from "../../stores/dict";

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
  operating_condition: props.modelValue.operating_condition || "",
  weather: props.modelValue.weather || "",
  equipment_state_type: props.modelValue.equipment_state_type || "",
});

function submit() {
  if (!form.batch_no || !form.device_no) return;
  if (props.requireStateType && !form.equipment_state_type) {
    ElMessage.warning("请选择 数据对应设备:状态类型");
    return;
  }
  const payload = { ...form };
  payload.equipment_state_type = payload.equipment_state_type || null;
  emit("update:modelValue", payload);
  emit("submit", payload);
}
</script>

<template>
  <el-form label-width="130px" @submit.prevent="submit">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="批次编号" required>
          <el-input v-model="form.batch_no" name="batch_no" placeholder="如 B2025-001" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="设备/机组编号" required>
          <el-input v-model="form.device_no" name="device_no" placeholder="如 F01" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="数据对应设备:状态类型" :required="requireStateType">
          <el-select v-model="form.equipment_state_type" name="equipment_state_type"
                     placeholder="风电/火电/光伏">
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
        <el-form-item label="所属场站">
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
          <el-input v-model="form.operating_condition" name="operating_condition"
                    placeholder="正常/故障/检修" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="天气条件">
          <el-input v-model="form.weather" name="weather" placeholder="如 晴，风速 8m/s" />
        </el-form-item>
      </el-col>
    </el-row>
    <slot />
  </el-form>
</template>
