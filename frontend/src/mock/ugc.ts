import type { UgcSubmitResult } from "@/types";

/**
 * UGC 投稿 mock（docs/api.md §12.3）
 * TODO(ep-backend): POST /questions/ugc 就绪后移除。
 */

export function mockUgcSubmit(): UgcSubmitResult {
  return {
    question_id: `ugc-${Date.now()}`,
    status: "pending",
    duplicated: false,
  };
}
