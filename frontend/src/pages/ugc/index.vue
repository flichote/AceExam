<template>
  <view class="page">
    <!-- 顶部说明 -->
    <view class="hero">
      <text class="hero-title">🧩 题库共建</text>
      <text class="hero-desc">上传你的题目，AI 初审后进入公共题库，帮到全校同学（题库飞轮）</text>
    </view>

    <!-- 投稿方式 -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">我要投稿</text>
        <text class="section-sub">AI 初审 · 审核通过即上线</text>
      </view>

      <view class="card actions">
        <view class="action" @click="goOcrPhoto">
          <text class="action-icon">📸</text>
          <view class="action-texts">
            <text class="action-title">拍照上传新题</text>
            <text class="action-desc">拍下纸质题，OCR 识别后提交（复用拍照录题）</text>
          </view>
          <text class="action-arrow">›</text>
        </view>
        <view class="action" @click="goManualNew">
          <text class="action-icon">✍️</text>
          <view class="action-texts">
            <text class="action-title">手动录入新题</text>
            <text class="action-desc">粘贴题干、选项与答案，结构化后提交</text>
          </view>
          <text class="action-arrow">›</text>
        </view>
        <view class="action" @click="goReport">
          <text class="action-icon">⚠️</text>
          <view class="action-texts">
            <text class="action-title">从题目报错纠错</text>
            <text class="action-desc">刷题/AI 讲解页发现题目有误，修改后重新投稿</text>
          </view>
          <text class="action-arrow">›</text>
        </view>
      </view>
    </view>

    <!-- 我的投稿（GET /ugc/status） -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">我的投稿</text>
        <text class="section-sub">共 {{ total }} 条</text>
      </view>

      <!-- 状态筛选 -->
      <view class="filters">
        <view
          v-for="f in filters"
          :key="f.value"
          class="filter-chip"
          :class="{ 'filter-chip--active': filter === f.value }"
          @click="onFilter(f.value)"
        >
          <text class="filter-chip-text">{{ f.label }}</text>
        </view>
      </view>

      <!-- 加载中 -->
      <template v-if="loading">
        <LoadingSkeleton v-for="i in 2" :key="i" />
      </template>

      <!-- 加载失败 -->
      <view v-else-if="error" class="card error-card">
        <text class="error-text">加载失败：{{ error }}</text>
        <view class="btn btn--primary error-btn" @click="load">
          <text class="btn--primary-text">重试</text>
        </view>
      </view>

      <!-- 列表 -->
      <template v-else>
        <view v-for="item in items" :key="item.question_id" class="card item">
          <view class="item-head">
            <view class="item-meta">
              <text class="item-subject">{{ item.subject_name }}</text>
              <text class="item-kp">{{ item.knowledge_point_name }}</text>
            </view>
            <view class="status" :class="statusClass(item.status)">
              <text class="status-text">{{ statusLabel(item.status) }}</text>
            </view>
          </view>

          <text class="item-content">{{ item.content }}</text>

          <!-- AI 初审结果 -->
          <view v-if="item.ai_review" class="ai-review">
            <view class="ai-review-head">
              <text class="ai-review-title">🤖 AI 初审：{{ verdictLabel(item.ai_review.verdict) }}</text>
              <text v-if="item.ai_review.confidence" class="ai-review-conf">
                {{ Math.round(item.ai_review.confidence * 100) }}%
              </text>
            </view>
            <text v-for="(r, i) in item.ai_review.reasons" :key="i" class="ai-review-reason">
              · {{ r }}
            </text>
          </view>

          <!-- 驳回理由 -->
          <view v-if="item.reject_reason" class="reject">
            <text class="reject-text">{{ item.reject_reason }}</text>
          </view>

          <text class="item-time">提交于 {{ formatTime(item.submitted_at) }}</text>
        </view>

        <view v-if="!items.length && !loading" class="card empty-card">
          <text class="empty-text">还没有投稿，快去上传第一道题吧</text>
        </view>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import type { UgcStatusItem } from "@/types";
import { fetchUgcStatus } from "@/api/ugc";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";

const filters = [
  { label: "全部", value: "" },
  { label: "审核中", value: "pending" },
  { label: "已通过", value: "active" },
  { label: "已驳回", value: "rejected" },
] as const;

const filter = ref<string>("");
const items = ref<UgcStatusItem[]>([]);
const total = ref(0);
const loading = ref(false);
const error = ref("");

