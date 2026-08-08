import type { TtsResult } from "@/types";
import {
  BASE_URL,
  getToken,
  request,
  toApiError,
  USE_MOCK,
} from "@/utils/request";
import { mockTts } from "@/mock/tts";

/**
 * 讲解语音 API（docs/api.md §12.1 / §12.2）
 *  - POST /chat/explain/{session_id}/tts   生成讲解语音（会员功能，免费 403）
 *  - GET  /tts/audio/{file_hash}.mp3       音频流（登录即可，带 Authorization）
 *
 * 说明：TTS 生成失败（502 / 403 / 404）是真实语义错误，不降级 mock ——
 * 前端需展示「生成失败 + 重试」，与 §12.1 行为一致。
 * mock 仅在 VITE_USE_MOCK=true 时顶替（演示播放流程）。
 */

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface RequestTtsOptions {
  /** 音色白名单：zh-CN-XiaoxiaoNeural（默认，晓晓）/ zh-CN-YunxiNeural（云希） */
  voice?: "zh-CN-XiaoxiaoNeural" | "zh-CN-YunxiNeural";
}

/** 生成讲解语音 → 返回 audio_url（相对路径） */
export async function requestTts(
  sessionId: string,
  opts: RequestTtsOptions = {}
): Promise<TtsResult> {
  if (USE_MOCK) {
    await delay(700);
    return mockTts(sessionId);
  }
  return request<TtsResult>({
    url: `/chat/explain/${encodeURIComponent(sessionId)}/tts`,
    method: "POST",
    data: opts.voice ? { voice: opts.voice } : {},
  });
}

/** 后端返回 /api/v1/tts/audio/xxx.mp3 → 补 origin 成完整 URL */
export function resolveAudioUrl(audioUrl: string): string {
  if (/^https?:\/\//i.test(audioUrl)) return audioUrl;
  const origin = BASE_URL.replace(/\/api\/v1\/?$/, "");
  return origin + audioUrl;
}

/**
 * 下载音频到本地（带 Authorization 头），返回可播放的本地路径：
 *  - H5：fetch → Blob → URL.createObjectURL（可带 header）
 *  - 小程序/App：uni.downloadFile（header 支持）
 */
// #ifdef H5
async function downloadAudioH5(url: string): Promise<string> {
  try {
    const resp = await fetch(url, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!resp.ok) {
      throw toApiError(`音频下载失败(${resp.status})`, resp.status);
    }
    const blob = await resp.blob();
    return URL.createObjectURL(blob);
  } catch (e) {
    // CORS / 网络层失败（无 status）：降级直接播放远程地址（audio 元素可跨域播放）；
    // 带 HTTP status 的错误（401/404/5xx）如实抛出
    const err = e as { status?: number };
    if (err && err.status) throw e;
    return url;
  }
}
// #endif

// #ifndef H5
function downloadAudioMp(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.downloadFile({
      url,
      header: { Authorization: `Bearer ${getToken()}` },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.tempFilePath);
        } else {
          reject(toApiError(`音频下载失败(${res.statusCode})`, res.statusCode));
        }
      },
      fail: (err) => reject(toApiError(err.errMsg || "音频下载失败", 0)),
    });
  });
}
// #endif

/** 统一入口：按平台分发（条件编译裁剪，vue-tsc 双分支可见但不同名） */
export function downloadTtsAudio(url: string): Promise<string> {
  // #ifdef H5
  return downloadAudioH5(url);
  // #endif
  // #ifndef H5
  return downloadAudioMp(url);
  // #endif
}
