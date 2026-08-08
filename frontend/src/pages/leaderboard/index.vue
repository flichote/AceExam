<template>
  <view class="page">
    <!-- 维度切换：全站 / 科目 / 班级（M3.5 scope=class） -->
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
      <view
        class="scope-tab"
        :class="{ 'scope-tab--active': scope === 'class' }"
        @click="switchScope('class')"
      >
        <text class="scope-tab-text" :class="{ 'scope-tab-text--active': scope === 'class' }">班级榜</text>
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

    <!-- 班级面板（班级榜时显示）：已加入 → 班级卡；未加入 → 建班/加入表单 -->
    <template v-if="scope === 'class'">
      <view v-if="myClass" class="class-card card">
        <view class="class-card-head">
          <text class="class-card-name">🏫 {{ myClass.name }}</text>
          <text class="class-card-count">{{ myClass.member_count }} 人</text>
        </view>
        <view class="class-card-meta">
          <text class="class-card-meta-text">
            我的名次：{{ myRank?.rank != null ? `#${myRank.rank}` : "未上榜" }}
          </text>
          <text v-if="myClass.invite_code" class="class-card-meta-text">
            邀请码 {{ myClass.invite_code }}
          </text>
        </view>
        <view v-if="myClass.invite_code" class="class-card-copy" @click="copyInvite">
          <text class="class-card-copy-text">📋 复制邀请码，邀请同学加入</text>
        </view>
      </view>

      <view v-else class="join-card card">
        <view class="join-tabs">
          <view
            class="join-tab"
            :class="{ 'join-tab--active': joinMode === 'create' }"
            @click="joinMode = 'create'"
          >
            <text class="join-tab-text" :class="{ 'join-tab-text--active': joinMode === 'create' }">创建班级</text>
          </view>
          <view
            class="join-tab"
            :class="{ 'join-tab--active': joinMode === 'join' }"
            @click="joinMode = 'join'"
          >
            <text class="join-tab-text" :class="{ 'join-tab-text--active': joinMode === 'join' }">加入班级</text>
          </view>
        </view>
        <input
          v-model="joinInput"
          class="join-input"
          :placeholder="joinMode === 'create' ? '输入班级名，如：计科2301' : '输入 6 位邀请码'"
          placeholder-class="join-input-placeholder"
          :maxlength="joinMode === 'create' ? 30 : 6"
        />
        <view
          class="btn btn--primary join-btn"
          :class="{ 'btn--disabled': joining || !joinInput.trim() }"
          @click="onJoin"
        >
          <text class="join-btn-text">
            {{ joining ? "处理中…" : joinMode === "create" ? "创建并进入班级" : "加入班级" }}
          </text>
        </view>
      </view>
    </template>

    <!-- 加载 / 错误 / 列表 -->
    <view v-if="loading" class="content">
      <LoadingSkeleton v-for="i in 4" :key="i" />
    </view>
    <view v-else-if="error" class="content">
      <EmptyState icon="⚠️" title="排行榜加载失败" :desc="error" action-text="重试" @action="reload" />
    </view>

    <template v-else>
      <!-- 班级榜未加入班级：引导加入（不请求班榜） -->
      <view v-if="scope === 'class' && !myClass" class="content">
        <EmptyState
          icon="🏫"
          title="加入班级后可查看班级排行"
          desc="创建班级生成邀请码，或输入同学的邀请码加入"
        />
      </view>

      <template v-else>
        <!-- 班级榜标题（班级元信息） -->
        <view v-if="scope === 'class' && classMeta" class="class-list-title">
          <text class="class-list-title-text">🏫 {{ classMeta.name }} · {{ classMeta.member_count }} 人</text>
        </view>

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
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import { fetchLeaderboard } from "@/api/leaderboard";
import { fetchMyClass, joinClass } from "@/api/classroom";
import type { LeaderboardItem, LeaderboardResponse, MyClassResponse } from "@/types";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";

const subjectStore = useSubjectStore();

type Scope = "global" | "subject" | "class";

const scope = ref<Scope>("global");
const subjectId = ref("");
const items = ref<LeaderboardItem[]>([]);
const me = ref<LeaderboardResponse["me"]>(null);
const classMeta = ref<LeaderboardResponse["class"]>(null);
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const loading = ref(false);
const error = ref("");

