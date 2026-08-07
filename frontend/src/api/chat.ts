import type { ChatMessage } from "@/types";
import { USE_MOCK } from "@/utils/request";
import { mockStreamReply, mockCitations } from "@/mock/chat";

export interface StreamChatOptions {
  messages: ChatMessage[];
  onChunk: (chunk: string) => void;
  onCitations?: (citations: ChatMessage["citations"]) => void;
}

/**
 * AI 对话流式接口
 * 对接点：POST /api/v1/chat/stream（SSE）
 *  - H5/App：fetch + ReadableStream 解析 text/event-stream
 *  - 小程序：uni.request 需 enableChunked + onChunkReceived（wx.request 流式）
 * TODO(ep-ai): 服务端 SSE 就绪后实现真实分支，此处 mock 顶替
 */
export async function streamChat(options: StreamChatOptions): Promise<void> {
  if (USE_MOCK) {
    // mock 流式：分块回调 + 附带教材引用（模拟 RAG 溯源）
    options.onCitations?.(mockCitations);
    return mockStreamReply(options.messages, options.onChunk);
  }

  // ===== 真实 SSE 分支（占位）=====
  // H5 示例：
  // const resp = await fetch(`${BASE_URL}/chat/stream`, {
  //   method: "POST",
  //   headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
  //   body: JSON.stringify({ messages: options.messages }),
  // });
  // const reader = resp.body!.getReader();
  // const decoder = new TextDecoder();
  // while (true) {
  //   const { done, value } = await reader.read();
  //   if (done) break;
  //   // 按行解析 data: 字段 → options.onChunk(chunk)
  // }
  throw new Error("SSE 未就绪（USE_MOCK=false 时才会走到这里）");
}
