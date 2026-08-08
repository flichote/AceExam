<template>
  <view class="poster">
    <canvas
      :id="canvasId"
      :canvas-id="canvasId"
      :style="{ width: W + 'px', height: H + 'px' }"
    />
  </view>
</template>

<script setup lang="ts">
import { getCurrentInstance, nextTick, onMounted, watch } from "vue";
import type { ShareCardData } from "@/types";
import { toApiError } from "@/utils/request";

/**
 * 成绩单海报（docs/api.md §12.8 / architecture.md §12.3 D12）
 *
 * 前端 canvas 生成：uni-app 旧版 CanvasContext（uni.createCanvasContext）
 * 在 H5 与小程序端行为一致（本项目图表组件同款，避免 type=2d 平台差异）。
 * 画布 343×609（750/1334 等比预览），导出时 uni.canvasToTempFilePath
 * destWidth=750 / destHeight=1334（H5 返回 base64，小程序返回临时文件路径）。
 *
 * 品牌视觉：amber 活力橙（#F59E0B / #D97706 / #FEF3C7），token 见 uni.scss。
 * 无数据边界：全零用户展示「开始第一题」引导（§12.8）。
 */

const props = defineProps<{ data: ShareCardData }>();

const instance = getCurrentInstance();
const canvasId = `share-poster-${Math.random().toString(36).slice(2, 8)}`;
const W = 343;
const H = 609;

/* 设计系统 token（canvas 无法读 SCSS 变量，常量对齐 uni.scss） */
const AMBER = "#F59E0B"; // $primary-500
const AMBER_DARK = "#D97706"; // $primary-600
const AMBER_LIGHT = "#FEF3C7"; // $primary-100
const INK = "#1F2937"; // $neutral-900
const GRAY = "#6B7280"; // $neutral-500
const WHITE = "#FFFFFF";

interface GradientLike {
  addColorStop(p: number, c: string): void;
}

interface CtxLike {
  setFontSize(n: number): void;
  setFillStyle(c: string | GradientLike): void;
  setTextAlign(a: "left" | "center" | "right"): void;
  fillText(s: string, x: number, y: number): void;
  beginPath(): void;
  moveTo(x: number, y: number): void;
  lineTo(x: number, y: number): void;
  arc(x: number, y: number, r: number, a1: number, a2: number): void;
  closePath(): void;
  fill(): void;
  fillRect(x: number, y: number, w: number, h: number): void;
  clearRect(x: number, y: number, w: number, h: number): void;
  createLinearGradient(x0: number, y0: number, x1: number, y1: number): GradientLike;
  draw(reserve?: boolean, cb?: () => void): void;
}

/** 圆角矩形路径（旧版 API 无 roundRect，手写 arc 路径） */
function roundRectPath(ctx: CtxLike, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arc(x + w - r, y + r, r, -Math.PI / 2, 0);
  ctx.lineTo(x + w, y + h - r);
  ctx.arc(x + w - r, y + h - r, r, 0, Math.PI / 2);
  ctx.lineTo(x + r, y + h);
  ctx.arc(x + r, y + h - r, r, Math.PI / 2, Math.PI);
  ctx.lineTo(x, y + r);
  ctx.arc(x + r, y + r, r, Math.PI, Math.PI * 1.5);
  ctx.closePath();
}

function text(
  ctx: CtxLike,
  str: string,
  x: number,
  y: number,
  size: number,
  color: string,
  align: "left" | "center" | "right" = "left"
) {
  ctx.setFontSize(size);
  ctx.setFillStyle(color);
  ctx.setTextAlign(align);
  ctx.fillText(str, x, y);
}

