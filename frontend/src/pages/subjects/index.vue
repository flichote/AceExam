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
        <text class="hero-greeting-text">{{ greetingText }} 👋</text>
        <text class="hero-greeting-sub">今天也要离上岸近一步</text>
      </view>
    </view>

    <!-- 今日任务卡片（备考计划，docs/api.md §8） -->
    <view class="plan-wrap">
      <DailyPlanCard
        :plan="planStore.plan"
        :task="planStore.todayTask"
        :checking-in="planStore.checkingIn"
        @checkin="onCheckin"
        @create="goCreatePlan"
      />
    </view>

    <!-- 挂科预警（M3：GET /me/warnings） -->
    <view v-if="warningsReady && warnings.length" class="section">
      <view class="section-head">
        <text class="section-title">挂科预警</text>
        <text class="section-sub">风险提示</text>
      </view>
      <WarningList
        :warnings="warnings"
        :overall-risk="overallRisk"
        @select="goWarningPractice"
      />
    </view>

    <!-- 薄弱知识点速览 Top3 -->
    <view v-if="weakKps.length" class="section">
      <view class="section-head">
        <text class="section-title">薄弱知识点</text>
        <text class="section-sub" @click="goDiagnose">去诊断 →</text>
      </view>
      <view
        v-for="kp in weakKps"
        :key="kp.id"
        class="card weak-card"
        @click="goPracticeByKp(kp)"
      >
        <view class="weak-card-left">
          <text class="weak-card-dot" />
          <text class="weak-card-name">{{ kp.name }}</text>
        </view>
        <SubjectPill label="薄弱" type="danger" />
      </view>
    </view>

    <!-- 我的课程（用户自选，GET /me/subjects，docs/api.md §13.3） -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">我的课程</text>
        <text class="section-sub">{{ mySubjects.length }} 门本学期课程</text>
      </view>

      <!-- 加载中骨架屏 -->
      <template v-if="mySubjectsLoading">
        <LoadingSkeleton v-for="i in 2" :key="i" />
      </template>

      <!-- 加载失败重试 -->
      <view v-else-if="mySubjectsError" class="card error-card">
        <text class="error-text">加载失败：{{ mySubjectsError }}</text>
        <view class="btn btn--primary error-btn" @click="loadMySubjects">
          <text class="btn--primary-text">重试</text>
        </view>
      </view>

      <!-- 空态：未选课 → 引导去广场 -->
      <view v-else-if="!mySubjects.length" class="card empty-card">
        <text class="empty-icon">🧭</text>
        <text class="empty-title">还没有本学期课程</text>
        <text class="empty-desc">去课程广场挑选你的公共课，AceExam 会跟踪每科进度</text>
        <view class="btn btn--primary empty-btn" @click="goPlaza">
          <text class="btn--primary-text">去课程广场 →</text>
        </view>
      </view>

      <!-- 课程卡片（含每科掌握度/进度） -->
      <view
        v-for="it in mySubjects"
        :key="it.subject.id"
        class="card subject-card"
        @click="goPractice(it.subject.id)"
      >
        <view class="subject-main">
          <view class="subject-left">
            <view class="subject-emoji">
              <text class="subject-emoji-text">{{ subjectEmoji(it.subject.id) }}</text>
            </view>
            <view class="subject-info">
              <view class="subject-name-row">
                <text class="subject-name">{{ it.subject.name }}</text>
                <SubjectPill :label="statsLabel(it.stats)" :type="statsType(it.stats)" />
              </view>
              <view class="subject-meta">
                <text class="subject-meta-text">已做 {{ it.stats.question_count }} 题</text>
                <text class="subject-meta-dot">·</text>
                <text class="subject-meta-text">正确率 {{ Math.round(it.stats.accuracy * 100) }}%</text>
              </view>
              <view class="subject-task">
                <view class="subject-task-bar">
                  <view
                    class="subject-task-fill"
                    :style="{ width: masteryPercent(it.stats.mastery) + '%' }"
                  />
                </view>
                <view class="subject-task-meta">
                  <text class="subject-meta-text">掌握度 {{ masteryPercent(it.stats.mastery) }}%</text>
                  <text v-if="it.stats.knowledge_points.weak" class="subject-weak">
                    薄弱 {{ it.stats.knowledge_points.weak }} 个
                  </text>
                </view>
              </view>
            </view>
          </view>
          <ProgressRing :percent="masteryPercent(it.stats.mastery)" :size="64" :stroke-width="5" />
        </view>
      </view>
    </view>

    <!-- 课程广场入口卡片 -->
    <view class="section">
      <view class="card plaza-entry" @click="goPlaza">
        <view class="plaza-entry-left">
          <view class="plaza-entry-icon">
            <text class="plaza-entry-icon-text">📚</text>
          </view>
          <view class="plaza-entry-texts">
            <text class="plaza-entry-title">课程广场</text>
            <text class="plaza-entry-desc">浏览公共课程，随时加入你的本学期课程</text>
          </view>
        </view>
        <text class="plaza-entry-arrow">›</text>
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
import { usePlanStore } from "@/stores/plan";
import { useAuthStore } from "@/stores/auth";
import type { KnowledgePointHit, WarningItem, RiskLevel, UserSubjectItem, UserSubjectStats } from "@/types";
import { fetchWarnings } from "@/api/warnings";
import { fetchDashboard } from "@/api/dashboard";
import { fetchMeSubjects } from "@/api/me";
import { getToken } from "@/utils/request";
import { isOnboarded } from "@/utils/onboarding";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";
import SubjectPill from "@/components/SubjectPill.vue";
import ProgressRing from "@/components/ProgressRing.vue";
import DailyPlanCard from "@/components/DailyPlanCard.vue";
import WarningList from "@/components/WarningList.vue";

