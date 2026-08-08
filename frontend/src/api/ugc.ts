import type { QuestionOption, QuestionType, UgcSubmitResult } from "@/types";
import { request, USE_MOCK } from "@/utils/request";
import { mockUgcSubmit } from "@/mock/ugc";

/**
 * UGC 题库共建 API（docs/api.md §12.3）
 *  - POST /questions/ugc  提交待审题（content ≥ 15 字；重复 → 409 DUPLICATE）
 * 与 /questions/from-ocr 的区别：UGC 进审核流（status=pending），from-ocr 个人直入库（active）。
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
