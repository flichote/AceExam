<template>
  <view class="page">
    <!-- 顶部 hero -->
    <view class="hero">
      <text class="hero-title">🧭 薄弱诊断</text>
      <text class="hero-desc">10 题快速定位薄弱点，AI 生成专属复习建议</text>
    </view>

    <!-- 摸底自测 -->
    <view class="section">
      <view class="card self-test-card">
        <view class="self-test-head">
          <view class="self-test-icon">
            <text class="self-test-icon-text">📝</text>
          </view>
          <view class="self-test-texts">
            <text class="self-test-title">摸底自测</text>
            <text class="self-test-desc">覆盖各章节，薄弱知识点加权出题</text>
          </view>
        </view>

        <!-- 科目选择 -->
        <view class="self-test-subject">
          <text class="self-test-label">测试科目</text>
          <picker :range="subjectNames" :value="subjectIndex" @change="onSubjectChange">
            <view class="self-test-picker">
              <text class="self-test-picker-text">{{ currentSubjectName }}</text>
              <text class="self-test-picker-arrow">▾</text>
            </view>
          </picker>
        </view>

        <view class="btn btn--primary start-btn" @click="start">
          <text class="start-btn-text">开始自测（10 题）</text>
        </view>
      </view>

      <!-- 上次报告入口 -->
      <view
        v-if="diagnoseStore.report"
        class="card last-report"
        @click="goReport"
      >
        <text class="last-report-icon">📊</text>
        <view class="last-report-texts">
          <text class="last-report-title">查看上次诊断报告</text>
          <text class="last-report-desc">{{ diagnoseStore.report.summary }}</text>
        </view>
        <text class="last-report-arrow">›</text>
      </view>

      <!-- 知识点图谱入口（M3） -->
      <view class="card graph-entry" @click="goGraph">
        <text class="graph-entry-icon">🌳</text>
        <view class="graph-entry-texts">
          <text class="graph-entry-title">知识点图谱</text>
          <text class="graph-entry-desc">章 → 节 → 知识点，状态着色一眼看清</text>
        </view>
        <text class="graph-entry-arrow">›</text>
      </view>
    </view>

    <!-- 薄弱知识点地图（P1 简化：列表） -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">薄弱知识点地图</text>
        <text class="section-sub">点击进入练习</text>
      </view>
      <view v-if="mapItems.length">
        <KnowledgeMap :items="mapItems" @select="onKpSelect" />
      </view>
      <view v-else class="card map-empty">
        <text class="map-empty-text">暂无诊断数据，先做一次摸底自测吧</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import { useDiagnoseStore } from "@/stores/diagnose";
import { usePlanStore } from "@/stores/plan";
import type { KnowledgePointHit } from "@/types";
import KnowledgeMap from "@/components/KnowledgeMap.vue";

const subjectStore = useSubjectStore();
const diagnoseStore = useDiagnoseStore();
const planStore = usePlanStore();

onLoad(() => {
  subjectStore.loadSubjects();
});
onShow(() => {
  subjectStore.loadSubjects();
  planStore.loadActive();
  if (!diagnoseStore.subjectId && subjectStore.subjects.length) {
    diagnoseStore.subjectId = subjectStore.subjects[0].id;
  }
});

const subjectIndex = computed(() => {
  const idx = subjectStore.subjects.findIndex((s) => s.id === diagnoseStore.subjectId);
  return idx < 0 ? 0 : idx;
});
const subjectNames = computed(() => subjectStore.subjects.map((s) => s.name));
const currentSubjectName = computed(
  () => subjectStore.subjectById(diagnoseStore.subjectId)?.name ?? "请选择科目"
);

function onSubjectChange(e: { detail: { value: string | number } }) {
  const idx = Number(e.detail.value);
  const s = subjectStore.subjects[idx];
  if (s) diagnoseStore.subjectId = s.id;
}

