<template>
  <view class="page">
    <!-- 顶部说明 -->
    <view class="hero">
      <text class="hero-title">📸 拍照录题</text>
      <text class="hero-desc">拍下纸质题，AI 识别成电子题并入库练习</text>
    </view>

    <!-- 科目选择 -->
    <view class="section">
      <view class="card field-card">
        <text class="field-label">目标科目</text>
        <picker :range="subjectNames" :value="subjectIndex" @change="onSubjectChange">
          <view class="field-picker">
            <text class="field-picker-text">{{ currentSubjectName }}</text>
            <text class="field-picker-arrow">▾</text>
          </view>
        </picker>
      </view>
    </view>

    <!-- 拍照/相册 -->
    <view class="section capture">
      <view class="capture-btn" @click="choosePhoto">
        <view class="capture-btn-inner">
          <text class="capture-icon">📷</text>
          <text class="capture-text">拍照识别</text>
        </view>
      </view>
      <view class="capture-alt" @click="chooseAlbum">
        <text class="capture-alt-text">从相册选择</text>
      </view>
      <text class="capture-tip">支持文字 + 公式混合识别（LaTeX 输出）</text>
    </view>

    <!-- 上传中 -->
    <view v-if="ocrStore.uploading" class="uploading">
      <view class="uploading-spinner" />
      <text class="uploading-text">AI 识别中…</text>
    </view>

    <!-- 手动录入兜底 -->
    <view class="section manual">
      <view class="card manual-card" @click="goManual">
        <text class="manual-icon">✍️</text>
        <view class="manual-texts">
          <text class="manual-title">识别不清？手动录入</text>
          <text class="manual-desc">直接粘贴题干，AI 帮你结构化</text>
        </view>
        <text class="manual-arrow">›</text>
      </view>
    </view>

    <!-- M5 题库共建入口 -->
    <view class="section ugc-entry">
      <view class="card ugc-entry-card" @click="goUgc">
        <text class="ugc-entry-icon">🧩</text>
        <view class="ugc-entry-texts">
          <text class="ugc-entry-title">题库共建 · 我的投稿</text>
          <text class="ugc-entry-desc">上传共享题，查看 AI 初审与审核状态</text>
        </view>
        <text class="ugc-entry-arrow">›</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import { useOcrStore } from "@/stores/ocr";

const subjectStore = useSubjectStore();
const ocrStore = useOcrStore();

onLoad(() => {
  subjectStore.loadSubjects();
});

onShow(() => {
  subjectStore.loadSubjects();
  if (!ocrStore.subjectId && subjectStore.subjects.length) {
    ocrStore.subjectId = subjectStore.subjects[0].id;
  }
});

const subjectIndex = computed(() => {
  const idx = subjectStore.subjects.findIndex((s) => s.id === ocrStore.subjectId);
  return idx < 0 ? 0 : idx;
});
const subjectNames = computed(() => subjectStore.subjects.map((s) => s.name));
const currentSubjectName = computed(
  () => subjectStore.subjectById(ocrStore.subjectId)?.name ?? "请选择科目"
);

function onSubjectChange(e: { detail: { value: string | number } }) {
  const idx = Number(e.detail.value);
  const s = subjectStore.subjects[idx];
  if (s) ocrStore.subjectId = s.id;
}

function choosePhoto() {
  doChoose("camera");
}
function chooseAlbum() {
  doChoose("album");
}

function doChoose(source: "camera" | "album") {
  if (!ocrStore.subjectId) {
    uni.showToast({ title: "请先选择目标科目", icon: "none" });
    return;
  }
  uni.chooseImage({
    count: 1,
    sourceType: [source],
    success: async (res) => {
      const filePath = res.tempFilePaths[0];
      // 契约 source 取值：photo（拍照）/ album（相册）
      const result = await ocrStore.upload(
        filePath,
        ocrStore.subjectId,
        source === "camera" ? "photo" : "album"
      );
      if (!result) return; // 失败已 toast
      if (result.status === "failed") {
        uni.showToast({ title: result.error === "OCR_EMPTY" ? "未识别到有效题目，请重拍" : "识别失败", icon: "none" });
        return;
      }
      uni.navigateTo({
        url: `/pages/ocr/confirm?uploadId=${encodeURIComponent(result.upload_id)}&subjectId=${encodeURIComponent(ocrStore.subjectId)}`,
      });
    },
  });
}

/** 手动录入兜底（无照片：直接进入空确认页） */
function goManual() {
  if (!ocrStore.subjectId) {
    uni.showToast({ title: "请先选择目标科目", icon: "none" });
    return;
  }
  uni.navigateTo({
    url: `/pages/ocr/confirm?subjectId=${encodeURIComponent(ocrStore.subjectId)}&manual=1`,
  });
}

/** M5 题库共建入口（我的投稿 + 审核状态） */
function goUgc() {
  uni.navigateTo({ url: "/pages/ugc/index" });
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
}

.section {
  padding: 32rpx;
}
.field-card {
  padding: 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.field-label {
  font-size: $font-body;
  font-weight: 600;
  color: $neutral-900;
}
.field-picker {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.field-picker-text {
  font-size: $font-body;
  color: $primary-600;
  font-weight: 600;
}
.field-picker-arrow {
  color: $neutral-300;
  font-size: 24rpx;
}

/* 拍照按钮 */
.capture {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.capture-btn {
  width: 240rpx;
  height: 240rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, $primary-500, $primary-600);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: $shadow-float;
}
.capture-btn:active {
  transform: scale(0.96);
}
.capture-btn-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.capture-icon {
  font-size: 72rpx;
}
.capture-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  margin-top: 8rpx;
}
.capture-alt {
  margin-top: 24rpx;
  padding: 12rpx 48rpx;
  border: 2rpx solid $primary-500;
  border-radius: $radius-btn;
}
.capture-alt-text {
  color: $primary-600;
  font-size: $font-body;
  font-weight: 600;
}
.capture-tip {
  margin-top: 16rpx;
  font-size: 22rpx;
  color: $neutral-300;
}

/* 上传中 */
.uploading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24rpx;
}
.uploading-spinner {
  width: 48rpx;
  height: 48rpx;
  border: 6rpx solid $primary-100;
  border-top-color: $primary-500;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.uploading-text {
  margin-top: 12rpx;
  font-size: $font-aux;
  color: $neutral-500;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 手动录入 */
.manual-card {
  display: flex;
  align-items: center;
  padding: 24rpx;
}
.manual-icon {
  font-size: 40rpx;
  margin-right: 16rpx;
}
.manual-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.manual-title {
  font-size: $font-body;
  font-weight: 600;
  color: $neutral-900;
}
.manual-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.manual-arrow {
  font-size: 40rpx;
  color: $neutral-300;
}

/* M5 题库共建入口 */
.ugc-entry {
  padding-top: 0;
}
.ugc-entry-card {
  display: flex;
  align-items: center;
  padding: 24rpx;
  border: 3rpx dashed $primary-500;
  box-shadow: none;
}
.ugc-entry-card:active {
  background: $primary-100;
}
.ugc-entry-icon {
  font-size: 40rpx;
  margin-right: 16rpx;
}
.ugc-entry-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.ugc-entry-title {
  font-size: $font-body;
  font-weight: 700;
  color: $primary-600;
}
.ugc-entry-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.ugc-entry-arrow {
  font-size: 36rpx;
  color: $primary-500;
}
</style>
