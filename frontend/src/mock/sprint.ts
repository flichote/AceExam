import type {
  SprintActivateResult,
  SprintQuestionsResponse,
  Question,
} from "@/types";
import { mockQuestions } from "@/mock/questions";

/**
 * 考前突击 mock（docs/api.md §11.2 / §11.3）
 * TODO(ep-backend): POST /subjects/{id}/sprint/activate + GET /subjects/{id}/sprint/questions 就绪后移除
 * mock 题单 = 高频考点题 ∪ 个人错题（交集去重、限量）；items 不含 answer（契约 §3.2）。
 */

function daysFromNow(n: number): string {
  const d = new Date(Date.now() + n * 86400000);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export function mockSprintActivate(subjectId: string): SprintActivateResult {
  return {
    sprint: {
      id: `mock-sprint-${Date.now()}`,
      subject_id: subjectId,
      status: "active",
      activated_at: new Date().toISOString(),
      auto_activated: false,
      exam_date: daysFromNow(7),
      days_left: 7,
      expires_at: daysFromNow(7),
    },
    created: true,
  };
}

export function mockSprintQuestions(
  subjectId: string,
  opts: { mode?: "review" | "mock"; count?: number } = {}
): SprintQuestionsResponse {
  const mode = opts.mode ?? "review";
  const count = opts.count ?? 20;
  const all = mockQuestions().filter((q) => q.subjectId === subjectId);
  const items: Question[] = all.slice(0, Math.min(count, all.length)).map((q) => {
    // 契约：题单不含 answer / explanation；附 tag 供前端展示「本卷含 N 道错题」
    const { answer: _answer, explanation: _explanation, ...rest } = q;
    return { ...rest, source: q.source ?? "seed" } as Question;
  });

  return {
    sprint_id: `mock-sprint-${Date.now()}`,
    status: "active",
    days_left: 7,
    high_freq_kps: [
      { id: "kp-lhopital", name: "洛必达法则", heat: 128, avg_accuracy: 0.42, has_past_exam: true },
      { id: "kp-deriv-chain", name: "链式法则", heat: 96, avg_accuracy: 0.5, has_past_exam: true },
      { id: "kp-int-parts", name: "分部积分法", heat: 81, avg_accuracy: 0.6, has_past_exam: false },
    ],
    items,
    summary: {
      high_freq_questions: Math.max(0, items.length - 2),
      wrong_review_questions: Math.min(2, items.length),
      deduped: 2,
      total: items.length,
    },
    mock:
      mode === "mock"
        ? { duration_min: 120, total_score: 100, started_at: null }
        : null,
  };
}
