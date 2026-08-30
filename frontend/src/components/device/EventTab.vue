<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../../api";

// 事件记录：多模态事件组数据集锚点，级别中文枚举 + 关联文件多选
const loading = ref(false);
const rows = ref([]);
const dialogVisible = ref(false);
const saving = ref(false);
const editingId = ref(null);
const deviceNos = ref([]);
const deviceFiles = ref([]);

const filters = reactive({ device_no: "", severity: "", timeRange: null });
const SEVERITIES = ["报警", "故障", "事故"];
const SEVERITY_TAG = { "报警": "warning", "故障": "danger", "事故": "danger" };

const emptyForm = () => ({
  event_time: "", timezone: "+08:00", device_no: "", event_type: "",
  severity: "报警", description: "", related_file_ids: [],
  root_cause: "", treatment: "", treatment_result: "", operating_condition: "",
});
const form = reactive(emptyForm());

async function loadDevices() {
  try {
    const { data } = await api.get("/point-dicts/device-nos");
    deviceNos.value = data.items;
  } catch { /* 设备列表加载失败不阻断 */ }
}

async function load() {
  loading.value = true;
  try {
    const params = {
      device_no: filters.device_no || undefined,
      severity: filters.severity || undefined,
      start: filters.timeRange?.[0] || undefined,
      end: filters.timeRange?.[1] || undefined,
    };
    const { data } = await api.get("/events", { params });
    rows.value = data.items;
  } finally {
    loading.value = false;
  }
}

async function loadFiles(deviceNo) {
  deviceFiles.value = [];
  if (!deviceNo) return;
  try {
    const { data } = await api.get("/files",
      { params: { device_no: deviceNo, page: 1, page_size: 100 } });
    deviceFiles.value = data.items;
  } catch { /* 文件列表加载失败不阻断 */ }
}

function openCreate() {
  Object.keys(form).forEach((k) => delete form[k]);
  Object.assign(form, emptyForm());
  editingId.value = null;
  dialogVisible.value = true;
}

function openEdit(row) {
  Object.assign(form, emptyForm(), {
    event_time: row.event_time, timezone: row.timezone,
    device_no: row.device_no, event_type: row.event_type,
    severity: row.severity, description: row.description,
    related_file_ids: row.related_files || [],
    root_cause: row.root_cause || "", treatment: row.treatment || "",
    treatment_result: row.treatment_result || "",
    operating_condition: row.operating_condition || "",
  });
  editingId.value = row.id;
  dialogVisible.value = true;
}

async function submit() {
  const payload = { ...form, related_file_ids: form.related_file_ids || [] };
  saving.value = true;
  try {
    if (editingId.value) {
      await api.put(`/events/${editingId.value}`, payload);
      ElMessage.success("事件已更新");
    } else {
      await api.post("/events", payload);
      ElMessage.success("事件已创建");
    }
    dialogVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除事件「${row.event_type}」？关联关系将一并删除。`,
    "删除确认", { type: "warning" });
  await api.delete(`/events/${row.id}`);
  ElMessage.success("事件已删除");
  load();
}

watch(() => form.device_no, loadFiles);
onMounted(async () => {
  await loadDevices();
  await load();
});
</script>

<template>
  <div>
    <el-card class="card">
      <el-form inline @submit.prevent="load()">
        <el-form-item label="设备">
          <el-select v-model="filters.device_no" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="d in deviceNos" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="级别">
          <el-select v-model="filters.severity" clearable placeholder="全部" style="width: 110px">
            <el-option v-for="s in SEVERITIES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker v-model="filters.timeRange" type="datetimerange"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          start-placeholder="开始时间" end-placeholder="结束时间" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit">查询</el-button>
          <el-button @click="Object.assign(filters, { device_no: '', severity: '', timeRange: null }); load()">
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增事件</el-button>
    </div>
    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="event_time" label="事件时间" width="170" />
      <el-table-column prop="device_no" label="设备" width="90" />
      <el-table-column prop="event_type" label="事件类型" min-width="150" show-overflow-tooltip />
      <el-table-column label="级别" width="90">
        <template #default="{ row }">
          <el-tag :type="SEVERITY_TAG[row.severity] || 'info'" size="small">
            {{ row.severity }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column prop="root_cause" label="根因分析" min-width="140" show-overflow-tooltip />
      <el-table-column prop="treatment" label="处置措施" min-width="140" show-overflow-tooltip />
      <el-table-column prop="related_file_count" label="关联文件数" width="100" align="center" />
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑事件' : '新增事件'" width="640px">
      <el-form label-width="110px">
        <el-form-item label="设备编号" required>
          <el-select v-model="form.device_no" name="ev_device_no" filterable allow-create
                     style="width: 100%" placeholder="选择或输入设备编号">
            <el-option v-for="d in deviceNos" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="事件时间" required>
          <el-date-picker v-model="form.event_time" name="event_time" type="datetime"
                          value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%"
                          placeholder="选择日期时间" />
        </el-form-item>
        <el-form-item label="事件类型" required>
          <el-input v-model="form.event_type" name="event_type"
                    placeholder="层级字符串，如 齿轮箱/轴承/磨损" />
        </el-form-item>
        <el-form-item label="级别" required>
          <el-select v-model="form.severity" name="ev_form_severity" style="width: 100%">
            <el-option v-for="s in SEVERITIES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="事件描述">
          <el-input v-model="form.description" name="ev_description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="根因分析">
          <el-input v-model="form.root_cause" type="textarea" :rows="2"
                    placeholder="如：高速轴轴承润滑脂老化干磨，温升持续 15 分钟" />
        </el-form-item>
        <el-form-item label="处置措施">
          <el-input v-model="form.treatment" type="textarea" :rows="2"
                    placeholder="如：停机组 → 更换 SKF-32222 轴承 → 重新对中" />
        </el-form-item>
        <el-form-item label="处置效果">
          <el-input v-model="form.treatment_result" type="textarea" :rows="2"
                    placeholder="如：更换后 24h 温升恢复正常，振动 RMS 回落至 1.2mm/s" />
        </el-form-item>
        <el-form-item label="工况环境">
          <el-input v-model="form.operating_condition" type="textarea" :rows="2"
                    placeholder="如：满发工况，环境温度 32℃，风速 8.5m/s" />
        </el-form-item>
        <el-form-item label="关联文件">
          <el-select v-model="form.related_file_ids" name="related_files" multiple filterable
                     style="width: 100%" placeholder="选择该设备已上传文件（可搜索）">
            <el-option v-for="f in deviceFiles" :key="f.id" :label="f.filename" :value="f.id" />
          </el-select>
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
.card {
  margin-bottom: 12px;
}
.toolbar {
  margin-bottom: 8px;
}
</style>
