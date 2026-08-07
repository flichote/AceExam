import type { WarningsResponse } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockWarnings } from "@/mock/warnings";

/**
 * 挂科预警 API（docs/api.md §11.7）
 *  - GET /me/warnings?subject_id=   风险列表（高/中/低徽章 + 理由 + 建议）
 * 规则层确定性计算等级，LLM 只生成 suggestion 措辞。
 */

export async function fetchWarnings(subjectId?: string): Promise<WarningsResponse> {
  const qs = subjectId ? `?subject_id=${subjectId}` : "";
  return withFallback(
    () => request<WarningsResponse>({ url: `/me/warnings${qs}`, method: "GET" }),
    () => mockWarnings()
  );
}
