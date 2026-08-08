<template>
  <view class="page">
    <!-- 顶部 hero -->
    <view class="hero" :style="{ paddingTop: statusBarHeight + 'px' }">
      <view class="hero-inner">
        <text class="hero-title">🎓 先配好你的课程</text>
        <text class="hero-sub">输入专业、勾选本学期课程，AceExam 为你生成专属备考计划</text>
      </view>
    </view>

    <!-- 专业输入 -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">我的专业</text>
        <text class="section-sub">后续可随时修改</text>
      </view>
      <view class="card field-card">
        <input
          v-model="major"
          class="field-input"
          placeholder="如：计算机科学与技术"
          placeholder-class="field-placeholder"
          maxlength="100"
        />
      </view>
    </view>

    <!-- 选课（从课程广场勾选） -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">本学期课程</text>
        <text class="section-sub">已选 {{ selectedIds.length }} 门</text>
      </view>

      <!-- 加载中 -->
      <template v-if="plazaLoading">
        <LoadingSkeleton v-for="i in 2" :key="i" />
      </template>

      <!-- 加载失败 -->
      <view v-else-if="plazaError" class="card error-card">
        <text class="error-text">课程广场加载失败：{{ plazaError }}</text>
        <view class="btn btn--primary error-btn" @click="loadPlaza">
          <text class="btn--primary-text">重试</text>
        </view>
      </view>

      <!-- 广场课程多选 -->
      <view v-else-if="plazaItems.length" class="card select-card">
        <checkbox-group class="select-group" @change="onCheckboxChange">
          <label
            v-for="item in plazaItems"
            :key="item.id"
            class="select-row"
            :class="{ 'select-row--checked': isChecked(item.id) }"
          >
            <checkbox
              :value="item.id"
              :checked="isChecked(item.id)"
              color="#F59E0B"
              class="select-checkbox"
            />
            <view class="select-info">
              <view class="select-name-row">
                <text class="select-name">{{ item.name }}</text>
                <text v-if="item.question_count > 0" class="select-count">{{ item.question_count }} 题</text>
                <text v-else class="select-count select-count--building">建设中</text>
              </view>
              <text v-if="item.description" class="select-desc">{{ item.description }}</text>
            </view>
          </label>
        </checkbox-group>
      </view>

      <!-- 广场为空 -->
      <view v-else class="card empty-card">
        <text class="empty-text">暂时没有可加入的公共课程</text>
      </view>
    </view>

    <!-- M5 校本课程：手动录入 + AI 匹配模板（录入页返回后自动刷新） -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">校本课程</text>
        <text class="section-sub">AI 匹配模板，跨校共享题库</text>
      </view>

      <!-- 已录入的校本实例（不在广场列表，保存时保留） -->
      <view v-if="schoolCourses.length" class="card school-list">
        <view v-for="c in schoolCourses" :key="c.subject.id" class="school-row">
          <text class="school-name">{{ c.subject.name }}</text>
          <text class="school-tag">校本</text>
        </view>
      </view>

      <view class="card entry-card" @click="goCourseEntry">
        <text class="entry-icon">📥</text>
        <view class="entry-texts">
          <text class="entry-title">录入校本课程</text>
          <text class="entry-desc">输入学校课程名，自动匹配到模板课程</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>
    </view>

    <!-- 底部操作 -->
    <view class="foot">
      <view
        class="btn btn--primary save-btn"
        :class="{ 'btn--disabled': saving }"
        @click="onSave"
      >
        <text class="save-btn-text">{{ saving ? "保存中…" : "保存并进入首页" }}</text>
      </view>
      <text class="skip-link" @click="onSkip">先跳过，稍后再选</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import type { PlazaSubject, UserSubjectItem } from "@/types";
import { fetchPlazaSubjects } from "@/api/subjects";
import { fetchMeSubjects, updateMeSubjects, updateProfile } from "@/api/me";
import { useAuthStore } from "@/stores/auth";
import { markOnboarded } from "@/utils/onboarding";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";

const authStore = useAuthStore();

const statusBarHeight = ref(20);
const major = ref("");
const plazaItems = ref<PlazaSubject[]>([]);
const selectedIds = ref<string[]>([]);
const plazaLoading = ref(false);
const plazaError = ref("");
const saving = ref(false);

/** 我的课程全量（GET /me/subjects）：用于识别校本实例 + 保存合并 */
const myCourses = ref<UserSubjectItem[]>([]);

onLoad(async () => {
  try {
    const info = uni.getSystemInfoSync();
    statusBarHeight.value = info.statusBarHeight || 20;
  } catch {
    statusBarHeight.value = 20;
  }
  // 预填专业（编辑模式复用本页）
  await authStore.refreshUser();
  major.value = authStore.user?.major || "";
  await loadPlaza();
  await loadMySubjects();
});

// 从「录入校本课程」页返回时刷新已录入列表（校本实例 + 勾选状态）
onShow(() => {
  if (plazaItems.value.length || plazaError.value) {
    loadPlaza();
    loadMySubjects();
  }
});

