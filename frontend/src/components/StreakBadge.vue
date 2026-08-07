<template>
  <view class="sb" :class="`sb--${variant}`">
    <text class="sb-icon">🔥</text>
    <text class="sb-text">{{ days }} 天</text>
  </view>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    /** 连续打卡天数 */
    days: number;
    /** primary 深色底（hero）/ light 浅色底（卡片） */
    variant?: "primary" | "light";
  }>(),
  {
    days: 0,
    variant: "light",
  }
);
</script>

<style lang="scss">
.sb {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
  padding: 8rpx 16rpx;
  border-radius: $radius-tag;
  flex-shrink: 0;
}
.sb-icon {
  font-size: 24rpx;
}
.sb-text {
  font-size: $font-aux;
  font-weight: 700;
}
.sb--light {
  background: $primary-100;
  .sb-text {
    color: $primary-600;
  }
}
.sb--primary {
  background: rgba(255, 255, 255, 0.2);
  .sb-text {
    color: #ffffff;
  }
}
</style>
