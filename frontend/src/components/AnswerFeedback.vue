<template>
  <view class="feedback" :class="isCorrect ? 'feedback--ok' : 'feedback--no'">
    <view class="feedback-head">
      <text class="feedback-icon">{{ isCorrect ? "🎉" : "💪" }}</text>
      <view class="feedback-texts">
        <text class="feedback-title">{{ isCorrect ? "回答正确！" : "答错了，别灰心" }}</text>
        <text class="feedback-sub">
          {{ isCorrect ? "掌握度 +1，继续保持连胜" : "先看解析，再让 AI 给你讲明白" }}
        </text>
      </view>
    </view>

    <view class="feedback-actions">
      <view class="btn btn--ghost" @click="$emit('view-explain')">
        <text class="btn-text btn-text--ghost">查看解析</text>
      </view>
      <view class="btn btn--primary" @click="$emit('ask-ai')">
        <text class="btn-text btn-text--primary">AI 讲解</text>
      </view>
      <view class="btn btn--plain" @click="$emit('next')">
        <text class="btn-text">下一题</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
defineProps<{ isCorrect: boolean }>();
defineEmits<{
  (e: "view-explain"): void;
  (e: "ask-ai"): void;
  (e: "next"): void;
}>();
</script>

<style lang="scss">
.feedback {
  padding: 32rpx;
  border-radius: $radius-card;
  animation: feedback-pop 200ms ease;
}
.feedback--ok {
  background: rgba($success-500, 0.1);
  border: 2rpx solid rgba($success-500, 0.35);
}
.feedback--no {
  background: rgba($danger-500, 0.08);
  border: 2rpx solid rgba($danger-500, 0.3);
}

.feedback-head {
  display: flex;
  align-items: center;
  margin-bottom: 20rpx;
}
.feedback-icon {
  font-size: 44rpx;
  margin-right: 16rpx;
}
.feedback-texts {
  display: flex;
  flex-direction: column;
}
.feedback-title {
  font-size: $font-card-title;
  font-weight: 700;
}
.feedback--ok .feedback-title {
  color: $success-500;
}
.feedback--no .feedback-title {
  color: $danger-500;
}
.feedback-sub {
  font-size: $font-aux;
  color: $neutral-500;
  margin-top: 4rpx;
}

.feedback-actions {
  display: flex;
  gap: 16rpx;
}
.btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18rpx 0;
  border-radius: $radius-btn;
}
.btn--ghost {
  background: #ffffff;
  border: 2rpx solid $primary-500;
}
.btn--primary {
  background: $primary-500;
}
.btn--plain {
  background: $neutral-100;
}
.btn-text {
  font-size: $font-body;
  font-weight: 600;
}
.btn-text--ghost {
  color: $primary-600;
}
.btn-text--primary {
  color: #ffffff;
}

@keyframes feedback-pop {
  0% {
    transform: scale(0.95);
    opacity: 0.6;
  }
  60% {
    transform: scale(1.02);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
