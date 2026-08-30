<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../../api";

// 铭牌台账：每设备一条，参数供物理规则库校验规则标定
const loading = ref(false);
const rows = ref([]);
const dialogVisible = ref(false);
const saving = ref(false);
const editingId = ref(null);

const emptyForm = () => ({
  device_no: "", device_model: "", rated_power: null, rated_wind_speed: null,
  rotor_diameter: null, hub_height: null, bearing_model: "", gearbox_ratio: null,
  generator_model: "", manufacturer: "", commission_date: "",
  design_life_years: null, extras_text: "{}",
});
const form = reactive(emptyForm());

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get("/nameplates");
    rows.value = data.items;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.keys(form).forEach((k) => delete form[k]);
  Object.assign(form, emptyForm());
  editingId.value = null;
  dialogVisible.value = true;
}

function openEdit(row) {
  Object.assign(form, emptyForm(), {
    device_no: row.device_no, device_model: row.device_model,
    rated_power: row.rated_power, rated_wind_speed: row.rated_wind_speed,
    rotor_diameter: row.rotor_diameter, hub_height: row.hub_height,
    bearing_model: row.bearing_model, gearbox_ratio: row.gearbox_ratio,
    generator_model: row.generator_model, manufacturer: row.manufacturer,
    commission_date: row.commission_date,
    design_life_years: row.design_life_years,
    extras_text: row.extras ? JSON.stringify(row.extras, null, 2) : "{}",
  });
  editingId.value = row.id;
  dialogVisible.value = true;
}

async function submit() {
  let extras;
  try {
    extras = JSON.parse(form.extras_text || "{}");
  } catch {
    ElMessage.error("其他参数不是合法 JSON，请修正后再保存");
    return;
  }
  const payload = { ...form, extras };
  delete payload.extras_text;
  saving.value = true;
  try {
    if (editingId.value) {
      await api.put(`/nameplates/${editingId.value}`, payload);
      ElMessage.success("铭牌已更新");
    } else {
      await api.post("/nameplates", payload);
      ElMessage.success("铭牌已创建");
    }
    dialogVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除设备 ${row.device_no} 的铭牌台账？`,
    "删除确认", { type: "warning" });
  await api.delete(`/nameplates/${row.id}`);
  ElMessage.success("铭牌已删除");
  load();
}

onMounted(load);
</script>

<template>
  <div>
    <el-alert type="info" :closable="false" show-icon class="tip"
              title="设备编号需与批次/文件中 device_no 一致；铭牌参数供物理规则库校验规则标定。" />
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增铭牌</el-button>
    </div>
    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="device_no" label="设备编号" width="110" />
      <el-table-column prop="device_model" label="型号" min-width="150" show-overflow-tooltip />
      <el-table-column label="额定功率(kW)" width="120">
        <template #default="{ row }">{{ row.rated_power ?? "-" }}</template>
      </el-table-column>
      <el-table-column label="转子直径(m)" width="120">
        <template #default="{ row }">{{ row.rotor_diameter ?? "-" }}</template>
      </el-table-column>
      <el-table-column prop="commission_date" label="投运日期" width="110" />
      <el-table-column label="创建者" width="100">
        <template #default="{ row }">{{ row.creator_name || "-" }}</template>
      </el-table-column>
      <el-table-column prop="manufacturer" label="制造商" width="130" show-overflow-tooltip />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑铭牌' : '新增铭牌'" width="720px">
      <el-form label-width="120px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="设备编号" required>
              <el-input v-model="form.device_no" name="device_no" placeholder="如 F01" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备型号">
              <el-input v-model="form.device_model" name="device_model" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="额定功率(kW)">
              <el-input-number v-model="form.rated_power" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="额定风速(m/s)">
              <el-input-number v-model="form.rated_wind_speed" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="转子直径(m)">
              <el-input-number v-model="form.rotor_diameter" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="轮毂高度(m)">
              <el-input-number v-model="form.hub_height" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="轴承型号">
              <el-input v-model="form.bearing_model" name="bearing_model" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="齿轮箱速比">
              <el-input-number v-model="form.gearbox_ratio" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发电机型号">
              <el-input v-model="form.generator_model" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="制造商">
              <el-input v-model="form.manufacturer" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="投运日期">
              <el-date-picker v-model="form.commission_date" type="date"
                              value-format="YYYY-MM-DD" style="width: 100%"
                              placeholder="选择投运日期" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设计寿命(年)">
              <el-input-number v-model="form.design_life_years" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="其他参数(JSON)">
              <el-input v-model="form.extras_text" type="textarea" :rows="3"
                        placeholder='如 {"机型": "GW82/1500"}' />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tip {
  margin-bottom: 12px;
}
.toolbar {
  margin-bottom: 8px;
}
</style>
