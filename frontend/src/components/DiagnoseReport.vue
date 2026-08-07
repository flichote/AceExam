<template>
  <view class="diagnose-report">
    <!-- 总结 -->
    <view class="card report-summary">
      <view class="report-summary-icon">📋</view>
      <text class="report-summary-title">诊断总结</text>
      <LatexText :text="report.summary" :font-size="'15px'" />
    </view>

    <!-- 薄弱 Top5 -->
    <view class="report-section">
      <view class="report-section-head">
        <text class="report-section-title">薄弱知识点 Top{{ report.weak_top5.length }}</text>
        <text class="report-section-sub">优先补练</text>
      </view>
      <view
        v-for="w in report.weak_top5"
        :key="w.rank"
        class="card weak-item"
      >
        <view class="weak-item-head">
          <view class="weak-rank" :class="rankClass(w.rank)">
            <text class="weak-rank-text">{{ w.rank }}</text>
          </view>
          <view class="weak-item-texts">
            <view class="weak-name-row">
              <text class="weak-name">{{ w.knowledge_point_name }}</text>
              <SubjectPill :label="statusText(w.status)" :type="statusType(w.status)" />
            </view>
            <view class="weak-meta">
              <text class="weak-meta-text">正确率 {{ Math.round(w.accuracy * 100) }}%</text>
              <text class="weak-meta-dot">·</text>
              <text class="weak-meta-text">练过 {{ w.practice_count }} 题</text>
            </view>
          </view>
        </view>
        <view class="weak-bar">
          <view class="weak-bar-fill" :style="{ width: accuracyPercent(w.accuracy) + '%' }" />
        </view>
        <view class="weak-suggestion">
          <text class="weak-suggestion-label">建议</text>
          <text class="weak-suggestion-text">{{ w.suggestion }}</text>
        </view>
      </view>
    </view>

    <!-- 优势 & 未开始 -->
    <view class="report-row">
      <view class="card report-mini">
        <text class="report-mini-title">✅ 优势</text>
        <view v-if="report.strengths.length" class="report-mini-list">
          <view v-for="(s, i) in report.strengths" :key="i" class="report-mini-item">
            <text class="report-mini-item-name">{{ s.knowledge_point_name }}</text>
            <text class="report-mini-item-num">{{ Math.round(s.accuracy * 100) }}%</text>
          </view>
        </view>
        <text v-else class="report-mini-empty">暂无</text>
      </view>
      <view class="card report-mini">
        <text class="report-mini-title">🚧 未开始</text>
        <view v-if="report.not_started.length" class="report-mini-list">
          <view v-for="(n, i) in report.not_started" :key="i" class="report-mini-item">
            <text class="report-mini-item-name">{{ n.knowledge_point_name }}</text>
            <text class="report-mini-item-num">Lv.{{ n.level }}</text>
          </view>
        </view>
        <text v-else class="report-mini-empty">暂无</text>
      </view>
    </view>

    <!-- 下一步建议 -->
    <view class="report-section">
      <view class="report-section-head">
        <text class="report-section-title">下一步建议</text>
      </view>
      <view class="card report-steps">
        <view v-for="(s, i) in report.suggested_next_steps" :key="i" class="report-step">
          <view class="report-step-dot">
            <text class="report-step-dot-text">{{ i + 1 }}</text>
          </view>
          <text class="report-step-text">{{ s }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { DiagnosisReport } from "@/types";
import LatexText from "./LatexText.vue";
import SubjectPill from "./SubjectPill.vue";

defineProps<{ report: DiagnosisReport }>();

function rankClass(rank: number): string {
  if (rank <= 2) return "weak-rank--danger";
  if (rank <= 3) return "weak-rank--warning";
  return "weak-rank--normal";
}

function accuracyPercent(a: number) {
  return Math.max(4, Math.round(a * 100));
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    weak: "薄弱",
    consolidating: "待巩固",
    mastered: "已掌握",
    not_started: "未开始",
  };
  return map[status] || status;
}

function statusType(status: string): string {
  const map: Record<string, string> = {
    weak: "danger",
    consolidating: "warning",
    mastered: "success",
    not_started: "neutral",
  };
  return map[status] || "neutral";
}
</script>

<style lang="scss">
.report-summary {
  padding: 28rpx;
  display: flex;
  flex-direction: column;
  margin-bottom: 8rpx;
}
.report-summary-icon {
  font-size: 40rpx;
  margin-bottom: 8rpx;
}
.report-summary-title {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
  margin-bottom: 12rpx;
}

.report-section {
  margin-top: 24rpx;
}
.report-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 0 8rpx 16rpx;
}
.report-section-title {
  font-size: 32rpx;
  font-weight: 700;
  color: $neutral-900;
}
.report-section-sub {
  font-size: 22rpx;
  color: $neutral-500;
}

.weak-item {
  padding: 24rpx;
  margin-bottom: 16rpx;
}
.weak-item-head {
  display: flex;
  align-items: center;
}
.weak-rank {
  width: 48rpx;
  height: 48rpx;
  border-radius: 12rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16rpx;
  flex-shrink: 0;
}
.weak-rank--danger {
  background: $danger-500;
}
.weak-rank--warning {
  background: $warning-500;
}
.weak-rank--normal {
  background: $neutral-400;
}
.weak-rank-text {
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 800;
}
.weak-item-texts {
  flex: 1;
  min-width: 0;
}
.weak-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.weak-name {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.weak-meta {
  display: flex;
  align-items: center;
  margin-top: 4rpx;
}
.weak-meta-text {
  font-size: 22rpx;
  color: $neutral-500;
}
.weak-meta-dot {
  color: $neutral-300;
  margin: 0 8rpx;
}
.weak-bar {
  height: 10rpx;
  background: $neutral-100;
  border-radius: 5rpx;
  overflow: hidden;
  margin-top: 16rpx;
}
.weak-bar-fill {
  height: 100%;
  background: $danger-500;
  border-radius: 5rpx;
}
.weak-suggestion {
  margin-top: 16rpx;
  background: rgba($info-500, 0.06);
  border-radius: $radius-tag;
  padding: 12rpx 16rpx;
}
.weak-suggestion-label {
  font-size: 22rpx;
  color: $info-500;
  font-weight: 600;
  margin-right: 8rpx;
}
.weak-suggestion-text {
  font-size: 24rpx;
  color: $neutral-500;
  line-height: 1.5;
}

.report-row {
  display: flex;
  gap: 16rpx;
  margin-top: 24rpx;
}
.report-mini {
  flex: 1;
  padding: 24rpx;
}
.report-mini-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.report-mini-list {
  margin-top: 12rpx;
}
.report-mini-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8rpx 0;
  border-bottom: 2rpx solid $neutral-100;
}
.report-mini-item:last-child {
  border-bottom: none;
}
.report-mini-item-name {
  font-size: 24rpx;
  color: $neutral-500;
}
.report-mini-item-num {
  font-size: 24rpx;
  font-weight: 700;
  color: $primary-600;
}
.report-mini-empty {
  font-size: 22rpx;
  color: $neutral-300;
  margin-top: 8rpx;
}

.report-steps {
  padding: 12rpx 24rpx;
}
.report-step {
  display: flex;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 2rpx solid $neutral-100;
}
.report-step:last-child {
  border-bottom: none;
}
.report-step-dot {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background: $primary-100;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16rpx;
  flex-shrink: 0;
}
.report-step-dot-text {
  color: $primary-600;
  font-size: 22rpx;
  font-weight: 700;
}
.report-step-text {
  flex: 1;
  font-size: $font-body;
  color: $neutral-900;
}
</style>
