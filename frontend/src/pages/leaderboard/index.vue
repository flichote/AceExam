<template>
  <view class="page">
    <!-- 维度切换：全局 / 科目 -->
    <view class="scope-bar">
      <view
        class="scope-tab"
        :class="{ 'scope-tab--active': scope === 'global' }"
        @click="switchScope('global')"
      >
        <text class="scope-tab-text" :class="{ 'scope-tab-text--active': scope === 'global' }">全站榜</text>
      </view>
      <view
        class="scope-tab"
        :class="{ 'scope-tab--active': scope === 'subject' }"
        @click="switchScope('subject')"
      >
        <text class="scope-tab-text" :class="{ 'scope-tab-text--active': scope === 'subject' }">科目榜</text>
      </view>
    </view>

    <!-- 科目选择（科目榜时显示） -->
    <view v-if="scope === 'subject'" class="subject-picker">
      <picker :range="subjectNames" :value="subjectIndex" @change="onSubjectChange">
        <view class="subject-picker-inner">
          <text class="subject-picker-label">科目</text>
          <text class="subject-picker-value">{{ currentSubjectName }}</text>
          <text class="subject-picker-arrow">▾</text>
        </view>
      </picker>
    </view>

    <!-- 加载 / 错误 / 列表 -->
    <view v-if="loading" class="content">
      <LoadingSkeleton v-for="i in 4" :key="i" />
    </view>
    <view v-else-if="error" class="content">
      <EmptyState icon="⚠️" title="排行榜加载失败" :desc="error" action-text="重试" @action="reload" />
    </view>

    <template v-else>
      <!-- 我的排名（置顶） -->
      <view v-if="me" class="me-row card">
        <view class="me-rank">
          <text class="me-rank-num">{{ me.rank ?? "—" }}</text>
          <text class="me-rank-label">我的排名</text>
        </view>
        <view class="me-stats">
          <view class="me-stat">
            <text class="me-stat-num">{{ me.total_correct }}</text>
            <text class="me-stat-label">做对</text>
          </view>
          <view class="me-stat">
            <text class="me-stat-num">{{ Math.round(me.accuracy * 100) }}%</text>
            <text class="me-stat-label">正确率</text>
          </view>
          <view class="me-stat">
            <text class="me-stat-num">{{ me.questions_practiced }}</text>
            <text class="me-stat-label">做题量</text>
          </view>
        </view>
        <text v-if="me.rank == null" class="me-hint">再对 {{ me.total_correct >= 30 ? 1 : 30 - me.total_correct }} 题进榜</text>
      </view>

      <!-- 排行列表 -->
      <view v-if="items.length" class="list">
        <view v-for="item in items" :key="item.user_id" class="card row" :class="{ 'row--top': item.rank <= 3 }">
          <view class="row-rank" :class="`row-rank--${item.rank}`">
            <text class="row-rank-text">{{ item.rank }}</text>
          </view>
          <view class="row-user">
            <text class="row-username">{{ item.username }}</text>
            <view class="row-tags">
              <text class="row-tag">🔥 {{ item.current_streak }} 天</text>
            </view>
          </view>
          <view class="row-stats">
            <text class="row-stat">做对 {{ item.total_correct }}</text>
            <text class="row-stat">正确率 {{ Math.round(item.accuracy * 100) }}%</text>
            <text class="row-stat">做题 {{ item.questions_practiced }}</text>
          </view>
        </view>
      </view>
      <view v-else class="content">
        <EmptyState icon="🏆" title="榜上暂时无人" desc="做题 30 题以上即可上榜" />
      </view>

      <!-- 加载更多 -->
      <view v-if="hasMore" class="load-more" @click="loadMore">
        <text class="load-more-text">加载更多</text>
      </view>
      <view v-else-if="items.length" class="load-more load-more--end">
        <text class="load-more-text">已经到底啦</text>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import { fetchLeaderboard } from "@/api/leaderboard";
import type { LeaderboardItem, LeaderboardResponse } from "@/types";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";

const subjectStore = useSubjectStore();

const scope = ref<"global" | "subject">("global");
const subjectId = ref("");
const items = ref<LeaderboardItem[]>([]);
const me = ref<LeaderboardResponse["me"]>(null);
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const loading = ref(false);
const error = ref("");

