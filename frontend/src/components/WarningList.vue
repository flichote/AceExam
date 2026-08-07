<template>
  <view class="wl">
    <!-- 整体风险 -->
    <view v-if="overallRisk" class="wl-overall" :class="`wl-overall--${overallRisk}`">
      <text class="wl-overall-label">整体挂科风险</text>
      <view class="wl-overall-badge">
        <text class="wl-overall-badge-text">{{ riskText[overallRisk] }}</text>
      </view>
    </view>

    <!-- 条目列表 -->
    <view
      v-for="w in warnings"
      :key="w.knowledge_point_id"
      class="card wl-item"
      @click="$emit('select', w)"
    >
      <view class="wl-item-head">
        <text class="wl-item-name">{{ w.knowledge_point_name }}</text>
        <SubjectPill
          :label="riskText[w.risk_level]"
          :type="riskType[w.risk_level]"
        />
      </view>

      <view class="wl-item-reasons">
        <view v-for="(r, i) in w.reasons" :key="i" class="wl-reason">
          <text class="wl-reason-dot">·</text>
          <text class="wl-reason-text">{{ r }}</text>
        </view>
      </view>

      <view v-if="w.suggestion" class="wl-item-suggest">
        <text class="wl-item-suggest-label">建议</text>
        <text class="wl-item-suggest-text">{{ w.suggestion }}</text>
      </view>

      <view class="wl-item-meta">
        <text v-if="w.days_left != null" class="wl-item-meta-text">距考试 {{ w.days_left }} 天</text>
        <text v-if="w.accuracy != null" class="wl-item-meta-text">
          正确率 {{ Math.round(w.accuracy * 100) }}%
        </text>
        <text class="wl-item-meta-text">练习 {{ w.practice_count }} 次</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { RiskLevel, WarningItem } from "@/types";
import SubjectPill from "./SubjectPill.vue";

defineProps<{
  warnings: WarningItem[];
  overallRisk?: RiskLevel | null;
}>();

defineEmits<{ (e: "select", w: WarningItem): void }>();

const riskText: Record<RiskLevel, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};
const riskType: Record<RiskLevel, string> = {
  high: "danger",
  medium: "warning",
  low: "success",
};
</script>

<style lang="scss">
.wl {
  padding-top: 8rpx;
}

/* 整体风险条 */
.wl-overall {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
  border-radius: $radius-btn;
  margin-bottom: 20rpx;
}
.wl-overall--high {
  background: rgba($danger-500, 0.08);
}
.wl-overall--medium {
  background: rgba($warning-500, 0.08);
}
.wl-overall--low {
  background: rgba($success-500, 0.08);
}
.wl-overall-label {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.wl-overall-badge {
  padding: 4rpx 16rpx;
  border-radius: $radius-tag;
}
.wl-overall--high .wl-overall-badge {
  background: $danger-500;
}
.wl-overall--medium .wl-overall-badge {
  background: $warning-500;
}
.wl-overall--low .wl-overall-badge {
  background: $success-500;
}
.wl-overall-badge-text {
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 700;
}

/* 条目 */
.wl-item {
  padding: 24rpx;
  margin-bottom: 16rpx;
}
.wl-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.wl-item-name {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.wl-item-reasons {
  margin-top: 12rpx;
}
.wl-reason {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  margin-bottom: 6rpx;
}
.wl-reason-dot {
  color: $danger-500;
  font-weight: 700;
}
.wl-reason-text {
  font-size: $font-aux;
  color: $neutral-500;
  line-height: 1.5;
}
.wl-item-suggest {
  margin-top: 12rpx;
  background: $primary-100;
  border-radius: $radius-tag;
  padding: 12rpx 16rpx;
}
.wl-item-suggest-label {
  font-size: 22rpx;
  color: $primary-600;
  font-weight: 700;
  margin-right: 8rpx;
}
.wl-item-suggest-text {
  font-size: 22rpx;
  color: $neutral-900;
  line-height: 1.5;
}
.wl-item-meta {
  display: flex;
  gap: 20rpx;
  margin-top: 12rpx;
}
.wl-item-meta-text {
  font-size: 22rpx;
  color: $neutral-300;
}
</style>
