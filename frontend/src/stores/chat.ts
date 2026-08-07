import { defineStore } from "pinia";
import { ref } from "vue";
import type { ChatMessage, Citation, StepCard } from "@/types";
import { streamChatExplain, streamChat } from "@/api/chat";

let seq = 0;
function nextId() {
  seq += 1;
  return `msg-${Date.now()}-${seq}`;
}

/** AI 对话状态：消息列表 + SSE 流式输出 + 分步讲解（docs/api.md §5） */
export const useChatStore = defineStore("chat", () => {
  const messages = ref<ChatMessage[]>([]);
  const streaming = ref(false);
  /** 讲解会话 id（追问依赖） */
  const sessionId = ref("");
  /** 当前讲解题目（explain 模式） */
  const explainQuestionId = ref("");
  /** 讲解是否已完成（未覆盖教材时提示） */
  const uncovered = ref(false);

  function reset() {
    messages.value = [];
    streaming.value = false;
    sessionId.value = "";
    explainQuestionId.value = "";
    uncovered.value = false;
  }

  /** 首次进入欢迎语 */
  function pushWelcome() {
    if (messages.value.length > 0) return;
    messages.value.push({
      id: nextId(),
      role: "assistant",
      content:
        "我是你的 AI 备考教练 👨‍🏫 从刷题页点「AI 讲解」可针对题目逐步讲解；也可以直接输入题目或知识点（比如「讲讲 sinx/x 的极限」），回答支持数学公式渲染。",
      createdAt: Date.now(),
    });
  }

  /** 追加用户消息 + 空助手占位，返回 live 引用（响应式） */
  function pushPair(userText: string): ChatMessage {
    messages.value.push({
      id: nextId(),
      role: "user",
      content: userText,
      createdAt: Date.now(),
    });
    const assistant: ChatMessage = {
      id: nextId(),
      role: "assistant",
      content: "",
      citations: [],
      steps: [],
      streaming: true,
      createdAt: Date.now(),
    };
    messages.value.push(assistant);
    return messages.value[messages.value.length - 1];
  }

  /** 按题讲解（explain）：POST /chat/explain（SSE） */
  async function startExplain(questionId: string, knowledgePoint = "") {
    if (streaming.value) return;
    const prefix = knowledgePoint ? `（知识点：${knowledgePoint}）` : "";
    const live = pushPair(`请帮我讲解这道题 ${prefix}`);
    streaming.value = true;
    explainQuestionId.value = questionId;
    uncovered.value = false;

    // 步骤卡构建：SSE step 事件开新卡，delta 追加到当前卡
    const steps: StepCard[] = [];
    let currentStep = -1;

    try {
      await streamChatExplain({
        questionId,
        onStep: ({ title }) => {
          steps.push({ title, content: "" });
          currentStep += 1;
        },
        onDelta: (delta) => {
          if (currentStep >= 0) {
            steps[currentStep].content += delta;
            live.steps = [...steps];
          } else {
            live.content += delta;
          }
        },
        onCitations: (citations) => {
          live.citations = citations;
        },
        onDone: ({ session_id, uncovered: unc }) => {
          sessionId.value = session_id || "";
          uncovered.value = unc;
        },
      });
    } catch (e) {
      live.content = `⚠️ 讲解请求失败：${(e as Error).message}`;
    } finally {
      live.streaming = false;
      streaming.value = false;
    }
  }

  /** 追问：POST /chat/followup（SSE，带会话上下文） */
  async function followup(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming.value || !sessionId.value) return;
    const live = pushPair(trimmed);
    streaming.value = true;

    const steps: StepCard[] = [];
    let currentStep = -1;

    try {
      await streamChatExplain({
        sessionId: sessionId.value,
        message: trimmed,
        onStep: ({ title }) => {
          steps.push({ title, content: "" });
          currentStep += 1;
        },
        onDelta: (delta) => {
          if (currentStep >= 0) {
            steps[currentStep].content += delta;
            live.steps = [...steps];
          } else {
            live.content += delta;
          }
        },
        onCitations: (citations) => {
          live.citations = citations;
        },
        onDone: ({ session_id, uncovered: unc }) => {
          if (session_id) sessionId.value = session_id;
          uncovered.value = unc;
        },
      });
    } catch (e) {
      live.content = `⚠️ 追问失败：${(e as Error).message}`;
    } finally {
      live.streaming = false;
      streaming.value = false;
    }
  }

  /** 自由对话（无 question_id/session_id：mock 流式，M3 接入通用助手） */
  async function sendFreeText(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming.value) return;
    const live = pushPair(trimmed);
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
  }

  /** 统一发送：explain 模式（有 session）走追问；否则自由对话 */
  async function send(text: string) {
    if (sessionId.value) return followup(text);
    return sendFreeText(text);
  }

  return {
    messages,
    streaming,
    sessionId,
    explainQuestionId,
    uncovered,
    reset,
    pushWelcome,
    startExplain,
    followup,
    sendFreeText,
    send,
  };
});