onShow(() => {
  load();
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const res = await fetchUgcStatus({ status: filter.value || undefined });
    items.value = res.items;
    total.value = res.total;
  } catch (e) {
    error.value = (e as Error).message || "加载失败";
  } finally {
    loading.value = false;
  }
}

function onFilter(v: string) {
  if (filter.value === v) return;
  filter.value = v;
  load();
}

function statusLabel(status: string): string {
  return { pending: "审核中", active: "已通过", rejected: "已驳回" }[status] || status;
}
function statusClass(status: string): string {
  return {
    pending: "status--pending",
    active: "status--active",
    rejected: "status--rejected",
  }[status] || "";
}
function verdictLabel(verdict: string): string {
  return { pass: "通过", flag: "存疑，待人工复核", unknown: "分析中" }[verdict] || verdict;
}

/** ISO → MM-DD HH:mm（本地时区） */
function formatTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}

/** 投稿入口（带 ugc 参数：确认页默认勾选「提交为共享题」） */
function goOcrPhoto() {
  uni.switchTab({ url: "/pages/ocr/index" });
}
function goManualNew() {
  uni.navigateTo({ url: "/pages/ocr/confirm?manual=1&ugc=1" });
}
function goReport() {
  uni.navigateTo({ url: "/pages/ocr/confirm?manual=1&ugc=1&report=1" });
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
  line-height: 1.6;
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

/* 投稿方式 */
.actions {
  padding: 8rpx 28rpx;
}
.action {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 26rpx 0;
  border-bottom: 2rpx solid $neutral-100;
}
.action:last-child {
  border-bottom: none;
}
.action:active {
  opacity: 0.7;
}
.action-icon {
  font-size: 40rpx;
  flex-shrink: 0;
}
.action-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.action-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.action-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.action-arrow {
  font-size: 36rpx;
  color: $neutral-300;
}

/* 筛选 */
.filters {
  display: flex;
  gap: 12rpx;
  margin-bottom: 20rpx;
}
.filter-chip {
  border: 2rpx solid $neutral-300;
  border-radius: $radius-tag;
  padding: 8rpx 22rpx;
}
.filter-chip--active {
  border-color: $primary-500;
  background: $primary-100;
}
.filter-chip-text {
  font-size: 24rpx;
  color: $neutral-500;
}
.filter-chip--active .filter-chip-text {
  color: $primary-600;
  font-weight: 700;
}

/* 投稿条目 */
.item {
  margin-bottom: 20rpx;
  padding: 24rpx;
}
.item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10rpx;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex: 1;
  min-width: 0;
}
.item-subject {
  font-size: 24rpx;
  font-weight: 700;
  color: $neutral-900;
}
.item-kp {
  font-size: 20rpx;
  color: $neutral-500;
  background: $neutral-100;
  border-radius: $radius-tag;
  padding: 2rpx 10rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200rpx;
}
.status {
  flex-shrink: 0;
  border-radius: $radius-tag;
  padding: 4rpx 14rpx;
}
.status-text {
  font-size: 22rpx;
  font-weight: 700;
}
.status--pending {
  background: rgba($warning-500, 0.14);
}
.status--pending .status-text {
  color: $warning-500;
}
.status--active {
  background: rgba($success-500, 0.12);
}
.status--active .status-text {
  color: $success-500;
}
.status--rejected {
  background: rgba($danger-500, 0.1);
}
.status--rejected .status-text {
  color: $danger-500;
}

.item-content {
  display: block;
  font-size: $font-body;
  color: $neutral-900;
  line-height: 1.6;
}

/* AI 初审 */
.ai-review {
  margin-top: 14rpx;
  background: $neutral-100;
  border-radius: $radius-btn;
  padding: 14rpx 18rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.ai-review-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ai-review-title {
  font-size: 22rpx;
  color: $neutral-900;
  font-weight: 600;
}
.ai-review-conf {
  font-size: 22rpx;
  color: $info-500;
  font-weight: 700;
}
.ai-review-reason {
  font-size: 20rpx;
  color: $neutral-500;
}

/* 驳回理由 */
.reject {
  margin-top: 14rpx;
  background: rgba($danger-500, 0.08);
  border-radius: $radius-btn;
  padding: 12rpx 16rpx;
}
.reject-text {
  font-size: 22rpx;
  color: $danger-500;
  line-height: 1.5;
}

.item-time {
  display: block;
  margin-top: 12rpx;
  font-size: 20rpx;
  color: $neutral-300;
}

/* 空/错误态 */
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
</style>
