import type { LoginResult, UserProfile } from "@/types";
import { request, withFallback, setToken } from "@/utils/request";

/**
 * 鉴权 API（docs/api.md §1，M1 无变更）
 *  - POST /auth/login    登录（公开）
 *  - GET /auth/me        当前用户（登录）
 * M3 前最小实现：401 跳登录页可完成真实登录（后端就绪时），mock 兜底。
 */

export async function login(username: string, password: string): Promise<LoginResult> {
  const result = await withFallback(
    () =>
      request<LoginResult>({
        url: "/auth/login",
        method: "POST",
        data: { username, password },
        auth: false,
        redirectOn401: false,
      }),
    () => ({
      access_token: `mock-token-${Date.now()}`,
      refresh_token: "mock-refresh",
      user: {
        id: "mock-user",
        username,
        role: "student",
        is_member: false,
        member_expires_at: null,
        created_at: new Date().toISOString(),
      },
    })
  );
  setToken(result.access_token);
  return result;
}

export async function fetchMe(): Promise<UserProfile> {
  return withFallback(
    () => request<UserProfile>({ url: "/auth/me", method: "GET" }),
    () => ({
      id: "mock-user",
      username: "期末选手",
      role: "student",
      is_member: false,
      member_expires_at: null,
      created_at: new Date().toISOString(),
    })
  );
}
