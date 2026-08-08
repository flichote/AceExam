<template>
  <view class="page">
    <!-- 加载中 -->
    <view v-if="loading" class="loading">
      <view class="loading-spinner" />
      <text class="loading-text">识别结果处理中…</text>
    </view>

    <template v-else>
      <!-- 识别结果编辑（OcrResultEditor） -->
      <OcrResultEditor
        :structured="structured"
        :raw-text="rawText"
        @update:structured="onStructuredChange"
        @update:rawText="onRawChange"
      />

      <!-- 知识点归属 -->
      <view class="card kp-card">
        <text class="kp-label">知识点归属</text>
        <!-- 自动推荐 -->
        <view v-if="suggestedKps.length" class="kp-suggest">
          <text class="kp-suggest-title">AI 推荐</text>
          <view class="kp-chips">
            <view
              v-for="kp in suggestedKps"
              :key="kp.id"
              class="kp-chip"
              :class="{ 'kp-chip--active': selectedKpId === kp.id }"
              @click="selectKp(kp.id)"
            >
              <text class="kp-chip-name">{{ kp.name }}</text>
              <text class="kp-chip-score">{{ Math.round(kp.score * 100) }}%</text>
            </view>
          </view>
        </view>
        <!-- 手动选择 -->
        <view class="kp-manual">
          <text class="kp-manual-title">手动选择</text>
          <picker :range="kpNames" :value="kpIndex" @change="onKpChange">
            <view class="kp-picker">
              <text class="kp-picker-text">{{ selectedKpName || "选择知识点" }}</text>
              <text class="kp-picker-arrow">▾</text>
            </view>
          </picker>
        </view>
      </view>

      <!-- 答案确认选项 -->
      <view class="card confirm-opt">
        <view class="confirm-opt-row" @click="confirmAnswer = !confirmAnswer">
          <view class="checkbox" :class="{ 'checkbox--on': confirmAnswer }">
            <text v-if="confirmAnswer" class="checkbox-mark">✓</text>
          </view>
          <text class="confirm-opt-text">确认答案可信，入库（含答案）</text>
        </view>
        <text v-if="lowConfidence" class="confirm-opt-warn">
          识别置信度较低，建议取消勾选，仅入库题目不含答案
        </text>
      </view>

      <!-- M3.5 UGC：投稿共享题库（进审核流） -->
      <view class="card confirm-opt">
        <view class="confirm-opt-row" @click="shareToUgc = !shareToUgc">
          <view class="checkbox" :class="{ 'checkbox--on': shareToUgc }">
            <text v-if="shareToUgc" class="checkbox-mark">✓</text>
          </view>
          <view class="ugc-texts">
            <text class="confirm-opt-text">提交为共享题（投稿共建公共题库）</text>
            <text class="ugc-hint">审核通过后其他同学也能练到这道题</text>
          </view>
        </view>
        <view v-if="ugcSubmitted" class="ugc-status">
          <text class="ugc-status-text">✅ 已提交，等待审核</text>
        </view>
      </view>

      <!-- 入库按钮 -->
      <view class="foot">
        <view
          class="btn btn--primary save-btn"
          :class="{ 'btn--disabled': saving || !selectedKpId }"
          @click="save"
        >
          <text class="save-btn-text">{{ saving ? "提交中…" : shareToUgc ? "投稿共享题" : "确认入库" }}</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { useOcrStore } from "@/stores/ocr";
import { useSubjectStore } from "@/stores/subject";
import { fetchKnowledgePoints } from "@/api/subjects";
import { confirmOcrQuestion } from "@/api/ocr";
import { submitUgcQuestion } from "@/api/ugc";
import type { OcrStructured, SuggestedKp } from "@/types";
import OcrResultEditor from "@/components/OcrResultEditor.vue";

const ocrStore = useOcrStore();
const subjectStore = useSubjectStore();

const loading = ref(true);
const saving = ref(false);
const uploadId = ref("");
const subjectId = ref("");
const manual = ref(false);

const structured = ref<OcrStructured>({
  type: "single",
  content: "",
  options: [],
  answer: "",
  analysis: "",
  confidence: 1,
});
const rawText = ref("");
const suggestedKps = ref<SuggestedKp[]>([]);
const selectedKpId = ref("");
const confirmAnswer = ref(true);
/** M3.5 UGC：勾选后提交为共享题（走审核流，POST /questions/ugc） */
const shareToUgc = ref(false);
/** 投稿后的待审核状态提示 */
const ugcSubmitted = ref(false);

// 知识点列表（手动选择）
const kpList = ref<{ id: string; name: string }[]>([]);

onLoad(async (options) => {
  subjectId.value = (options?.subjectId as string) || "";
  uploadId.value = (options?.uploadId as string) || "";
  manual.value = (options?.manual as string) === "1";

  if (!subjectId.value) {
    subjectId.value = ocrStore.subjectId || subjectStore.subjects[0]?.id || "";
  }
  await subjectStore.loadSubjects();
  await loadKps();

  if (!manual.value && ocrStore.uploadResult) {
    const res = ocrStore.uploadResult;
    if (res.structured) structured.value = { ...structured.value, ...res.structured };
    rawText.value = res.raw_text ?? "";
    suggestedKps.value = res.suggested_kps ?? [];
    if (res.structured?.confidence !== undefined && res.structured.confidence < 0.6) {
      confirmAnswer.value = false;
    }
    if (suggestedKps.value.length) {
      selectedKpId.value = suggestedKps.value[0].id;
    }
  } else {
    // 手动录入：空题目骨架
    structured.value = { type: "single", content: "", options: [{ key: "A", text: "" }], answer: "", analysis: "" };
  }
  loading.value = false;
});

