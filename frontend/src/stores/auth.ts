import { defineStore } from "pinia";
import type { UserProfile } from "@/types";
import { login as apiLogin, fetchMe } from "@/api/auth";
import { getToken, clearToken } from "@/utils/request";

/**
 * 鉴权状态（docs/api.md §1）
 * M3 前最小实现：登录页可真实登录（后端就绪时）+ mock 兜底；401 统一跳登录页。
 */
export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null as UserProfile | null,
    loggingIn: false,
  }),

  getters: {
    isLoggedIn: () => !!getToken(),
    isMember: (state) => state.user?.is_member ?? false,
  },

  actions: {
    async login(username: string, password: string): Promise<boolean> {
      if (this.loggingIn) return false;
      this.loggingIn = true;
      try {
        const res = await apiLogin(username, password);
        this.user = res.user;
        return true;
      } catch (e) {
        uni.showToast({ title: (e as Error).message || "登录失败", icon: "none" });
        return false;
      } finally {
        this.loggingIn = false;
      }
    },

    async refreshUser() {
      if (!getToken()) return;
      try {
        this.user = await fetchMe();
      } catch {
        /* 未登录/失败静默 */
      }
    },

    logout() {
      clearToken();
      this.user = null;
    },
  },
});
