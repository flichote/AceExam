import type { Question } from "@/types";
import { request, USE_MOCK } from "@/utils/request";
import { mockQuestions } from "@/mock/questions";

/**
 * 刷题 API
 * 对接点：GET /api/v1/subjects/{subjectId}/questions
 * 约定：作答前不返回 answer / explanation（ADR-0002 / docs/architecture.md）
 */
export async function fetchQuestions(subjectId: string): Promise<Question[]> {
  if (USE_MOCK) {
    return mockQuestions().filter((q) => q.subjectId === subjectId);
  }
  const data = await request<Question[]>({
    url: `/subjects/${subjectId}/questions`,
    method: "GET",
  });
  return data;
}

/** 提交答案：mock 阶段本地判对错；真实阶段由后端返回 answer + explanation */
export async function submitAnswer(
  questionId: string,
  selected: string[]
): Promise<{ correct: boolean; answer: string[]; explanation: string }> {
  // TODO(ep-backend): POST /api/v1/questions/{id}/submit，请求体 { selected }
  if (USE_MOCK) {
    const q = mockQuestions().find((item) => item.id === questionId);
    const answer = q?.answer ?? [];
    const correct = answer.length === selected.length && answer.every((k) => selected.includes(k));
    return { correct, answer, explanation: q?.explanation ?? "" };
  }
  const data = await request<{ correct: boolean; answer: string[]; explanation: string }>({
    url: `/questions/${questionId}/submit`,
    method: "POST",
    data: { selected },
  });
  return data;
}
