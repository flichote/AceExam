import type { TtsResult } from "@/types";

/**
 * 讲解语音 mock（docs/api.md §12.1）
 * TODO(ep-backend/ep-ai): POST /chat/explain/{session_id}/tts 就绪后移除。
 * audio_url 指向 uni-app 官方文档示例音频（可真实播放，演示播放链路）。
 */

export function mockTts(sessionId: string): TtsResult {
  return {
    session_id: sessionId,
    audio_url: "https://web-ext-storage.dcloud.net.cn/doc/uniapp/ForElise.mp3",
    voice: "zh-CN-XiaoxiaoNeural",
    text_preview: "第一步，我们先理解题意：题干给出极限式……",
    cache_hit: false,
    created_at: new Date().toISOString(),
  };
}