const subjectStore = useSubjectStore();
const planStore = usePlanStore();
const authStore = useAuthStore();

const statusBarHeight = ref(20);

/** 我的课程（GET /me/subjects，docs/api.md §13.3） */
const mySubjects = ref<UserSubjectItem[]>([]);
const mySubjectsLoading = ref(false);
const mySubjectsError = ref("");

/** 挂科预警（M3） */
const warnings = ref<WarningItem[]>([]);
const overallRisk = ref<RiskLevel | null>(null);
const warningsReady = ref(false);

onLoad(() => {
  try {
    const info = uni.getSystemInfoSync();
    statusBarHeight.value = info.statusBarHeight || 20;
  } catch {
    statusBarHeight.value = 20;
  }
});

onShow(() => {
  authStore.refreshUser();
  subjectStore.loadSubjects();
  planStore.loadActive();
  loadMySubjects();
  loadWarnings();
  loadStreak();
  maybeRedirectOnboarding();
});

/** 首次使用引导：登录后未配置专业/课程 → 选课引导页（docs/api.md §13 / architecture.md §13.3） */
function maybeRedirectOnboarding() {
  if (!getToken() || isOnboarded()) return;
  if (mySubjects.value.length > 0) return;
  setTimeout(() => {
    uni.reLaunch({ url: "/pages/onboarding/index" });
  }, 300);
}

async function loadMySubjects() {
  mySubjectsLoading.value = true;
  mySubjectsError.value = "";
  try {
    const res = await fetchMeSubjects();
    mySubjects.value = res.items;
  } catch (e) {
    mySubjectsError.value = (e as Error).message || "加载失败";
  } finally {
    mySubjectsLoading.value = false;
  }
}

/** 课程 emoji 兜底（UserSubjectItem 无 emoji 字段，用 id 关键词映射） */
function subjectEmoji(id: string): string {
  if (id.includes("math")) return "📐";
  if (id.includes("eng") || id.includes("english")) return "🇬🇧";
  if (id.includes("phy")) return "⚛️";
  if (id.includes("prob")) return "🎲";
  if (id.includes("algebra")) return "🧮";
  return "📘";
}

/** 掌握度（0~1）→ 0-100 */
function masteryPercent(mastery: number): number {
  return Math.max(0, Math.min(100, Math.round(mastery * 100)));
}

/** 每科状态徽章：按掌握度近似映射（design-system 状态映射） */
function statsLabel(stats: UserSubjectStats): string {
  if (stats.mastery >= 0.8) return "已掌握";
  if (stats.mastery >= 0.4) return "待巩固";
  if (stats.question_count > 0) return "薄弱";
  return "未开始";
}
function statsType(stats: UserSubjectStats): string {
  if (stats.mastery >= 0.8) return "success";
  if (stats.mastery >= 0.4) return "warning";
  if (stats.question_count > 0) return "danger";
  return "cramming";
}

async function loadWarnings() {
  try {
    const res = await fetchWarnings();
    warnings.value = res.items;
    overallRisk.value = res.overall_risk;
  } catch {
    warnings.value = [];
    overallRisk.value = null;
  } finally {
    warningsReady.value = true;
  }
}

