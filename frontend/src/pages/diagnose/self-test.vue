<template>
  <view class="page">
    <!-- 进度 -->
    <view class="info">
      <view class="info-left">
        <text class="info-title">摸底自测</text>
        <text class="info-sub">已答 {{ diagnose.answeredCount }}/{{ diagnose.total }}</text>
      </view>
      <view class="info-progress">
        <text class="info-progress-text">{{ index + 1 }}/{{ diagnose.total }}</text>
      </view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="content">
      <LoadingSkeleton />
      <LoadingSkeleton />
    </view>

    <view v-else-if="error" class="content">
      <EmptyState icon="⚠️" title="自测加载失败" :desc="error" action-text="重试" @action="reload" />
    </view>

    <template v-else-if="current">
      <view class="content">
        <QuestionCard
          :question="current"
          :selected="selected"
          :answered="false"
          :blank-input="blankInput"
          @select="onSelect"
          @update:blank="blankInput = $event"
        />
      </view>
    </template>

    <!-- 提交 -->
    <view class="foot">
      <view class="nav-row">
        <view
          class="btn nav-btn nav-btn--plain"
          :class="{ 'btn--disabled': index === 0 }"
          @click="goPrev"
        >
          <text class="nav-btn-text">上一题</text>
        </view>
        <view
          v-if="index < diagnose.total - 1"
          class="btn nav-btn btn--primary"
          :class="{ 'btn--disabled': !currentAnswered }"
          @click="goNext"
        >
          <text class="nav-btn-text nav-btn-text--primary">下一题</text>
        </view>
      </view>
      <view
        class="btn btn--primary submit-btn"
        :class="{ 'btn--disabled': diagnose.answeredCount < diagnose.total }"
        @click="onSubmit"
      >
        <text class="submit-btn-text">
          {{ diagnose.submitting ? "分析中…" : diagnose.answeredCount === diagnose.total ? "提交并生成报告" : `还有 ${diagnose.total - diagnose.answeredCount} 题` }}
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { useDiagnoseStore } from "@/stores/diagnose";
import type { Question, QuestionType } from "@/types";
import QuestionCard from "@/components/QuestionCard.vue";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";

const diagnose = useDiagnoseStore();

const loading = ref(false);
const error = ref("");
const index = ref(0);
const selected = ref<string[]>([]);
const blankInput = ref("");

onLoad(async (options) => {
  const reportId = (options?.reportId as string) || "";
  if (!reportId && !diagnose.selfTest) {
    // 无 store 数据（如直接进入）：回诊断页发起
    error.value = "请先从「诊断」页发起自测";
    return;
  }
  loading.value = true;
  await new Promise((r) => setTimeout(r, 50));
  loading.value = false;
  applyQuestion();
});

const current = computed<Question | null>(() => {
  const q = diagnose.questions[index.value];
  if (!q) return null;
  return {
    id: q.id,
    subjectId: diagnose.subjectId,
    type: q.type,
    knowledgePoint: "自测",
    difficulty: q.difficulty,
    stem: q.content,
    options: q.options,
  };
});

function applyQuestion() {
  const q = diagnose.questions[index.value];
  if (!q) return;
  const saved = diagnose.answers[q.id];
  if (Array.isArray(saved)) {
    selected.value = saved;
    blankInput.value = "";
  } else if (typeof saved === "string") {
    selected.value = [];
    blankInput.value = saved;
  } else {
    selected.value = [];
    blankInput.value = "";
  }
}

function onSelect(key: string) {
  const q = diagnose.questions[index.value];
  if (!q) return;
  if (q.type === "single") {
    selected.value = [key];
  } else if (q.type === "multiple") {
    selected.value = selected.value.includes(key)
      ? selected.value.filter((k) => k !== key)
      : [...selected.value, key];
  }
  persist();
  // 单选自动进下一题
  if (q.type === "single" && index.value < diagnose.total - 1) {
    setTimeout(goNext, 180);
  }
}

function persist() {
  const q = diagnose.questions[index.value];
  if (!q) return;
  const isInputType = q.type === "blank" || q.type === "essay";
  diagnose.setAnswer(q.id, isInputType ? blankInput.value.trim() : selected.value);
}

// 填空/简答：输入变化即持久化（否则 answeredCount 不增长，无法提交）
watch(blankInput, (val) => {
  const q = diagnose.questions[index.value];
  if (q && (q.type === "blank" || q.type === "essay")) {
    diagnose.setAnswer(q.id, val.trim());
  }
});

const currentAnswered = computed(() => {
  const q = diagnose.questions[index.value];
  if (!q) return false;
  const v = diagnose.answers[q.id];
  if (q.type === "blank" || q.type === "essay") return typeof v === "string" && v.trim().length > 0;
  return Array.isArray(v) && v.length > 0;
});

function goPrev() {
  if (index.value === 0) return;
  index.value -= 1;
  applyQuestion();
}

function goNext() {
  if (index.value >= diagnose.total - 1) return;
  index.value += 1;
  applyQuestion();
}

async function onSubmit() {
  if (diagnose.answeredCount < diagnose.total || diagnose.submitting) return;
  const report = await diagnose.submit();
  if (report) {
    uni.navigateTo({ url: `/pages/diagnose/report?reportId=${diagnose.reportId}` });
  }
}

function reload() {
  // 无 store 数据时无法重试
  uni.navigateBack();
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 40rpx;
}

.info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 32rpx;
}
.info-left {
  display: flex;
  flex-direction: column;
}
.info-title {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
}
.info-sub {
  font-size: $font-aux;
  color: $neutral-500;
  margin-top: 2rpx;
}
.info-progress {
  background: $primary-100;
  border-radius: $radius-tag;
  padding: 6rpx 16rpx;
}
.info-progress-text {
  color: $primary-600;
  font-size: $font-aux;
  font-weight: 700;
}

.content {
  padding: 0 32rpx;
}

.foot {
  padding: 24rpx 32rpx 0;
}
.nav-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 16rpx;
}
.nav-btn {
  flex: 1;
  padding: 18rpx 0;
}
.nav-btn--plain {
  background: $neutral-100;
}
.nav-btn-text {
  font-size: $font-body;
  font-weight: 600;
  color: $neutral-500;
}
.nav-btn-text--primary {
  color: #ffffff;
}
.submit-btn {
  padding: 22rpx 0;
}
.submit-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}
</style>
