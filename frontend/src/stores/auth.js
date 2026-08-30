import { defineStore } from "pinia";
import api from "../api";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("dch_token") || "",
    user: JSON.parse(localStorage.getItem("dch_user") || "null"),
  }),
  getters: {
    isAuthenticated: (s) => !!s.token,
    isAdmin: (s) => s.user?.role === "admin",
  },
  actions: {
    async login(username, password) {
      const { data } = await api.post("/auth/login", { username, password });
      this.token = data.access_token;
      localStorage.setItem("dch_token", this.token);
      await this.fetchMe();
    },
    async fetchMe() {
      const { data } = await api.get("/auth/me");
      this.user = data;
      localStorage.setItem("dch_user", JSON.stringify(data));
    },
    logout() {
      this.token = "";
      this.user = null;
      localStorage.removeItem("dch_token");
      localStorage.removeItem("dch_user");
    },
  },
});
