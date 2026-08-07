<template>
  <view class="citation">
    <view class="citation-head">
      <text class="citation-head-icon">📖</text>
      <view class="citation-head-texts">
        <text class="citation-source">{{ citation.source }}</text>
        <text class="citation-chapter">{{ citation.chapter }}</text>
      </view>
    </view>
    <view class="citation-snippet">
      <text class="citation-quote">“{{ citation.snippet }}”</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { Citation } from "@/types";

defineProps<{ citation: Citation }>();
</script>

<style lang="scss">
.citation {
  border-left: 6rpx solid $info-500;
  background: rgba($info-500, 0.08);
  border-radius: 12rpx;
  padding: 16rpx 20rpx;
  margin-top: 16rpx;
}
.citation-head {
  display: flex;
  align-items: flex-start;
}
.citation-head-icon {
  font-size: 28rpx;
  margin-right: 12rpx;
  margin-top: 2rpx;
}
.citation-head-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.citation-source {
  font-size: $font-aux;
  color: $info-500;
  font-weight: 600;
}
.citation-chapter {
  font-size: 12px;
  color: $neutral-500;
  margin-top: 2rpx;
}
.citation-snippet {
  margin-top: 10rpx;
}
.citation-quote {
  font-size: $font-aux;
  color: $neutral-500;
  line-height: 1.6;
}
</style>
