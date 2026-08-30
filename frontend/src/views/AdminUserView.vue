<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../api";
import { useDictStore } from "../stores/dict";

// 用户管理（admin CRUD + 重置密码 + 停用即时失效 TC-AUTH-003）
const dict = useDictStore();
const rows = ref([]);
const loading = ref(false);
const dialog = ref(false);
const editingId = ref("");
const saving = ref(false);
const newPassword = ref("");

// v-model 需成员表达式，对话框显隐由 computed 代理（TC-AUTH-004）
const passwordDialog = computed({
  get: () => !!newPassword.value,
  set: (v) => { if (!v) newPassword.value = ""; },
});

const form = reactive({
  username: "", display_name: "", password: "",
  role: "user", organization_id: "", is_active: 1,
});

async function load() {
  loading.value = true;
  try {
    const [{ data: users }] = await Promise.all([
      api.get("/admin/users"),
      dict.loadOrganizations(),
    ]);
    rows.value = users.items;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = "";
  Object.assign(form, {
    username: "", display_name: "", password: "",
    role: "user", organization_id: "", is_active: 1,
  });
  dialog.value = true;
}

function openEdit(row) {
  editingId.value = row.id;
  Object.assign(form, {
    username: row.username, display_name: row.display_name, password: "",
    role: row.role, organization_id: row.organization_id || "", is_active: row.is_active,
  });
  dialog.value = true;
}

async function handleSave() {
  saving.value = true;
  try {
    if (editingId.value) {
      const { organization_id, is_active, role, display_name } = form;
      await api.put(`/admin/users/${editingId.value}`, {
        display_name, role, organization_id: organization_id || null, is_active,
      });
    } else {
      await api.post("/admin/users", {
        ...form, organization_id: form.organization_id || null,
      });
    }
    ElMessage.success("已保存");
    dialog.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function handleToggle(row) {
  await api.put(`/admin/users/${row.id}`, { is_active: row.is_active });
  ElMessage.success(row.is_active ? "已启用" : "已停用（即时失效）");
  load();
}

async function handleResetPassword(row) {
  await ElMessageBox.confirm(`确认为用户 ${row.username} 重置密码？`, "重置密码", {
    type: "warning",
  });
  const { data } = await api.post(`/admin/users/${row.id}/reset-password`);
  newPassword.value = data.new_password;
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除用户 ${row.username}？`, "删除确认", { type: "warning" });
  await api.delete(`/admin/users/${row.id}`);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <h3>用户管理</h3>
      <el-button type="primary" @click="openCreate">新增用户</el-button>
    </div>

    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="username" label="账号" width="130" />
      <el-table-column prop="display_name" label="姓名" width="120" />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">{{ row.role === "admin" ? "管理员" : "对接人" }}</template>
      </el-table-column>
      <el-table-column label="所属单位" min-width="160">
        <template #default="{ row }">
          {{ dict.organizations.find((o) => o.id === row.organization_id)?.name || "-" }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-switch :model-value="row.is_active === 1" :active-value="1" :inactive-value="0"
                     active-text="启用" inactive-text="停用" @change="handleToggle(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="warning" @click="handleResetPassword(row)">重置密码</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="editingId ? '编辑用户' : '新增用户'" width="520px">
      <el-form label-width="100px" @submit.prevent="handleSave">
        <el-form-item label="账号" required>
          <el-input v-model="form.username" name="username" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="form.display_name" name="display_name" />
        </el-form-item>
        <el-form-item v-if="!editingId" label="初始密码" required>
          <el-input v-model="form.password" name="password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="form.role" name="role">
            <el-option label="管理员" value="admin" />
            <el-option label="对接人" value="user" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属单位">
          <el-select v-model="form.organization_id" name="organization_id" clearable
                     placeholder="不选则无单位归属">
            <el-option v-for="o in dict.organizations" :key="o.id"
                       :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0"
                     active-text="启用" inactive-text="停用" />
        </el-form-item>
        <div class="footer">
          <el-button @click="dialog = false">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
        </div>
      </el-form>
    </el-dialog>

    <el-dialog v-model="passwordDialog" title="重置密码成功" width="420px">
      <p>用户新密码（仅显示一次，请立即告知用户）：</p>
      <el-input :model-value="newPassword" readonly>
        <template #append>
          <el-button @click="navigator.clipboard.writeText(newPassword)">复制</el-button>
        </template>
      </el-input>
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
