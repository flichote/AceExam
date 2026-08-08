import type { Question, PracticeResponse, AnswerResult, QuestionType } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockQuestions } from "@/mock/questions";

/**
 * 刷题 API（docs/api.md §3.2 / §3.3）
 *  - GET /subjects/{subject_id}/practice/questions  自适应选题（M2 新增）
 *  - POST /questions/{question_id}/answers          完整作答链路（M2 新增，取代 /submit）
 */

export interface FetchPracticeOptions {
  count?: number;
  /** 会话内已展示题 id，防重复 */
  excludeIds?: string[];
  knowledgePointId?: string;
  difficulty?: number;
}

export async function fetchPracticeQuestions(
  subjectId: string,
  opts: FetchPracticeOptions = {}
): Promise<PracticeResponse> {
  const query: string[] = [];
  if (opts.count) query.push(`count=${opts.count}`);
  if (opts.knowledgePointId) query.push(`knowledge_point_id=${opts.knowledgePointId}`);
  if (opts.difficulty) query.push(`difficulty=${opts.difficulty}`);
  (opts.excludeIds || []).forEach((id) => query.push(`exclude_ids=${id}`));
  const qs = query.length ? `?${query.join("&")}` : "";

  return withFallback(
    () =>
      request<PracticeResponse>({
        url: `/subjects/${subjectId}/practice/questions${qs}`,
        method: "GET",
      }),
    () => {
      // mock 自适应选题：科目过滤 + 排除已见 + 生成可解释策略
      let items = mockQuestions().filter((q) => q.subjectId === subjectId);
      if (opts.excludeIds?.length) {
        items = items.filter((q) => !(opts.excludeIds as string[]).includes(q.id));
      }
      const kpNames = Array.from(new Set(items.map((q) => q.knowledgePoint)));
      return {
        items,
        strategy: {
          target_kps: kpNames.slice(0, 3).map((name, i) => ({
            id: `kp-${i}`,
            name,
            level: 3,
            status: "weak",
            score: 78.5 - i * 10,
            reason: "正确率偏低，薄弱优先",
          })),
          weights: { status: 50, error: 35, recency: 10, difficulty: 5 },
          requested_at: new Date().toISOString(),
        },
      };
    }
  );
}

/** 按题型构造 answer 信封（docs/api.md §3.3：single="C" / multi=["A","C"] / blank="3" / essay=文本） */
export function buildAnswerValue(
  type: QuestionType,
  selected: string[],
  blankInput: string
): { type: QuestionType; value: string | string[] } {
  if (type === "single") return { type, value: selected[0] ?? "" };
  if (type === "multiple") return { type, value: selected };
  return { type, value: blankInput };
}

export async function submitQuestionAnswer(
  questionId: string,
  answer: { type: QuestionType; value: string | string[] },
  timeSpentSeconds: number,
  source: "practice" | "review" = "practice"
): Promise<AnswerResult> {
  return withFallback(
    () =>
      request<AnswerResult>({
        url: `/questions/${questionId}/answers`,
        method: "POST",
        data: { answer, time_spent_seconds: timeSpentSeconds, source },
      }),
    () => {
      // mock 本地判对错（M1 行为保留）
      const q = mockQuestions().find((item) => item.id === questionId);
      const correctKeys = q?.answer ?? [];
      const selected = Array.isArray(answer.value) ? answer.value : [answer.value];
      const correct =
        correctKeys.length === selected.length && correctKeys.every((k) => selected.includes(k));
      return {
        correct,
        correct_answer: q?.type === "multiple" ? correctKeys : (correctKeys[0] ?? ""),
        analysis: q?.explanation ?? "",
        knowledge_point: {
          id: q?.knowledgePointId ?? "kp-1",
          name: q?.knowledgePoint ?? "知识点",
          level: q?.difficulty ?? 3,
        },
        knowledge_state: {
          status: correct ? "consolidating" : "weak",
          correct_count: correct ? 1 : 0,
          wrong_count: correct ? 0 : 1,
          streak: 0,
        },
        explanation_available: true,
      };
    },
    undefined,
    { write: true } // POST 提交答案失败不降级 mock
  );
}
