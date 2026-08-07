import type { DashboardSummary, TrendResponse } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockDashboard, mockTrend } from "@/mock/dashboard";

/**
 * 学习数据看板 API（docs/api.md §11.4 / §11.5）
 *  - GET /me/dashboard            汇总（做题量 / 正确率 / 掌握度 / 连胜 / 薄弱计数 / 每科分解）
 *  - GET /me/dashboard/trend      时间序列（近 30 天做题量 + 正确率折线图数据）
 */

export async function fetchDashboard(subjectId?: string): Promise<DashboardSummary> {
  const qs = subjectId ? `?subject_id=${subjectId}` : "";
  return withFallback(
    () => request<DashboardSummary>({ url: `/me/dashboard${qs}`, method: "GET" }),
    () => mockDashboard()
  );
}

export interface FetchTrendOptions {
  days?: number;
  subjectId?: string;
  granularity?: "day" | "week" | "month";
}

export async function fetchDashboardTrend(
  opts: FetchTrendOptions = {}
): Promise<TrendResponse> {
  const query: string[] = [];
  if (opts.days) query.push(`days=${opts.days}`);
  if (opts.subjectId) query.push(`subject_id=${opts.subjectId}`);
  if (opts.granularity) query.push(`granularity=${opts.granularity}`);
  const qs = query.length ? `?${query.join("&")}` : "";

  return withFallback(
    () => request<TrendResponse>({ url: `/me/dashboard/trend${qs}`, method: "GET" }),
    () => mockTrend(opts.days ?? 30)
  );
}
