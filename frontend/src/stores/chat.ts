import { defineStore } from "pinia";
import { ref } from "vue";
import type { ChatMessage } from "@/types";
import { streamChat } from "@/api/chat";

let seq = 0;
function nextId() {
  seq += 1;
  return `msg-${Date.now()}-${seq}`;
}

/** AI 对话状态：消息列表 + mock SSE 流式输出 */
export const useChatStore = defineStore("chat", () => {
  const messages = ref<ChatMessage[]>([]);
  const streaming = ref(false);

  function reset() {
    messages.value = [];
    streaming.value = false;
  }

  /** 首次进入时的欢迎语（只在空会话时插入） */
  function pushWelcome() {
    if (messages.value.length > 0) return;
    messages.value.push({
      id: nextId(),
      role: "assistant",
      content:
        "我是你的 AI 备考教练 👨‍🏫 输入题目或知识点（比如「讲讲 sinx/x 的极限」），我来 step-by-step 讲给你听，回答支持数学公式渲染。",
      createdAt: Date.now(),
    });
  }

  /** 追加助手消息（先占位 streaming，再逐块填充） */
  async function send(text: string, withWelcome = false) {
    const trimmed = text.trim();
    if (!trimmed || streaming.value) return;

    messages.value.push({
      id: nextId(),
      role: "user",
      content: trimmed,
      createdAt: Date.now(),
    });

    const assistant: ChatMessage = {
      id: nextId(),
      role: "assistant",
      content: "",
      citations: [],
      streaming: true,
      createdAt: Date.now(),
    };
    messages.value.push(assistant);
    // 通过响应式代理引用（push 后的数组元素），保证流式增量能触发视图更新
    const live = messages.value[messages.value.length - 1];
    streaming.value = true;

    try {
      await streamChat({
        messages: messages.value,
        onChunk: (chunk) => {
          live.content += chunk;
        },
        onCitations: (citations) => {
          if (citations) live.citations = citations;
        },
      });
    } catch (e) {
      live.content += `\n\n> ⚠️ 请求失败：${(e as Error).message}`;
    } finally {
      live.streaming = false;
      streaming.value = false;
    }

    if (withWelcome) {
      messages.value.push({
        id: nextId(),
        role: "assistant",
        content:
          "我是你的 AI 备考教练 👨‍🏫 可以问我任何题目，比如「讲讲 sinx/x 的极限」或「定积分怎么算」。回答支持数学公式渲染哦。",
        createdAt: Date.now(),
      });
    }
  }

  return { messages, streaming, send, reset, pushWelcome };
});
