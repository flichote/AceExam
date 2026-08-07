import type { DashboardSummary, TrendResponse, TrendItem } from "@/types";

/**
 * 学习数据看板 mock（docs/api.md §11.4 / §11.5）
 * TODO(ep-backend): GET /me/dashboard + GET /me/dashboard/trend 就绪后移除
 */

export function mockDashboard(): DashboardSummary {
  return {
    totals: { questions_practiced: 1280, correct_count: 940, accuracy: 0.734 },
    mastery: { leaf_total: 28, mastered: 9, mastery_pct: 0.321 },
    streak: { current: 5, longest: 12 },
    weak_points: { weak: 6, consolidating: 4 },
    per_subject: [
      { subject_id: "advanced-math", subject_name: "高等数学（上）", questions_practiced: 680, correct_count: 470, accuracy: 0.691, mastery_pct: 0.32 },
      { subject_id: "english", subject_name: "大学英语（四）", questions_practiced: 420, correct_count: 330, accuracy: 0.786, mastery_pct: 0.45 },
      { subject_id: "linear-algebra", subject_name: "线性代数", questions_practiced: 180, correct_count: 140, accuracy: 0.778, mastery_pct: 0.15 },
    ],
    exam: { has_active_plan: true, days_left: 7 },
  };
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function mockTrend(days = 30): TrendResponse {
  const items: TrendItem[] = [];
  const today = new Date();
  let mastered = 4;
  let practicedTotal = 0;
  let correctTotal = 0;
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(today.getTime() - i * 86400000);
    const bucket = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    // 周末做题少、周中多；最近几天贴近真实状态
    const weekend = d.getDay() === 0 || d.getDay() === 6;
    const practiced = weekend ? Math.round(Math.random() * 15 + 10) : Math.round(Math.random() * 30 + 20);
    const correct = Math.round(practiced * (0.6 + Math.random() * 0.25));
    practicedTotal += practiced;
    correctTotal += correct;
    // 掌握度单调不减（as-of 近似）
    if (i % 6 === 0 && mastered < 12) mastered += 1;
    items.push({
      bucket_start: bucket,
      questions_practiced: practiced,
      correct_count: correct,
      accuracy: practiced > 0 ? correct / practiced : null,
      mastered_kp_count: mastered,
      mastery_pct: mastered / 28,
    });
  }
  return { granularity: "day", items };
}
