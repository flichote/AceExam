/**
 * 学习趋势折线图（自绘 canvas，H5 / mp-weixin 通用）
 *
 * 数据：GET /me/dashboard/trend（docs/api.md §11.5）
 * - 柱状：每日做题量（questions_practiced）
 * - 折线：每日正确率（accuracy 0~1，null 桶跳过连线）
 * 颜色取设计系统 token：做题量 $primary-500 / 正确率 $success-500。
 */

<template>
  <view class="tl">
    <canvas
      :id="canvasId"
      :canvas-id="canvasId"
      :style="{ width: canvasW + 'px', height: canvasH + 'px' }"
    />
    <view class="tl-legend">
      <view class="tl-legend-item">
        <view class="tl-legend-bar" />
        <text class="tl-legend-text">做题量</text>
      </view>
      <view class="tl-legend-item">
        <view class="tl-legend-line" />
        <text class="tl-legend-text">正确率</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance, nextTick, ref, watch } from "vue";
import type { TrendItem } from "@/types";

const props = withDefaults(
  defineProps<{
    items: TrendItem[];
    /** 画布宽度（px） */
    width?: number;
    /** 画布高度（px） */
    height?: number;
  }>(),
  {
    items: () => [],
    width: 343,
    height: 220,
  }
);

const instance = getCurrentInstance();
const canvasId = `tl-canvas-${Math.random().toString(36).slice(2, 8)}`;
const canvasW = ref(props.width);
const canvasH = ref(props.height);

const series = computed(() => {
  const items = props.items;
  const maxCount = Math.max(1, ...items.map((i) => i.questions_practiced));
  return { items, maxCount };
});

function draw() {
  nextTick(() => {
    const ctx = uni.createCanvasContext(canvasId, instance?.proxy);
    const { items, maxCount } = series.value;
    const W = canvasW.value;
    const H = canvasH.value;
    ctx.clearRect(0, 0, W, H);

    // 绘图区（左侧留轴标签，右侧留百分比轴）
    const padL = 30;
    const padR = 34;
    const padT = 14;
    const padB = 24;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    // 网格线（0 / 50% / 100%）
    ctx.setStrokeStyle("#F3F4F6"); // $neutral-100
    ctx.setLineWidth(1);
    [0, 0.5, 1].forEach((ratio) => {
      const y = padT + plotH * (1 - ratio);
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(W - padR, y);
      ctx.stroke();
      ctx.setFillStyle("#9CA3AF"); // $neutral-400
      ctx.setFontSize(9);
      ctx.setTextAlign("right");
      ctx.fillText(`${Math.round(ratio * 100)}%`, padL - 4, y + 3);
    });

    if (!items.length) {
      ctx.setFillStyle("#9CA3AF");
      ctx.setFontSize(12);
      ctx.setTextAlign("center");
      ctx.fillText("暂无趋势数据", W / 2, H / 2);
      ctx.draw();
      return;
    }

    const n = items.length;
    const slot = plotW / n;
    const barW = Math.min(10, slot * 0.5);

    // 柱状：做题量
    items.forEach((it, i) => {
      const h = (it.questions_practiced / maxCount) * plotH;
      const x = padL + slot * i + (slot - barW) / 2;
      const y = padT + plotH - h;
      ctx.setFillStyle("rgba(245, 158, 11, 0.45)"); // $primary-500 45%
      ctx.fillRect(x, y, barW, h);
    });

    // 折线：正确率（null 跳过连线）
    const points: { x: number; y: number }[] = [];
    items.forEach((it, i) => {
      if (it.accuracy == null) return;
      const x = padL + slot * i + slot / 2;
      const y = padT + plotH * (1 - it.accuracy);
      points.push({ x, y });
    });
    if (points.length > 1) {
      ctx.setStrokeStyle("#10B981"); // $success-500
      ctx.setLineWidth(2);
      ctx.beginPath();
      points.forEach((p, i) => {
        if (i === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      });
      ctx.stroke();
    }
    points.forEach((p) => {
      ctx.setFillStyle("#10B981");
      ctx.beginPath();
      ctx.arc(p.x, p.y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });

    // X 轴：首 / 中 / 末日期标签
    const labelIdx = [0, Math.floor(n / 2), n - 1];
    labelIdx.forEach((i) => {
      const it = items[i];
      if (!it) return;
      const short = it.bucket_start.slice(5); // MM-DD
      ctx.setFillStyle("#9CA3AF");
      ctx.setFontSize(9);
      ctx.setTextAlign("center");
      ctx.fillText(short, padL + slot * i + slot / 2, H - 8);
    });

    ctx.draw();
  });
}

watch(() => props.items, draw, { deep: true });
defineExpose({ draw });
</script>

<style lang="scss">
.tl {
  padding-top: 8rpx;
}
.tl-legend {
  display: flex;
  gap: 24rpx;
  padding: 12rpx 8rpx 0;
}
.tl-legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.tl-legend-bar {
  width: 20rpx;
  height: 12rpx;
  background: rgba($primary-500, 0.45);
  border-radius: 4rpx;
}
.tl-legend-line {
  width: 24rpx;
  height: 4rpx;
  background: $success-500;
  border-radius: 4rpx;
}
.tl-legend-text {
  font-size: 22rpx;
  color: $neutral-500;
}
</style>
