import type { ClassInfo, JoinClassResult, MyClassResponse } from "@/types";
import { request, USE_MOCK, withFallback } from "@/utils/request";
import { mockJoinClass, mockMyClass } from "@/mock/classroom";

/**
 * 班级 API（docs/api.md §12.6 / §12.7）
 *  - POST /me/class   建班 { name } 或加入 { invite_code }（二选一）
 *  - GET  /me/class   我的班级 + 班内名次
 * 班级榜 scope=class 见 api/leaderboard.ts（§12.7 修订）。
 */

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface JoinClassPayload {
  /** 建班：班级名（与 invite_code 二选一） */
  name?: string;
  /** 加入：6 位邀请码（与 name 二选一） */
  invite_code?: string;
}

export async function joinClass(payload: JoinClassPayload): Promise<JoinClassResult> {
  if (USE_MOCK) {
    await delay(500);
    return mockJoinClass(payload);
  }
  // 写操作不降级 mock：404（邀请码不存在）/ 422（参数非法）如实抛出
  return request<JoinClassResult>({
    url: "/me/class",
    method: "POST",
    data: { ...payload },
  });
}

/** 我的班级（读操作：真实失败降级 mock） */
export async function fetchMyClass(): Promise<MyClassResponse> {
  return withFallback(
    () => request<MyClassResponse>({ url: "/me/class", method: "GET" }),
    () => mockMyClass()
  );
}

export type { ClassInfo };
