/**
 * AceExam 前端领域类型
 * 与后端约定字段见 docs/architecture.md（API 路由骨架）
 */

/** 科目状态 → 徽章映射（docs/design/design-system.md） */
export type SubjectStatus =
  | "mastered" // 已掌握（success）
  | "weak" // 薄弱（danger）
  | "consolidating" // 待巩固（warning）
  | "cramming"; // 突击中（primary 描边）

export interface Subject {
  id: string;
  name: string;
  /** 卡片图标：emoji 文本，避免静态图片资源 */
  emoji: string;
  /** 考试日期（ISO yyyy-mm-dd） */
  examDate: string;
  /** 距考试天数 */
  examCountdown: number;
  /** 掌握度 */
  mastery: {
    mastered: number; // 已掌握题数
    total: number; // 总题数
    percent: number; // 0-100
  };
  status: SubjectStatus;
  /** 今日任务进度 */
  todayTask: {
    done: number;
    total: number;
  };
  /** 连续学习天数 */
  streak: number;
}

export type QuestionType = "single" | "multiple";

export interface QuestionOption {
  /** A / B / C / D */
  key: string;
  /** 选项文本，支持 $...$ LaTeX 公式 */
  text: string;
}

export interface Question {
  id: string;
  subjectId: string;
  type: QuestionType;
  /** 知识点（用于刷题页顶部标签） */
  knowledgePoint: string;
  /** 1-5 */
  difficulty: number;
  /** 题干，支持 $...$ / $$...$$ LaTeX 公式 */
  stem: string;
  options: QuestionOption[];
  /**
   * 正确选项 key 列表。
   * 后端约定：作答前不返回 answer（ADR-0002 / docs/architecture.md）。
   * mock 阶段随题下发，联调时按后端响应调整（TODO(ep-backend)）。
   */
  answer?: string[];
  /** 解析，支持 LaTeX；同样由"提交后"接口返回 */
  explanation?: string;
  /** AI 讲解引用（RAG 溯源，ADR-0003） */
  citations?: Citation[];
}

/** 教材引用块（RAG 溯源：教材名 + 章节 + 原文片段） */
export interface Citation {
  source: string;
  chapter: string;
  snippet: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  /** 支持 $...$ LaTeX 片段 */
  content: string;
  citations?: Citation[];
  /** 流式输出中（mock SSE） */
  streaming?: boolean;
  createdAt: number;
}

/** 答题记录（我的-数据看板 mock） */
export interface PracticeStat {
  total: number;
  correct: number;
  accuracy: number; // 0-100
  streak: number;
  week: { day: string; count: number }[];
}
