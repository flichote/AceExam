<template>
  <view class="tts">
    <!-- 待生成：🔊 听讲解 -->
    <view v-if="status === 'idle'" class="tts-btn" @click="generate">
      <text class="tts-btn-text">🔊 听讲解</text>
    </view>

    <!-- 生成中 -->
    <view v-else-if="status === 'loading'" class="tts-btn tts-btn--loading">
      <view class="tts-spinner" />
      <text class="tts-btn-text">语音生成中…</text>
    </view>

    <!-- 播放条 -->
    <view v-else-if="status === 'playing' || status === 'paused'" class="tts-bar">
      <view class="tts-bar-play" @click="togglePlay">
        <text class="tts-bar-play-icon">{{ status === "playing" ? "⏸" : "▶️" }}</text>
      </view>
      <view class="tts-bar-info">
        <text class="tts-bar-title">讲解语音</text>
        <text class="tts-bar-sub">{{ cacheHit ? "已缓存 · 秒开" : "edge-tts 合成" }}</text>
      </view>
      <view class="tts-bar-stop" @click="stop">
        <text class="tts-bar-stop-text">✕</text>
      </view>
    </view>

    <!-- 生成/播放失败 → 重试 -->
    <view v-else class="tts-error">
      <text class="tts-error-text">⚠️ {{ errorMsg }}</text>
      <view class="tts-error-retry" @click="generate">
        <text class="tts-error-retry-text">重试</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { downloadTtsAudio, requestTts, resolveAudioUrl } from "@/api/tts";
import type { ApiError } from "@/utils/request";

/**
 * TTS 讲解语音播放器（docs/api.md §12.1 / §12.2）
 * 讲解完成后展示「🔊 听讲解」→ POST /chat/explain/{session_id}/tts 生成
 * → 下载音频（带 Authorization）→ uni.createInnerAudioContext 播放。
 * 状态机：idle → loading → playing / paused → error（生成失败提示重试）。
 */

const props = defineProps<{
  sessionId: string;
}>();

type TtsStatus = "idle" | "loading" | "playing" | "paused" | "error";

const status = ref<TtsStatus>("idle");
const errorMsg = ref("");
const cacheHit = ref(false);
let ctx: UniApp.InnerAudioContext | null = null;

/** 生成失败提示映射（§12.1 错误：403 会员 / 404 / 422 / 502） */
function ttsErrorMessage(e: unknown): string {
  const err = e as ApiError;
  switch (err.code) {
    case "PAYMENT_REQUIRED":
      return "听讲解为会员功能，开通会员后可用";
    case "EXPLANATION_NOT_FOUND":
      return "暂无可生成的讲解内容，请先完成一次讲解";
    case "TTS_UNAVAILABLE":
      return "语音服务暂不可用，请稍后重试";
    default:
      return err.message || "语音生成失败";
  }
}

/** 销毁旧实例（避免 -99 错误，context7 核对 uni-app 官方建议） */
function destroyCtx() {
  if (ctx) {
    try {
      ctx.pause();
      ctx.destroy();
    } catch {
      /* 忽略销毁异常 */
    }
    ctx = null;
  }
}

async function generate() {
  if (status.value === "loading") return;
  destroyCtx();
  status.value = "loading";
  errorMsg.value = "";
  try {
    const tts = await requestTts(props.sessionId);
    cacheHit.value = tts.cache_hit;
    const fullUrl = resolveAudioUrl(tts.audio_url);
    const localUrl = await downloadTtsAudio(fullUrl);

    const audio = uni.createInnerAudioContext();
    ctx = audio;
    audio.autoplay = true;
    audio.src = localUrl;
    audio.onPlay(() => {
      status.value = "playing";
    });
    audio.onPause(() => {
      status.value = "paused";
    });
    audio.onEnded(() => {
      status.value = "idle";
      destroyCtx();
    });
    audio.onError(() => {
      status.value = "error";
      errorMsg.value = "音频播放失败，请重试";
      destroyCtx();
    });
    audio.play();
  } catch (e) {
    status.value = "error";
    errorMsg.value = ttsErrorMessage(e);
  }
}

function togglePlay() {
  if (!ctx) return;
  if (status.value === "playing") {
    ctx.pause();
  } else if (status.value === "paused") {
    ctx.play();
  }
}

function stop() {
  status.value = "idle";
  destroyCtx();
}

onBeforeUnmount(() => {
  destroyCtx();
});

defineExpose({ generate, stop });
</script>

<style lang="scss">
.tts {
  margin-top: 16rpx;
}

.tts-btn {
  display: inline-flex;
  align-items: center;
  gap: 10rpx;
  padding: 12rpx 24rpx;
  border-radius: $radius-btn;
  background: linear-gradient(135deg, $primary-500, $primary-600);
  box-shadow: $shadow-card;
}
.tts-btn--loading {
  opacity: 0.75;
}
.tts-btn-text {
  color: #ffffff;
  font-size: $font-aux;
  font-weight: 700;
}
.tts-spinner {
  width: 24rpx;
  height: 24rpx;
  border: 4rpx solid rgba(255, 255, 255, 0.4);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: tts-spin 0.8s linear infinite;
}
@keyframes tts-spin {
  to {
    transform: rotate(360deg);
  }
}

.tts-bar {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: #ffffff;
  border: 2rpx solid $neutral-100;
  border-radius: $radius-btn;
  padding: 14rpx 20rpx;
  box-shadow: $shadow-card;
}
.tts-bar-play {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: $primary-100;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tts-bar-play-icon {
  font-size: 28rpx;
}
.tts-bar-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.tts-bar-title {
  font-size: $font-aux;
  font-weight: 700;
  color: $neutral-900;
}
.tts-bar-sub {
  font-size: 20rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.tts-bar-stop {
  padding: 8rpx;
}
.tts-bar-stop-text {
  font-size: 24rpx;
  color: $neutral-400;
}

.tts-error {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: rgba($danger-500, 0.06);
  border-radius: $radius-btn;
  padding: 12rpx 20rpx;
}
.tts-error-text {
  flex: 1;
  font-size: 22rpx;
  color: $danger-500;
}
.tts-error-retry {
  padding: 8rpx 20rpx;
  border: 2rpx solid $danger-500;
  border-radius: $radius-tag;
}
.tts-error-retry-text {
  font-size: 22rpx;
  color: $danger-500;
  font-weight: 600;
}
</style>
