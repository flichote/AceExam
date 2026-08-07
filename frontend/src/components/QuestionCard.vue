<template>
  <view v-if="question" class="qcard card">
    <!-- 题干 + 公式 -->
    <view class="qcard-stem">
      <LatexText :text="question.stem" :font-size="'17px'" />
    </view>

    <!-- 选项 -->
    <view
      v-for="opt in question.options"
      :key="opt.key"
      class="option"
      :class="optionClass(opt.key)"
      @click="onSelect(opt.key)"
    >
      <view class="option-letter" :class="letterClass(opt.key)">
        <text class="option-letter-text">{{ opt.key }}</text>
      </view>
      <view class="option-body">
        <LatexText :text="opt.text" :font-size="'15px'" />
      </view>
      <text v-if="answered && isCorrectKey(opt.key)" class="option-mark">✓</text>
      <text v-else-if="answered && isWrongKey(opt.key)" class="option-mark">✗</text>
    </view>

    <view v-if="question.type === 'multiple'" class="qcard-hint">
      <text class="qcard-hint-text">多选：可点选多个选项</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { Question } from "@/types";
import LatexText from "./LatexText.vue";

const props = withDefaults(
  defineProps<{
    question: Question;
    /** 已选中的选项 key */
    selected: string[];
    /** 已提交（锁定并展示对错） */
    answered: boolean;
    /** 正确选项（提交后由反馈返回） */
    correctKeys?: string[];
  }>(),
  {
    selected: () => [],
    answered: false,
    correctKeys: () => [],
  }
);

const emit = defineEmits<{ (e: "select", key: string): void }>();

function onSelect(key: string) {
  if (props.answered) return;
  emit("select", key);
}

function isSelected(key: string) {
  return props.selected.includes(key);
}
function isCorrectKey(key: string) {
  return props.answered && props.correctKeys.includes(key);
}
function isWrongKey(key: string) {
  return props.answered && isSelected(key) && !props.correctKeys.includes(key);
}

function optionClass(key: string): string {
  if (isWrongKey(key)) return "option--wrong";
  if (isCorrectKey(key)) return "option--correct";
  if (isSelected(key)) return "option--selected";
  return "";
}

function letterClass(key: string): string {
  if (isWrongKey(key)) return "option-letter--wrong";
  if (isCorrectKey(key)) return "option-letter--correct";
  if (isSelected(key)) return "option-letter--selected";
  return "";
}
</script>

<style lang="scss">
.qcard {
  padding: 32rpx;
}
.qcard-stem {
  margin-bottom: 24rpx;
  color: $neutral-900;
}
.qcard-hint {
  margin-top: 16rpx;
}
.qcard-hint-text {
  font-size: $font-aux;
  color: $neutral-500;
}

/* 选项卡片 */
.option {
  display: flex;
  align-items: center;
  padding: 20rpx 24rpx;
  margin-bottom: 16rpx;
  border: 2rpx solid $neutral-300;
  border-radius: $radius-btn;
  background: #ffffff;
  transition: all 200ms ease;
}
.option:active {
  transform: scale(0.98);
}
.option--selected {
  border-color: $primary-500;
  background: $primary-100;
}
.option--correct {
  border-color: $success-500;
  background: rgba($success-500, 0.08);
  animation: feedback-pop 200ms ease;
}
.option--wrong {
  border-color: $danger-500;
  background: rgba($danger-500, 0.08);
  animation: feedback-pop 200ms ease;
}

.option-letter {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: $neutral-100;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20rpx;
  flex-shrink: 0;
  transition: all 200ms ease;
}
.option-letter--selected {
  background: $primary-500;
}
.option-letter--correct {
  background: $success-500;
}
.option-letter--wrong {
  background: $danger-500;
}
.option-letter-text {
  color: $neutral-500;
  font-weight: 600;
  font-size: $font-body;
}
.option-letter--selected .option-letter-text,
.option-letter--correct .option-letter-text,
.option-letter--wrong .option-letter-text {
  color: #ffffff;
}

.option-body {
  flex: 1;
  color: $neutral-900;
}
.option-mark {
  margin-left: 12rpx;
  font-size: 32rpx;
  font-weight: 700;
}
.option--correct .option-mark {
  color: $success-500;
}
.option--wrong .option-mark {
  color: $danger-500;
}

@keyframes feedback-pop {
  0% {
    transform: scale(0.95);
  }
  60% {
    transform: scale(1.02);
  }
  100% {
    transform: scale(1);
  }
}
</style>