/** 校本实例：我的课程中不属于广场公共课的条目（保存时保留，避免被全量覆盖清掉） */
const schoolCourses = computed(() => {
  const plazaIds = new Set(plazaItems.value.map((p) => p.id));
  return myCourses.value.filter((it) => !plazaIds.has(it.subject.id));
});

async function loadPlaza() {
  plazaLoading.value = true;
  plazaError.value = "";
  try {
    const res = await fetchPlazaSubjects();
    plazaItems.value = res.items;
  } catch (e) {
    plazaError.value = (e as Error).message || "加载失败";
  } finally {
    plazaLoading.value = false;
  }
}

/** 预勾选已加入课程（编辑模式 / 重复进入） */
async function loadMySubjects() {
  try {
    const res = await fetchMeSubjects();
    myCourses.value = res.items;
    selectedIds.value = res.items.map((it) => it.subject.id);
  } catch {
    /* 未登录/失败静默 */
  }
}

function isChecked(id: string): boolean {
  return selectedIds.value.includes(id);
}

function onCheckboxChange(e: { detail: { value: string[] } }) {
  selectedIds.value = e.detail.value;
}

/** 去录入校本课程（M5：联想 + 匹配 + 手动建实例） */
function goCourseEntry() {
  uni.navigateTo({ url: "/pages/course-entry/index" });
}

/** 保存：PUT /me/profile（专业非空时）→ PUT /me/subjects（幂等覆盖） */
async function onSave() {
  if (saving.value) return;
  const trimmed = major.value.trim();
  saving.value = true;
  try {
    if (trimmed) {
      await updateProfile(trimmed);
    }
    // 全量覆盖：勾选的广场课 ∪ 已录入的校本实例（防止 PUT /me/subjects 清掉手动录入课程）
    const target = new Set(selectedIds.value);
    schoolCourses.value.forEach((it) => target.add(it.subject.id));
    await updateMeSubjects(Array.from(target));
    markOnboarded();
    uni.showToast({ title: "已保存 🎉", icon: "none" });
    setTimeout(() => {
      uni.switchTab({ url: "/pages/subjects/index" });
    }, 400);
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "保存失败", icon: "none" });
  } finally {
    saving.value = false;
  }
}

/** 跳过：不填专业不选课，直接进首页（后续可从「我的」页修改） */
function onSkip() {
  markOnboarded();
  uni.switchTab({ url: "/pages/subjects/index" });
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
.hero-inner {
  display: flex;
  flex-direction: column;
  padding-top: 32rpx;
}
.hero-title {
  color: #ffffff;
  font-size: 40rpx;
  font-weight: 800;
  letter-spacing: 1rpx;
}
.hero-sub {
  color: rgba(255, 255, 255, 0.85);
  font-size: 24rpx;
  margin-top: 8rpx;
  line-height: 1.6;
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

/* 专业输入 */
.field-card {
  padding: 8rpx 24rpx;
}
.field-input {
  padding: 20rpx 0;
  font-size: $font-body;
  color: $neutral-900;
}
.field-placeholder {
  color: $neutral-300;
}

/* 选课列表 */
.select-card {
  padding: 8rpx 24rpx;
}
.select-group {
  display: flex;
  flex-direction: column;
}
.select-row {
  display: flex;
  align-items: flex-start;
  padding: 24rpx 0;
  border-bottom: 2rpx solid $neutral-100;
}
.select-row:last-child {
  border-bottom: none;
}
.select-checkbox {
  margin-top: 4rpx;
  transform: scale(0.9);
}
.select-info {
  flex: 1;
  min-width: 0;
  margin-left: 8rpx;
  display: flex;
  flex-direction: column;
}
.select-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.select-name {
  font-size: $font-body;
  font-weight: 600;
  color: $neutral-900;
}
.select-count {
  font-size: 20rpx;
  color: $neutral-500;
  background: $neutral-100;
  border-radius: $radius-tag;
  padding: 2rpx 10rpx;
}
.select-count--building {
  color: $warning-500;
  background: rgba($warning-500, 0.1);
}
.select-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 4rpx;
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

/* M5 校本课程 */
.school-list {
  padding: 8rpx 24rpx;
  margin-bottom: 16rpx;
}
.school-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 0;
  border-bottom: 2rpx solid $neutral-100;
}
.school-row:last-child {
  border-bottom: none;
}
.school-name {
  font-size: $font-body;
  font-weight: 600;
  color: $neutral-900;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.school-tag {
  font-size: 20rpx;
  color: $info-500;
  background: rgba($info-500, 0.1);
  border-radius: $radius-tag;
  padding: 2rpx 10rpx;
  flex-shrink: 0;
}
.entry-card {
  display: flex;
  align-items: center;
  padding: 24rpx;
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

/* 底部 */
.foot {
  padding: 16rpx 48rpx 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.save-btn {
  width: 100%;
  padding: 20rpx 0;
}
.save-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}
.skip-link {
  margin-top: 24rpx;
  font-size: $font-aux;
  color: $neutral-500;
  text-decoration: underline;
}
</style>
