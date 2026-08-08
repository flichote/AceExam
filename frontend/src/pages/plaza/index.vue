<template>
  <view class="page">
    <!-- 顶部说明 -->
    <view class="intro">
      <text class="intro-title">📚 课程广场</text>
      <text class="intro-sub">公共课程任你选，加入后出现在首页「我的课程」</text>
    </view>

    <!-- M5 搜索框：别名联想（GET /courses/aliases）→ 定位模板课 -->
    <view class="search">
      <view class="search-box">
        <text class="search-icon">🔍</text>
        <input
          v-model="keyword"
          class="search-input"
          placeholder="搜别名：高数 / 英语 / 线代…"
          placeholder-class="search-placeholder"
          maxlength="50"
          @input="onKeywordInput"
          @focus="onKeywordInput"
        />
        <text v-if="keyword" class="search-clear" @click="clearKeyword">✕</text>
      </view>

      <!-- 别名联想下拉 -->
      <view v-if="suggestions.length" class="search-suggest">
        <view
          v-for="s in suggestions"
          :key="s.alias"
          class="search-suggest-row"
          @click="onPickAlias(s)"
        >
          <text class="search-suggest-alias">{{ s.alias }}</text>
          <text class="search-suggest-arrow">→</text>
          <text class="search-suggest-template">{{ s.template_name }}</text>
        </view>
      </view>

      <!-- 当前筛选 -->
      <view v-if="searchTarget" class="search-target">
        <text class="search-target-text">筛选：{{ searchTarget.name }}</text>
        <text class="search-target-clear" @click="clearSearchTarget">✕ 清除</text>
      </view>
    </view>

    <!-- 加载中 -->
    <template v-if="loading">
      <view class="wrap">
        <LoadingSkeleton v-for="i in 3" :key="i" />
      </view>
    </template>

    <!-- 加载失败 -->
    <view v-else-if="error" class="wrap">
      <view class="card error-card">
        <text class="error-text">加载失败：{{ error }}</text>
        <view class="btn btn--primary error-btn" @click="load">
          <text class="btn--primary-text">重试</text>
        </view>
      </view>
    </view>

    <!-- 广场课程列表 -->
    <template v-else>
      <view class="wrap">
        <view
          v-for="item in visibleItems"
          :key="item.id"
          class="card plaza-card"
        >
          <view class="plaza-main">
            <view class="plaza-info">
              <view class="plaza-name-row">
                <text class="plaza-name">{{ item.name }}</text>
                <text v-if="item.joined" class="plaza-tag">已加入</text>
              </view>
              <text v-if="item.description" class="plaza-desc">{{ item.description }}</text>
              <view class="plaza-meta">
                <text v-if="item.question_count > 0" class="plaza-count">📝 {{ item.question_count }} 题</text>
                <text v-else class="plaza-count plaza-count--building">题库建设中</text>
                <text class="plaza-code">{{ item.code }}</text>
              </view>
            </view>

            <!-- 加入/移出按钮 -->
            <view
              class="btn plaza-btn"
              :class="item.joined ? 'plaza-btn--joined' : 'btn--primary'"
              @click="onToggle(item)"
            >
              <text
                class="plaza-btn-text"
                :class="item.joined ? 'plaza-btn-text--joined' : ''"
              >
                {{ item.joined ? "移出" : "加入" }}
              </text>
            </view>
          </view>
        </view>

        <!-- 搜索无结果：模板课未上架 → 引导录入 -->
        <view v-if="searchTarget && !visibleItems.length" class="card no-result">
          <text class="no-result-title">「{{ searchTarget.name }}」暂未在广场上架</text>
          <text class="no-result-desc">该模板课程题库可能尚未开放，你可以先录入校本课程，匹配后同样共享题库</text>
          <view class="btn btn--primary no-result-btn" @click="goCourseEntry">
            <text class="btn--primary-text">去录入校本课程</text>
          </view>
        </view>

        <view v-if="!visibleItems.length && !searchTarget" class="card empty-card">
          <text class="empty-text">暂时没有可加入的公共课程</text>
        </view>

        <!-- 录入校本课程入口 -->
        <view class="card entry-card" @click="goCourseEntry">
          <text class="entry-icon">📥</text>
          <view class="entry-texts">
            <text class="entry-title">没有找到你的课程？录入校本课程</text>
            <text class="entry-desc">输入学校课程名，AI 匹配模板，题库跨校共享</text>
          </view>
          <text class="entry-arrow">›</text>
        </view>
      </view>
    </template>

    <view class="page-foot">
      <text class="page-foot-text">加入后即可在首页看到该课程的学习进度</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import type { CourseAliasItem, PlazaSubject } from "@/types";
