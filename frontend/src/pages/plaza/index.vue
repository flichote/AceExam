<template>
  <view class="page">
    <!-- 顶部说明 -->
    <view class="intro">
      <text class="intro-title">📚 课程广场</text>
      <text class="intro-sub">公共课程任你选，加入后出现在首页「我的课程」</text>
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
          v-for="item in items"
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

        <view v-if="!items.length" class="card empty-card">
          <text class="empty-text">暂时没有可加入的公共课程</text>
        </view>
      </view>
    </template>

    <view class="page-foot">
      <text class="page-foot-text">加入后即可在首页看到该课程的学习进度</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import type { PlazaSubject } from "@/types";
import { fetchPlazaSubjects } from "@/api/subjects";
import { updateMeSubjects } from "@/api/me";
import { getToken } from "@/utils/request";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";

const items = ref<PlazaSubject[]>([]);
const loading = ref(false);
const error = ref("");
const updatingId = ref("");

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
</style>
