import type { ChatExplainResult, ChatMessage, Citation } from "@/types";
import {
  BASE_URL,
  getToken,
  USE_MOCK,
  toApiError,
} from "@/utils/request";
import { mockExplain, mockFollowup, mockStreamReply, mockCitations } from "@/mock/chat";

/**
 * AI 讲解 API（docs/api.md §5）
 *  - POST /chat/explain?stream=true   按题讲解（SSE，question_id 必填）
 *  - POST /chat/followup?stream=true  追问（SSE，session_id + message）
 *  - 非流式：stream=false 返回完整 JSON（老基础库降级）
 * SSE 事件格式：每事件一行 `data: {json}` + 空行分隔（§0.4）
 */

export interface ExplainStreamOptions {
  /** 讲解模式：题目 id */
  questionId?: string;
  /** 追问模式：会话 id + 消息 */
  sessionId?: string;
  message?: string;
  onDelta?: (delta: string) => void;
  onStep?: (step: { step_index: number; title: string }) => void;
  onCitations?: (citations: Citation[]) => void;
  onDone?: (result: { session_id: string; uncovered: boolean; model?: string }) => void;
}

export interface SseFrame {
  type: string;
  [k: string]: unknown;
}

function buildStreamTarget(opts: ExplainStreamOptions): { url: string; body: Record<string, unknown> } {
  if (opts.questionId) {
    return {
      url: "/chat/explain?stream=true",
      body: { question_id: opts.questionId, followup_session_id: null },
    };
  }
  return {
    url: "/chat/followup?stream=true",
    body: { session_id: opts.sessionId, message: opts.message },
  };
}

function dispatchFrame(frame: SseFrame, opts: ExplainStreamOptions): void {
  switch (frame.type) {
    case "delta":
      opts.onDelta?.(String(frame.content ?? ""));
      break;
    case "step":
      opts.onStep?.({
        step_index: Number(frame.step_index ?? 0),
        title: String(frame.title ?? "步骤"),
      });
      break;
    case "citations":
      opts.onCitations?.(frame.citations as Citation[]);
      break;
    case "done":
      opts.onDone?.({
        session_id: String(frame.session_id ?? ""),
        uncovered: Boolean(frame.uncovered),
        model: frame.model as string | undefined,
      });
      break;
    case "error":
      throw toApiError(
        String(frame.message ?? "讲解出错"),
        undefined,
        String(frame.code ?? "STREAM_ERROR")
      );
    default:
      break;
  }
}

/** 解析 SSE 缓冲：按空行切帧、取 data: 行 JSON */
function parseSseBuffer(buffer: string): SseFrame[] {
  const frames: SseFrame[] = [];
  const blocks = buffer.split(/\r?\n\r?\n/);
  for (const block of blocks) {
    const dataLines = block
      .split(/\r?\n/)
      .filter((l) => l.startsWith("data:"));
    if (!dataLines.length) continue;
    const payload = dataLines.map((l) => l.replace(/^data:\s?/, "")).join("\n");
    try {
      frames.push(JSON.parse(payload) as SseFrame);
    } catch {
      /* 不完整帧忽略 */
    }
  }
  return frames;
}

/* ===== H5：fetch + ReadableStream ===== */
// #ifdef H5
async function streamH5(opts: ExplainStreamOptions): Promise<void> {
  const { url, body } = buildStreamTarget(opts);
  const resp = await fetch(BASE_URL + url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok || !resp.body) {
    throw toApiError(`讲解请求失败(${resp.status})`, resp.status);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // 只处理完整的帧（最后一个 \n\n 之后可能是不完整帧）
    const lastSep = buffer.lastIndexOf("\n\n");
    if (lastSep >= 0) {
      const complete = buffer.slice(0, lastSep);
      buffer = buffer.slice(lastSep + 2);
      for (const f of parseSseBuffer(complete)) dispatchFrame(f, opts);
    }
  }
  for (const f of parseSseBuffer(buffer)) dispatchFrame(f, opts);
}
// #endif

/* ===== 小程序 / App：uni.request enableChunked ===== */
// #ifndef H5
/** 流式 UTF-8 解码：返回已消费字节数，未消费的留在缓冲区等下一块 */
function utf8DecodeStream(bytes: Uint8Array): { text: string; consumed: number } {
  let out = "";
  let i = 0;
  while (i < bytes.length) {
    const b = bytes[i];
    if (b < 0x80) {
      out += String.fromCharCode(b);
      i += 1;
      continue;
    }
    let need = 0;
    let cp = 0;
    if (b >= 0xc2 && b <= 0xdf) {
      need = 1;
      cp = b & 0x1f;
    } else if (b >= 0xe0 && b <= 0xef) {
      need = 2;
      cp = b & 0x0f;
    } else if (b >= 0xf0 && b <= 0xf4) {
      need = 3;
      cp = b & 0x07;
    } else {
      i += 1; // 非法字节跳过
      continue;
    }
    if (i + need >= bytes.length) break; // 多字节序列不完整，保留
    let ok = true;
    for (let k = 1; k <= need; k++) {
      const c = bytes[i + k];
      if ((c & 0xc0) !== 0x80) {
        ok = false;
        break;
      }
      cp = (cp << 6) | (c & 0x3f);
    }
    if (!ok) {
      i += 1;
      continue;
    }
    out += String.fromCodePoint(cp);
    i += need + 1;
  }
  return { text: out, consumed: i };
}