import { fetchPlazaSubjects } from "@/api/subjects";
import { fetchCourseAliases } from "@/api/courses";
import { updateMeSubjects } from "@/api/me";
import { getToken } from "@/utils/request";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";

const items = ref<PlazaSubject[]>([]);
const loading = ref(false);
const error = ref("");
const updatingId = ref("");

const keyword = ref("");
const suggestions = ref<CourseAliasItem[]>([]);
/** 当前按模板课筛选（null = 全量） */
const searchTarget = ref<{ code: string; name: string } | null>(null);

let aliasTimer: ReturnType<typeof setTimeout> | undefined;
let aliasSeq = 0;

onShow(() => {
  load();
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const res = await fetchPlazaSubjects();
    items.value = res.items;
  } catch (e) {
    error.value = (e as Error).message || "加载失败";
  } finally {
    loading.value = false;
  }
}

/** 搜索联想：防抖 300ms 拉 GET /courses/aliases */
function onKeywordInput() {
  if (aliasTimer) clearTimeout(aliasTimer);
  aliasTimer = setTimeout(async () => {
    const q = keyword.value.trim();
    const seq = ++aliasSeq;
    if (!q) {
      suggestions.value = [];
      return;
    }
    try {
      const list = await fetchCourseAliases(q, 8);
      if (seq === aliasSeq) suggestions.value = list;
    } catch {
      if (seq === aliasSeq) suggestions.value = [];
    }
  }, 300);
}

/** 点选别名 → 按模板课筛选广场列表 */
function onPickAlias(s: CourseAliasItem) {
  if (aliasTimer) clearTimeout(aliasTimer);
  aliasSeq++;
  suggestions.value = [];
  keyword.value = s.alias;
  searchTarget.value = { code: s.template_code, name: s.template_name };
}

function clearKeyword() {
  keyword.value = "";
  suggestions.value = [];
}

function clearSearchTarget() {
  searchTarget.value = null;
  keyword.value = "";
  suggestions.value = [];
}

/** 筛选后的广场列表 */
const visibleItems = computed(() => {
  if (!searchTarget.value) return items.value;
  return items.value.filter(
    (i) =>
      i.code === searchTarget.value?.code ||
      i.name === searchTarget.value?.name
  );
});

function goCourseEntry() {
  uni.navigateTo({ url: "/pages/course-entry/index" });
}

/** 加入/移出：本地翻转 joined → PUT /me/subjects 全量覆盖（§13.2 幂等） */
async function onToggle(item: PlazaSubject) {
  if (updatingId.value) return;
  if (!getToken()) {
    uni.showToast({ title: "请先登录后再加入课程", icon: "none" });
    setTimeout(() => {
      uni.navigateTo({ url: "/pages/auth/login" });
    }, 600);
    return;
  }
  updatingId.value = item.id;
  // 目标集合：当前已加入集合 ± 当前项
  const target = new Set(items.value.filter((i) => i.joined).map((i) => i.id));
  if (target.has(item.id)) {
    target.delete(item.id);
  } else {
    target.add(item.id);
  }
  try {
    await updateMeSubjects(Array.from(target));
    // 成功后同步本地状态
    items.value = items.value.map((i) => ({
      ...i,
      joined: i.id === item.id ? !item.joined : i.joined,
    }));
    uni.showToast({
      title: item.joined ? "已移出课程" : "已加入课程 🎉",
      icon: "none",
    });
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "操作失败", icon: "none" });
  } finally {
    updatingId.value = "";
  }
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

