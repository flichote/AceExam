import { defineStore } from "pinia";
import type {
  Question,
  KnowledgeState,
  SprintSession,
  SprintQuestionsResponse,
  SprintMockMeta,
} from "@/types";
import { activateSprint, fetchSprintQuestions } from "@/api/sprint";
import { submitQuestionAnswer, buildAnswerValue } from "@/api/practice";

/**
 * 考前突击状态（docs/api.md §11.2 / §11.3）
 * - 手动激活 POST /subjects/{id}/sprint/activate（幂等；免费 403）
 * - 题单 GET /subjects/{id}/sprint/questions（days_left ≤ 7 自动激活）
 * - 答题流程复用刷题链路（POST /questions/{id}/answers）
 */
export const useSprintStore = defineStore("sprint", {
  state: () => ({
    subjectId: "",
    session: null as SprintSession | null,
    data: null as SprintQuestionsResponse | null,
    mode: "review" as "review" | "mock",
    loading: false,
    activating: false,
    error: "",
    /** 是否已进入答题（题单已加载） */
    started: false,
    /** 模拟卷剩余秒数（mode=mock 前端计时） */
    mockSecondsLeft: 0,
    mockTimer: null as ReturnType<typeof setInterval> | null,

    // 答题状态（复用刷题组件）
    questions: [] as Question[],
    index: 0,
    selected: [] as string[],
    blankInput: "",
    answered: false,
    isCorrect: false,
    explanationVisible: false,
    knowledgeState: null as KnowledgeState | null,
    _answeredAt: 0,
  }),

  getters: {
    total: (state) => state.questions.length,
    current: (state): Question | null => state.questions[state.index] ?? null,
    progress: (state) => (state.questions.length ? state.index + 1 : 0),
    daysLeft: (state) => state.data?.days_left ?? state.session?.days_left ?? null,
    mockMeta: (state): SprintMockMeta | null => state.data?.mock ?? null,
    summary: (state) => state.data?.summary ?? null,
    highFreqKps: (state) => state.data?.high_freq_kps ?? [],
    mockTimeText: (state) => {
      const s = state.mockSecondsLeft;
      if (s <= 0) return "00:00";
      const mm = String(Math.floor(s / 60)).padStart(2, "0");
      const ss = String(s % 60).padStart(2, "0");
      return `${mm}:${ss}`;
    },
  },

  actions: {
    /** 手动激活（幂等；免费用户 403 由调用方捕获展示会员引导） */
    async activate(subjectId: string): Promise<boolean> {
      if (this.activating) return false;
      this.activating = true;
      try {
        const res = await activateSprint(subjectId);
        this.session = res.sprint;
        return true;
      } catch (e) {
        uni.showToast({ title: (e as Error).message || "激活失败", icon: "none" });
        return false;
      } finally {
        this.activating = false;
      }
    },

    /** 拉取突击题单（首次访问 days_left ≤ 7 自动激活） */
    async load(subjectId: string, mode: "review" | "mock" = "review", count = 20) {
      this.subjectId = subjectId;
      this.mode = mode;
      this.loading = true;
      this.error = "";
      try {
        const res = await fetchSprintQuestions(subjectId, { mode, count });
        this.data = res;
        this.session = this.session
          ? { ...this.session, days_left: res.days_left, status: res.status }
          : null;
        // 契约映射：content → stem、knowledge_point_id → knowledgePoint
        this.questions = res.items.map((q) => ({
          ...q,
          stem: q.stem || (q as unknown as { content?: string }).content || "",
          knowledgePoint: q.knowledgePoint || "知识点",
        }));
        this.started = this.questions.length > 0;
        this.index = 0;
        this.resetAnswer();
        // 模拟卷计时
        if (mode === "mock" && res.mock) {
          this.startMockTimer(res.mock.duration_min * 60);
        } else {
          this.stopMockTimer();
        }
      } catch (e) {
        this.error = (e as Error).message || "突击题单加载失败";
      } finally {
        this.loading = false;
      }
    },

    startMockTimer(seconds: number) {
      this.stopMockTimer();
      this.mockSecondsLeft = seconds;
      this.mockTimer = setInterval(() => {
        if (this.mockSecondsLeft > 0) this.mockSecondsLeft -= 1;
        else this.stopMockTimer();
      }, 1000);
    },

    stopMockTimer() {
      if (this.mockTimer) {
        clearInterval(this.mockTimer);
        this.mockTimer = null;
      }
    },

    resetAnswer() {
      this.selected = [];
      this.blankInput = "";
      this.answered = false;
      this.isCorrect = false;
      this.explanationVisible = false;
      this.knowledgeState = null;
      this._answeredAt = Date.now();
    },

    selectOption(key: string) {
      if (this.answered || !this.current) return;
      if (this.current.type === "single") {
        this.selected = [key];
      } else if (this.current.type === "multiple") {
        this.selected = this.selected.includes(key)
          ? this.selected.filter((k) => k !== key)
          : [...this.selected, key];
      }
    },

    canSubmit(): boolean {
      const q = this.current;
      if (!q || this.answered) return false;
      if (q.type === "blank" || q.type === "essay") return this.blankInput.trim().length > 0;
      return this.selected.length > 0;
    },

    async submit() {
      const q = this.current;
      if (!q || this.answered) return;
      const answer = buildAnswerValue(q.type, this.selected, this.blankInput.trim());
      const timeSpent = Math.max(1, Math.round((Date.now() - this._answeredAt) / 1000));
      try {
        const res = await submitQuestionAnswer(q.id, answer, timeSpent, "review");
        this.answered = true;
        this.isCorrect = res.correct;
        q.answer = Array.isArray(res.correct_answer)
          ? res.correct_answer
          : res.correct_answer
            ? [res.correct_answer]
            : [];
        if (res.analysis) q.explanation = res.analysis;
        this.knowledgeState = res.knowledge_state ?? null;
      } catch (e) {
        uni.showToast({ title: (e as Error).message || "提交失败，请重试", icon: "none" });
      }
    },

    toggleExplanation() {
      this.explanationVisible = !this.explanationVisible;
    },

    next() {
      if (this.index < this.questions.length - 1) {
        this.index += 1;
        this.resetAnswer();
      }
    },

    restart() {
      this.index = 0;
      this.resetAnswer();
    },

    reset() {
      this.stopMockTimer();
      this.session = null;
      this.data = null;
      this.questions = [];
      this.started = false;
      this.error = "";
      this.mode = "review";
    },
  },
});