const maxStreak = computed(() => {
  if (dashboardStreak.value > 0) return dashboardStreak.value;
  return subjectStore.subjects.reduce((max, s) => Math.max(max, s.streak), 0);
});
const dashboardStreak = ref(0);

/** 首页连胜徽章：优先 GET /me/dashboard（M3），无则用科目 streak 兜底 */
async function loadStreak() {
  try {
    const d = await fetchDashboard();
    dashboardStreak.value = d.streak.current;
  } catch {
    dashboardStreak.value = 0;
  }
}

/** 薄弱知识点速览（Top3，来自计划快照 weak_kps） */
const weakKps = computed<KnowledgePointHit[]>(() => {
  const all = planStore.weakKps.filter((k) => (k.status || "").includes("weak"));
  return all.slice(0, 3);
});

const greeting = computed(() => {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 12) return "早上好";
  if (h < 18) return "下午好";
  return "晚上好";
});

/** 首页问候：登录用户显示「用户名同学，早上好」；未登录/无用户回退「同学」 */
const greetingText = computed(() => {
  const name = authStore.user?.username?.trim();
  return name ? `${name} 同学，${greeting.value}` : `${greeting.value}，同学`;
});

/** tab 间传递科目：selectSubject + switchTab（navigateTo 无法打开 tabBar 页） */
function goPractice(subjectId: string) {
  subjectStore.selectSubject(subjectId);
  uni.switchTab({ url: "/pages/practice/index" });
}

/** 课程广场 */
function goPlaza() {
  uni.navigateTo({ url: "/pages/plaza/index" });
}

function goPracticeByKp(kp: KnowledgePointHit) {
  const sid = planStore.plan?.subject_id || mySubjects.value[0]?.subject.id || subjectStore.subjects[0]?.id;
  if (sid) subjectStore.selectSubject(sid);
  uni.switchTab({ url: "/pages/practice/index" });
}

/** 预警条目 → 对应知识点练习 */
function goWarningPractice(w: WarningItem) {
  const sid = planStore.plan?.subject_id || mySubjects.value[0]?.subject.id || subjectStore.subjects[0]?.id;
  if (sid) subjectStore.selectSubject(sid);
  uni.switchTab({
    url: `/pages/practice/index?subjectId=${encodeURIComponent(sid || "")}&kpId=${encodeURIComponent(w.knowledge_point_id)}`,
  });
}

function goCreatePlan(subjectId?: string) {
  const qs = subjectId ? `?subjectId=${subjectId}` : "";
  uni.navigateTo({ url: `/pages/plan/create${qs}` });
}

function goChat() {
  uni.navigateTo({ url: "/pages/chat/index" });
}

function goDiagnose() {
  uni.switchTab({ url: "/pages/diagnose/index" });
}

function onCheckin() {
  planStore.checkin();
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

/* 今日任务卡（浮在 hero 下沿） */
.plan-wrap {
  margin-top: -20rpx;
  position: relative;
  z-index: 1;
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
  color: $info-500;
}

/* 薄弱速览 */
.weak-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
  margin-bottom: 12rpx;
}
.weak-card-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.weak-card-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: $danger-500;
}
.weak-card-name {
  font-size: $font-body;
  font-weight: 600;
  color: $neutral-900;
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

/* 我的课程空态 */
.empty-card {
  padding: 48rpx 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.empty-icon {
  font-size: 56rpx;
}
.empty-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
  margin-top: 16rpx;
}
.empty-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 8rpx;
  line-height: 1.6;
}
.empty-btn {
  margin-top: 24rpx;
  padding: 14rpx 40rpx;
}

/* 课程广场入口 */
.plaza-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx;
}
.plaza-entry-left {
  display: flex;
  align-items: center;
}
.plaza-entry-icon {
  width: 80rpx;
  height: 80rpx;
  border-radius: 24rpx;
  background: linear-gradient(135deg, $primary-500, $primary-600);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20rpx;
}
.plaza-entry-icon-text {
  font-size: 40rpx;
}
.plaza-entry-texts {
  display: flex;
  flex-direction: column;
}
.plaza-entry-title {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
}
.plaza-entry-desc {
  font-size: $font-aux;
  color: $neutral-500;
  margin-top: 2rpx;
}
.plaza-entry-arrow {
  font-size: 44rpx;
  color: $neutral-300;
}

/* 课程卡片内掌握度行 */
.subject-task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6rpx;
}
.subject-weak {
  font-size: 20rpx;
  color: $danger-500;
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
