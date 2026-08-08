import type {
  QuestionOption,
  QuestionType,
  UgcSubmitResult,
  UgcUploadResult,
  UgcStatusResponse,
} from "@/types";
import { request, withFallback, USE_MOCK } from "@/utils/request";
import { mockUgcSubmit, mockUgcUpload, mockUgcStatus } from "@/mock/ugc";

/**
 * UGC 题库共建 API
 *  - POST /questions/ugc  M3.5 投稿（docs/api.md §12.3，兼容旧客户端；进审核流 status=pending）
 *  - POST /ugc/upload     M5 投稿（docs/api.md §14.4，内置 AI 初审：verdict + confidence + reasons）
 *  - GET /ugc/status      M5 审核状态查询（docs/api.md §14.5，仅本人投稿，可 status 过滤）
 * 写操作不降级 mock（4xx 业务错误如实抛出），仅 USE_MOCK 演示模式顶替。
 */

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface UgcSubmitPayload {
  subject_id: string;
  knowledge_point_id: string;
  type: QuestionType;
  content: string;
  options: QuestionOption[];
  answer: string;
  analysis?: string;
  /** 拍照识别来源的 upload_id；手动录入传 null */
  ocr_upload_id?: string | null;
}

/** M5 POST /ugc/upload 请求体（§14.4）：UgcSubmitPayload + skip_ai_review */
export interface UgcUploadPayload extends UgcSubmitPayload {
  /** 默认 false；true = 跳过 AI 初审（管理端/测试用） */
  skip_ai_review?: boolean;
}

/** M3.5 POST /questions/ugc（保留：旧客户端/个人录题兼容） */
export async function submitUgcQuestion(
  payload: UgcSubmitPayload
): Promise<UgcSubmitResult> {
  if (USE_MOCK) {
    await delay(500);
    return mockUgcSubmit();
  }
  return request<UgcSubmitResult>({
    url: "/questions/ugc",
    method: "POST",
    data: { ...payload },
  });
}

/** M5 POST /ugc/upload：投稿 + AI 初审（推荐入口，docs/api.md §14.4） */
export async function submitUgcUpload(
  payload: UgcUploadPayload
): Promise<UgcUploadResult> {
  if (USE_MOCK) {
    await delay(800);
    return mockUgcUpload();
  }
  return request<UgcUploadResult>({
    url: "/ugc/upload",
    method: "POST",
    data: { ...payload, skip_ai_review: payload.skip_ai_review ?? false },
  });
}

/** M5 GET /ugc/status：我的投稿审核状态（仅本人，status 可选过滤） */
export async function fetchUgcStatus(params: {
  status?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<UgcStatusResponse> {
  const data: Record<string, unknown> = { page: params.page ?? 1, page_size: params.page_size ?? 20 };
  if (params.status) data.status = params.status;
  return withFallback(
    () =>
      request<UgcStatusResponse>({
        url: "/ugc/status",
        method: "GET",
        data,
      }),
    () => mockUgcStatus(params)
  );
}
