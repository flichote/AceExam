import type { ActivePlanResponse, CheckinResult } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockCreatePlan, mockActivePlan, mockCheckin } from "@/mock/plans";

/**
 * 备考计划 API（docs/api.md §8）
 *  - POST /plans               创建计划（考试科目 + 日期 + 每日题量）
 *  - GET /plans/active         今日任务 + 预告（首页）
 *  - POST /plans/{plan_id}/checkin  打卡（幂等）
 */

export interface CreatePlanPayload {
  subject_id: string;
  exam_date: string;
  daily_question_target: number;
  title?: string;
}

/** 创建计划 → 返回 plan + weak_kps 快照 + 今日任务 */
export async function createPlan(payload: CreatePlanPayload): Promise<ActivePlanResponse> {
  return withFallback(
    () =>
      request<ActivePlanResponse>({
        url: "/plans",
        method: "POST",
        data: {
          subject_id: payload.subject_id,
          exam_date: payload.exam_date,
          daily_question_target: payload.daily_question_target,
          title: payload.title || "期末冲刺计划",
        },
      }),
    () => mockCreatePlan(),
    undefined,
    { write: true } // POST 写操作失败不降级 mock
  );
}

/** 首页今日任务（无 active 计划返回 { plan: null, today_task: null, upcoming: [] }） */
export async function fetchActivePlan(subjectId?: string): Promise<ActivePlanResponse> {
  const qs = subjectId ? `?subject_id=${subjectId}` : "";
  return withFallback(
    () =>
      request<ActivePlanResponse>({
        url: `/plans/active${qs}`,
        method: "GET",
      }),
    () => mockActivePlan()
  );
}

export async function checkinPlan(planId: string): Promise<CheckinResult> {
  return withFallback(
    () =>
      request<CheckinResult>({
        url: `/plans/${planId}/checkin`,
        method: "POST",
        data: {},
      }),
    () => mockCheckin(),
    undefined,
    { write: true } // POST 写操作失败不降级 mock
  );
}
