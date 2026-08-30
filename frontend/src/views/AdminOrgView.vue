<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../api";

// 单位管理（admin CRUD，架构 3.1）
const rows = ref([]);
const loading = ref(false);
const dialog = ref(false);
const editingId = ref("");
const saving = ref(false);

const ORG_TYPES = ["场站", "电厂", "运维单位"];

const form = reactive({
  name: "", type: "场站", contact_person: "", contact_phone: "",
});

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get("/admin/organizations");
    rows.value = data.items;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = "";
  Object.assign(form, { name: "", type: "场站", contact_person: "", contact_phone: "" });
  dialog.value = true;
}

function openEdit(row) {
  editingId.value = row.id;
  Object.assign(form, {
    name: row.name, type: row.type,
    contact_person: row.contact_person || "", contact_phone: row.contact_phone || "",
  });
  dialog.value = true;
}

async function handleSave() {
  saving.value = true;
  try {
    if (editingId.value) {
      await api.put(`/admin/organizations/${editingId.value}`, { ...form });
    } else {
      await api.post("/admin/organizations", { ...form });
    }
    ElMessage.success("已保存");
    dialog.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(
    `确认删除单位 ${row.name}？其下批次与用户将无法归属。`,
    "删除确认", { type: "warning" });
  await api.delete(`/admin/organizations/${row.id}`);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <h3>单位管理</h3>
      <el-button type="primary" @click="openCreate">新增单位</el-button>
    </div>

    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="name" label="单位名称" min-width="180" />
      <el-table-column prop="type" label="类型" width="110" />
      <el-table-column prop="contact_person" label="联系人" width="120" />
      <el-table-column prop="contact_phone" label="联系电话" width="150" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="editingId ? '编辑单位' : '新增单位'" width="520px">
      <el-form label-width="100px" @submit.prevent="handleSave">
        <el-form-item label="单位名称" required>
          <el-input v-model="form.name" name="name" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="form.type" name="type">
            <el-option v-for="t in ORG_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_person" name="contact_person" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.contact_phone" name="contact_phone" />
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
.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
