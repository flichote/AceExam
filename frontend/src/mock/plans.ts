import type { ActivePlanResponse, CheckinResult, Plan, TodayTask } from "@/types";

/**
 * 备考计划 mock（docs/api.md §8）
 * TODO(ep-backend): POST /plans + GET /plans/active + POST /plans/{id}/checkin 就绪后移除
 */

function daysFromNow(n: number): string {
  const d = new Date(Date.now() + n * 86400000);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function mockPlan(): Plan {
  return {
    id: "mock-plan-1",
    subject_id: "advanced-math",
    title: "期末冲刺计划",
    exam_date: daysFromNow(21),
    days_left: 21,
    status: "active",
    daily_question_target: 10,
  };
}

function mockTodayTask(checkedIn = false): TodayTask {
  return {
    date: daysFromNow(0),
    target_questions: 10,
    focus_kps: [
      { id: "kp-lhopital", name: "洛必达法则", reason: "薄弱，正确率 25%" },
      { id: "kp-integral", name: "定积分", reason: "薄弱，正确率 40%" },
    ],
    type: "weak_practice",
    reason: "距考试 21 天，优先巩固薄弱点",
    done: { questions_practiced: 3, correct_count: 2, checked_in: checkedIn },
  };
}

export function mockCreatePlan(): ActivePlanResponse {
  return {
    plan: mockPlan(),
    today_task: mockTodayTask(false),
    upcoming: [
      {
        date: daysFromNow(1),
        target_questions: 10,
        focus_kps: [{ id: "kp-lhopital", name: "洛必达法则" }],
        type: "weak_practice",
      },
    ],
    weak_kps: [
      { id: "kp-lhopital", name: "洛必达法则", level: 3, status: "weak", accuracy: 0.25 },
      { id: "kp-integral", name: "定积分", level: 3, status: "weak", accuracy: 0.4 },
      { id: "kp-deriv", name: "导数", level: 2, status: "consolidating", accuracy: 0.55 },
    ],
  };
}

export function mockActivePlan(): ActivePlanResponse {
  return {
    plan: mockPlan(),
    today_task: mockTodayTask(false),
    upcoming: [
      {
        date: daysFromNow(1),
        target_questions: 10,
        focus_kps: [{ id: "kp-lhopital", name: "洛必达法则" }],
        type: "weak_practice",
      },
    ],
    weak_kps: [
      { id: "kp-lhopital", name: "洛必达法则", level: 3, status: "weak", accuracy: 0.25 },
      { id: "kp-integral", name: "定积分", level: 3, status: "weak", accuracy: 0.4 },
      { id: "kp-deriv", name: "导数", level: 2, status: "consolidating", accuracy: 0.55 },
    ],
  };
}

export function mockCheckin(): CheckinResult {
  return {
    checked_in: true,
    already_checked_in: false,
    session: {
      session_date: daysFromNow(0),
      questions_practiced: 3,
      correct_count: 2,
      checked_in: true,
      checked_in_at: new Date().toISOString(),
    },
  };
}
