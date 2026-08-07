import type { OcrUploadResult, OcrStructured } from "@/types";

/**
 * OCR 拍照录题 mock（docs/api.md §6）
 * TODO(ep-ai): POST /api/v1/ocr/upload 就绪后移除，见 api/ocr.ts
 */

/** 识别结果 canned（模拟 Pix2Text 输出的 Markdown/LaTeX） */
const mockStructured: OcrStructured = {
  type: "single",
  content: "求极限 $\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x}$ 的值：",
  options: [
    { key: "A", text: "$0$" },
    { key: "B", text: "$1$" },
    { key: "C", text: "$\\infty$" },
    { key: "D", text: "不存在" },
  ],
  answer: "B",
  analysis:
    "这是第一个重要极限：$\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x} = 1$。可由夹逼定理证明。",
  confidence: 0.87,
};

export function mockOcrUpload(): OcrUploadResult {
  return {
    upload_id: `mock-ocr-${Date.now()}`,
    status: "parsed",
    raw_text:
      "求极限 $\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x}$ 的值：\n\nA. 0  B. 1  C. ∞  D. 不存在\n\n（选项由识别生成，请核对）",
    structured: mockStructured,
    suggested_kps: [
      { id: "kp-lim", name: "极限", score: 0.93 },
      { id: "kp-deriv", name: "导数", score: 0.41 },
      { id: "kp-integral", name: "定积分", score: 0.22 },
    ],
  };
}

export function mockOcrConfirm(): {
  question_id: string;
  upload_id: string;
  status: "confirmed";
  duplicated: boolean;
} {
  return {
    question_id: `mock-ugc-${Date.now()}`,
    upload_id: `mock-ocr-${Date.now()}`,
    status: "confirmed",
    duplicated: false,
  };
}