function draw(): Promise<void> {
  return new Promise((resolve) => {
    nextTick(() => {
      const ctx = uni.createCanvasContext(canvasId, instance?.proxy) as unknown as CtxLike;
      const d = props.data;
      ctx.clearRect(0, 0, W, H);

      /* 背景：amber 渐变 */
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, AMBER);
      grad.addColorStop(0.5, AMBER_LIGHT);
      grad.addColorStop(1, WHITE);
      ctx.setFillStyle(grad);
      ctx.fillRect(0, 0, W, H);

      /* 头部：品牌 + 用户 + 日期 */
      text(ctx, "AceExam", 28, 52, 18, WHITE, "left");
      text(ctx, "期末通关闭环 · 成绩单", W - 28, 52, 10, "rgba(255,255,255,0.85)", "right");
      text(ctx, d.username || "期末选手", 28, 100, 24, WHITE, "left");
      const dateStr = (d.generated_at || "").slice(0, 10);
      text(ctx, `学习战绩 · ${dateStr || "期末冲刺"}`, 28, 130, 11, "rgba(255,255,255,0.9)", "left");

      /* 数据卡（2×2） */
      const cardX = 24;
      const cardY = 168;
      const cardW = W - 48;
      const cardH = 152;
      roundRectPath(ctx, cardX, cardY, cardW, cardH, 16);
      ctx.setFillStyle(WHITE);
      ctx.fill();

      if (!d.totals.questions_practiced) {
        /* 无数据边界：全零用户引导开始第一题（§12.8） */
        text(ctx, "开始第一题，期末通关", W / 2, cardY + cardH / 2, 14, AMBER_DARK, "center");
      } else {
        const cells = [
          { label: "连胜(天)", value: `${d.streak.current}` },
          { label: "掌握度", value: `${Math.round(d.mastery.overall_pct * 100)}%` },
          { label: "做题量", value: `${d.totals.questions_practiced}` },
          { label: "本周正确率", value: `${Math.round(d.recent_7d.accuracy * 100)}%` },
        ];
        const cellW = cardW / 2;
        const cellH = cardH / 2;
        cells.forEach((c, i) => {
          const cx = cardX + (i % 2) * cellW;
          const cy = cardY + Math.floor(i / 2) * cellH;
          text(ctx, c.value, cx + 24, cy + 48, 26, AMBER_DARK, "left");
          text(ctx, c.label, cx + 24, cy + 70, 10, GRAY, "left");
        });
      }

      /* 详情卡 */
      const detY = 340;
      roundRectPath(ctx, cardX, detY, cardW, 148, 16);
      ctx.setFillStyle(WHITE);
      ctx.fill();

      let rowY = detY + 32;
      const line = (label: string, value: string) => {
        text(ctx, label, cardX + 24, rowY, 11, GRAY, "left");
        text(ctx, value, cardX + 130, rowY, 12, INK, "left");
        rowY += 28;
      };

      const best = d.mastery.best_subject;
      line("最佳科目", best ? `${best.subject_name} ${Math.round(best.mastery_pct * 100)}%` : "暂未开始");
      line("近 7 天", `做题 ${d.recent_7d.questions_practiced} · 正确率 ${Math.round(d.recent_7d.accuracy * 100)}%`);
      line("薄弱点", `${d.weak_points.weak} 薄弱 · ${d.weak_points.consolidating} 待巩固`);
      if (d.class) line("班级", d.class.name);
      if (d.exam) line("考试", `${d.exam.subject_name} · 还有 ${d.exam.days_left} 天`);

      /* 底部 */
      text(ctx, "长按保存 · 分享我的期末战绩", W / 2, 560, 10, GRAY, "center");
      text(ctx, "AceExam · AI 期末备考教练", W / 2, 584, 10, AMBER_DARK, "center");

      ctx.draw(false, () => resolve());
    });
  });
}

/** 导出海报图片：H5 返回 base64，小程序/App 返回临时文件路径 */
function exportImage(): Promise<string> {
  return new Promise((resolve, reject) => {
    draw().then(() => {
      uni.canvasToTempFilePath(
        {
          canvasId,
          x: 0,
          y: 0,
          width: W,
          height: H,
          destWidth: 750,
          destHeight: 1334,
          fileType: "png",
          success: (res) => resolve(res.tempFilePath),
          fail: (err) => reject(toApiError(err.errMsg || "海报生成失败", 0)),
        },
        instance?.proxy
      );
    });
  });
}

onMounted(() => {
  draw();
});

watch(
  () => props.data,
  () => draw(),
  { deep: true }
);

defineExpose({ exportImage, draw });
</script>

<style lang="scss">
.poster {
  display: flex;
  justify-content: center;
}
</style>
