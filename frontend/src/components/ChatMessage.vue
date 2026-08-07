<template>
  <view class="msg" :class="isUser ? 'msg--user' : 'msg--assistant'">
    <view v-if="!isUser" class="msg-avatar">
      <text class="msg-avatar-text">🤖</text>
    </view>

    <view class="msg-main">
      <!-- AI 讲解：分步卡片 -->
      <template v-if="!isUser && message.steps && message.steps.length">
        <view class="steps-wrap">
          <AiExplainCard
            v-for="(step, i) in message.steps"
            :key="i"
            :step="step"
            :index="i"
            :expanded="expandedSteps[i] !== false"
            :streaming="!!message.streaming"
            @toggle="toggleStep(i)"
          />
        </view>
        <!-- 结论 / 兜底文本 -->
        <view v-if="message.content" class="bubble bubble--assistant">
          <LatexText :text="message.content" :font-size="'15px'" :color="'#1F2937'" />
        </view>
        <!-- RAG 未覆盖提示 -->
        <view v-if="!isUser && message.streaming === false && uncoveredOnly" class="uncovered">
          <text class="uncovered-text">📖 教材库暂未覆盖该题，以下为通用讲解</text>
        </view>
      </template>

      <!-- 普通气泡 -->
      <view v-else class="bubble" :class="isUser ? 'bubble--user' : 'bubble--assistant'">
        <LatexText
          :text="message.content"
          :font-size="'15px'"
          :color="isUser ? '#FFFFFF' : '#1F2937'"
        />

        <!-- 流式输出中的打字指示 -->
        <view v-if="message.streaming && !message.content" class="typing">
          <view class="typing-dot" />
          <view class="typing-dot" />
          <view class="typing-dot" />
        </view>
      </view>

      <!-- 教材引用（RAG 溯源） -->
      <view v-if="!isUser && message.citations && message.citations.length">
        <CitationBlock
          v-for="(c, i) in message.citations"
          :key="i"
          :citation="c"
        />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { ChatMessage } from "@/types";
import LatexText from "./LatexText.vue";
import CitationBlock from "./CitationBlock.vue";
import AiExplainCard from "./AiExplainCard.vue";

const props = defineProps<{ message: ChatMessage; uncovered?: boolean }>();

const isUser = computed(() => props.message.role === "user");

/** 折叠状态：默认全展开，点击收起（key 为步骤索引） */
const expandedSteps = ref<Record<number, boolean>>({});
function toggleStep(i: number) {
  expandedSteps.value[i] = expandedSteps.value[i] !== false ? false : true;
}

const uncoveredOnly = computed(() => props.uncovered === true);
</script>

<style lang="scss">
.msg {
  display: flex;
  margin-bottom: 24rpx;
}
.msg--user {
  justify-content: flex-end;
}
.msg--assistant {
  justify-content: flex-start;
}

.msg-avatar {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: $primary-100;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16rpx;
  flex-shrink: 0;
}
.msg-avatar-text {
  font-size: 32rpx;
}

.msg-main {
  max-width: 82%;
  display: flex;
  flex-direction: column;
}

.steps-wrap {
  width: 100%;
}

.bubble {
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  word-break: break-word;
}
.bubble--assistant {
  background: #ffffff;
  border: 2rpx solid $neutral-100;
  border-top-left-radius: 4rpx;
  box-shadow: $shadow-card;
}
.bubble--user {
  background: $primary-500;
  border-top-right-radius: 4rpx;
}
.bubble-user-text {
  color: #ffffff;
  font-size: $font-body;
  line-height: 1.5;
}

/* RAG 未覆盖提示 */
.uncovered {
  margin-top: 8rpx;
  background: rgba($warning-500, 0.1);
  border-radius: $radius-tag;
  padding: 8rpx 16rpx;
}
.uncovered-text {
  font-size: 22rpx;
  color: $warning-500;
}

/* 打字指示 */
.typing {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  margin-top: 12rpx;
}
.typing-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: $primary-500;
  animation: typing-bounce 1.2s infinite ease-in-out;
}
.typing-dot:nth-child(2) {
  animation-delay: 0.15s;
}
.typing-dot:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-8rpx);
    opacity: 1;
  }
}
</style>
