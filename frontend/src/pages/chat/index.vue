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
          v-for="m in chatStore.messages"
          :key="m.id"
          :id="`anchor-${m.id}`"
        >
          <ChatMessage :message="m" />
        </view>
      </view>
    </scroll-view>

    <!-- 输入栏 -->
    <view class="inputbar">
      <input
        v-model="draft"
        class="inputbar-field"
        placeholder="输入题目或知识点，回车发送…"
        placeholder-class="inputbar-placeholder"
        confirm-type="send"
        :disabled="chatStore.streaming"
        @confirm="onSend"
      />
      <view
        class="btn btn--primary inputbar-send"
        :class="{ 'btn--disabled': !draft.trim() || chatStore.streaming }"
        @click="onSend"
      >
        <text class="inputbar-send-text">发送</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { useChatStore } from "@/stores/chat";
import ChatMessage from "@/components/ChatMessage.vue";

const chatStore = useChatStore();
const draft = ref("");
const scrollAnchor = ref("");

/**
 * 从刷题页"AI 讲解"进入：携带题干，自动发起提问
 * TODO(ep-ai): 后续可携带 questionId 让后端按题讲解（RAG 命中教材引用）
 */
onLoad((options) => {
  const stem = options?.stem as string | undefined;
  const knowledgePoint = options?.knowledgePoint as string | undefined;

  if (stem) {
    const q = decodeURIComponent(stem);
    const prefix = knowledgePoint ? `（知识点：${decodeURIComponent(knowledgePoint)}）` : "";
    chatStore.send(`${q}${prefix}，请帮我讲解一下这道题`);
  } else {
    chatStore.pushWelcome();
  }
});

const lastMsgId = computed(() => {
  const msgs = chatStore.messages;
  return msgs.length ? msgs[msgs.length - 1].id : "";
});

async function onSend() {
  const text = draft.value.trim();
  if (!text || chatStore.streaming) return;
  draft.value = "";
  await chatStore.send(text);
  // 滚到底部
  await nextTick();
  scrollAnchor.value = `anchor-${lastMsgId.value}`;
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
