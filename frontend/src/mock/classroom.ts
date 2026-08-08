import type { ClassInfo, JoinClassResult, MyClassResponse } from "@/types";

/**
 * 班级 mock（docs/api.md §12.6 / §12.7）
 * TODO(ep-backend): POST/GET /me/class 就绪后移除。
 * 模块内持状态：初始未加入 → 演示「加入班级」完整流程；
 * 建班/加入后，排行榜 mock（mock/leaderboard scope=class）可读到班级。
 */

let mockClass: ClassInfo | null = null; // 初始 null = 未加入（演示加入流程）

export function getMockClass(): ClassInfo | null {
  return mockClass;
}

export function mockMyClass(): MyClassResponse {
  if (!mockClass) return { class: null, my_rank: null };
  return {
    class: mockClass,
    my_rank: { rank: 3, total_correct: 180 },
  };
}

export function mockJoinClass(payload: {
  name?: string;
  invite_code?: string;
}): JoinClassResult {
  if (payload.name) {
    mockClass = {
      id: "class-001",
      name: payload.name,
      invite_code: "A1B2C3",
      member_count: 12,
      is_creator: true,
    };
  } else {
    mockClass = {
      id: "class-001",
      name: "计科2301",
      invite_code: null,
      member_count: 12,
      is_creator: false,
    };
  }
  return { class: mockClass, joined: true };
}
