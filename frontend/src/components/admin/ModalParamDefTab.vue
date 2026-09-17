<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../../api";

// 模态参数 Schema 字典 Tab（Phase 0 §2.2）：全局共享；键名发布后不可改名（渲染器按名读取）
const rows = ref([]);
const loading = ref(false);
const dialog = ref(false);
const editingId = ref("");
const saving = ref(false);

const MODALITIES = [
  { value: "SCADA", label: "工艺参数" }, { value: "VIB", label: "振动信号" },
  { value: "AUD", label: "声纹/音频" }, { value: "IR", label: "红外热像" },
  { value: "CAM", label: "可见光照片" }, { value: "VID", label: "视频" },
  { value: "TXT", label: "文本" }, { value: "RPT", label: "报表" },
];
const MODALITY_LABELS = Object.fromEntries(MODALITIES.map((m) => [m.value, m.label]));
const VALUE_TYPES = ["float", "int", "str", "bool", "json"];
const REQUIRED_OPTS = [
  { v: 0, label: "可选" }, { v: 1, label: "必填" }, { v: 2, label: "条件必填" },
];
const REQUIRED_LABELS = Object.fromEntries(REQUIRED_OPTS.map((o) => [o.v, o.label]));

const form = reactive({
  modality: "IR", param_key: "", label: "", unit: "", value_type: "float",
  required: 0, min_value: null, max_value: null, description: "",
});

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get("/modal-params");
    rows.value = data.items;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = "";
  Object.assign(form, {
    modality: "IR", param_key: "", label: "", unit: "", value_type: "float",
    required: 0, min_value: null, max_value: null, description: "",
  });
  dialog.value = true;
}

function openEdit(row) {
  editingId.value = row.id;
  Object.assign(form, {
    modality: row.modality, param_key: row.param_key, label: row.label,
    unit: row.unit || "", value_type: row.value_type, required: row.required,
    min_value: row.min_value, max_value: row.max_value, description: row.description || "",
  });
  dialog.value = true;
}

async function handleSave() {
  saving.value = true;
  try {
    const payload = {
      label: form.label, unit: form.unit || null, value_type: form.value_type,
      required: form.required, min_value: form.min_value, max_value: form.max_value,
      description: form.description || null,
    };
    if (editingId.value) {
      await api.put(`/admin/modal-params/${editingId.value}`, payload);
      ElMessage.success("已保存");
    } else {
      await api.post("/admin/modal-params", {
        modality: form.modality, param_key: form.param_key, ...payload,
      });
      ElMessage.success("已新增");
    }
    dialog.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div>
    <div class="toolbar">
      <span class="hint">模态采集参数语义定义（Phase 2 schema 驱动表单与渲染器取权威键的数据源），键名与模态发布后不可改名。</span>
      <el-button type="primary" @click="openCreate">新增参数定义</el-button>
    </div>
    <el-table :data="rows" border v-loading="loading">
      <el-table-column label="模态" width="120">
        <template #default="{ row }">{{ MODALITY_LABELS[row.modality] || row.modality }}</template>
      </el-table-column>
      <el-table-column prop="param_key" label="权威键名" min-width="160" />
      <el-table-column prop="label" label="中文名" min-width="140" />
      <el-table-column prop="unit" label="单位" width="80" />
      <el-table-column prop="value_type" label="类型" width="80" />
      <el-table-column label="必填" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="row.required === 1 ? 'danger' : row.required === 2 ? 'warning' : 'info'">
            {{ REQUIRED_LABELS[row.required] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="范围" width="160">
        <template #default="{ row }">
          {{ row.min_value === null && row.max_value === null ? "—" : `${row.min_value ?? "−∞"} ~ ${row.max_value ?? "+∞"}` }}
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="editingId ? '编辑参数定义' : '新增参数定义'" width="620px">
      <el-form label-width="130px" @submit.prevent="handleSave">
        <el-form-item label="模态" required>
          <el-select v-model="form.modality" name="modality" :disabled="!!editingId">
            <el-option v-for="m in MODALITIES" :key="m.value" :label="`${m.label}（${m.value}）`" :value="m.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="权威键名" required>
          <el-input v-model="form.param_key" name="param_key" :disabled="!!editingId"
                    placeholder="小写下划线，如 emissivity（发布后不可改名）" />
        </el-form-item>
        <el-form-item label="中文名" required>
          <el-input v-model="form.label" name="label" placeholder="如 发射率" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" name="unit" placeholder="如 ℃ / Hz（无单位留空）" />
        </el-form-item>
        <el-form-item label="值类型" required>
          <el-select v-model="form.value_type" name="value_type">
            <el-option v-for="t in VALUE_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="必填级别">
          <el-radio-group v-model="form.required" name="required">
            <el-radio v-for="o in REQUIRED_OPTS" :key="o.v" :value="o.v">{{ o.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="数值范围">
          <el-input-number v-model="form.min_value" :controls="false" placeholder="最小（可空）" class="range" />
          <span class="tilde">~</span>
          <el-input-number v-model="form.max_value" :controls="false" placeholder="最大（可空）" class="range" />
          <span class="tip">条件必填触发说明可写于下方「说明」</span>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" name="description" type="textarea" :rows="2" />
        </el-form-item>
        <div class="footer">
          <el-button @click="dialog = false">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
        </div>
      </el-form>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.hint { color: #909399; font-size: 13px; }
.range { width: 140px; }
.tilde { margin: 0 8px; color: #909399; }
.tip { margin-left: 12px; color: #909399; font-size: 12px; }
.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
