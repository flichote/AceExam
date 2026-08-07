<template>
  <view class="page">
    <!-- 自定义顶栏（navigationStyle: custom） -->
    <view class="hero" :style="{ paddingTop: statusBarHeight + 'px' }">
      <view class="hero-top">
        <view class="hero-titles">
          <text class="hero-title">AceExam</text>
          <text class="hero-slogan">期末通关 · 一战上岸</text>
        </view>
        <view class="hero-streak" @click="goChat">
          <text class="hero-streak-icon">🔥</text>
          <text class="hero-streak-text">连胜 {{ maxStreak }} 天</text>
        </view>
      </view>
      <view class="hero-greeting">
        <text class="hero-greeting-text">{{ greeting }}，同学 👋</text>
        <text class="hero-greeting-sub">今天也要离上岸近一步</text>
      </view>
    </view>

    <!-- 科目卡片列表 -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">我的科目</text>
        <text class="section-sub">{{ subjectCount }} 门备考中</text>
      </view>

      <!-- 加载中骨架屏 -->
      <template v-if="subjectStore.loading">
        <LoadingSkeleton v-for="i in 2" :key="i" />
      </template>

      <!-- 加载失败重试 -->
      <view v-else-if="subjectStore.error" class="card error-card">
        <text class="error-text">加载失败：{{ subjectStore.error }}</text>
        <view class="btn btn--primary error-btn" @click="subjectStore.loadSubjects(true)">
          <text class="btn--primary-text">重试</text>
        </view>
      </view>

      <!-- 科目卡片 -->
      <view
        v-for="s in subjectStore.subjects"
        :key="s.id"
        class="card subject-card"
        @click="goPractice(s.id)"
      >
        <view class="subject-main">
          <view class="subject-left">
            <view class="subject-emoji">
              <text class="subject-emoji-text">{{ s.emoji }}</text>
            </view>
            <view class="subject-info">
              <view class="subject-name-row">
                <text class="subject-name">{{ s.name }}</text>
                <SubjectPill
                  :label="statusText[s.status]"
                  :type="statusType[s.status]"
                />
              </view>
              <view class="subject-meta">
                <text class="subject-meta-text">距考试 {{ s.examCountdown }} 天</text>
                <text class="subject-meta-dot">·</text>
                <text class="subject-meta-text">今日 {{ s.todayTask.done }}/{{ s.todayTask.total }} 题</text>
              </view>
              <view class="subject-task">
                <view class="subject-task-bar">
                  <view
                    class="subject-task-fill"
                    :style="{ width: taskPercent(s.todayTask) + '%' }"
                  />
                </view>
              </view>
            </view>
          </view>
          <ProgressRing :percent="s.mastery.percent" :size="64" :stroke-width="5" />
        </view>

        <view class="subject-foot">
          <text class="subject-foot-text">已掌握 {{ s.mastery.mastered }}/{{ s.mastery.total }} 题</text>
          <view class="btn btn--primary subject-go">
            <text class="btn--primary-text">去刷题 →</text>
          </view>
        </view>
      </view>
    </view>

    <!-- AI 备考教练入口 -->
    <view class="section">
      <view class="card ai-entry" @click="goChat">
        <view class="ai-entry-left">
          <view class="ai-entry-icon">
            <text class="ai-entry-icon-text">🤖</text>
          </view>
          <view class="ai-entry-texts">
            <text class="ai-entry-title">AI 备考教练</text>
            <text class="ai-entry-desc">不懂就问，讲到你懂为止</text>
          </view>
        </view>
        <text class="ai-entry-arrow">›</text>
      </view>
    </view>

    <view class="page-foot">
      <text class="page-foot-text">AceExam · 让你的期末稳稳上岸</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import type { SubjectStatus } from "@/types";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";
import SubjectPill from "@/components/SubjectPill.vue";
import ProgressRing from "@/components/ProgressRing.vue";

const subjectStore = useSubjectStore();

const statusBarHeight = ref(20);

onLoad(() => {
  try {
    const info = uni.getSystemInfoSync();
    statusBarHeight.value = info.statusBarHeight || 20;
  } catch {
    statusBarHeight.value = 20;
  }
});

onShow(() => {
  subjectStore.loadSubjects();
});

/** 状态 → 徽章文案 / 类型（docs/design/design-system.md 状态映射） */
const statusText: Record<SubjectStatus, string> = {
  mastered: "已掌握",
  weak: "薄弱",
  consolidating: "待巩固",
  cramming: "突击中",
};
const statusType: Record<SubjectStatus, string> = {
  mastered: "success",
  weak: "danger",
  consolidating: "warning",
  cramming: "cramming",
};

