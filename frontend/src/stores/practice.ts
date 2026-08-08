import { defineStore } from "pinia";
import type { Question, PracticeStrategy, KnowledgeState, PracticeResponse } from "@/types";
import {
  fetchPracticeQuestions,
  submitQuestionAnswer,
  buildAnswerValue,
} from "@/api/practice";
import { fetchKnowledgePoints, buildKpNameMap } from "@/api/subjects";

/**
 * 刷题状态：自适应选题（M2）/ 作答反馈 / 策略可解释性
 * 说明：options 风格，保证 vue-tsc 下 getters 类型推断稳定
 */
export const usePracticeStore = defineStore("practice", {
  state: () => ({
    subjectId: "",
    questions: [] as Question[],
    index: 0,
    loading: false,
    error: "",
    /** 已选中的选项 key（单选 1 项 / 多选多项） */
    selected: [] as string[],
    /** 填空题/大题文本输入 */
    blankInput: "",
    /** 已提交（锁定选项） */
    answered: false,
    isCorrect: false,
    explanationVisible: false,
    /** 本次自适应选题策略（可解释性展示） */
    strategy: null as PracticeStrategy | null,
    /** 知识点 id → 名称（标签展示） */
    kpNameMap: {} as Record<string, string>,
    /** 会话内已展示题 id（防重复，next 批次排除） */
    seenIds: [] as string[],
    wrongAnswerId: "",
    knowledgeState: null as KnowledgeState | null,
    /** 作答起始时间戳（time_spent_seconds） */
    _answeredAt: 0,
    /** 本组答对题数（结算面板统计） */
    correctCount: 0,
    /** 本组是否已全部作答完成（答完最后一题） */
    finished: false,
    /** 每题作答结果：questionId → 是否答对（结算面板逐题回顾） */
    results: {} as Record<string, boolean>,
  }),

  getters: {
    total: (state) => state.questions.length,
    current: (state): Question | null => state.questions[state.index] ?? null,
    progress: (state) => (state.questions.length ? state.index + 1 : 0),
    /** 当前题型是否需文本输入 */
    isInputType: (state) => {
      const q = state.questions[state.index];
      return !!q && (q.type === "blank" || q.type === "essay");
    },
  },

  actions: {
    async loadKnowledgePoints(subjectId_: string) {
      try {
        const kps = await fetchKnowledgePoints(subjectId_);
        this.kpNameMap = Object.fromEntries(
          buildKpNameMap(kps, this.strategy?.target_kps ?? [])
        );
      } catch {
        /* 知识点加载失败不阻塞刷题 */
      }
    },

    async loadQuestions(subjectId_: string, count = 10, kpId?: string) {
      this.subjectId = subjectId_;
      this.loading = true;
      this.error = "";
      try {
        const res: PracticeResponse = await fetchPracticeQuestions(subjectId_, {
          count,
          excludeIds: this.seenIds,
          ...(kpId ? { knowledgePointId: kpId } : {}),
        });
        this.strategy = res.strategy;
        // 合并策略命中知识点到名称映射（题目只给 knowledge_point_id 时也能显示标签）
        this.kpNameMap = {
          ...this.kpNameMap,
          ...Object.fromEntries((res.strategy?.target_kps ?? []).map((h) => [h.id, h.name])),
        };
        // 契约映射：content → stem、knowledge_point_id → knowledgePoint
        this.questions = res.items.map((q) => ({
          ...q,
          stem: q.stem || (q as unknown as { content?: string }).content || "",
          knowledgePoint: this.kpNameMap[q.knowledgePointId || ""] || q.knowledgePoint || "知识点",
        }));
        res.items.forEach((q) => {
          if (!this.seenIds.includes(q.id)) this.seenIds.push(q.id);
        });
        this.index = 0;
        this.correctCount = 0;
        this.finished = false;
        this.results = {};
        this.resetAnswer();
        await this.loadKnowledgePoints(subjectId_);
      } catch (e) {
        this.error = (e as Error).message || "题目加载失败";
      } finally {
        this.loading = false;
      }
    },

    resetAnswer() {
      this.selected = [];
      this.blankInput = "";
      this.answered = false;
      this.isCorrect = false;
      this.explanationVisible = false;
      this.wrongAnswerId = "";
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
        const res = await submitQuestionAnswer(q.id, answer, timeSpent, "practice");
        this.answered = true;
        this.isCorrect = res.correct;
        if (res.correct) this.correctCount += 1;
        this.results[q.id] = res.correct;
        q.answer = Array.isArray(res.correct_answer)
          ? res.correct_answer
          : res.correct_answer
            ? [res.correct_answer]
            : [];
        if (res.analysis) q.explanation = res.analysis;
        this.wrongAnswerId = res.wrong_answer_id ?? "";
        this.knowledgeState = res.knowledge_state ?? null;
      } catch (e) {
        // 业务错误（403/404/422…）保留可作答状态，不锁定选项
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
      } else if (this.answered) {
        // 答完最后一题：进入结算面板（对错统计 + 解析回顾）
        this.finished = true;
      }
    },

    /** 结算后查看本题解析（从结算面板回到最后一题） */
    reviewLast() {
      this.finished = false;
      this.explanationVisible = true;
    },

    restart() {
      this.index = 0;
      this.correctCount = 0;
      this.finished = false;
      this.results = {};
      this.resetAnswer();
    },
  },
});
