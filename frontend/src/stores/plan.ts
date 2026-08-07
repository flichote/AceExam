import { defineStore } from "pinia";
import type { ActivePlanResponse, CheckinResult } from "@/types";
import { fetchActivePlan, checkinPlan } from "@/api/plans";

/**
 * 备考计划状态：首页今日任务卡片（docs/api.md §8）
 * 数据源：GET /plans/active（plan + today_task + upcoming + weak_kps）
 */
export const usePlanStore = defineStore("plan", {
  state: () => ({
    data: null as ActivePlanResponse | null,
    loading: false,
    error: "",
    checkingIn: false,
  }),

  getters: {
    hasPlan: (state) => !!state.data?.plan,
    plan: (state) => state.data?.plan ?? null,
    todayTask: (state) => state.data?.today_task ?? null,
    weakKps: (state) => state.data?.weak_kps ?? [],
    upcoming: (state) => state.data?.upcoming ?? [],
  },

  actions: {
    async loadActive(subjectId?: string) {
      this.loading = true;
      this.error = "";
      try {
        this.data = await fetchActivePlan(subjectId);
      } catch (e) {
        this.error = (e as Error).message || "今日任务加载失败";
      } finally {
        this.loading = false;
      }
    },

    /** 创建计划后回填（POST /plans 响应含 plan + today_task） */
    setFromCreate(data: ActivePlanResponse) {
      this.data = data;
    },

    /** 打卡（幂等：already_checked_in 不报错） */
    async checkin(): Promise<CheckinResult | null> {
      if (!this.data?.plan || this.checkingIn) return null;
      this.checkingIn = true;
      try {
        const res = await checkinPlan(this.data.plan.id);
        if (this.data.today_task?.done) {
          this.data.today_task.done.checked_in = true;
        }
        return res;
      } catch (e) {
        uni.showToast({ title: (e as Error).message || "打卡失败", icon: "none" });
        return null;
      } finally {
        this.checkingIn = false;
      }
    },
  },
});
