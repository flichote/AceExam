/**
 * 统一请求封装：uni.request 拦截 + token 注入 + 统一错误处理 + mock 降级
 *
 * 对接策略（T11 约定，见 docs/api.md §0）：
 *  - 主路径走真实 API；仅在网络错误 / 服务端 5xx 时降级到 mock（withFallback）
 *  - 设置 VITE_USE_MOCK=true 可强制走 mock（联调后端未启动时）
 *  - 401：清除 token 并跳登录页（pages/auth/login，M3 完整登录流程前的最小实现）
 *  - 业务 4xx：按错误码统一 toast（§0.2 错误码表）
 */
const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
  "http://127.0.0.1:8000/api/v1";

/** 强制 mock：env 显式 VITE_USE_MOCK=true 时生效；否则真实优先 + mock 兜底 */
export const USE_MOCK = (import.meta.env.VITE_USE_MOCK as string | undefined) === "true";

export const TOKEN_KEY = "aceexam_token";
export const LOGIN_PAGE = "/pages/auth/login";

export function getToken(): string {
  return (uni.getStorageSync(TOKEN_KEY) as string) || "";
}

export function setToken(token: string) {
  uni.setStorageSync(TOKEN_KEY, token);
}

export function clearToken() {
  uni.removeStorageSync(TOKEN_KEY);
}

export interface ApiError extends Error {
  status?: number;
  code?: string;
  detail?: unknown;
}

export function toApiError(message: string, status?: number, code?: string, detail?: unknown): ApiError {
  const e = new Error(message) as ApiError;
  e.status = status;
  e.code = code;
  e.detail = detail;
  return e;
}

/** 错误码 → 人话（docs/api.md §0.2） */
const ERROR_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: "参数有误，请检查后重试",
  UNAUTHORIZED: "登录已过期，请重新登录",
  FORBIDDEN: "没有权限执行此操作",
  PAYMENT_REQUIRED: "该功能为会员专享，开通会员后使用",
  NOT_FOUND: "资源不存在",
  ALREADY_EXISTS: "已存在，请勿重复提交",
  ALREADY_COMPLETED: "已提交过，请勿重复操作",
  UNPROCESSABLE_ENTITY: "提交内容与题型不符",
  RATE_LIMITED: "操作过于频繁，请稍后再试",
  INTERNAL_ERROR: "服务器开小差了，请稍后再试",
  RAG_NO_HIT: "教材库暂未覆盖该题目，已生成通用讲解",
  OCR_EMPTY: "未识别到有效题目，请重拍或手动录入",
};

export function mapErrorCode(code?: string): string {
  if (!code) return "请求失败";
  return ERROR_MESSAGES[code] || `请求失败（${code}）`;
}

export interface RequestOptions {
  url: string;
  method?: "GET" | "POST" | "PUT" | "DELETE";
  data?: Record<string, unknown>;
  header?: Record<string, string>;
  /** 是否自动注入 Authorization，默认 true */
  auth?: boolean;
  /** 是否显示全局 loading，默认 false */
  showLoading?: boolean;
  /** 401 时是否跳登录页（默认 true；登录接口自身传 false） */
  redirectOn401?: boolean;
}

interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
}

/** 401 统一处理：清 token + toast + 跳登录页 */
function handle401(redirect: boolean) {
  clearToken();
  uni.showToast({ title: "登录已过期，请重新登录", icon: "none" });
  if (redirect) {
    setTimeout(() => {
      uni.navigateTo({ url: LOGIN_PAGE });
    }, 600);
  }
}

export function request<T>(options: RequestOptions): Promise<T> {
  const {
    url,
    method = "GET",
    data,
    header = {},
    auth = true,
    showLoading = false,
    redirectOn401 = true,
  } = options;

  if (showLoading) {
    uni.showLoading({ title: "加载中…", mask: true });
  }

  return new Promise<T>((resolve, reject) => {
    const token = getToken();
    uni.request({
      url: BASE_URL + url,
      method,
      data,
      header: {
        "Content-Type": "application/json",
        ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
        ...header,
      },
      success: (res) => {
        if (showLoading) uni.hideLoading();
        const status = res.statusCode;
        if (status >= 200 && status < 300) {
          const body = res.data as ApiEnvelope<T>;
          // 兼容两种约定：直接返回数据 或 { code, data } 信封
          if (body && typeof body === "object" && "data" in body && "code" in body) {
            if (body.code === 0 || body.code === 200) {
              resolve(body.data);
            } else {
              const err = toApiError(mapErrorCode(String(body.code)), status, String(body.code));
              uni.showToast({ title: err.message, icon: "none" });
              reject(err);
            }
          } else {
            resolve(res.data as T);
          }
        } else if (status === 401) {
          const hadToken = !!token;
          handle401(redirectOn401 && hadToken);
          reject(toApiError("Unauthorized", 401, "UNAUTHORIZED"));
        } else {
          // 业务错误：解析 { code, message } 统一 toast（§0.2）
          const body = (res.data || {}) as { code?: string; message?: string; detail?: unknown };
          const message = body.message || mapErrorCode(body.code) || `请求失败(${status})`;
          const code = body.code || `HTTP_${status}`;
          uni.showToast({ title: message, icon: "none" });
          reject(toApiError(message, status, code, body.detail));
        }
      },
      fail: (err) => {
        if (showLoading) uni.hideLoading();
        // 网络层失败：status 0，由 withFallback 决定是否降级 mock
        reject(toApiError(err.errMsg || "网络错误，请检查连接", 0, "NETWORK_ERROR"));
      },
    });
  });
}

/** 网络层错误（无 HTTP 状态） */
export function isNetworkError(e: unknown): boolean {
  return (e as ApiError)?.status === 0;
}

/**
 * 真实 API 优先 + mock 降级：
 *  - USE_MOCK=true 时直接 mock（联调开关）
 *  - 否则尝试真实请求；网络错误 / 5xx / 未登录 401 → 降级 mock 并轻提示
 *  - 业务 4xx（403/404/409/422/429）视为真实语义错误，正常抛出
 */
export async function withFallback<T>(
  real: () => Promise<T>,
  mock: () => T | Promise<T>,
  fallbackHint = "服务暂不可用，已加载演示数据"
): Promise<T> {
  if (USE_MOCK) return mock();
  try {
    return await real();
  } catch (e) {
    const err = e as ApiError;
    const status = err.status;
    const fallbackable = !status || status >= 500 || (status === 401 && !getToken());
    if (!fallbackable) throw e;
    uni.showToast({ title: fallbackHint, icon: "none" });
    return mock();
  }
}

export { BASE_URL };
