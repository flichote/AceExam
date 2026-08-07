<template>
  <view class="page">
    <!-- 突击模式头（primary 描边 + 倒计时） -->
    <view class="sprint-head">
      <view class="sprint-head-top">
        <view class="sprint-head-left">
          <text class="sprint-head-icon">⚡</text>
          <view class="sprint-head-texts">
            <text class="sprint-head-title">考前突击</text>
            <text class="sprint-head-sub">{{ subjectName }}</text>
          </view>
        </view>
        <view v-if="sprint.daysLeft != null" class="sprint-countdown">
          <text class="sprint-countdown-num">{{ sprint.daysLeft }}</text>
          <text class="sprint-countdown-unit">天后考试</text>
        </view>
      </view>

      <!-- 模式切换：复习题单 / 模拟卷 -->
      <view class="sprint-modes">
        <view
          class="sprint-mode"
          :class="{ 'sprint-mode--active': sprint.mode === 'review' }"
          @click="switchMode('review')"
        >
          <text class="sprint-mode-text" :class="{ 'sprint-mode-text--active': sprint.mode === 'review' }">
            复习题单
          </text>
        </view>
        <view
          class="sprint-mode"
          :class="{ 'sprint-mode--active': sprint.mode === 'mock' }"
          @click="switchMode('mock')"
        >
          <text class="sprint-mode-text" :class="{ 'sprint-mode-text--active': sprint.mode === 'mock' }">
            模拟卷
          </text>
        </view>
      </view>

      <!-- 模拟卷计时 -->
      <view v-if="sprint.mode === 'mock' && sprint.mockMeta" class="sprint-mock-meta">
        <view class="sprint-mock-item">
          <text class="sprint-mock-label">时长</text>
          <text class="sprint-mock-value">{{ sprint.mockMeta.duration_min }} 分钟</text>
        </view>
        <view class="sprint-mock-item">
          <text class="sprint-mock-label">总分</text>
          <text class="sprint-mock-value">{{ sprint.mockMeta.total_score }} 分</text>
        </view>
        <view class="sprint-mock-item">
          <text class="sprint-mock-label">剩余</text>
          <text class="sprint-mock-value sprint-mock-value--timer">{{ sprint.mockTimeText }}</text>
        </view>
      </view>
    </view>

    <!-- 加载中 -->
    <view v-if="sprint.loading" class="content">
      <LoadingSkeleton />
      <LoadingSkeleton />
    </view>

    <!-- 加载失败（403 会员引导 / 网络） -->
    <view v-else-if="sprint.error" class="content">
      <EmptyState
        icon="🔒"
        title="突击模式不可用"
        :desc="sprint.error"
        action-text="开通会员 / 重试"
        @action="handleErrorAction"
      />
    </view>

    <!-- 未开始：题单说明 + 开始 -->
    <view v-else-if="!sprint.started" class="content">
      <view class="card sprint-intro">
        <text class="sprint-intro-title">⚡ 考前突击题单</text>
        <text class="sprint-intro-desc">
          高频考点题优先，搭配你的个人错题回顾；做错的题自动进错题本。
        </text>
        <view v-if="sprint.highFreqKps.length" class="sprint-intro-kps">
          <text class="sprint-intro-label">本次高频考点</text>
          <view class="sprint-intro-kp-list">
            <view v-for="kp in sprint.highFreqKps" :key="kp.id" class="sprint-intro-kp">
              <text class="sprint-intro-kp-name">{{ kp.name }}</text>
              <text class="sprint-intro-kp-heat">热度 {{ kp.heat }}</text>
            </view>
          </view>
        </view>
        <view class="btn btn--primary sprint-start" @click="start">
          <text class="sprint-start-text">{{ sprint.mode === 'mock' ? '开始模拟考试' : '开始突击' }}</text>
        </view>
      </view>
    </view>

    <!-- 答题中 -->
    <template v-else>
      <view class="info">
        <view class="info-left">
          <text class="info-subject">{{ subjectName }}</text>
          <view v-if="sprint.current" class="info-kp">
            <text class="info-kp-text">{{ sprint.current.knowledgePoint }}</text>
          </view>
        </view>
        <view class="info-progress">
          <text class="info-progress-text">{{ sprint.progress }}/{{ sprint.total }}</text>
        </view>
      </view>

      <!-- 本卷含错题提示 -->
      <view v-if="sprint.summary && sprint.summary.wrong_review_questions > 0" class="wrong-tip">
        <text class="wrong-tip-text">
          本卷含 {{ sprint.summary.wrong_review_questions }} 道你的错题，优先拿下
        </text>
      </view>

      <!-- 全部完成 -->
      <view v-if="!sprint.current" class="content">
        <EmptyState
          icon="🏆"
          title="突击完成！"
          desc="高频考点 + 错题已过一遍，继续保持"
          action-text="再来一组"
          @action="restart"
        />
      </view>

      <template v-else>
        <view class="content">
          <QuestionCard
            :question="sprint.current"
            :selected="sprint.selected"
            :answered="sprint.answered"
            :correct-keys="sprint.current.answer ?? []"
            :blank-input="sprint.blankInput"
            @select="sprint.selectOption"
            @update:blank="sprint.blankInput = $event"
          />

          <view
            v-if="!sprint.answered"
            class="btn btn--primary submit"
            :class="{ 'btn--disabled': !sprint.canSubmit() }"
            @click="sprint.submit"
          >
            <text class="submit-text">提交答案</text>
          </view>

          <template v-else>
            <AnswerFeedback
              :is-correct="sprint.isCorrect"
              @view-explain="sprint.toggleExplanation"
              @ask-ai="goAiExplain"
              @next="sprint.next"
            />

            <view v-if="sprint.explanationVisible && sprint.current.explanation" class="card explain">
              <view class="explain-head">
                <text class="explain-title">📝 答案解析</text>
              </view>
              <LatexText :text="sprint.current.explanation" />
            </view>
          </template>
        </view>
      </template>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onUnload } from "@dcloudio/uni-app";
