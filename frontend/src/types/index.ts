/**
 * AceExam 前端领域类型
 * 字段与后端契约对齐：docs/api.md（M2 v1.0，28 端点）
 * M1 兼容：Question 保留 stem/knowledgePoint 展示字段，由 api 层做契约映射。
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

export type QuestionType = "single" | "multiple" | "blank" | "essay";

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
  /** 知识点（刷题页顶部标签，api 层由 knowledge_point_id 映射为名称） */
  knowledgePoint: string;
  /** 1-5 */
  difficulty: number;
  /** 题干（api 层由 content 映射），支持 $...$ / $$...$$ LaTeX 公式 */
  stem: string;
  options: QuestionOption[];
  /**
   * 正确选项 key 列表。
   * 后端契约：作答前不返回 answer（docs/api.md §3.2）。
   */
  answer?: string[];
  /** 解析，支持 LaTeX；由提交接口返回 */
  explanation?: string;
  /** 知识点 id（契约字段透传） */
  knowledgePointId?: string;
  /** 来源：textbook | ugc | seed */
  source?: string;
  createdAt?: string;
  /** AI 讲解引用（RAG 溯源，mock 阶段随题下发） */
  citations?: Citation[];
}

/** 教材引用块（RAG 溯源：教材名 + 章节 + 原文片段，docs/api.md §5.1） */
export interface Citation {
  source: string;
  chapter: string;
  section?: string;
  page?: string;
  snippet: string;
  /** 检索相似度 0.75~1.0 */
  score?: number;
}

/* ===== M2 刷题（docs/api.md §3.2 / §3.3）===== */

/** 自适应选题命中知识点（可解释性） */
export interface KnowledgePointHit {
  id: string;
  name: string;
  level: number;
  status?: string;
  /** 掌握度 0-100 */
  score?: number;
  accuracy?: number;
  reason?: string;
}

export interface PracticeStrategy {
  target_kps: KnowledgePointHit[];
  weights: Record<string, number>;
  requested_at: string;
}

/** GET /subjects/{id}/practice/questions 响应 */
export interface PracticeResponse {
  items: Question[];
  strategy: PracticeStrategy;
}

export interface KnowledgeState {
  status: string; // weak | consolidating | mastered | not_started
  correct_count: number;
  wrong_count: number;
  streak: number;
}

/** POST /questions/{id}/answers 响应 */
export interface AnswerResult {
  correct: boolean;
  /** 单选为 "C"，多选为 ["A","C"] */
  correct_answer: string | string[];
  analysis?: string;
  knowledge_point?: { id: string; name: string; level: number };
  knowledge_state?: KnowledgeState;
  wrong_answer_id?: string;
  explanation_available?: boolean;
}

/* ===== M2 AI 讲解（docs/api.md §5）===== */

/** 分步讲解卡片（可折叠） */
export interface StepCard {
  title: string;
  content: string;
}

export interface ChatExplainResult {
  session_id: string;
  steps: StepCard[];
  conclusion: string;
  citations: Citation[];
  uncovered: boolean;
  model?: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  /** 纯文本内容；讲解模式也可作为 conclusion */
  content: string;
  /** AI 讲解分步卡片 */
  steps?: StepCard[];
  citations?: Citation[];
  /** 流式输出中 */
  streaming?: boolean;
  createdAt: number;
}

/* ===== M2 OCR 拍照录题（docs/api.md §6）===== */

export interface OcrStructured {
  type: QuestionType;
  content: string;
  options: QuestionOption[];
  answer: string;
  analysis: string;
  /** 0~1；< 0.6 前端提示人工核对 */
  confidence?: number;
}

export interface SuggestedKp {
  id: string;
  name: string;
  score: number;
}

export interface OcrUploadResult {
  upload_id: string;
  status: "pending" | "parsed" | "failed";
  raw_text: string | null;
  structured: OcrStructured | null;
  suggested_kps: SuggestedKp[] | null;
  error?: string | null;
}

/* ===== M2 诊断（docs/api.md §7）===== */

export interface SelfTestQuestion {
  id: string;
  knowledge_point_id: string;
  type: QuestionType;
  content: string;
  options: QuestionOption[];
  difficulty: number;
}

export interface SelfTestResult {
  report_id: string;
  subject_id: string;
  status: "in_progress" | "completed";
  questions: SelfTestQuestion[];
  coverage?: { chapter_id: string; chapter_name: string; questions: number }[];
}

export interface WeakTop {
  rank: number;
  knowledge_point_id: string;
  knowledge_point_name: string;
  level: number;
  accuracy: number;
  practice_count: number;
  status: string;
  suggestion: string;
}

export interface DiagnosisReport {
  report_id: string;
  status: string;
  summary: string;
  weak_top5: WeakTop[];
  strengths: { knowledge_point_name: string; accuracy: number }[];
  not_started: { knowledge_point_name: string; level: number }[];
  suggested_next_steps: string[];
}

/* ===== M2 备考计划（docs/api.md §8）===== */

export interface Plan {
  id: string;
  subject_id: string;
  title: string;
  exam_date: string;
  days_left: number;
  status: string; // active
  daily_question_target: number;
}

export interface FocusKp {
  id: string;
  name: string;
  reason?: string;
}

export interface TodayTask {
  date: string;
  target_questions: number;
  focus_kps: FocusKp[];
  type: string; // daily | intensify | sprint | weak_practice
  reason?: string;
  done?: {
    questions_practiced: number;
    correct_count: number;
    checked_in: boolean;
  };
}