const subjects = computed(() => subjectStore.subjects);
const subjectNames = computed(() => subjectStore.subjects.map((s) => s.name));
const subjectIndex = computed(() => {
  const idx = subjectStore.subjects.findIndex((s) => s.id === subjectId.value);
  return idx < 0 ? 0 : idx;
});
const currentSubjectName = computed(
  () => subjectStore.subjectById(subjectId.value)?.name ?? "全部科目"
);
const hasMore = computed(() => items.value.length < total.value);

onLoad(async () => {
  await subjectStore.loadSubjects();
  if (!subjectId.value && subjectStore.subjects.length) {
    subjectId.value = subjectStore.subjects[0].id;
  }
});

onShow(() => {
  reload();
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const res = await fetchLeaderboard({
      scope: scope.value,
      subjectId: scope.value === "subject" ? subjectId.value : undefined,
      page: page.value,
      pageSize,
    });
    items.value = page.value === 1 ? res.items : [...items.value, ...res.items];
    total.value = res.total;
    me.value = res.me;
  } catch (e) {
    error.value = (e as Error).message || "排行榜加载失败";
  } finally {
    loading.value = false;
  }
}

function reload() {
  page.value = 1;
  load();
}

function loadMore() {
  page.value += 1;
  load();
}

function switchScope(s: "global" | "subject") {
  if (scope.value === s) return;
  scope.value = s;
  reload();
}

function onSubjectChange(e: { detail: { value: string | number } }) {
  const idx = Number(e.detail.value);
  const s = subjectStore.subjects[idx];
  if (s) {
    subjectId.value = s.id;
    reload();
  }
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

/* 维度切换 */
.scope-bar {
  display: flex;
  gap: 12rpx;
  padding: 24rpx 32rpx 0;
}
.scope-tab {
  flex: 1;
  padding: 16rpx 0;
  border-radius: $radius-btn;
  background: #ffffff;
  border: 2rpx solid $neutral-300;
  display: flex;
  justify-content: center;
}
.scope-tab--active {
  background: $primary-500;
  border-color: $primary-500;
}
.scope-tab-text {
  font-size: $font-body;
  color: $neutral-500;
  font-weight: 600;
}
.scope-tab-text--active {
  color: #ffffff;
}

/* 科目选择 */
.subject-picker {
  padding: 20rpx 32rpx 0;
}
.subject-picker-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #ffffff;
  border-radius: $radius-btn;
  padding: 16rpx 24rpx;
}
.subject-picker-label {
  font-size: 24rpx;
  color: $neutral-500;
}
.subject-picker-value {
  font-size: $font-body;
  color: $primary-600;
  font-weight: 600;
}
.subject-picker-arrow {
  color: $neutral-300;
  font-size: 24rpx;
}

.content {
  padding: 24rpx 32rpx;
}

/* 我的排名 */
.me-row {
  margin: 24rpx 32rpx 0;
  padding: 24rpx;
  display: flex;
  align-items: center;
  border: 3rpx solid $primary-500;
}
.me-rank {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-right: 24rpx;
  border-right: 2rpx solid $neutral-100;
}
.me-rank-num {
  font-size: 40rpx;
  font-weight: 800;
  color: $primary-600;
}
.me-rank-label {
  font-size: 20rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.me-stats {
  flex: 1;
  display: flex;
  justify-content: space-around;
}
.me-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.me-stat-num {
  font-size: 28rpx;
  font-weight: 700;
  color: $neutral-900;
}
.me-stat-label {
  font-size: 20rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.me-hint {
  font-size: 20rpx;
  color: $warning-500;
}

/* 排行列表 */
.list {
  padding: 24rpx 32rpx 0;
}
.row {
  display: flex;
  align-items: center;
  padding: 20rpx 24rpx;
  margin-bottom: 12rpx;
}
.row--top {
  border: 2rpx solid $primary-100;
}
.row-rank {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: $neutral-100;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16rpx;
  flex-shrink: 0;
}
.row-rank--1 {
  background: $warning-500;
}
.row-rank--2 {
  background: $neutral-400;
}
.row-rank--3 {
  background: $primary-500;
}
.row-rank-text {
  font-size: 28rpx;
  font-weight: 800;
  color: #ffffff;
}
.row-user {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.row-username {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-tags {
  margin-top: 4rpx;
}
.row-tag {
  font-size: 20rpx;
  color: $primary-600;
}
.row-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.row-stat {
  font-size: 20rpx;
  color: $neutral-500;
  line-height: 1.5;
}

.load-more {
  padding: 24rpx;
  display: flex;
  justify-content: center;
}
.load-more-text {
  font-size: $font-aux;
  color: $primary-600;
}
.load-more--end .load-more-text {
  color: $neutral-300;
}
</style>
