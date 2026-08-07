<template>
  <view class="page">
    <!-- 刷题信息栏 -->
    <view class="info">
      <view class="info-left">
        <text class="info-subject">{{ subjectName }}</text>
        <SubjectPill v-if="practice.current" :label="practice.current.knowledgePoint" type="primary" />
      </view>
      <view class="info-progress">
        <text class="info-progress-text">{{ practice.total ? progress : 0 }}/{{ practice.total }}</text>
      </view>
    </view>

    <!-- 本次自适应策略（可解释性：本次优先知识点） -->
    <view v-if="strategyKps.length" class="strategy">
      <text class="strategy-label">本次优先</text>
      <scroll-view scroll-x class="strategy-scroll">
        <view class="strategy-list">
          <view
            v-for="kp in strategyKps"
            :key="kp.id"
            class="strategy-chip"
          >
            <text class="strategy-chip-name">{{ kp.name }}</text>
            <text class="strategy-chip-reason">{{ kp.reason || "薄弱优先" }}</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 加载中 -->
    <view v-if="practice.loading" class="content">
      <LoadingSkeleton />
      <LoadingSkeleton />
    </view>

    <!-- 加载失败 -->
    <view v-else-if="practice.error" class="content">
      <EmptyState
        icon="⚠️"
        title="题目加载失败"
        :desc="practice.error"
        action-text="重试"
        @action="reload"
      />
    </view>

    <!-- 全部刷完（本组已尽，可再来一组：排除已见题） -->
    <view v-else-if="!practice.current" class="content">
      <EmptyState
        icon="🏆"
        title="本组刷完啦"
        desc="已自动排除做过的题，可继续下一组"
        action-text="再来一组"
        @action="practice.restart"
      />
    </view>

    <!-- 题目 -->
    <template v-else>
      <view class="content">
        <QuestionCard
          :question="practice.current"
          :selected="practice.selected"
          :answered="practice.answered"
          :correct-keys="practice.current.answer ?? []"
          :blank-input="practice.blankInput"
          @select="practice.selectOption"
          @update:blank="practice.blankInput = $event"
        />

        <!-- 提交按钮 -->
        <view
          v-if="!practice.answered"
          class="btn btn--primary submit"
          :class="{ 'btn--disabled': !practice.canSubmit() }"
          @click="practice.submit"
        >
          <text class="submit-text">提交答案</text>
        </view>

        <!-- 作答反馈 -->
        <template v-else>
          <AnswerFeedback
            :is-correct="practice.isCorrect"
            @view-explain="practice.toggleExplanation"
            @ask-ai="goAiExplain"
            @next="practice.next"
          />

          <!-- 连续正确提醒（knowledge_state.streak） -->
          <view v-if="practice.knowledgeState && practice.knowledgeState.streak >= 3" class="streak-tip">
            <text class="streak-tip-text">🔥 连续 3 次正确，「{{ practice.current.knowledgePoint }}」已掌握！</text>
          </view>

          <!-- 解析（可展开） -->
          <view v-if="practice.explanationVisible && practice.current.explanation" class="card explain">
            <view class="explain-head">
              <text class="explain-title">📝 答案解析</text>
            </view>
            <LatexText :text="practice.current.explanation" />
          </view>
        </template>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { usePracticeStore } from "@/stores/practice";
import { useSubjectStore } from "@/stores/subject";
import QuestionCard from "@/components/QuestionCard.vue";
import AnswerFeedback from "@/components/AnswerFeedback.vue";
import LatexText from "@/components/LatexText.vue";
import SubjectPill from "@/components/SubjectPill.vue";
import EmptyState from "@/components/EmptyState.vue";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";

const practice = usePracticeStore();
const subjectStore = useSubjectStore();

const pendingSubjectId = ref("");

onLoad((options) => {
  pendingSubjectId.value = (options?.subjectId as string) || "";
  init();
});

async function init() {
  let sid = pendingSubjectId.value || subjectStore.currentSubjectId;
  if (!sid) {
    // 未指定科目：默认第一门（列表为空时先拉取）
    if (!subjectStore.subjects.length) {
      await subjectStore.loadSubjects();
    }
    sid = subjectStore.subjects[0]?.id ?? "";
    if (!sid) {
      practice.error = "暂无科目，请先回首页选科";
      return;
    }
  }
  subjectStore.selectSubject(sid);
  await practice.loadQuestions(sid);
}

function reload() {
  practice.loadQuestions(practice.subjectId || pendingSubjectId.value || subjectStore.currentSubjectId);
}

const subjectName = computed(() => {
  if (!practice.subjectId) return "刷题";
  return subjectStore.subjectById(practice.subjectId)?.name ?? practice.subjectId;
});

const progress = computed(() => practice.progress);

/** 本次自适应策略命中知识点（可解释性展示） */
const strategyKps = computed(() => practice.strategy?.target_kps ?? []);

function goAiExplain() {
  const q = practice.current;
  if (!q) return;
  uni.navigateTo({
    url:
      `/pages/chat/index?subjectId=${encodeURIComponent(practice.subjectId)}` +
      `&questionId=${encodeURIComponent(q.id)}` +
      `&knowledgePoint=${encodeURIComponent(q.knowledgePoint)}` +
      `&stem=${encodeURIComponent(q.stem)}`,
  });
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
}

/* 顶部信息栏 */
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

/* 自适应策略条 */
.strategy {
  padding: 0 32rpx 16rpx;
}
.strategy-label {
  font-size: 22rpx;
  color: $neutral-500;
  margin-right: 12rpx;
}
.strategy-scroll {
  white-space: nowrap;
  margin-top: 8rpx;
}
.strategy-list {
  display: inline-flex;
  gap: 12rpx;
}
.strategy-chip {
  display: inline-flex;
  flex-direction: column;
  background: rgba($danger-500, 0.08);
  border: 2rpx solid rgba($danger-500, 0.25);
  border-radius: $radius-tag;
  padding: 8rpx 16rpx;
}
.strategy-chip-name {
  font-size: 24rpx;
  font-weight: 700;
  color: $danger-500;
}
.strategy-chip-reason {
  font-size: 20rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}

.content {
  padding: 0 32rpx 48rpx;
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

/* 连续正确提醒 */
.streak-tip {
  margin-top: 16rpx;
  background: rgba($success-500, 0.1);
  border-radius: $radius-tag;
  padding: 12rpx 16rpx;
}
.streak-tip-text {
  font-size: 24rpx;
  color: $success-500;
}

/* 解析卡片 */
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
