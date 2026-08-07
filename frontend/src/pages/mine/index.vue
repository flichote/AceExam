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
    </view>

    <!-- 学习数据看板（P1 完整版见 docs/design/pages.md） -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">学习数据</text>
        <text class="section-sub">本周</text>
      </view>
      <view class="card stats">
        <view class="stat">
          <text class="stat-num">{{ stat.total }}</text>
          <text class="stat-label">累计做题</text>
        </view>
        <view class="stat-divider" />
        <view class="stat">
          <text class="stat-num">{{ stat.accuracy }}%</text>
          <text class="stat-label">正确率</text>
        </view>
        <view class="stat-divider" />
        <view class="stat">
          <text class="stat-num">{{ stat.streak }}</text>
          <text class="stat-label">连续打卡(天)</text>
        </view>
      </view>

      <!-- 本周做题柱状（mock，P1 换 ECharts/图表） -->
      <view class="card week">
        <view class="week-bars">
          <view v-for="w in stat.week" :key="w.day" class="week-col">
            <view class="week-bar-track">
              <view class="week-bar" :style="{ height: weekBarHeight(w.count) }" />
            </view>
            <text class="week-day">{{ w.day }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 功能菜单 -->
    <view class="section">
      <view class="card menu">
        <view v-for="item in menus" :key="item.label" class="menu-item" @click="onMenu(item.label)">
          <text class="menu-icon">{{ item.icon }}</text>
          <text class="menu-label">{{ item.label }}</text>
          <text class="menu-arrow">›</text>
        </view>
      </view>
    </view>

    <view class="page-foot">
      <text class="page-foot-text">AceExam v1.0.0 · M2 五件套</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import { useAuthStore } from "@/stores/auth";
import { mockPracticeStat } from "@/mock/stats";

const subjectStore = useSubjectStore();
const authStore = useAuthStore();
// TODO(ep-backend): GET /api/v1/me/stats 就绪后接入 store，当前 mock
const stat = mockPracticeStat();

onShow(() => {
  subjectStore.loadSubjects();
  authStore.refreshUser();
});

const nearestExam = computed(() => {
  const list = subjectStore.subjects;
  if (!list.length) return "--";
  const nearest = list.reduce((min, s) => (s.examCountdown < min.examCountdown ? s : min));
  return `${nearest.name} ${nearest.examCountdown} 天`;
});

const maxWeekCount = Math.max(...stat.week.map((w) => w.count), 1);
function weekBarHeight(count: number) {
  return `${Math.max(8, Math.round((count / maxWeekCount) * 100))}%`;
}

const menus = [
  { icon: "🗓️", label: "备考计划" },
  { icon: "📕", label: "错题本" },
  { icon: "📊", label: "学习数据" },
  { icon: "⚙️", label: "设置" },
];

function onMenu(label: string) {
  if (label === "备考计划") {
    uni.navigateTo({ url: "/pages/plan/create" });
    return;
  }
  if (label === "错题本") {
    uni.switchTab({ url: "/pages/practice/index" });
    return;
  }
  // TODO: M3 实现对应页面
  uni.showToast({ title: `「${label}」将在 M3 提供`, icon: "none" });
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
  font-size: 40rpx;
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

.week {
  margin-top: 24rpx;
  padding: 32rpx 24rpx;
}
.week-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}
.week-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}
.week-bar-track {
  height: 120rpx;
  width: 32rpx;
  background: $neutral-100;
  border-radius: 8rpx;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}
.week-bar {
  width: 100%;
  background: $primary-500;
  border-radius: 8rpx;
  transition: height 400ms ease-out;
}
.week-day {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 12rpx;
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
