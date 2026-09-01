import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

import AppLayout from "../layouts/AppLayout.vue";
import LoginView from "../views/LoginView.vue";
import BatchListView from "../views/BatchListView.vue";
import BatchCreateView from "../views/BatchCreateView.vue";
import BatchImportView from "../views/BatchImportView.vue";
import BatchDetailView from "../views/BatchDetailView.vue";
import UploadView from "../views/UploadView.vue";
import FileListView from "../views/FileListView.vue";
import FileDetailView from "../views/FileDetailView.vue";
import AdminOrgView from "../views/AdminOrgView.vue";
import AdminUserView from "../views/AdminUserView.vue";
import AdminBatchNoRuleView from "../views/AdminBatchNoRuleView.vue";
import AuditView from "../views/AuditView.vue";
import DeviceLedgerView from "../views/DeviceLedgerView.vue";
import EventLedgerView from "../views/EventLedgerView.vue";

// 路由表按架构 3.1（10 页面）
const routes = [
  { path: "/login", component: LoginView, meta: { public: true } },
  {
    path: "/",
    component: AppLayout,
    redirect: "/batches",
    children: [
      { path: "batches", component: BatchListView },
      { path: "batch-imports", component: BatchImportView },
      { path: "batches/new", component: BatchCreateView },
      { path: "batches/:id", component: BatchDetailView },
      { path: "batches/:id/upload", component: UploadView },
      { path: "files", component: FileListView },
      { path: "files/:id", component: FileDetailView },
      { path: "admin/organizations", component: AdminOrgView, meta: { adminOnly: true } },
      { path: "admin/users", component: AdminUserView, meta: { adminOnly: true } },
      { path: "admin/batch-no-rule", component: AdminBatchNoRuleView, meta: { adminOnly: true } },
      { path: "audit", component: AuditView, meta: { adminOnly: true } },
      { path: "devices", component: DeviceLedgerView },
      { path: "events", component: EventLedgerView },
    ],
  },
  { path: "/:pathMatch(.*)*", redirect: "/batches" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 全局前置守卫（架构 3.4）：无 token → /login；有 token 无 user → fetchMe；
// /admin/* 与 /audit 仅 role=admin，否则重定向 /batches
router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.public) {
    if (auth.isAuthenticated && to.path === "/login") return "/batches";
    return true;
  }
  if (!auth.token) return "/login";
  if (!auth.user) {
    try {
      await auth.fetchMe();
    } catch {
      auth.logout();
      return "/login";
    }
  }
  if (to.meta.adminOnly && !auth.isAdmin) return "/batches";
  return true;
});

export default router;
