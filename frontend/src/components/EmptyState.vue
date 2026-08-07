<template>
  <view class="empty">
    <text class="empty-icon">{{ icon }}</text>
    <text class="empty-title">{{ title }}</text>
    <text class="empty-desc">{{ desc }}</text>
    <view v-if="actionText" class="empty-btn" @click="$emit('action')">
      <text class="empty-btn-text">{{ actionText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    icon?: string;
    title?: string;
    desc?: string;
    actionText?: string;
  }>(),
  {
    icon: "📭",
    title: "这里空空如也",
    desc: "",
    actionText: "",
  }
);

defineEmits<{ (e: "action"): void }>();
</script>

<style lang="scss">
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64rpx 32rpx;
}
.empty-icon {
  font-size: 64rpx;
  margin-bottom: 16rpx;
}
.empty-title {
  font-size: $font-body;
  color: $neutral-900;
  font-weight: 600;
  margin-bottom: 8rpx;
}
.empty-desc {
  font-size: $font-aux;
  color: $neutral-500;
  text-align: center;
}
.empty-btn {
  margin-top: 24rpx;
  padding: 12rpx 40rpx;
  border-radius: $radius-btn;
  background: $primary-500;
}
.empty-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 600;
}
</style>
