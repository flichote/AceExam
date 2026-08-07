import { defineStore } from "pinia";
import type { SelfTestResult, DiagnosisReport } from "@/types";
import { startSelfTest, submitDiagnosis } from "@/api/diagnose";

/**
 * 摸底诊断状态（docs/api.md §7）
 * 自测 10 题 → 提交 → 诊断报告（薄弱 Top5 + 建议）
 */
export const useDiagnoseStore = defineStore("diagnose", {
  state: () => ({
    subjectId: "",
    selfTest: null as SelfTestResult | null,
    reportId: "",
    /** question_id → 作答值（single/blank/essay 为 string；multiple 为 string[]） */
    answers: {} as Record<string, string | string[]>,
    report: null as DiagnosisReport | null,
    loading: false,
    submitting: false,
    error: "",
  }),

  getters: {
    questions: (state) => state.selfTest?.questions ?? [],
    total: (state) => state.selfTest?.questions.length ?? 0,
    answeredCount: (state) =>
      state.selfTest?.questions.filter((q) => state.answers[q.id] !== undefined).length ?? 0,
  },

  actions: {
    async start(subjectId: string, count = 10) {
      this.subjectId = subjectId;
      this.loading = true;
      this.error = "";
      this.report = null;
      try {
        this.selfTest = await startSelfTest(subjectId, count);
        this.reportId = this.selfTest.report_id;
        this.answers = {};
      } catch (e) {
        this.error = (e as Error).message || "自测启动失败";
      } finally {
        this.loading = false;
      }
    },

    setAnswer(questionId: string, value: string | string[]) {
      this.answers[questionId] = value;
    },

    async submit(): Promise<DiagnosisReport | null> {
      if (this.submitting || !this.reportId) return null;
      this.submitting = true;
      try {
        const answers = Object.entries(this.answers).map(([question_id, answer]) => ({
          question_id,
          answer,
        }));
        this.report = await submitDiagnosis(this.reportId, answers);
        return this.report;
      } catch (e) {
        uni.showToast({ title: (e as Error).message || "提交失败", icon: "none" });
        return null;
      } finally {
        this.submitting = false;
      }
    },

    reset() {
      this.selfTest = null;
      this.reportId = "";
      this.answers = {};
      this.report = null;
    },
  },
});