const subjectCount = computed(() => subjectStore.subjects.length);
const maxStreak = computed(() =>
  subjectStore.subjects.reduce((max, s) => Math.max(max, s.streak), 0)
);

function taskPercent(task: { done: number; total: number }) {
  return task.total ? Math.round((task.done / task.total) * 100) : 0;
}

const greeting = computed(() => {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 12) return "早上好";
  if (h < 18) return "下午好";
  return "晚上好";
});

function goPractice(subjectId: string) {
  uni.navigateTo({ url: `/pages/practice/index?subjectId=${subjectId}` });
}

function goChat() {
  uni.navigateTo({ url: "/pages/chat/index" });
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

/* 顶部 hero */
.hero {
  background: linear-gradient(135deg, $primary-500 0%, $primary-600 100%);
  border-bottom-left-radius: 40rpx;
  border-bottom-right-radius: 40rpx;
  padding-left: 32rpx;
  padding-right: 32rpx;
  padding-bottom: 40rpx;
}
.hero-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding-top: 24rpx;
}
.hero-titles {
  display: flex;
  flex-direction: column;
}
.hero-title {
  color: #ffffff;
  font-size: 40rpx;
  font-weight: 800;
  letter-spacing: 1rpx;
}
.hero-slogan {
  color: rgba(255, 255, 255, 0.85);
  font-size: 24rpx;
  margin-top: 4rpx;
}
.hero-streak {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: $radius-tag;
  padding: 8rpx 16rpx;
}
.hero-streak-icon {
  font-size: 28rpx;
  margin-right: 8rpx;
}
.hero-streak-text {
  color: #ffffff;
  font-size: $font-aux;
  font-weight: 600;
}
.hero-greeting {
  margin-top: 32rpx;
  display: flex;
  flex-direction: column;
}
.hero-greeting-text {
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 700;
}
.hero-greeting-sub {
  color: rgba(255, 255, 255, 0.8);
  font-size: 24rpx;
  margin-top: 4rpx;
}

/* 区块 */
.section {
  padding: 32rpx;
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20rpx;
}
.section-title {
  font-size: 32rpx;
  font-weight: 700;
  color: $neutral-900;
}
.section-sub {
  font-size: $font-aux;
  color: $neutral-500;
}

/* 科目卡片 */
.subject-card {
  padding: 28rpx;
  margin-bottom: 24rpx;
}
.subject-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.subject-left {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  margin-right: 20rpx;
}
.subject-emoji {
  width: 88rpx;
  height: 88rpx;
  border-radius: 24rpx;
  background: $primary-100;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20rpx;
  flex-shrink: 0;
}
.subject-emoji-text {
  font-size: 44rpx;
}
.subject-info {
  flex: 1;
  min-width: 0;
}
.subject-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.subject-name {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.subject-meta {
  display: flex;
  align-items: center;
  margin-top: 8rpx;
}
.subject-meta-text {
  font-size: $font-aux;
  color: $neutral-500;
}
.subject-meta-dot {
  font-size: $font-aux;
  color: $neutral-300;
  margin: 0 8rpx;
}
.subject-task {
  margin-top: 12rpx;
}
.subject-task-bar {
  height: 10rpx;
  background: $neutral-100;
  border-radius: 5rpx;
  overflow: hidden;
}
.subject-task-fill {
  height: 100%;
  background: $primary-500;
  border-radius: 5rpx;
  transition: width 400ms ease-out;
}

.subject-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 2rpx solid $neutral-100;
}
.subject-foot-text {
  font-size: $font-aux;
  color: $neutral-500;
}
.subject-go {
  padding: 12rpx 32rpx;
}
.btn--primary-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 600;
}

/* AI 入口 */
.ai-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx;
}
.ai-entry-left {
  display: flex;
  align-items: center;
}
.ai-entry-icon {
  width: 80rpx;
  height: 80rpx;
  border-radius: 24rpx;
  background: linear-gradient(135deg, $primary-500, $primary-600);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20rpx;
}
.ai-entry-icon-text {
  font-size: 40rpx;
}
.ai-entry-texts {
  display: flex;
  flex-direction: column;
}
.ai-entry-title {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
}
.ai-entry-desc {
  font-size: $font-aux;
  color: $neutral-500;
  margin-top: 2rpx;
}
.ai-entry-arrow {
  font-size: 44rpx;
  color: $neutral-300;
}

/* 错误态 */
.error-card {
  padding: 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.error-text {
  color: $danger-500;
  font-size: $font-body;
}
.error-btn {
  margin-top: 20rpx;
  padding: 12rpx 48rpx;
}

.page-foot {
  padding: 24rpx;
  display: flex;
  justify-content: center;
}
.page-foot-text {
  font-size: 22rpx;
  color: $neutral-300;
}
</style>
