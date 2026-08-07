<template>
  <view class="page">
    <!-- 个人信息卡 -->
    <view class="card profile">
      <view class="profile-avatar">
        <text class="profile-avatar-text">🎓</text>
      </view>
      <view class="profile-info">
        <view class="profile-name-row">
          <text class="profile-name">{{ authStore.user?.username || "期末选手" }}</text>
          <view class="profile-badge" @click="goLogin">
            <text class="profile-badge-text">{{ authStore.isMember ? "会员版" : "免费版" }}</text>
          </view>
        </view>
        <text class="profile-sub">距考试最近：{{ nearestExam }}</text>
      </view>
      <StreakBadge v-if="dashboard && dashboard.streak.current > 0" :days="dashboard.streak.current" variant="primary" />
    </view>

    <!-- 学习数据看板（M3：GET /me/dashboard） -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">学习数据</text>
        <text class="section-sub">全部科目</text>
      </view>

      <view v-if="dashboardLoading" class="card stats">
        <LoadingSkeleton />
      </view>
      <view v-else-if="dashboardError" class="card error-card">
        <text class="error-text">{{ dashboardError }}</text>
        <view class="btn btn--primary error-btn" @click="loadDashboard">
          <text class="btn--primary-text">重试</text>
        </view>
      </view>

      <template v-else-if="dashboard">
        <!-- 汇总卡：做题量 / 正确率 / 掌握度 / 连胜 -->
        <view class="card stats">
          <view class="stat">
            <text class="stat-num">{{ dashboard.totals.questions_practiced }}</text>
            <text class="stat-label">累计做题</text>
          </view>
          <view class="stat-divider" />
          <view class="stat">
            <text class="stat-num">{{ Math.round(dashboard.totals.accuracy * 100) }}%</text>
            <text class="stat-label">正确率</text>
          </view>
          <view class="stat-divider" />
          <view class="stat">
            <text class="stat-num">{{ Math.round(dashboard.mastery.mastery_pct * 100) }}%</text>
            <text class="stat-label">掌握度</text>
          </view>
          <view class="stat-divider" />
          <view class="stat">
            <text class="stat-num">🔥{{ dashboard.streak.current }}</text>
            <text class="stat-label">连胜(天)</text>
          </view>
        </view>

        <!-- 趋势折线图（近 30 天做题量 + 正确率） -->
        <view class="card trend">
          <view class="trend-head">
            <text class="trend-title">近 30 天趋势</text>
            <text class="trend-sub">柱：做题量 · 线：正确率</text>
          </view>
          <TrendLineChart :items="trendItems" :width="chartWidth" />
        </view>

        <!-- 薄弱点 + 每科分解 -->
        <view class="card weak-summary">
          <view class="weak-summary-head">
            <text class="weak-summary-title">薄弱点</text>
            <text class="weak-summary-count">
              <text class="weak-summary-count--danger">{{ dashboard.weak_points.weak }}</text> 薄弱 ·
              <text class="weak-summary-count--warning">{{ dashboard.weak_points.consolidating }}</text> 待巩固
            </text>
          </view>
          <view class="per-subject">
            <view v-for="ps in dashboard.per_subject" :key="ps.subject_id" class="per-subject-row">
              <text class="per-subject-name">{{ ps.subject_name }}</text>
              <view class="per-subject-bar">
                <view class="per-subject-fill" :style="{ width: Math.round(ps.mastery_pct * 100) + '%' }" />
              </view>
              <text class="per-subject-pct">{{ Math.round(ps.mastery_pct * 100) }}%</text>
            </view>
          </view>
        </view>
      </template>
    </view>

    <!-- 功能菜单 -->
    <view class="section">
      <view class="card menu">
        <view v-for="item in menus" :key="item.label" class="menu-item" @click="onMenu(item)">
          <text class="menu-icon">{{ item.icon }}</text>
          <text class="menu-label">{{ item.label }}</text>
          <text class="menu-arrow">›</text>
        </view>
      </view>
    </view>

    <view class="page-foot">
      <text class="page-foot-text">AceExam v1.0.0 · M3 体验增强</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import { useAuthStore } from "@/stores/auth";
import { fetchDashboard, fetchDashboardTrend } from "@/api/dashboard";
import type { DashboardSummary, TrendItem } from "@/types";
import StreakBadge from "@/components/StreakBadge.vue";
import TrendLineChart from "@/components/TrendLineChart.vue";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";

const subjectStore = useSubjectStore();
const authStore = useAuthStore();

const dashboard = ref<DashboardSummary | null>(null);
const dashboardLoading = ref(false);
const dashboardError = ref("");
const trendItems = ref<TrendItem[]>([]);
const chartWidth = ref(311); // 343 - 卡片 padding 32

onShow(async () => {
  subjectStore.loadSubjects();
  authStore.refreshUser();
  await loadDashboard();
});

