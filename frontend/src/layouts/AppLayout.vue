<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const activeMenu = computed(() => route.path);

// 菜单按角色渲染：admin 才显示管理端入口（TC-AUTH-002）
const menus = computed(() => {
  const items = [
    { path: "/batches", label: "批次管理" },
    { path: "/files", label: "文件检索" },
    { path: "/devices", label: "设备台账" },
    { path: "/events", label: "事件记录" },
  ];
  if (auth.isAdmin) {
    items.push(
      { path: "/admin/organizations", label: "单位管理" },
      { path: "/admin/users", label: "用户管理" },
      { path: "/admin/batch-no-rule", label: "批次编号规则" },
      { path: "/audit", label: "审计日志" }
    );
  }
  return items;
});

async function handleLogout() {
  await ElMessageBox.confirm("确认退出登录？", "提示", { type: "warning" });
  auth.logout();
  router.push("/login");
}
</script>

<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand">原始数据采集入库</div>
      <div class="user">
        <span>{{ auth.user?.display_name }}（{{ auth.user?.role === "admin" ? "管理员" : "对接人" }}）</span>
        <el-button link type="primary" @click="handleLogout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px">
        <el-menu :default-active="activeMenu" router>
          <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
            {{ m.label }}
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
}
.brand {
  font-size: 16px;
  font-weight: 600;
}
.user {
  display: flex;
  align-items: center;
  gap: 12px;
}
.el-aside {
  border-right: 1px solid #e4e7ed;
}
</style>
