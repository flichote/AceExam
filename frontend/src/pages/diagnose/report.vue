<template>
  <view class="page">
    <!-- 加载中 -->
    <view v-if="loading" class="center">
      <view class="loading-spinner" />
      <text class="loading-text">诊断报告生成中…</text>
    </view>

    <!-- 无报告 -->
    <view v-else-if="!report" class="center">
      <EmptyState
        icon="🧭"
        title="暂无诊断报告"
        desc="先做一次摸底自测，AI 会为你生成薄弱点分析与建议"
        action-text="去做自测"
        @action="goDiagnose"
      />
    </view>

    <template v-else>
      <!-- 诊断报告 -->
      <view class="head">
        <text class="head-title">📊 诊断报告</text>
        <text class="head-sub">基于本次自测 + 历史练习数据</text>
      </view>
      <DiagnoseReport :report="report" />

      <!-- 薄弱知识点地图（P1 简化：列表） -->
      <view class="section">
        <view class="section-head">
          <text class="section-title">薄弱知识点地图</text>
          <text class="section-sub">点击进入练习</text>
        </view>
        <KnowledgeMap :items="mapItems" @select="onKpSelect" />
      </view>

      <!-- 底部操作 -->
      <view class="foot">
        <view class="btn btn--primary foot-btn" @click="goPractice">
          <text class="foot-btn-text">按薄弱点去刷题</text>
        </view>
        <view class="btn foot-btn foot-btn--plain" @click="reRun">
          <text class="foot-btn-text foot-btn-text--plain">重新自测</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { useDiagnoseStore } from "@/stores/diagnose";
import { useSubjectStore } from "@/stores/subject";
import type { WeakTop, KnowledgePointHit } from "@/types";
import DiagnoseReport from "@/components/DiagnoseReport.vue";
import KnowledgeMap from "@/components/KnowledgeMap.vue";
import EmptyState from "@/components/EmptyState.vue";

const diagnose = useDiagnoseStore();
const subjectStore = useSubjectStore();

const loading = ref(false);

onLoad(() => {
  // 报告在 diagnoseStore（提交后存内存）；直接进入时回诊断页
  if (!diagnose.report) {
    loading.value = false;
    return;
  }
});

const report = computed(() => diagnose.report);

/** weak_top5 → KnowledgeMap 可识别结构（status/accuracy 字段对齐） */
const mapItems = computed<KnowledgePointHit[]>(() =>
  (diagnose.report?.weak_top5 ?? []).map((w: WeakTop) => ({
    id: w.knowledge_point_id,
    name: w.knowledge_point_name,
    level: w.level,
    status: w.status,
    accuracy: w.accuracy,
    practice_count: w.practice_count,
    reason: w.suggestion,
  }))
);

function goPractice() {
  const sid = diagnose.subjectId || subjectStore.subjects[0]?.id;
  if (sid) subjectStore.selectSubject(sid);
  uni.switchTab({ url: "/pages/practice/index" });
}

function onKpSelect() {
  goPractice();
}

function reRun() {
  diagnose.reset();
  uni.navigateBack();
}

function goDiagnose() {
  uni.switchTab({ url: "/pages/diagnose/index" });
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

.head {
  padding: 32rpx 32rpx 8rpx;
  display: flex;
  flex-direction: column;
}
.head-title {
  font-size: 40rpx;
  font-weight: 800;
  color: $neutral-900;
}
.head-sub {
  font-size: 24rpx;
  color: $neutral-500;
  margin-top: 4rpx;
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

.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}
.loading-spinner {
  width: 48rpx;
  height: 48rpx;
  border: 6rpx solid $primary-100;
  border-top-color: $primary-500;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-text {
  margin-top: 12rpx;
  font-size: $font-aux;
  color: $neutral-500;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.foot {
  padding: 0 32rpx calc(24rpx + env(safe-area-inset-bottom));
  display: flex;
  gap: 16rpx;
}
.foot-btn {
  flex: 1;
  padding: 20rpx 0;
}
.foot-btn--plain {
  background: $neutral-100;
}
.foot-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 1rpx;
}
.foot-btn-text--plain {
  color: $neutral-500;
}
</style>