async function start() {
  if (!diagnoseStore.subjectId) {
    uni.showToast({ title: "请先选择测试科目", icon: "none" });
    return;
  }
  uni.showLoading({ title: "正在出题…", mask: true });
  await diagnoseStore.start(diagnoseStore.subjectId, 10);
  uni.hideLoading();
  if (diagnoseStore.error) {
    uni.showToast({ title: diagnoseStore.error, icon: "none" });
    return;
  }
  uni.navigateTo({ url: `/pages/diagnose/self-test?reportId=${diagnoseStore.reportId}` });
}

function goReport() {
  uni.navigateTo({ url: `/pages/diagnose/report?reportId=${diagnoseStore.reportId}` });
}

function goGraph() {
  const sid = diagnoseStore.subjectId || subjectStore.subjects[0]?.id || "";
  uni.navigateTo({ url: `/pages/diagnose/graph?subjectId=${encodeURIComponent(sid)}` });
}

/** 薄弱地图数据：计划快照 weak_kps（无计划时为空，引导自测） */
const mapItems = computed<KnowledgePointHit[]>(() => planStore.weakKps);

function onKpSelect() {
  const sid = planStore.plan?.subject_id || subjectStore.subjects[0]?.id;
  if (sid) subjectStore.selectSubject(sid);
  uni.switchTab({ url: "/pages/practice/index" });
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

.hero {
  background: linear-gradient(135deg, $primary-500 0%, $primary-600 100%);
  padding: 48rpx 32rpx 40rpx;
  display: flex;
  flex-direction: column;
}
.hero-title {
  color: #ffffff;
  font-size: 40rpx;
  font-weight: 800;
}
.hero-desc {
  color: rgba(255, 255, 255, 0.85);
  font-size: 24rpx;
  margin-top: 8rpx;
}

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

.self-test-card {
  padding: 28rpx;
}
.self-test-head {
  display: flex;
  align-items: center;
  margin-bottom: 24rpx;
}
.self-test-icon {
  width: 88rpx;
  height: 88rpx;
  border-radius: 24rpx;
  background: $primary-100;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20rpx;
}
.self-test-icon-text {
  font-size: 44rpx;
}
.self-test-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.self-test-title {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
}
.self-test-desc {
  font-size: $font-aux;
  color: $neutral-500;
  margin-top: 2rpx;
}
.self-test-subject {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: $neutral-100;
  border-radius: $radius-btn;
  padding: 16rpx 20rpx;
  margin-bottom: 20rpx;
}
.self-test-label {
  font-size: 24rpx;
  color: $neutral-500;
}
.self-test-picker {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.self-test-picker-text {
  font-size: $font-body;
  color: $primary-600;
  font-weight: 600;
}
.self-test-picker-arrow {
  color: $neutral-300;
  font-size: 24rpx;
}
.start-btn {
  padding: 20rpx 0;
}
.start-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}

.last-report {
  margin-top: 20rpx;
  padding: 24rpx;
  display: flex;
  align-items: center;
}
.last-report-icon {
  font-size: 40rpx;
  margin-right: 16rpx;
}
.last-report-texts {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.last-report-title {
  font-size: $font-body;
  font-weight: 600;
  color: $neutral-900;
}
.last-report-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.last-report-arrow {
  font-size: 40rpx;
  color: $neutral-300;
}

/* 知识点图谱入口（M3） */
.graph-entry {
  margin-top: 20rpx;
  padding: 24rpx;
  display: flex;
  align-items: center;
  border: 3rpx solid $primary-500;
}
.graph-entry-icon {
  font-size: 40rpx;
  margin-right: 16rpx;
}
.graph-entry-texts {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.graph-entry-title {
  font-size: $font-body;
  font-weight: 700;
  color: $primary-600;
}
.graph-entry-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.graph-entry-arrow {
  font-size: 40rpx;
  color: $primary-500;
}

.map-empty {
  padding: 40rpx;
  display: flex;
  justify-content: center;
}
.map-empty-text {
  font-size: $font-aux;
  color: $neutral-300;
}
</style>
