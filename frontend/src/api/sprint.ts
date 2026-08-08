import type { SprintActivateResult, SprintQuestionsResponse } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockSprintActivate, mockSprintQuestions } from "@/mock/sprint";

/**
 * 考前突击 API（docs/api.md §11.2 / §11.3）
 *  - POST /subjects/{subject_id}/sprint/activate   手动激活（幂等；会员功能，免费 403）
 *  - GET /subjects/{subject_id}/sprint/questions   突击题单（days_left ≤ 7 自动激活）
 * 答题流程复用现有刷题链路（POST /questions/{id}/answers，见 api/practice.ts）
 */

/** 手动激活突击（403 PAYMENT_REQUIRED 时前端展示会员引导） */
export async function activateSprint(subjectId: string): Promise<SprintActivateResult> {
  return withFallback(
    () =>
      request<SprintActivateResult>({
        url: `/subjects/${subjectId}/sprint/activate`,
        method: "POST",
        data: {},
      }),
    () => mockSprintActivate(subjectId),
    undefined,
    { write: true } // POST 写操作失败不降级 mock
  );
}

export interface FetchSprintOptions {
  /** review 混合题单 / mock 模拟卷 */
  mode?: "review" | "mock";
  /** 题量 1..50（题池不足返回实际数量） */
  count?: number;
}

export async function fetchSprintQuestions(
  subjectId: string,
  opts: FetchSprintOptions = {}
): Promise<SprintQuestionsResponse> {
  const query: string[] = [];
  query.push(`mode=${opts.mode ?? "review"}`);
  if (opts.count) query.push(`count=${opts.count}`);
  const qs = query.length ? `?${query.join("&")}` : "";

  return withFallback(
    () =>
      request<SprintQuestionsResponse>({
        url: `/subjects/${subjectId}/sprint/questions${qs}`,
        method: "GET",
      }),
    () => mockSprintQuestions(subjectId, opts)
  );
}
