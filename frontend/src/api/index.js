import axios from "axios";
import { ElMessage } from "element-plus";
import { useAuthStore } from "../stores/auth";

const api = axios.create({ baseURL: "/api/v1", timeout: 30000 });

api.interceptors.request.use((cfg) => {
  const s = useAuthStore();
  if (s.token) cfg.headers.Authorization = `Bearer ${s.token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const { response } = err;
    if (response?.status === 401) {
      const s = useAuthStore();
      s.logout();
      if (location.pathname !== "/login") location.href = "/login";
    }
    ElMessage.error(response?.data?.detail || "请求失败");
    return Promise.reject(err);
  }
);

export default api;
