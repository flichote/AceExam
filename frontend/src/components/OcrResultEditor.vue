<template>
  <view class="ocr-editor">
    <!-- 置信度提示 -->
    <view
      v-if="structured.confidence !== undefined && structured.confidence < 0.6"
      class="ocr-warn"
    >
      <text class="ocr-warn-text">
        ⚠️ 识别置信度较低（{{ Math.round(structured.confidence * 100) }}%），请人工核对题目与答案
      </text>
    </view>

    <!-- 原始 Markdown（可折叠，可编辑） -->
    <view class="card ocr-section">
      <view class="ocr-section-head" @click="showRaw = !showRaw">
        <text class="ocr-section-title">原始识别文本</text>
        <text class="ocr-section-arrow">{{ showRaw ? "▾" : "▸" }}</text>
      </view>
      <textarea
        v-if="showRaw"
        v-model="rawDraft"
        class="ocr-textarea ocr-raw"
        :maxlength="-1"
        placeholder="Pix2Text 识别的 Markdown/LaTeX 原文…"
        @blur="commitRaw"
      />
    </view>

    <!-- 结构化题目编辑 -->
    <view class="card ocr-section">
      <view class="ocr-section-head">
        <text class="ocr-section-title">题目内容（可编辑）</text>
      </view>

      <!-- 题型 -->
      <view class="ocr-field">
        <text class="ocr-label">题型</text>
        <picker :range="typeLabels" :value="typeIndex" @change="onTypeChange">
          <view class="ocr-picker">
            <text class="ocr-picker-text">{{ typeLabels[typeIndex] }}</text>
            <text class="ocr-picker-arrow">▾</text>
          </view>
        </picker>
      </view>

      <!-- 题干 -->
      <view class="ocr-field">
        <text class="ocr-label">题干</text>
        <textarea
          v-model="copy.content"
          class="ocr-textarea"
          :maxlength="-1"
          placeholder="支持 $LaTeX$ 公式，如 $\lim_{x\to0}\frac{\sin x}{x}$"
          @blur="emitChange"
        />
      </view>

      <!-- 选项（单选/多选） -->
      <template v-if="copy.type === 'single' || copy.type === 'multiple'">
        <view class="ocr-field">
          <text class="ocr-label">选项</text>
          <view
            v-for="(opt, i) in copy.options"
            :key="opt.key"
            class="ocr-option-row"
          >
            <view class="ocr-option-key">
              <text class="ocr-option-key-text">{{ opt.key }}</text>
            </view>
            <input
              v-model="opt.text"
              class="ocr-input ocr-option-input"
              :placeholder="`选项 ${opt.key}`"
              @blur="emitChange"
            />
            <view v-if="copy.options.length > 2" class="ocr-option-del" @click="removeOption(i)">
              <text class="ocr-option-del-text">✕</text>
            </view>
          </view>
          <view v-if="copy.options.length < 8" class="ocr-add-option" @click="addOption">
            <text class="ocr-add-option-text">＋ 添加选项</text>
          </view>
        </view>
      </template>

      <!-- 答案 -->
      <view class="ocr-field">
        <text class="ocr-label">答案</text>
        <input
          v-model="copy.answer"
          class="ocr-input"
          :placeholder="copy.type === 'multiple' ? '多选，用逗号分隔，如 A,C' : '如 B'"
          @blur="emitChange"
        />
      </view>

      <!-- 解析 -->
      <view class="ocr-field">
        <text class="ocr-label">解析</text>
        <textarea
          v-model="copy.analysis"
          class="ocr-textarea"
          :maxlength="-1"
          placeholder="可留空，AI 讲解时生成"
          @blur="emitChange"
        />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import type { OcrStructured, QuestionType } from "@/types";

const props = defineProps<{
  structured: OcrStructured;
  rawText: string;
}>();

const emit = defineEmits<{
  (e: "update:structured", value: OcrStructured): void;
  (e: "update:rawText", value: string): void;
}>();

const typeLabels = ["单选题", "多选题", "填空题", "简答题"];
const typeValues: QuestionType[] = ["single", "multiple", "blank", "essay"];

const copy = reactive<OcrStructured>({
  type: "single",
  content: "",
  options: [],
  answer: "",
  analysis: "",
  confidence: 1,
});