async function loadDashboard() {
  dashboardLoading.value = true;
  dashboardError.value = "";
  try {
    const [d, t] = await Promise.all([
      fetchDashboard(),
      fetchDashboardTrend({ days: 30, granularity: "day" }),
    ]);
    dashboard.value = d;
    trendItems.value = t.items;
  } catch (e) {
    dashboardError.value = (e as Error).message || "看板加载失败";
  } finally {
    dashboardLoading.value = false;
  }
}

const nearestExam = computed(() => {
  const list = subjectStore.subjects;
  if (!list.length) return "--";
  const nearest = list.reduce((min, s) => (s.examCountdown < min.examCountdown ? s : min));
  return `${nearest.name} ${nearest.examCountdown} 天`;
});

const menus = [
  { icon: "🗓️", label: "备考计划", action: "plan" },
  { icon: "📕", label: "错题本", action: "wrong" },
  { icon: "🏆", label: "排行榜", action: "leaderboard" },
  { icon: "🌳", label: "知识点图谱", action: "graph" },
  { icon: "⚙️", label: "设置", action: "settings" },
];

function onMenu(item: { label: string; action: string }) {
  if (item.action === "plan") {
    uni.navigateTo({ url: "/pages/plan/create" });
    return;
  }
  if (item.action === "wrong") {
    uni.switchTab({ url: "/pages/practice/index" });
    return;
  }
  if (item.action === "leaderboard") {
    uni.navigateTo({ url: "/pages/leaderboard/index" });
    return;
  }
  if (item.action === "graph") {
    const sid = subjectStore.subjects[0]?.id || "";
    uni.navigateTo({ url: `/pages/diagnose/graph?subjectId=${encodeURIComponent(sid)}` });
    return;
  }
  uni.showToast({ title: "「设置」将在后续版本提供", icon: "none" });
}

function goLogin() {
  uni.navigateTo({ url: "/pages/auth/login" });
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

/* 个人卡 */
.profile {
  margin: 32rpx;
  display: flex;
  align-items: center;
  padding: 32rpx;
}
.profile-avatar {
  width: 112rpx;
  height: 112rpx;
  border-radius: 50%;
  background: $primary-100;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 24rpx;
  flex-shrink: 0;
}
.profile-avatar-text {
  font-size: 56rpx;
}
.profile-info {
  flex: 1;
  min-width: 0;
}
.profile-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.profile-name {
  font-size: 40rpx;
  font-weight: 800;
  color: $neutral-900;
}
.profile-badge {
  background: $primary-100;
  border-radius: $radius-tag;
  padding: 4rpx 12rpx;
}
.profile-badge-text {
  font-size: 20rpx;
  color: $primary-600;
  font-weight: 600;
}
.profile-sub {
  font-size: $font-aux;
  color: $neutral-500;
  margin-top: 8rpx;
}

/* 数据 */
.section {
  padding: 0 32rpx 32rpx;
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

.stats {
  display: flex;
  align-items: center;
  padding: 32rpx 0;
}
.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stat-num {
  font-size: 34rpx;
  font-weight: 800;
  color: $primary-600;
}
.stat-label {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 8rpx;
}
.stat-divider {
  width: 2rpx;
  height: 56rpx;
  background: $neutral-100;
}

/* 趋势图 */
.trend {
  margin-top: 24rpx;
  padding: 24rpx;
}
.trend-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12rpx;
}
.trend-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.trend-sub {
  font-size: 20rpx;
  color: $neutral-300;
}

/* 薄弱 + 每科分解 */
.weak-summary {
  margin-top: 24rpx;
  padding: 24rpx;
}
.weak-summary-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.weak-summary-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.weak-summary-count {
  font-size: 22rpx;
  color: $neutral-500;
}
.weak-summary-count--danger {
  color: $danger-500;
  font-weight: 700;
}
.weak-summary-count--warning {
  color: $warning-500;
  font-weight: 700;
}
.per-subject {
  margin-top: 16rpx;
}
.per-subject-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 10rpx;
}
.per-subject-name {
  width: 160rpx;
  font-size: 22rpx;
  color: $neutral-500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.per-subject-bar {
  flex: 1;
  height: 12rpx;
  background: $neutral-100;
  border-radius: 6rpx;
  overflow: hidden;
}
.per-subject-fill {
  height: 100%;
  background: $primary-500;
  border-radius: 6rpx;
  transition: width 400ms ease-out;
}
.per-subject-pct {
  width: 64rpx;
  text-align: right;
  font-size: 22rpx;
  color: $neutral-900;
  font-weight: 600;
}

/* 菜单 */
.menu {
  padding: 8rpx 28rpx;
}
.menu-item {
  display: flex;
  align-items: center;
  padding: 28rpx 0;
  border-bottom: 2rpx solid $neutral-100;
}
.menu-item:last-child {
  border-bottom: none;
}
.menu-icon {
  font-size: 32rpx;
  margin-right: 20rpx;
}
.menu-label {
  flex: 1;
  font-size: $font-body;
  color: $neutral-900;
}
.menu-arrow {
  font-size: 40rpx;
  color: $neutral-300;
}

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
