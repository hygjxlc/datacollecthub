<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../../api";

// 测点字典：SCADA 通道号 → 物理量/单位/缩放系数（physical = raw * slope + offset）
const loading = ref(false);
const deviceNos = ref([]);
const currentDevice = ref("");
const rows = ref([]);
const dialogVisible = ref(false);
const saving = ref(false);
const editingId = ref(null);

const emptyForm = () => ({
  device_no: "", channel_no: "", name: "", unit: "", scale_slope: null,
  scale_offset: null, data_type: "", range_min: null, range_max: null,
  description: "",
});
const form = reactive(emptyForm());

const filteredRows = computed(() =>
  currentDevice.value
    ? rows.value.filter((r) => r.device_no === currentDevice.value)
    : rows.value);

async function loadDevices() {
  const { data } = await api.get("/point-dicts/device-nos");
  deviceNos.value = data.items;
  if (!currentDevice.value && data.items.length) currentDevice.value = data.items[0];
}

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get("/point-dicts");
    rows.value = data.items;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.keys(form).forEach((k) => delete form[k]);
  Object.assign(form, emptyForm(), { device_no: currentDevice.value });
  editingId.value = null;
  dialogVisible.value = true;
}

function openEdit(row) {
  Object.assign(form, emptyForm(), {
    device_no: row.device_no, channel_no: row.channel_no, name: row.name,
    unit: row.unit, scale_slope: row.scale_slope,
    scale_offset: row.scale_offset, data_type: row.data_type,
    range_min: row.range_min, range_max: row.range_max,
    description: row.description,
  });
  editingId.value = row.id;
  dialogVisible.value = true;
}

async function submit() {
  saving.value = true;
  try {
    if (editingId.value) {
      await api.put(`/point-dicts/${editingId.value}`, form);
      ElMessage.success("测点已更新");
    } else {
      await api.post("/point-dicts", form);
      ElMessage.success("测点已创建");
    }
    dialogVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除通道 ${row.channel_no} 的测点定义？`,
    "删除确认", { type: "warning" });
  await api.delete(`/point-dicts/${row.id}`);
  ElMessage.success("测点已删除");
  load();
}

onMounted(async () => {
  await loadDevices();
  await load();
});
</script>

<template>
  <div>
    <div class="toolbar">
      <el-select v-model="currentDevice" placeholder="选择设备" style="width: 180px">
        <el-option v-for="d in deviceNos" :key="d" :label="d" :value="d" />
      </el-select>
      <el-button type="primary" :disabled="!currentDevice" @click="openCreate">新增测点</el-button>
    </div>
    <el-table :data="filteredRows" border v-loading="loading">
      <el-table-column prop="device_no" label="设备编号" width="100" />
      <el-table-column prop="channel_no" label="通道号" width="120" />
      <el-table-column prop="name" label="物理量" min-width="150" show-overflow-tooltip />
      <el-table-column prop="unit" label="单位" width="80" />
      <el-table-column prop="scale_slope" label="slope" width="90" />
      <el-table-column prop="scale_offset" label="offset" width="90" />
      <el-table-column prop="data_type" label="数据类型" width="100" />
      <el-table-column label="创建者" width="100">
        <template #default="{ row }">{{ row.creator_name || "-" }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑测点' : '新增测点'" width="640px">
      <el-form label-width="110px">
        <el-form-item label="设备编号" required>
          <el-select v-model="form.device_no" style="width: 100%">
            <el-option v-for="d in deviceNos" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="通道号" required>
          <el-input v-model="form.channel_no" name="channel_no" placeholder="如 CH1" />
        </el-form-item>
        <el-form-item label="物理量名称" required>
          <el-input v-model="form.name" name="pd_name" placeholder="如 齿轮箱轴承温度" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" name="unit" placeholder="℃/kW/rpm" />
        </el-form-item>
        <el-form-item label="slope">
          <el-input-number v-model="form.scale_slope" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="offset">
          <el-input-number v-model="form.scale_offset" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="数据类型">
          <el-select v-model="form.data_type" clearable style="width: 100%">
            <el-option v-for="t in ['float', 'int', 'string', 'boolean']"
                       :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="量程 min">
          <el-input-number v-model="form.range_min" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="量程 max">
          <el-input-number v-model="form.range_max" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
</style>