const rawDraft = ref("");
const showRaw = ref(false);

watch(
  () => props.structured,
  (v) => {
    Object.assign(copy, {
      type: v.type || "single",
      content: v.content || "",
      options: (v.options || []).map((o) => ({ key: o.key, text: o.text })),
      answer: v.answer || "",
      analysis: v.analysis || "",
      confidence: v.confidence,
    });
  },
  { immediate: true, deep: true }
);

watch(
  () => props.rawText,
  (v) => {
    rawDraft.value = v || "";
  },
  { immediate: true }
);

const typeIndex = computed(() => Math.max(0, typeValues.indexOf(copy.type)));

function onTypeChange(e: { detail: { value: string | number } }) {
  const idx = Number(e.detail.value);
  copy.type = typeValues[idx] || "single";
  if ((copy.type === "single" || copy.type === "multiple") && copy.options.length === 0) {
    copy.options = [
      { key: "A", text: "" },
      { key: "B", text: "" },
    ];
  }
  emitChange();
}

function addOption() {
  const nextKey = String.fromCharCode(65 + copy.options.length);
  copy.options.push({ key: nextKey, text: "" });
  emitChange();
}

function removeOption(i: number) {
  copy.options.splice(i, 1);
  emitChange();
}

function emitChange() {
  emit("update:structured", {
    type: copy.type,
    content: copy.content,
    options: copy.options.map((o) => ({ key: o.key, text: o.text })),
    answer: copy.answer.trim(),
    analysis: copy.analysis,
    confidence: props.structured.confidence,
  });
}

function commitRaw() {
  emit("update:rawText", rawDraft.value);
}
</script>

<style lang="scss">
.ocr-editor {
  padding: 8rpx 32rpx 48rpx;
}

.ocr-warn {
  background: rgba($danger-500, 0.08);
  border: 2rpx solid rgba($danger-500, 0.3);
  border-radius: $radius-btn;
  padding: 16rpx 20rpx;
  margin-bottom: 20rpx;
}
.ocr-warn-text {
  font-size: 24rpx;
  color: $danger-500;
  line-height: 1.5;
}

.ocr-section {
  padding: 24rpx;
  margin-bottom: 20rpx;
}
.ocr-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}
.ocr-section-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.ocr-section-arrow {
  font-size: 28rpx;
  color: $neutral-300;
}

.ocr-field {
  margin-bottom: 20rpx;
}
.ocr-label {
  display: block;
  font-size: 24rpx;
  font-weight: 600;
  color: $neutral-500;
  margin-bottom: 8rpx;
}
.ocr-input,
.ocr-textarea {
  width: 100%;
  box-sizing: border-box;
  background: $neutral-100;
  border-radius: $radius-btn;
  padding: 16rpx 20rpx;
  font-size: $font-body;
  color: $neutral-900;
}
.ocr-textarea {
  min-height: 140rpx;
  line-height: 1.6;
}
.ocr-raw {
  min-height: 200rpx;
  font-size: 24rpx;
  color: $neutral-500;
}

.ocr-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: $neutral-100;
  border-radius: $radius-btn;
  padding: 16rpx 20rpx;
}
.ocr-picker-text {
  font-size: $font-body;
  color: $neutral-900;
}
.ocr-picker-arrow {
  color: $neutral-300;
  font-size: 24rpx;
}

.ocr-option-row {
  display: flex;
  align-items: center;
  margin-bottom: 12rpx;
}
.ocr-option-key {
  width: 48rpx;
  height: 48rpx;
  border-radius: $radius-tag;
  background: $primary-100;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12rpx;
  flex-shrink: 0;
}
.ocr-option-key-text {
  color: $primary-600;
  font-size: 24rpx;
  font-weight: 700;
}
.ocr-option-input {
  flex: 1;
  padding: 12rpx 16rpx;
}
.ocr-option-del {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 8rpx;
  flex-shrink: 0;
}
.ocr-option-del-text {
  color: $neutral-300;
  font-size: 28rpx;
}
.ocr-add-option {
  margin-top: 4rpx;
  padding: 10rpx 0;
}
.ocr-add-option-text {
  font-size: 24rpx;
  color: $info-500;
}
</style>
