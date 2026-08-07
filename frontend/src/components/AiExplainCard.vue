<template>
  <view class="ai-step card" :class="{ 'ai-step--open': expanded }">
    <!-- 步骤头（点击折叠/展开） -->
    <view class="ai-step-head" @click="$emit('toggle')">
      <view class="ai-step-badge">
        <text class="ai-step-badge-text">{{ index + 1 }}</text>
      </view>
      <text class="ai-step-title">{{ step.title }}</text>
      <view class="ai-step-arrow">
        <text class="ai-step-arrow-text">{{ expanded ? "▾" : "▸" }}</text>
      </view>
    </view>

    <!-- 步骤内容（可折叠） -->
    <view v-if="expanded" class="ai-step-body">
      <LatexText :text="step.content" :font-size="'15px'" />
      <!-- 流式生成中 -->
      <view v-if="streaming && !step.content" class="ai-step-typing">
        <view class="typing-dot" />
        <view class="typing-dot" />
        <view class="typing-dot" />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { StepCard } from "@/types";
import LatexText from "./LatexText.vue";

withDefaults(
  defineProps<{
    step: StepCard;
    index: number;
    expanded?: boolean;
    streaming?: boolean;
  }>(),
  {
    expanded: true,
    streaming: false,
  }
);

defineEmits<{ (e: "toggle"): void }>();
</script>

<style lang="scss">
.ai-step {
  margin-bottom: 16rpx;
  padding: 0;
  overflow: hidden;
}
.ai-step-head {
  display: flex;
  align-items: center;
  padding: 20rpx 24rpx;
  cursor: pointer;
}
.ai-step-badge {
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  background: $primary-500;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16rpx;
  flex-shrink: 0;
}
.ai-step-badge-text {
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 700;
}
.ai-step-title {
  flex: 1;
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.ai-step-arrow-text {
  font-size: 28rpx;
  color: $neutral-300;
}
.ai-step-body {
  padding: 0 24rpx 24rpx 84rpx;
  color: $neutral-500;
}

/* 打字指示 */
.ai-step-typing {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  margin-top: 8rpx;
}
.typing-dot {
  width: 10rpx;
  height: 10rpx;
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
    transform: translateY(-6rpx);
    opacity: 1;
  }
}
</style>
