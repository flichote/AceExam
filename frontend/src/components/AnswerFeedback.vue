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
        <text class="btn-text">{{ isLast ? "查看结果" : "下一题" }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
defineProps<{ isCorrect: boolean; isLast?: boolean }>();
defineEmits<{
  (e: "view-explain"): void;
  (e: "ask-ai"): void;
  (e: "next"): void;
}>();
</script>
