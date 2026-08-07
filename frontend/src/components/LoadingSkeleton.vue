<template>
  <view class="skeleton card">
    <view class="skeleton-line skeleton-line--lg" />
    <view class="skeleton-line skeleton-line--md" />
    <view class="skeleton-line skeleton-line--md" />
    <view class="skeleton-row">
      <view class="skeleton-line skeleton-line--sm" />
      <view class="skeleton-line skeleton-line--sm" />
    </view>
  </view>
</template>

<style lang="scss">
.skeleton {
  padding: 32rpx;
}
.skeleton-line {
  background: linear-gradient(90deg, $neutral-100 25%, #ffffff 50%, $neutral-100 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.4s infinite;
  border-radius: $radius-tag;
  margin-bottom: 20rpx;
}
.skeleton-line--lg {
  height: 40rpx;
  width: 80%;
}
.skeleton-line--md {
  height: 32rpx;
  width: 100%;
}
.skeleton-line--sm {
  height: 32rpx;
  width: 45%;
}
.skeleton-row {
  display: flex;
  gap: 16rpx;
  margin-top: 8rpx;
}
@keyframes skeleton-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
