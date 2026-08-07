import { defineStore } from "pinia";
import type { Question } from "@/types";
import { fetchQuestions, submitAnswer } from "@/api/questions";

/**
 * 刷题状态：题目列表 / 当前进度 / 作答反馈
 * 说明：采用 options 风格，保证 vue-tsc(1.0.x) 下 getters 类型推断稳定
 */
export const usePracticeStore = defineStore("practice", {
  state: () => ({
    subjectId: "",
    questions: [] as Question[],
    index: 0,
    loading: false,
    error: "",
    /** 已选中的选项 key（单选为 1 项，多选为多项） */
    selected: [] as string[],
    /** 是否已提交（提交后锁定选项） */
    answered: false,
    isCorrect: false,
    explanationVisible: false,
  }),

  getters: {
    total: (state) => state.questions.length,
    current: (state): Question | null => state.questions[state.index] ?? null,
    progress: (state) => (state.questions.length ? state.index + 1 : 0),
  },

  actions: {
    async loadQuestions(subjectId_: string) {
      this.subjectId = subjectId_;
      this.loading = true;
      this.error = "";
      try {
        this.questions = await fetchQuestions(subjectId_);
        this.index = 0;
        this.resetAnswer();
      } catch (e) {
        this.error = (e as Error).message || "题目加载失败";
      } finally {
        this.loading = false;
      }
    },

    resetAnswer() {
      this.selected = [];
      this.answered = false;
      this.isCorrect = false;
      this.explanationVisible = false;
    },

    selectOption(key: string) {
      if (this.answered || !this.current) return;
      if (this.current.type === "single") {
        this.selected = [key];
      } else {
        this.selected = this.selected.includes(key)
          ? this.selected.filter((k) => k !== key)
          : [...this.selected, key];
      }
    },

    async submit() {
      const q = this.current;
      if (!q || this.selected.length === 0 || this.answered) return;
      this.answered = true;
      const res = await submitAnswer(q.id, this.selected);
      this.isCorrect = res.correct;
      // mock 阶段 explanation 已内嵌；真实阶段以后端返回为准
      if (q.explanation == null && res.explanation) {
        q.explanation = res.explanation;
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
  },
});