import { useSprintStore } from "@/stores/sprint";
import { useSubjectStore } from "@/stores/subject";
import QuestionCard from "@/components/QuestionCard.vue";
import AnswerFeedback from "@/components/AnswerFeedback.vue";
import LatexText from "@/components/LatexText.vue";
import EmptyState from "@/components/EmptyState.vue";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";

const sprint = useSprintStore();
const subjectStore = useSubjectStore();

const subjectId = ref("");

onLoad(async (options) => {
  subjectId.value = (options?.subjectId as string) || "";
  if (!subjectId.value && subjectStore.subjects.length) {
    subjectId.value = subjectStore.subjects[0].id;
  }
  if (!subjectId.value) {
    await subjectStore.loadSubjects();
    subjectId.value = subjectStore.subjects[0]?.id ?? "";
  }
  if (subjectId.value) {
    subjectStore.selectSubject(subjectId.value);
    await sprint.load(subjectId.value, "review", 20);
  }
});

onUnload(() => {
  sprint.reset();
});

const subjectName = computed(() => {
  if (!subjectId.value) return "刷题";
  return subjectStore.subjectById(subjectId.value)?.name ?? subjectId.value;
});

async function switchMode(mode: "review" | "mock") {
  if (sprint.mode === mode || sprint.loading) return;
  sprint.mode = mode;
  sprint.started = false;
  sprint.data = null;
  sprint.questions = [];
  await sprint.load(subjectId.value, mode, 20);
}

function start() {
  if (!sprint.questions.length && !sprint.loading) {
    // 题单为空时重新拉取
    sprint.load(subjectId.value, sprint.mode, 20);
    return;
  }
  sprint.started = true;
}

function restart() {
  sprint.index = 0;
  sprint.resetAnswer();
  sprint.started = true;
}

function handleErrorAction() {
  // 403 会员引导：跳登录/会员页（M3 会员中心 P2，先提示）
  uni.showToast({ title: "会员功能即将开放，敬请期待", icon: "none" });
  setTimeout(() => uni.navigateBack(), 600);
}

