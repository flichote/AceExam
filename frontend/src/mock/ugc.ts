import type {
  UgcSubmitResult,
  UgcUploadResult,
  UgcStatusResponse,
} from "@/types";

/**
 * UGC 投稿 mock
 * TODO(ep-backend): POST /questions/ugc、POST /ugc/upload、GET /ugc/status 就绪后移除
 */

export function mockUgcSubmit(): UgcSubmitResult {
  return {
    question_id: `ugc-${Date.now()}`,
    status: "pending",
    duplicated: false,
  };
}

/** M5 POST /ugc/upload mock：AI 初审通过（verdict=pass, confidence 0.9） */
export function mockUgcUpload(): UgcUploadResult {
  return {
    question_id: `ugc-${Date.now()}`,
    status: "pending",
    duplicated: false,
    ai_review: {
      verdict: "pass",
      confidence: 0.9,
      reasons: ["题干完整", "答案自算一致", "知识点归属正确"],
    },
  };
}

const STATUS_SEED: UgcStatusResponse["items"] = [
  {
    question_id: "ugc-1001",
    subject_id: "advanced-math",
    subject_name: "高等数学",
    knowledge_point_id: "kp-lhopital",
    knowledge_point_name: "洛必达法则",
    type: "single",
    content: "求极限 lim(x→0) (sin x)/x，下列结果正确的是（）",
    status: "pending",
    reject_reason: null,
    ai_review: {
      verdict: "pass",
      confidence: 0.92,
      reasons: ["题干完整", "答案自算一致"],
    },
    submitted_at: "2026-08-08T09:30:00Z",
    reviewed_at: null,
  },
  {
    question_id: "ugc-1000",
    subject_id: "english",
    subject_name: "大学英语",
    knowledge_point_id: "kp-reading",
    knowledge_point_name: "阅读理解",
    type: "single",
    content: "According to the passage, the author believes that …",
    status: "active",
    reject_reason: null,
    ai_review: {
      verdict: "pass",
      confidence: 0.88,
      reasons: ["题干完整", "答案自算一致"],
    },
    submitted_at: "2026-08-07T18:00:00Z",
    reviewed_at: "2026-08-08T02:00:00Z",
  },
  {
    question_id: "ugc-0999",
    subject_id: "advanced-math",
    subject_name: "高等数学",
    knowledge_point_id: "kp-lim",
    knowledge_point_name: "极限",
    type: "blank",
    content: "函数 f(x)=1/x 在 x→0 时的极限是____",
    status: "rejected",
    reject_reason: "[AI:flag] 答案自算不一致：该极限不存在（无穷大）",
    ai_review: {
      verdict: "flag",
      confidence: 0.74,
      reasons: ["答案自算不一致", "题干未限定单侧极限"],
    },
    submitted_at: "2026-08-06T20:00:00Z",
    reviewed_at: "2026-08-07T10:00:00Z",
  },
];

/** M5 GET /ugc/status mock：默认全量，可按 status 过滤 */
export function mockUgcStatus(params: {
  status?: string;
  page?: number;
  page_size?: number;
} = {}): UgcStatusResponse {
  const items = params.status
    ? STATUS_SEED.filter((it) => it.status === params.status)
    : STATUS_SEED;
  return {
    items,
    page: params.page ?? 1,
    page_size: params.page_size ?? 20,
    total: items.length,
  };
}
