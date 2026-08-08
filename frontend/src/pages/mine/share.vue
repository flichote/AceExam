<template>
  <view class="page">
    <view class="head">
      <text class="head-title">📊 我的成绩单</text>
      <text class="head-desc">一键生成战绩海报，分享给同学</text>
    </view>

    <!-- 加载 -->
    <view v-if="loading" class="card poster-box">
      <LoadingSkeleton />
    </view>

    <!-- 错误 -->
    <view v-else-if="error" class="card poster-box">
      <EmptyState icon="⚠️" title="海报数据加载失败" :desc="error" action-text="重试" @action="load" />
    </view>

    <template v-else-if="data">
      <!-- 海报预览 -->
      <view class="poster-box">
        <SharePoster ref="posterRef" :data="data" />
      </view>

      <!-- 保存 / 分享 -->
      <view class="actions">
        <view
          class="btn btn--primary action-btn"
          :class="{ 'btn--disabled': exporting }"
          @click="onSave"
        >
          <text class="action-btn-text">{{ exporting ? "生成中…" : "保存海报" }}</text>
        </view>
        <view class="btn action-btn action-btn--ghost" @click="onShare">
          <text class="action-btn-ghost-text">分享给同学</text>
        </view>
      </view>
      <view class="tip">
        <text class="tip-text">H5 直接下载图片 · 小程序保存到相册</text>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad, onShareAppMessage } from "@dcloudio/uni-app";
import { fetchShareCard } from "@/api/share";
import type { ShareCardData } from "@/types";
import SharePoster from "@/components/SharePoster.vue";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";

/**
 * 成绩单海报分享（docs/api.md §12.8 / architecture.md §12.3 D12）
 *  - GET /me/share-card 拉取聚合数据 → SharePoster canvas 绘制（amber 品牌视觉）
 *  - 保存：H5 canvasToTempFilePath(base64) → <a download>；小程序/App → saveImageToPhotosAlbum
 *  - 分享：小程序 onShareAppMessage 带图；H5 提示长按保存后转发
 */

const loading = ref(false);
const error = ref("");
const data = ref<ShareCardData | null>(null);
const exporting = ref(false);
const posterRef = ref<InstanceType<typeof SharePoster> | null>(null);
const posterPath = ref("");

onLoad(() => {
  load();
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    data.value = await fetchShareCard();
  } catch (e) {
    error.value = (e as Error).message || "数据加载失败";
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  if (exporting.value) return;
  exporting.value = true;
  try {
    const filePath = await posterRef.value?.exportImage();
    if (!filePath) throw new Error("海报生成失败");
    posterPath.value = filePath;
    // #ifdef H5
    downloadH5(filePath);
    // #endif
    // #ifndef H5
    saveToAlbum(filePath);
    // #endif
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "生成失败", icon: "none" });
  } finally {
    exporting.value = false;
  }
}

function onShare() {
  // #ifdef H5
  uni.showToast({ title: "请先保存海报，再转发给同学", icon: "none" });
  // #endif
  // #ifndef H5
  uni.showToast({ title: "点击右上角 · 转发给同学", icon: "none" });
  // #endif
}

// #ifdef H5
/** H5：base64 dataURL → <a download> 触发下载 */
function downloadH5(dataUrl: string) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = `AceExam-${data.value?.username || "战绩"}-海报.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
// #endif

// #ifndef H5
/** 小程序/App：保存到系统相册（需 scope.writePhotosAlbum 授权，失败引导去设置） */
function saveToAlbum(filePath: string) {
  uni.saveImageToPhotosAlbum({
    filePath,
    success: () => uni.showToast({ title: "已保存到相册", icon: "success" }),
    fail: (err) => {
      const msg = (err as { errMsg?: string }).errMsg || "";
      if (msg.includes("auth") || msg.includes("deny") || msg.includes("cancel")) {
        uni.showModal({
          title: "需要相册权限",
          content: "保存海报需要相册权限，请在设置中开启",
          confirmText: "去设置",
          success: (r) => {
            if (r.confirm) uni.openSetting();
          },
        });
      } else {
        uni.showToast({ title: "保存失败，请重试", icon: "none" });
      }
    },
  });
}
// #endif

/** 小程序转发（H5 无此生命周期） */
onShareAppMessage(() => ({
  title: `我在 AceExam 的学习战绩，快来一起备考！`,
  path: "/pages/mine/index",
  imageUrl: posterPath.value || undefined,
}));
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

.head {
  padding: 32rpx;
}
.head-title {
  font-size: 40rpx;
  font-weight: 800;
  color: $neutral-900;
}
.head-desc {
  display: block;
  margin-top: 8rpx;
  font-size: $font-aux;
  color: $neutral-500;
}

.poster-box {
  margin: 0 32rpx;
  padding: 24rpx;
  display: flex;
  justify-content: center;
  overflow: hidden;
  border-radius: $radius-card;
}

.actions {
  padding: 32rpx 32rpx 0;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.action-btn {
  padding: 22rpx 0;
}
.action-btn--ghost {
  border: 2rpx solid $primary-500;
  background: #ffffff;
}
.action-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
}
.action-btn-ghost-text {
  color: $primary-600;
  font-size: $font-body;
  font-weight: 700;
}

.tip {
  padding: 16rpx 32rpx;
  display: flex;
  justify-content: center;
}
.tip-text {
  font-size: 22rpx;
  color: $neutral-300;
}
</style>
