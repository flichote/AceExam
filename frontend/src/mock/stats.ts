import type { PracticeStat } from "@/types";

/**
 * 我的-学习数据看板 mock
 * TODO(ep-backend): GET /api/v1/me/stats 就绪后移除
 */
export function mockPracticeStat(): PracticeStat {
  return {
    total: 342,
    correct: 271,
    accuracy: 79,
    streak: 7,
    week: [
      { day: "一", count: 32 },
      { day: "二", count: 45 },
      { day: "三", count: 28 },
      { day: "四", count: 56 },
      { day: "五", count: 40 },
      { day: "六", count: 61 },
      { day: "日", count: 44 },
    ],
  };
}
