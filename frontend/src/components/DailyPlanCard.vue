<template>
  <!-- 无计划：引导创建 -->
  <view v-if="!plan" class="plan-card card plan-card--empty" @click="$emit('create')">
    <view class="plan-empty-icon">🗓️</view>
    <view class="plan-empty-texts">
      <text class="plan-empty-title">还没有备考计划</text>
      <text class="plan-empty-desc">设置考试科目与日期，AI 教练为你生成每日任务</text>
    </view>
    <view class="btn btn--primary plan-empty-btn">
      <text class="plan-empty-btn-text">去创建 →</text>
    </view>
  </view>

  <!-- 有计划：倒计时 + 今日任务 + 打卡 -->
  <view v-else class="plan-card card">
    <view class="plan-head">
      <view class="plan-head-left">
        <text class="plan-head-icon">🗓️</text>
        <view class="plan-head-texts">
          <text class="plan-title">{{ plan.title }}</text>
          <text class="plan-status">进行中</text>
        </view>
      </view>
      <view class="plan-countdown">
        <text class="plan-countdown-num">{{ plan.days_left }}</text>
        <text class="plan-countdown-unit">天后考试</text>
      </view>
    </view>

    <!-- 今日任务 -->
    <view v-if="task" class="plan-task">
      <view class="plan-task-head">
        <text class="plan-task-title">今日任务</text>
        <text class="plan-task-date">{{ shortDate(task.date) }}</text>
      </view>
      <view class="plan-task-bar">
        <view
          class="plan-task-fill"
          :style="{ width: taskPercent + '%' }"
        />
      </view>
      <view class="plan-task-meta">
        <text class="plan-task-meta-text">
          已完成 {{ task.done?.questions_practiced ?? 0 }}/{{ task.target_questions }} 题
          · 答对 {{ task.done?.correct_count ?? 0 }}
        </text>
        <text v-if="task.type === 'weak_practice'" class="plan-task-tag">薄弱优先</text>
      </view>

      <!-- 今日重点知识点 -->
      <view v-if="task.focus_kps && task.focus_kps.length" class="plan-kps">
        <text class="plan-kps-label">今日重点</text>
        <view class="plan-kps-list">
          <SubjectPill
            v-for="kp in task.focus_kps"
            :key="kp.id"
            :label="kp.name"
            type="danger"
          />
        </view>
      </view>
      <text v-if="task.reason" class="plan-reason">{{ task.reason }}</text>

      <!-- 打卡按钮 -->
      <view
        class="btn plan-checkin"
        :class="checkedIn ? 'plan-checkin--done' : 'btn--primary'"
        :disabled="checkedIn || checkingIn"
        @click="$emit('checkin')"
      >
        <text
          class="plan-checkin-text"
          :class="checkedIn ? 'plan-checkin-text--done' : ''"
        >
          {{ checkedIn ? "✓ 今日已打卡" : checkingIn ? "打卡中…" : "打卡" }}
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Plan, TodayTask } from "@/types";
import SubjectPill from "./SubjectPill.vue";

const props = withDefaults(
  defineProps<{
    plan: Plan | null;
    task: TodayTask | null;
    checkingIn?: boolean;
  }>(),
  {
    plan: null,
    task: null,
    checkingIn: false,
  }
);

defineEmits<{
  (e: "checkin"): void;
  (e: "create"): void;
}>();

const taskPercent = computed(() => {
  if (!props.task || !props.task.target_questions) return 0;
  const pct = ((props.task.done?.questions_practiced ?? 0) / props.task.target_questions) * 100;
  return Math.min(100, Math.round(pct));
});

const checkedIn = computed(() => props.task?.done?.checked_in ?? false);

function shortDate(date: string) {
  const d = new Date(date.replace(/-/g, "/"));
  if (Number.isNaN(d.getTime())) return date;
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}
</script>

<style lang="scss">
.plan-card {
  padding: 28rpx;
  margin: 0 32rpx 24rpx;
  background: linear-gradient(135deg, $primary-500 0%, $primary-600 100%);
  border-radius: $radius-card;
}
.plan-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.plan-head-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.plan-head-icon {
  font-size: 40rpx;
}
.plan-head-texts {
  display: flex;
  flex-direction: column;
}
.plan-title {
  color: #ffffff;
  font-size: $font-card-title;
  font-weight: 700;
}
.plan-status {
  color: rgba(255, 255, 255, 0.85);
  font-size: 22rpx;
  margin-top: 2rpx;
}
.plan-countdown {
  display: flex;
  align-items: baseline;
  background: rgba(255, 255, 255, 0.2);
  border-radius: $radius-tag;
  padding: 8rpx 16rpx;
}
.plan-countdown-num {
  color: #ffffff;
  font-size: 36rpx;
  font-weight: 800;
  margin-right: 6rpx;
}
.plan-countdown-unit {
  color: rgba(255, 255, 255, 0.9);
  font-size: 20rpx;
}

.plan-task {
  background: rgba(255, 255, 255, 0.96);
  border-radius: $radius-btn;
  padding: 20rpx;
  margin-top: 20rpx;
}
.plan-task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.plan-task-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.plan-task-date {
  font-size: 22rpx;
  color: $neutral-500;
}
.plan-task-bar {
  height: 10rpx;
  background: $neutral-100;
  border-radius: 5rpx;
  overflow: hidden;
  margin-top: 12rpx;
}
.plan-task-fill {
  height: 100%;
  background: $primary-500;
  border-radius: 5rpx;
  transition: width 400ms ease-out;
}
.plan-task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10rpx;
}
.plan-task-meta-text {
  font-size: 22rpx;
  color: $neutral-500;
}
.plan-task-tag {
  font-size: 20rpx;
  color: $danger-500;
  background: rgba($danger-500, 0.1);
  border-radius: $radius-tag;
  padding: 2rpx 10rpx;
}

.plan-kps {
  margin-top: 12rpx;
}
.plan-kps-label {
  font-size: 22rpx;
  color: $neutral-500;
  margin-right: 8rpx;
}
.plan-kps-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-top: 6rpx;
}
.plan-reason {
  display: block;
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 12rpx;
  line-height: 1.5;
}

.plan-checkin {
  margin-top: 16rpx;
  padding: 18rpx 0;
  border-radius: $radius-btn;
}
.plan-checkin--done {
  background: rgba($success-500, 0.12);
  pointer-events: none;
}
.plan-checkin-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}
.plan-checkin-text--done {
  color: $success-500;
}

/* 空态引导 */
.plan-card--empty {
  background: #ffffff;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  display: flex;
}
.plan-empty-icon {
  font-size: 48rpx;
  margin-right: 16rpx;
}
.plan-empty-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.plan-empty-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.plan-empty-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 4rpx;
}
.plan-empty-btn {
  padding: 10rpx 24rpx;
  flex-shrink: 0;
}
.plan-empty-btn-text {
  color: #ffffff;
  font-size: $font-aux;
  font-weight: 600;
}
</style>
