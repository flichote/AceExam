import type { SelfTestResult, DiagnosisReport } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockStartSelfTest, mockDiagnosisReport } from "@/mock/diagnose";

/**
 * 摸底诊断 API（docs/api.md §7）
 *  - POST /diagnose/self-test           发起自测（10 题快读定位）
 *  - GET /diagnose/self-test/{report_id} 取题/状态
 *  - POST /diagnose/report              提交自测 → 诊断报告（薄弱 Top5 + 建议）
 */

export async function startSelfTest(subjectId: string, count = 10): Promise<SelfTestResult> {
  return withFallback(
    () =>
      request<SelfTestResult>({
        url: "/diagnose/self-test",
        method: "POST",
        data: { subject_id: subjectId, count, include_weak: true },
      }),
    () => mockStartSelfTest()
  );
}

export async function fetchSelfTest(reportId: string): Promise<SelfTestResult> {
  return withFallback(
    () =>
      request<SelfTestResult>({
        url: `/diagnose/self-test/${reportId}`,
        method: "GET",
      }),
    () => mockStartSelfTest()
  );
}

export interface DiagnosisAnswer {
  question_id: string;
  answer: string | string[];
}

export async function submitDiagnosis(
  reportId: string,
  answers: DiagnosisAnswer[]
): Promise<DiagnosisReport> {
  return withFallback(
    () =>
      request<DiagnosisReport>({
        url: "/diagnose/report",
        method: "POST",
        data: { report_id: reportId, answers },
      }),
    () => mockDiagnosisReport()
  );
}
