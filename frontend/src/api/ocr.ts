import type { OcrUploadResult, OcrStructured } from "@/types";
import { BASE_URL, getToken, request, USE_MOCK, toApiError } from "@/utils/request";
import { mockOcrUpload, mockOcrConfirm } from "@/mock/ocr";

/**
 * 拍照录题 API（docs/api.md §6）
 *  - POST /ocr/upload（multipart：file + subject_id + source）
 *  - GET /ocr/upload/{upload_id}（202 pending 时轮询）
 *  - POST /questions/from-ocr（确认入库）
 */

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** 上传照片 → 识别结果（200 parsed / 202 pending；failed 时前端提示重拍） */
export async function uploadOcrImage(
  filePath: string,
  subjectId: string,
  source: "photo" | "album" = "photo"
): Promise<OcrUploadResult> {
  if (USE_MOCK) {
    await delay(600);
    return mockOcrUpload();
  }
  try {
    return await realUpload(filePath, subjectId, source);
  } catch (e) {
    if ((e as { status?: number })?.status === 0) {
      uni.showToast({ title: "服务暂不可用，已加载演示识别结果", icon: "none" });
      return mockOcrUpload();
    }
    throw e;
  }
}

function realUpload(
  filePath: string,
  subjectId: string,
  source: "photo" | "album"
): Promise<OcrUploadResult> {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: BASE_URL + "/ocr/upload",
      filePath,
      name: "file",
      formData: { subject_id: subjectId, source },
      header: { Authorization: `Bearer ${getToken()}` },
      success: (res) => {
        let body: OcrUploadResult & { message?: string; code?: string };
        try {
          body = JSON.parse(res.data as string);
        } catch {
          reject(toApiError("上传响应解析失败", res.statusCode));
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(body);
        } else {
          reject(toApiError(body?.message || `上传失败(${res.statusCode})`, res.statusCode, body?.code));
        }
      },
      fail: (err) => reject(toApiError(err.errMsg || "上传失败", 0)),
    });
  });
}

/** pending 轮询（§6.2），最多 maxTries 次 */
export async function pollOcrUpload(
  uploadId: string,
  maxTries = 10,
  intervalMs = 1500
): Promise<OcrUploadResult> {
  for (let i = 0; i < maxTries; i++) {
    const res = await request<OcrUploadResult>({ url: `/ocr/upload/${uploadId}`, method: "GET" });
    if (res.status === "parsed" || res.status === "failed") return res;
    await delay(intervalMs);
  }
  throw toApiError("识别超时，请重试", 0, "OCR_TIMEOUT");
}

export interface ConfirmOcrPayload {
  upload_id: string;
  subject_id: string;
  knowledge_point_id: string;
  structured: OcrStructured;
  /** 答案置信度过低时可置 false 跳过答案入库 */
  confirm_answer: boolean;
}

export async function confirmOcrQuestion(
  payload: ConfirmOcrPayload
): Promise<{ question_id: string; upload_id: string; status: string; duplicated: boolean }> {
  if (USE_MOCK) {
    await delay(400);
    return mockOcrConfirm();
  }
  return request({ url: "/questions/from-ocr", method: "POST", data: { ...payload } });
}