async function loadKps() {
  if (!subjectId.value) return;
  try {
    const kps = await fetchKnowledgePoints(subjectId.value);
    kpList.value = kps;
  } catch {
    kpList.value = [];
  }
}

const kpNames = computed(() => kpList.value.map((k) => k.name));
const kpIndex = computed(() => Math.max(0, kpList.value.findIndex((k) => k.id === selectedKpId.value)));

const selectedKpName = computed(
  () => kpList.value.find((k) => k.id === selectedKpId.value)?.name ?? ""
);

const lowConfidence = computed(
  () => structured.value.confidence !== undefined && structured.value.confidence < 0.6
);

function onStructuredChange(v: OcrStructured) {
  structured.value = v;
}
function onRawChange(v: string) {
  rawText.value = v;
}
function selectKp(id: string) {
  selectedKpId.value = id;
}
function onKpChange(e: { detail: { value: string | number } }) {
  const idx = Number(e.detail.value);
  const kp = kpList.value[idx];
  if (kp) selectedKpId.value = kp.id;
}

async function save() {
  if (saving.value || !selectedKpId.value) {
    uni.showToast({ title: "请先选择知识点归属", icon: "none" });
    return;
  }
  saving.value = true;
  try {
    // 手动录入无 upload_id：生成本地占位（同 from-ocr 语义）
    const resolvedUploadId = uploadId.value || `manual-${Date.now()}`;

    if (shareToUgc.value) {
      // M3.5 UGC 投稿：POST /questions/ugc（进审核流 status=pending）
      const res = await submitUgcQuestion({
        subject_id: subjectId.value,
        knowledge_point_id: selectedKpId.value,
        type: structured.value.type,
        content: structured.value.content,
        options: structured.value.options,
        answer: structured.value.answer,
        analysis: structured.value.analysis || undefined,
        ocr_upload_id: manual.value ? null : resolvedUploadId,
      });
      ugcSubmitted.value = true;
      uni.showToast({
        title: res.duplicated ? "题库已有该题（未重复投稿）" : "投稿成功，等待审核 🕐",
        icon: "none",
      });
      setTimeout(() => uni.navigateBack(), 900);
      return;
    }

    const res = await confirmOcrQuestion({
      upload_id: resolvedUploadId,
      subject_id: subjectId.value,
      knowledge_point_id: selectedKpId.value,
      structured: {
        type: structured.value.type,
        content: structured.value.content,
        options: structured.value.options,
        answer: structured.value.answer,
        analysis: structured.value.analysis,
        confidence: structured.value.confidence,
      },
      confirm_answer: confirmAnswer.value,
    });
    uni.showToast({
      title: res.duplicated ? "题库已有该题（未重复入库）" : "入库成功 ✅",
      icon: "none",
    });
    setTimeout(() => uni.navigateBack(), 800);
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "提交失败", icon: "none" });
  } finally {
    saving.value = false;
  }
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}
.loading-spinner {
  width: 48rpx;
  height: 48rpx;
  border: 6rpx solid $primary-100;
  border-top-color: $primary-500;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-text {
  margin-top: 12rpx;
  font-size: $font-aux;
  color: $neutral-500;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 知识点归属 */
.kp-card {
  margin: 0 32rpx 20rpx;
  padding: 24rpx;
}
.kp-label {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
  display: block;
  margin-bottom: 16rpx;
}
.kp-suggest-title,
.kp-manual-title {
  font-size: 24rpx;
  color: $neutral-500;
  display: block;
  margin-bottom: 8rpx;
}
.kp-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 16rpx;
}
.kp-chip {
  display: flex;
  align-items: center;
  gap: 8rpx;
  border: 2rpx solid $neutral-300;
  border-radius: $radius-tag;
  padding: 8rpx 16rpx;
}
.kp-chip--active {
  border-color: $primary-500;
  background: $primary-100;
}
.kp-chip-name {
  font-size: 24rpx;
  color: $neutral-900;
  font-weight: 600;
}
.kp-chip-score {
  font-size: 20rpx;
  color: $neutral-500;
}
.kp-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: $neutral-100;
  border-radius: $radius-btn;
  padding: 14rpx 20rpx;
}
.kp-picker-text {
  font-size: $font-body;
  color: $neutral-900;
}
.kp-picker-arrow {
  color: $neutral-300;
  font-size: 24rpx;
}

/* 答案确认 */
.confirm-opt {
  margin: 0 32rpx 20rpx;
  padding: 24rpx;
}
.confirm-opt-row {
  display: flex;
  align-items: center;
}
.checkbox {
  width: 40rpx;
  height: 40rpx;
  border-radius: 8rpx;
  border: 2rpx solid $neutral-300;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16rpx;
  flex-shrink: 0;
}
.checkbox--on {
  background: $primary-500;
  border-color: $primary-500;
}
.checkbox-mark {
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 700;
}
.confirm-opt-text {
  font-size: $font-body;
  color: $neutral-900;
}
.confirm-opt-warn {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $warning-500;
}

/* M3.5 UGC 投稿 */
.ugc-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.ugc-hint {
  margin-top: 4rpx;
  font-size: 20rpx;
  color: $neutral-500;
}
.ugc-status {
  margin-top: 16rpx;
  background: rgba($success-500, 0.08);
  border-radius: $radius-tag;
  padding: 10rpx 16rpx;
}
.ugc-status-text {
  font-size: 22rpx;
  color: $success-500;
  font-weight: 600;
}

/* 入库按钮 */
.foot {
  padding: 0 32rpx calc(24rpx + env(safe-area-inset-bottom));
}
.save-btn {
  padding: 22rpx 0;
}
.save-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}
</style>