function goAiExplain() {
  const q = sprint.current;
  if (!q) return;
  uni.navigateTo({
    url:
      `/pages/chat/index?subjectId=${encodeURIComponent(subjectId.value)}` +
      `&questionId=${encodeURIComponent(q.id)}` +
      `&knowledgePoint=${encodeURIComponent(q.knowledgePoint)}` +
      `&stem=${encodeURIComponent(q.stem)}`,
  });
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

/* 突击头（primary 描边 + 倒计时） */
.sprint-head {
  margin: 24rpx 32rpx;
  padding: 28rpx;
  border-radius: $radius-card;
  background: linear-gradient(135deg, $primary-100 0%, #ffffff 60%);
  border: 3rpx solid $primary-500;
  box-shadow: 0 4rpx 16rpx rgba($primary-500, 0.12);
}
.sprint-head-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.sprint-head-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.sprint-head-icon {
  font-size: 44rpx;
}
.sprint-head-texts {
  display: flex;
  flex-direction: column;
}
.sprint-head-title {
  font-size: $font-card-title;
  font-weight: 800;
  color: $primary-600;
}
.sprint-head-sub {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.sprint-countdown {
  display: flex;
  align-items: baseline;
  background: $primary-500;
  border-radius: $radius-tag;
  padding: 8rpx 16rpx;
}
.sprint-countdown-num {
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 800;
  margin-right: 6rpx;
}
.sprint-countdown-unit {
  color: rgba(255, 255, 255, 0.9);
  font-size: 20rpx;
}

/* 模式切换 */
.sprint-modes {
  display: flex;
  gap: 12rpx;
  margin-top: 20rpx;
}
.sprint-mode {
  flex: 1;
  padding: 12rpx 0;
  border-radius: $radius-btn;
  background: #ffffff;
  border: 2rpx solid $neutral-300;
  display: flex;
  justify-content: center;
}
.sprint-mode--active {
  background: $primary-500;
  border-color: $primary-500;
}
.sprint-mode-text {
  font-size: 24rpx;
  color: $neutral-500;
  font-weight: 600;
}
.sprint-mode-text--active {
  color: #ffffff;
}

/* 模拟卷元信息 */
.sprint-mock-meta {
  display: flex;
  gap: 8rpx;
  margin-top: 16rpx;
}
.sprint-mock-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: rgba(255, 255, 255, 0.8);
  border-radius: $radius-tag;
  padding: 10rpx 0;
}
.sprint-mock-label {
  font-size: 20rpx;
  color: $neutral-500;
}
.sprint-mock-value {
  font-size: 24rpx;
  color: $neutral-900;
  font-weight: 700;
  margin-top: 2rpx;
}
.sprint-mock-value--timer {
  color: $danger-500;
}

/* 内容区 */
.content {
  padding: 0 32rpx 48rpx;
}

/* 题单介绍 */
.sprint-intro {
  padding: 32rpx;
}
.sprint-intro-title {
  font-size: $font-card-title;
  font-weight: 800;
  color: $neutral-900;
}
.sprint-intro-desc {
  font-size: $font-aux;
  color: $neutral-500;
  margin-top: 12rpx;
  line-height: 1.6;
}
.sprint-intro-kps {
  margin-top: 20rpx;
}
.sprint-intro-label {
  font-size: 22rpx;
  color: $neutral-500;
}
.sprint-intro-kp-list {
  margin-top: 12rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.sprint-intro-kp {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: $primary-100;
  border-radius: $radius-tag;
  padding: 10rpx 16rpx;
}
.sprint-intro-kp-name {
  font-size: 24rpx;
  color: $primary-600;
  font-weight: 600;
}
.sprint-intro-kp-heat {
  font-size: 20rpx;
  color: $neutral-500;
}
.sprint-start {
  margin-top: 24rpx;
  padding: 20rpx 0;
}
.sprint-start-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}

/* 信息栏 */
.info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 32rpx;
}
.info-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  min-width: 0;
}
.info-subject {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.info-kp {
  background: $primary-100;
  border-radius: $radius-tag;
  padding: 4rpx 12rpx;
  flex-shrink: 0;
}
.info-kp-text {
  font-size: 20rpx;
  color: $primary-600;
  font-weight: 600;
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

/* 错题提示 */
.wrong-tip {
  margin: 0 32rpx 8rpx;
  background: rgba($danger-500, 0.08);
  border-radius: $radius-tag;
  padding: 10rpx 16rpx;
}
.wrong-tip-text {
  font-size: 22rpx;
  color: $danger-500;
}

.submit {
  margin-top: 8rpx;
  padding: 22rpx 0;
}
.submit-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}

.explain {
  margin-top: 24rpx;
  padding: 32rpx;
}
.explain-head {
  margin-bottom: 16rpx;
}
.explain-title {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
}
</style>
