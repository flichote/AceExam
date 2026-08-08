<template>
  <view class="chat">
    <!-- 消息列表 -->
    <scroll-view
      class="chat-list"
      scroll-y
      :scroll-into-view="scrollAnchor"
      scroll-with-animation
    >
      <view class="chat-list-inner">
        <view
          v-for="(m, idx) in chatStore.messages"
          :key="m.id"
          :id="`anchor-${m.id}`"
        >
          <ChatMessage :message="m" :uncovered="chatStore.uncovered" />
          <!-- M3.5 TTS：讲解完成后（最后一条含分步卡的非流式消息）显示「🔊 听讲解」 -->
          <TtsPlayer
            v-if="idx === lastExplanationIndex && chatStore.sessionId"
            :session-id="chatStore.sessionId"
          />
        </view>
      </view>
    </scroll-view>

    <!-- 输入栏：explain 模式 = 追问 -->
    <view class="inputbar">
      <input
        v-model="draft"
        class="inputbar-field"
        :placeholder="inputPlaceholder"
        placeholder-class="inputbar-placeholder"
        confirm-type="send"
        :disabled="chatStore.streaming || explainLoading"
        @confirm="onSend"
      />
      <view
        class="btn btn--primary inputbar-send"
        :class="{ 'btn--disabled': !draft.trim() || chatStore.streaming || explainLoading }"
        @click="onSend"
      >
        <text class="inputbar-send-text">{{ chatStore.sessionId ? "追问" : "发送" }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { useChatStore } from "@/stores/chat";
import ChatMessage from "@/components/ChatMessage.vue";
import TtsPlayer from "@/components/TtsPlayer.vue";

const chatStore = useChatStore();
const draft = ref("");
const scrollAnchor = ref("");
const explainLoading = ref(false);

/**
 * 进入模式：
 *  - 刷题页「AI 讲解」→ 携带 questionId，自动发起按题讲解（POST /chat/explain SSE）
 *  - 首页 AI 教练入口 → 自由对话（mock 流式，M3 通用助手）
 */
onLoad((options) => {
  const questionId = (options?.questionId as string) || "";
  const stem = (options?.stem as string) || "";
  const knowledgePoint = (options?.knowledgePoint as string) || "";

  if (questionId) {
    explainLoading.value = true;
    chatStore
      .startExplain(questionId, knowledgePoint ? decodeURIComponent(knowledgePoint) : "")
      .finally(() => {
        explainLoading.value = false;
        scrollToBottom();
      });
  } else if (stem) {
    // 兼容旧入口：无 questionId 时用题干自由提问
    const q = decodeURIComponent(stem);
    const prefix = knowledgePoint ? `（知识点：${decodeURIComponent(knowledgePoint)}）` : "";
    chatStore.sendFreeText(`${q}${prefix}，请帮我讲解一下这道题`);
  } else {
    chatStore.pushWelcome();
  }
});

const inputPlaceholder = computed(() => {
  if (chatStore.sessionId) return "还不懂？追问…";
  if (chatStore.explainQuestionId) return "讲解生成中…";
  return "输入题目或知识点，回车发送…";
});

const lastMsgId = computed(() => {
  const msgs = chatStore.messages;
  return msgs.length ? msgs[msgs.length - 1].id : "";
});

/**
 * 最后一条「已完成的分步讲解」消息索引（M3.5 TTS 按钮挂载点）：
 * 讲解/追问完成后（assistant + steps + 非流式），取最后一条。
 */
const lastExplanationIndex = computed(() => {
  const msgs = chatStore.messages;
  let idx = -1;
  for (let i = 0; i < msgs.length; i += 1) {
    const m = msgs[i];
    if (m.role === "assistant" && m.steps && m.steps.length && !m.streaming) {
      idx = i;
    }
  }
  return idx;
});

async function onSend() {
  const text = draft.value.trim();
  if (!text || chatStore.streaming) return;
  draft.value = "";
  await chatStore.send(text);
  scrollToBottom();
}

function scrollToBottom() {
  nextTick(() => {
    scrollAnchor.value = `anchor-${lastMsgId.value}`;
  });
}
</script>

<style lang="scss">
.chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.chat-list {
  flex: 1;
  overflow: hidden;
}
.chat-list-inner {
  padding: 32rpx;
}

/* 输入栏 */
.inputbar {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 16rpx 24rpx;
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
  background: #ffffff;
  border-top: 2rpx solid $neutral-100;
}
.inputbar-field {
  flex: 1;
  height: 76rpx;
  background: $neutral-100;
  border-radius: 38rpx;
  padding: 0 28rpx;
  font-size: $font-body;
  color: $neutral-900;
}
.inputbar-placeholder {
  color: $neutral-300;
}
.inputbar-send {
  padding: 0 36rpx;
  height: 76rpx;
  flex-shrink: 0;
}
.inputbar-send-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
}
</style>
