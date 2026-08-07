/**
 * 统一请求封装：uni.request 拦截 + token 注入 + 统一错误处理
 * TODO(ep-backend): 后端就绪后
 *   1) 将 USE_MOCK 置 false（或按构建环境注入）
 *   2) 确认 BASE_URL 指向真实网关（本地 dev 可配 VITE_API_BASE_URL）
 */
const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
  "http://127.0.0.1:8000/api/v1";

/** 后端未就绪：true 时全部走 mock，接口层保留真实请求代码路径 */
export const USE_MOCK = true;

const TOKEN_KEY = "aceexam_token";

export function getToken(): string {
  return (uni.getStorageSync(TOKEN_KEY) as string) || "";
}

export function setToken(token: string) {
  uni.setStorageSync(TOKEN_KEY, token);
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
}

interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
}

export function request<T>(options: RequestOptions): Promise<T> {
  const { url, method = "GET", data, header = {}, auth = true, showLoading = false } = options;

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
              reject(new Error(body.message || "请求失败"));
            }
          } else {
            resolve(res.data as T);
          }
        } else if (status === 401) {
          // TODO(ep-backend): 401 统一处理——清 token + 跳登录页（登录流程 M3 提供）
          uni.removeStorageSync(TOKEN_KEY);
          uni.showToast({ title: "登录已过期", icon: "none" });
          reject(new Error("Unauthorized"));
        } else {
          uni.showToast({ title: `请求失败(${status})`, icon: "none" });
          reject(new Error(`HTTP ${status}`));
        }
      },
      fail: (err) => {
        if (showLoading) uni.hideLoading();
        reject(new Error(err.errMsg || "网络错误"));
      },
    });
  });
}
