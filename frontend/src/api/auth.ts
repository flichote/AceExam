import type { LoginResult, UserProfile } from "@/types";
import { request, withFallback, setToken } from "@/utils/request";

/**
 * 鉴权 API（docs/api.md §1）
 *  - POST /auth/register 注册（公开，201 创建 + 直接发 token）
 *  - POST /auth/login    登录（公开）
 *  - GET /auth/me        当前用户（登录）
 */

export async function register(username: string, password: string): Promise<LoginResult> {
  const result = await withFallback(
    () =>
      request<LoginResult>({
        url: "/auth/register",
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
        major: "",
        role: "student",
        is_member: false,
        member_expires_at: null,
        created_at: new Date().toISOString(),
      },
    }),
    "服务暂不可用，请稍后再试",
    { write: true } // POST 注册失败不降级 mock（用户名冲突等要如实报错）
  );
  setToken(result.access_token);
  return result;
}

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
        major: "计算机科学与技术",
        role: "student",
        is_member: false,
        member_expires_at: null,
        created_at: new Date().toISOString(),
      },
    }),
    "服务暂不可用，已加载演示数据",
    { write: true } // POST 登录失败不降级 mock（否则假装登录成功）
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
      major: "计算机科学与技术",
      role: "student",
      is_member: false,
      member_expires_at: null,
      created_at: new Date().toISOString(),
    })
  );
}
