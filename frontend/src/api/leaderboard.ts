import type { LeaderboardResponse } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockLeaderboard } from "@/mock/leaderboard";

/**
 * 排行榜 API（docs/api.md §11.6）
 *  - GET /leaderboard?scope=global|subject&subject_id=&page=&page_size=
 * 口径：主排序 total_correct 降序，次排序 accuracy（样本 ≥ 30 题）；<30 题不进榜。
 */

export interface FetchLeaderboardOptions {
  scope?: "global" | "subject";
  subjectId?: string;
  page?: number;
  pageSize?: number;
}

export async function fetchLeaderboard(
  opts: FetchLeaderboardOptions = {}
): Promise<LeaderboardResponse> {
  const query: string[] = [];
  query.push(`scope=${opts.scope ?? "global"}`);
  if (opts.subjectId) query.push(`subject_id=${opts.subjectId}`);
  query.push(`page=${opts.page ?? 1}`);
  query.push(`page_size=${opts.pageSize ?? 20}`);
  const qs = query.join("&");

  return withFallback(
    () => request<LeaderboardResponse>({ url: `/leaderboard?${qs}`, method: "GET" }),
    () => mockLeaderboard(opts)
  );
}