export interface ActivePlanResponse {
  plan: Plan | null;
  today_task: TodayTask | null;
  upcoming: TodayTask[];
  weak_kps?: KnowledgePointHit[];
}

export interface CheckinResult {
  checked_in: boolean;
  already_checked_in: boolean;
  session: {
    session_date: string;
    questions_practiced: number;
    correct_count: number;
    checked_in: boolean;
    checked_in_at: string;
  } | null;
}

/* ===== M2 auth（docs/api.md §1）===== */

export interface UserProfile {
  id: string;
  username: string;
  role: string;
  is_member: boolean;
  member_expires_at: string | null;
  created_at: string;
}

export interface LoginResult {
  access_token: string;
  refresh_token: string;
  user: UserProfile;
}

/** 答题记录（我的-数据看板 mock，P1 接入统计接口） */
export interface PracticeStat {
  total: number;
  correct: number;
  accuracy: number; // 0-100
  streak: number;
  week: { day: string; count: number }[];
}

/* ===== M3 图谱 / 突击 / 看板 / 排行 / 预警（docs/api.md §11）===== */

/** 图谱节点状态（docs/api.md §11.1；叶子实时状态 / 父节点聚合） */
export type GraphNodeStatus = "mastered" | "weak" | "consolidating" | "untouched";

/** 知识点图谱节点（章 level=1 / 节 level=2 / 知识点 level=3） */
export interface GraphNode {
  id: string;
  name: string;
  level: number;
  status: GraphNodeStatus;
  /** 该节点（子树）题量 */
  question_count: number;
  /** 仅叶子有练习记录时返回 */
  practice_count?: number;
  /** 仅叶子有练习记录时返回（0~1，未接触为 null） */
  accuracy?: number | null;
  children?: GraphNode[];
}

/** GET /subjects/{id}/knowledge-graph 响应（§11.1） */
export interface KnowledgeGraphResponse {
  subject_id: string;
  subject_name: string;
  generated_at: string;
  root: GraphNode;
  stats: {
    total_nodes: number;
    leaf_count: number;
    mastered_count: number;
    weak_count: number;
    consolidating_count: number;
    untouched_count: number;
  };
}

/* ===== M3 考前突击（§11.2 / §11.3）===== */

export interface SprintSession {
  id: string;
  subject_id: string;
  status: string; // active
  activated_at: string;
  auto_activated: boolean;
  exam_date: string | null;
  days_left: number | null;
  expires_at: string | null;
}

export interface SprintActivateResult {
  sprint: SprintSession;
  created: boolean;
}

export interface HighFreqKp {
  id: string;
  name: string;
  heat: number;
  avg_accuracy: number;
  has_past_exam: boolean;
}

export interface SprintSummary {
  high_freq_questions: number;
  wrong_review_questions: number;
  deduped: number;
  total: number;
}

export interface SprintMockMeta {
  duration_min: number;
  total_score: number;
  started_at: string | null;
}

/** GET /subjects/{id}/sprint/questions 响应（§11.3） */
export interface SprintQuestionsResponse {
  sprint_id: string;
  status: string;
  days_left: number | null;
  high_freq_kps: HighFreqKp[];
  /** QuestionPublic（不含 answer/analysis；tag: high_freq | wrong_review） */
  items: Question[];
  summary: SprintSummary;
  mock: SprintMockMeta | null;
}

/* ===== M3 学习数据看板（§11.4 / §11.5）===== */

export interface DashboardSummary {
  totals: { questions_practiced: number; correct_count: number; accuracy: number };
  mastery: { leaf_total: number; mastered: number; mastery_pct: number };
  streak: { current: number; longest: number };
  weak_points: { weak: number; consolidating: number };
  per_subject: {
    subject_id: string;
    subject_name: string;
    questions_practiced: number;
    correct_count: number;
    accuracy: number;
    mastery_pct: number;
  }[];
  exam: { has_active_plan: boolean; days_left: number | null };
}

export interface TrendItem {
  bucket_start: string;
  questions_practiced: number;
  correct_count: number;
  /** 桶无做题记录为 null */
  accuracy: number | null;
  mastered_kp_count: number;
  mastery_pct: number;
}

export interface TrendResponse {
  granularity: string;
  items: TrendItem[];
}

/* ===== M3 排行榜（§11.6）===== */

export interface LeaderboardItem {
  rank: number;
  user_id: string;
  username: string;
  total_correct: number;
  questions_practiced: number;
  accuracy: number;
  current_streak: number;
}

export interface LeaderboardResponse {
  scope: string;
  items: LeaderboardItem[];
  page: number;
  page_size: number;
  total: number;
  /** 当前用户（不在榜时 rank=null 但附统计） */
  me: {
    rank: number | null;
    total_correct: number;
    questions_practiced: number;
    accuracy: number;
  } | null;
}

/* ===== M3 挂科预警（§11.7）===== */

export type RiskLevel = "high" | "medium" | "low";

export interface WarningItem {
  knowledge_point_id: string;
  knowledge_point_name: string;
  risk_level: RiskLevel;
  /** 规则层确定性理由 */
  reasons: string[];
  /** LLM（flash）措辞 */
  suggestion: string;
  days_left: number | null;
  accuracy: number | null;
  practice_count: number;
}

export interface WarningsResponse {
  overall_risk: RiskLevel | null;
  items: WarningItem[];
  generated_at: string;
}