/* M3.5 班级：我的班级 + 建班/加入表单 */
const myClass = ref<MyClassResponse["class"]>(null);
const myRank = ref<MyClassResponse["my_rank"]>(null);
const joinMode = ref<"create" | "join">("create");
const joinInput = ref("");
const joining = ref(false);

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
  if (scope.value === "class") {
    await loadMyClass();
  }
});

onShow(() => {
  reload();
});

async function loadMyClass() {
  try {
    const res = await fetchMyClass();
    myClass.value = res.class;
    myRank.value = res.my_rank;
  } catch {
    myClass.value = null;
    myRank.value = null;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    // 班级榜未加入班级：不请求班榜（真实后端会 422 CLASS_NOT_JOINED）
    if (scope.value === "class" && !myClass.value) {
      items.value = [];
      total.value = 0;
      me.value = null;
      classMeta.value = null;
      return;
    }
    const res = await fetchLeaderboard({
      scope: scope.value,
      subjectId: scope.value === "subject" ? subjectId.value : undefined,
      page: page.value,
      pageSize,
    });
    items.value = page.value === 1 ? res.items : [...items.value, ...res.items];
    total.value = res.total;
    me.value = res.me;
    classMeta.value = res.class ?? null;
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

async function switchScope(s: Scope) {
  if (scope.value === s) return;
  scope.value = s;
  error.value = "";
  if (s === "class" && !myClass.value) {
    await loadMyClass();
  }
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

/** 建班 / 加入班级：POST /me/class（docs/api.md §12.6） */
async function onJoin() {
  const input = joinInput.value.trim();
  if (!input || joining.value) return;
  joining.value = true;
  try {
    const payload =
      joinMode.value === "create" ? { name: input } : { invite_code: input };
    await joinClass(payload);
    uni.showToast({
      title: joinMode.value === "create" ? "班级创建成功 🎉" : "已加入班级 🎉",
      icon: "none",
    });
    joinInput.value = "";
    await loadMyClass();
    reload();
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "操作失败", icon: "none" });
  } finally {
    joining.value = false;
  }
}

/** 复制邀请码（仅建班人可见） */
function copyInvite() {
  const code = myClass.value?.invite_code;
  if (!code) return;
  uni.setClipboardData({
    data: code,
    success: () => uni.showToast({ title: "邀请码已复制", icon: "none" }),
  });
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

/* 班级卡（已加入） */
.class-card {
  margin: 20rpx 32rpx 0;
  padding: 24rpx;
  border: 3rpx solid $primary-500;
}
.class-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.class-card-name {
  font-size: 32rpx;
  font-weight: 800;
  color: $neutral-900;
}
.class-card-count {
  font-size: 22rpx;
  color: $neutral-500;
}
.class-card-meta {
  display: flex;
  gap: 24rpx;
  margin-top: 12rpx;
}
.class-card-meta-text {
  font-size: 22rpx;
  color: $primary-600;
}
.class-card-copy {
  margin-top: 16rpx;
  background: $primary-100;
  border-radius: $radius-tag;
  padding: 12rpx 20rpx;
  display: inline-flex;
}
.class-card-copy-text {
  font-size: 22rpx;
  color: $primary-600;
  font-weight: 600;
}

/* 加入班级表单（未加入） */
.join-card {
  margin: 20rpx 32rpx 0;
  padding: 24rpx;
}
.join-tabs {
  display: flex;
  gap: 12rpx;
  margin-bottom: 16rpx;
}
.join-tab {
  flex: 1;
  padding: 12rpx 0;
  border-radius: $radius-tag;
  background: $neutral-100;
  display: flex;
  justify-content: center;
}
.join-tab--active {
  background: $primary-100;
}
.join-tab-text {
  font-size: $font-aux;
  color: $neutral-500;
  font-weight: 600;
}
.join-tab-text--active {
  color: $primary-600;
}
.join-input {
  background: $neutral-100;
  border-radius: $radius-btn;
  padding: 16rpx 20rpx;
  font-size: $font-body;
  color: $neutral-900;
}
.join-input-placeholder {
  color: $neutral-300;
}
.join-btn {
  margin-top: 16rpx;
  padding: 18rpx 0;
}
.join-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
}

/* 班级榜标题 */
.class-list-title {
  padding: 20rpx 32rpx 0;
}
.class-list-title-text {
  font-size: 24rpx;
  color: $neutral-500;
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
