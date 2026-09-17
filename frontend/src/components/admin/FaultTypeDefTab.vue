<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../../api";

// 故障类型字典 Tab（Phase 0 §2.5）：admin 维护；code 发布后不可改名、仅可停用（is_active=0）
const rows = ref([]);
const loading = ref(false);
const dialog = ref(false);
const editingId = ref("");
const saving = ref(false);
const SEVERITIES = ["报警", "故障", "事故"];

const form = reactive({
  code: "", name: "", severity: "故障", sort_no: 0, description: "",
});

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get("/admin/fault-types");
    rows.value = data.items;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = "";
  Object.assign(form, { code: "", name: "", severity: "故障", sort_no: 0, description: "" });
  dialog.value = true;
}

function openEdit(row) {
  editingId.value = row.id;
  Object.assign(form, {
    code: row.code, name: row.name, severity: row.severity,
    sort_no: row.sort_no, description: row.description || "",
  });
  dialog.value = true;
}

async function handleSave() {
  saving.value = true;
  try {
    if (editingId.value) {
      const { name, severity, sort_no, description } = form;
      await api.put(`/admin/fault-types/${editingId.value}`, { name, severity, sort_no, description });
      ElMessage.success("已保存");
    } else {
      await api.post("/admin/fault-types", { ...form });
      ElMessage.success("已新增");
    }
    dialog.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function toggleActive(row) {
  await api.put(`/admin/fault-types/${row.id}`, { is_active: row.is_active });
  ElMessage.success(row.is_active ? "已启用" : "已停用（新申报不可选，存量 EVT_ID 不受影响）");
  load();
}

onMounted(load);
</script>

<template>
  <div>
    <div class="toolbar">
      <span class="hint">故障类型对齐三级标签树第三级，code 一经发布不可改名（入 EVT_ID 类型段），仅可停用。</span>
      <el-button type="primary" @click="openCreate">新增故障类型</el-button>
    </div>
    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="code" label="code" min-width="210" />
      <el-table-column prop="name" label="中文层级串" min-width="180" />
      <el-table-column prop="severity" label="默认严重度" width="110">
        <template #default="{ row }">
          <el-tag :type="row.severity === '事故' ? 'danger' : row.severity === '故障' ? 'warning' : 'info'"
                  size="small">{{ row.severity }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" :active-value="1" :inactive-value="0"
                     active-text="启用" inactive-text="停用" @change="toggleActive(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="sort_no" label="排序" width="70" />
      <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="editingId ? '编辑故障类型' : '新增故障类型'" width="560px">
      <el-form label-width="120px" @submit.prevent="handleSave">
        <el-form-item label="code" required>
          <el-input v-model="form.code" name="code" :disabled="!!editingId"
                    placeholder="大写下划线英文，如 GEARBOX_BEARING_WEAR（发布后不可改名）" />
        </el-form-item>
        <el-form-item label="中文层级串" required>
          <el-input v-model="form.name" name="name" placeholder="如 齿轮箱-轴承-磨损（与 Event.event_type 口径一致）" />
        </el-form-item>
        <el-form-item label="默认严重度">
          <el-select v-model="form.severity" name="severity">
            <el-option v-for="s in SEVERITIES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="form.sort_no" :min="0" name="sort_no" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" name="description" type="textarea" :rows="2"
                    placeholder="判定语义/挂载提示（可选）" />
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
.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