/* 顶部说明 */
.intro {
  padding: 32rpx 32rpx 8rpx;
  display: flex;
  flex-direction: column;
}
.intro-title {
  font-size: 36rpx;
  font-weight: 800;
  color: $neutral-900;
}
.intro-sub {
  font-size: 24rpx;
  color: $neutral-500;
  margin-top: 4rpx;
}

.wrap {
  padding: 24rpx 32rpx;
}

/* 广场卡片 */
.plaza-card {
  padding: 28rpx;
  margin-bottom: 24rpx;
}
.plaza-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.plaza-info {
  flex: 1;
  min-width: 0;
  margin-right: 20rpx;
}
.plaza-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.plaza-name {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plaza-tag {
  font-size: 20rpx;
  color: $success-500;
  background: rgba($success-500, 0.12);
  border-radius: $radius-tag;
  padding: 2rpx 10rpx;
  flex-shrink: 0;
}
.plaza-desc {
  display: block;
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 8rpx;
  line-height: 1.5;
}
.plaza-meta {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 10rpx;
}
.plaza-count {
  font-size: 22rpx;
  color: $neutral-500;
}
.plaza-count--building {
  color: $warning-500;
}
.plaza-code {
  font-size: 20rpx;
  color: $neutral-300;
}

/* 加入按钮 */
.plaza-btn {
  padding: 14rpx 32rpx;
  flex-shrink: 0;
}
.plaza-btn--joined {
  background: $neutral-100;
}
.plaza-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 600;
}
.plaza-btn-text--joined {
  color: $neutral-500;
}

/* 空 / 错误态 */
.empty-card {
  padding: 48rpx;
  display: flex;
  justify-content: center;
}
.empty-text {
  color: $neutral-300;
  font-size: $font-body;
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

/* M5 搜索 */
.search {
  padding: 16rpx 32rpx 0;
}
.search-box {
  display: flex;
  align-items: center;
  background: #ffffff;
  border-radius: $radius-btn;
  border: 2rpx solid $neutral-100;
  padding: 14rpx 20rpx;
}
.search-icon {
  font-size: 28rpx;
  margin-right: 12rpx;
  color: $neutral-300;
}
.search-input {
  flex: 1;
  font-size: $font-body;
  color: $neutral-900;
}
.search-placeholder {
  color: $neutral-300;
}
.search-clear {
  font-size: 28rpx;
  color: $neutral-300;
  padding: 4rpx 8rpx;
}
.search-suggest {
  background: #ffffff;
  border-radius: $radius-btn;
  box-shadow: $shadow-float;
  margin-top: 8rpx;
  overflow: hidden;
}
.search-suggest-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 20rpx 24rpx;
  border-bottom: 2rpx solid $neutral-100;
}
.search-suggest-row:active {
  background: $primary-100;
}
.search-suggest-alias {
  font-size: $font-body;
  color: $neutral-900;
  font-weight: 600;
  max-width: 240rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-suggest-arrow {
  color: $neutral-300;
  font-size: 22rpx;
}
.search-suggest-template {
  flex: 1;
  font-size: $font-body;
  color: $primary-600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-target {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12rpx;
  background: $primary-100;
  border-radius: $radius-tag;
  padding: 10rpx 18rpx;
}
.search-target-text {
  font-size: 24rpx;
  color: $primary-600;
  font-weight: 600;
}
.search-target-clear {
  font-size: 22rpx;
  color: $neutral-500;
}

/* 搜索无结果 */
.no-result {
  padding: 40rpx 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 24rpx;
}
.no-result-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.no-result-desc {
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $neutral-500;
  text-align: center;
  line-height: 1.5;
}
.no-result-btn {
  margin-top: 20rpx;
  padding: 12rpx 40rpx;
}

/* 录入校本课程入口 */
.entry-card {
  display: flex;
  align-items: center;
  padding: 24rpx;
  margin-top: 8rpx;
  border: 3rpx dashed $primary-500;
  box-shadow: none;
}
.entry-card:active {
  background: $primary-100;
}
.entry-icon {
  font-size: 40rpx;
  margin-right: 16rpx;
}
.entry-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.entry-title {
  font-size: $font-body;
  font-weight: 700;
  color: $primary-600;
}
.entry-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.entry-arrow {
  font-size: 36rpx;
  color: $primary-500;
}
</style>