function streamChunked(opts: ExplainStreamOptions): Promise<void> {
  return new Promise((resolve, reject) => {
    const { url, body } = buildStreamTarget(opts);
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    };
    // enableChunked 为小程序端流式请求参数（uni-app 类型未收录，透传 wx.request）
    const options = {
      url: BASE_URL + url,
      method: "POST",
      data: body,
      header: headers,
      enableChunked: true,
      success: (res: UniApp.RequestSuccessCallbackResult) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve();
        } else {
          reject(toApiError(`讲解请求失败(${res.statusCode})`, res.statusCode));
        }
      },
      fail: (err: UniApp.GeneralCallbackResult) => {
        reject(toApiError(err.errMsg || "网络错误", 0));
      },
    };
    const task = uni.request(options as unknown as Parameters<typeof uni.request>[0]);

    // onChunkReceived 能力探测（老基础库/不支持时 success 后 resolve，无流式增量）
    const rt = task as unknown as {
      onChunkReceived?: (cb: (res: { data: ArrayBuffer }) => void) => void;
    };
    if (typeof rt.onChunkReceived !== "function") {
      reject(toApiError("当前环境不支持流式讲解", 0, "SSE_UNSUPPORTED"));
      return;
    }
    let pending = new Uint8Array(0);
    let buffer = "";
    rt.onChunkReceived((res) => {
      const chunk = new Uint8Array(res.data);
      const merged = new Uint8Array(pending.length + chunk.length);
      merged.set(pending);
      merged.set(chunk, pending.length);
      const { text, consumed } = utf8DecodeStream(merged);
      pending = merged.slice(consumed);
      buffer += text;
      const lastSep = buffer.lastIndexOf("\n\n");
      if (lastSep >= 0) {
        const complete = buffer.slice(0, lastSep);
        buffer = buffer.slice(lastSep + 2);
        for (const f of parseSseBuffer(complete)) dispatchFrame(f, opts);
      }
    });
  });
}
// #endif

/* ===== mock 流式讲解（SSE 事件序列模拟）===== */
function mockStreamExplain(opts: ExplainStreamOptions): Promise<void> {
  return new Promise((resolve) => {
    const result: ChatExplainResult = opts.questionId
      ? mockExplain()
      : mockFollowup(opts.message ?? "");
    const steps = result.steps;
    const delay = 90;
    let stepIdx = 0;

    const streamStep = () => {
      if (stepIdx >= steps.length) {
        // conclusion + citations + done
        const c = result.conclusion;
        for (let i = 0; i < c.length; i += 8) {
          setTimeout(() => opts.onDelta?.(c.slice(i, i + 8)), delay * (i / 8 + 1));
        }
        setTimeout(() => opts.onCitations?.(result.citations), delay * (c.length / 8 + 1));
        setTimeout(() => {
          opts.onDone?.({
            session_id: result.session_id,
            uncovered: result.uncovered,
            model: result.model,
          });
          resolve();
        }, delay * (c.length / 8 + 2));
        return;
      }
      const step = steps[stepIdx];
      opts.onStep?.({ step_index: stepIdx, title: step.title });
      const content = step.content;
      for (let i = 0; i < content.length; i += 8) {
        setTimeout(() => opts.onDelta?.(content.slice(i, i + 8)), delay * (i / 8 + 1));
      }
      setTimeout(() => {
        stepIdx += 1;
        streamStep();
      }, delay * (content.length / 8 + 1));
    };
    streamStep();
  });
}

/** 讲解 / 追问统一入口（SSE 流式） */
export async function streamChatExplain(opts: ExplainStreamOptions): Promise<void> {
  if (USE_MOCK) return mockStreamExplain(opts);
  // #ifdef H5
  return streamH5(opts);
  // #endif
  // #ifndef H5
  return streamChunked(opts);
  // #endif
}

/** 非流式获取讲解（降级路径：stream=false 返回完整 JSON） */
export async function explainNonStream(
  questionId: string,
  sessionId?: string,
  message?: string
): Promise<ChatExplainResult> {
  if (USE_MOCK) return mockExplain();
  const url = sessionId ? "/chat/followup" : "/chat/explain";
  const data = sessionId
    ? { session_id: sessionId, message }
    : { question_id: questionId, followup_session_id: null };
  const { request } = await import("@/utils/request");
  return request<ChatExplainResult>({ url, method: "POST", data });
}

/* ===== 自由对话（无 question_id/session_id 时保留 mock，M3 接入通用助手）===== */

export interface StreamChatOptions {
  messages: ChatMessage[];
  onChunk: (chunk: string) => void;
  onCitations?: (citations: ChatMessage["citations"]) => void;
}

export async function streamChat(options: StreamChatOptions): Promise<void> {
  // 自由对话无真实端点（契约仅 explain/followup），保持 mock 流式
  options.onCitations?.(mockCitations);
  return mockStreamReply(options.messages, options.onChunk);
}
