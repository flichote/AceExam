/**
 * 知识点图谱树（自绘 canvas，H5 / mp-weixin 通用）
 *
 * 背景：architecture.md §11.1 定案 H5/App 用 uni-echarts，mp-weixin 降级 canvas；
 * 本文档 T16 兜底 = 自绘 canvas 树（三级固定布局，不增包体）。
 * 实现说明：uni-app 旧版 canvas API（uni.createCanvasContext）在 H5 与小程序端
 * 行为一致，节点状态色取设计系统 token（见下方 STATUS_COLOR，与 uni.scss 对齐）。
 *
 * Props: root（GraphNode 三级树，含状态着色）
 * Emits: select(node) — 点击叶子/父节点
 */

<template>
  <view class="kg">
    <!-- 图例 -->
    <view class="kg-legend">
      <view v-for="g in legend" :key="g.key" class="kg-legend-item">
        <view class="kg-legend-dot" :style="{ background: g.color }" />
        <text class="kg-legend-text">{{ g.label }}</text>
      </view>
    </view>

    <!-- 画布（横向可滚动：叶子多时 canvas 加宽） -->
    <scroll-view scroll-x class="kg-scroll" :show-scrollbar="false">
      <canvas
        :id="canvasId"
        :canvas-id="canvasId"
        :style="{ width: canvasW + 'px', height: canvasH + 'px' }"
        @touchstart="onTouch"
        @click="onClick"
      />
    </scroll-view>

    <!-- 选中节点详情 -->
    <view v-if="selected" class="kg-detail card">
      <view class="kg-detail-head">
        <text class="kg-detail-name">{{ selected.name }}</text>
        <SubjectPill :label="statusText[selected.status]" :type="statusType[selected.status]" />
      </view>
      <view class="kg-detail-meta">
        <text class="kg-detail-meta-text">题量 {{ selected.question_count ?? 0 }}</text>
        <text v-if="selected.practice_count !== undefined" class="kg-detail-meta-text">
          练习 {{ selected.practice_count }} 次
        </text>
        <text v-if="selected.accuracy != null" class="kg-detail-meta-text">
          正确率 {{ Math.round(selected.accuracy * 100) }}%
        </text>
      </view>
      <view class="kg-detail-actions">
        <view class="btn btn--primary kg-detail-btn" @click="practiceNode">
          <text class="kg-detail-btn-text">去练习</text>
        </view>
        <view v-if="isLeaf(selected)" class="btn kg-detail-btn kg-detail-btn--ghost" @click="explainNode">
          <text class="kg-detail-btn-ghost-text">AI 讲解</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance, nextTick, onMounted, ref, watch } from "vue";
import type { GraphNode, GraphNodeStatus } from "@/types";
import SubjectPill from "./SubjectPill.vue";

const props = defineProps<{
  root: GraphNode;
  /** 画布宽度（px），默认 345（375 设计稿 - 左右 16px 边距 × 2 ≈ 343） */
  width?: number;
  /** 画布高度（px） */
  height?: number;
}>();

const emit = defineEmits<{ (e: "select", node: GraphNode): void }>();

const instance = getCurrentInstance();
const canvasId = `kg-canvas-${Math.random().toString(36).slice(2, 8)}`;
const canvasW = ref(props.width ?? 343);
const canvasH = ref(props.height ?? 430);
const selected = ref<GraphNode | null>(null);
/** 收起状态：nodeId -> collapsed（父节点可展开/收起） */
const collapsed = ref<Record<string, boolean>>({});
/** 布局后的节点位置：nodeId -> {x, y, w, h}（命中检测用） */
const nodeBoxes = ref<Record<string, { x: number; y: number; w: number; h: number }>>({});

/* 状态色（设计系统 token：docs/design/design-system.md / uni.scss） */
const STATUS_COLOR: Record<GraphNodeStatus, string> = {
  mastered: "#10B981", // $success-500
  weak: "#EF4444", // $danger-500
  consolidating: "#F59E0B", // $warning-500
  untouched: "#9CA3AF", // $neutral-400
};
const statusText: Record<GraphNodeStatus, string> = {
  mastered: "已掌握",
  weak: "薄弱",
  consolidating: "待巩固",
  untouched: "未接触",
};
const statusType: Record<GraphNodeStatus, string> = {
  mastered: "success",
  weak: "danger",
  consolidating: "warning",
  untouched: "neutral",
};
const legend = [
  { key: "mastered", label: "已掌握", color: STATUS_COLOR.mastered },
  { key: "weak", label: "薄弱", color: STATUS_COLOR.weak },
  { key: "consolidating", label: "待巩固", color: STATUS_COLOR.consolidating },
  { key: "untouched", label: "未接触", color: STATUS_COLOR.untouched },
];

function isLeaf(n: GraphNode): boolean {
  return !n.children || n.children.length === 0;
}

/* ===== 布局：三级树（root → children → grandchildren） ===== */
interface Placed {
  node: GraphNode;
  x: number;
  y: number;
  w: number;
  h: number;
  level: number;
}

function measure(name: string): { w: number; h: number } {
  const len = Math.min(name.length, 8);
  return { w: Math.max(56, 20 + len * 11), h: 34 };
}

function layoutTree(): { placed: Placed[]; totalW: number; totalH: number } {
  const placed: Placed[] = [];
  const root = props.root;
  const visible = (n: GraphNode): boolean => !collapsed.value[n.id];

  const childrenOf = (n: GraphNode): GraphNode[] =>
    visible(n) ? (n.children ?? []) : [];

  // 按层收集可见节点
  const levels: GraphNode[][] = [[root]];
  let frontier = [root];
  while (frontier.length) {
    const next: GraphNode[] = [];
    frontier.forEach((n) => next.push(...childrenOf(n)));
    if (!next.length) break;
    levels.push(next);
    frontier = next;
  }

  const marginX = 14;
  const gapX = 14;
  const rowGap = 70;
  const topPad = 44;
  const bottomPad = 12;

  // 逐层计算 x（层内均分）
  const rows: Placed[][] = [];
  levels.forEach((nodes, li) => {
    const row: Placed[] = [];
    nodes.forEach((node) => {
      const { w, h } = measure(node.name);
      row.push({ node, x: 0, y: topPad + li * rowGap, w, h, level: li });
    });
    rows.push(row);
  });

  // 层宽 = 节点总宽 + 间距
  let totalW = 0;
  rows.forEach((row) => {
    const rowW = row.reduce((acc, p) => acc + p.w, 0) + (row.length - 1) * gapX + marginX * 2;
    totalW = Math.max(totalW, rowW);
  });
  totalW = Math.max(totalW, canvasW.value);
  const totalH = topPad + rows.length * rowGap + bottomPad;

  // 计算 x：每行居中（若行宽 < totalW 则居中，否则从 marginX 起排）
  rows.forEach((row) => {
    const rowW = row.reduce((acc, p) => acc + p.w, 0) + (row.length - 1) * gapX;
    let cursor = Math.max(marginX, (totalW - rowW) / 2);
    row.forEach((p) => {
      p.x = cursor;
      cursor += p.w + gapX;
    });
  });

  rows.flat().forEach((p) => placed.push(p));
  canvasH.value = Math.max(props.height ?? 430, totalH);
  canvasW.value = totalW;
  return { placed, totalW, totalH };
}

function draw() {
  nextTick(() => {
    const ctx = uni.createCanvasContext(canvasId, instance?.proxy);
    const { placed } = layoutTree();
    const boxes: Record<string, { x: number; y: number; w: number; h: number }> = {};
    placed.forEach((p) => {
      boxes[p.node.id] = { x: p.x, y: p.y, w: p.w, h: p.h };
    });
    nodeBoxes.value = boxes;

    ctx.clearRect(0, 0, canvasW.value, canvasH.value);
    const byId = new Map<string, Placed>();
    placed.forEach((p) => byId.set(p.node.id, p));

    // 连线（先画线再画节点，避免线压字）
    placed.forEach((p) => {
      const children = p.node.children ?? [];
      children.forEach((c) => {
        const cp = byId.get(c.id);
        if (!cp) return;
        const color = STATUS_COLOR[p.node.status];
        ctx.setStrokeStyle(color);
        ctx.setLineWidth(1.5);
        ctx.setGlobalAlpha(0.5);
        ctx.beginPath();
        ctx.moveTo(p.x + p.w / 2, p.y + p.h);
        ctx.quadraticCurveTo(
          p.x + p.w / 2,
          p.y + p.h + (cp.y - p.y - p.h) / 2,
          cp.x + cp.w / 2,
          cp.y
        );
        ctx.stroke();
        ctx.setGlobalAlpha(1);
      });
    });

    // 节点
    placed.forEach((p) => {
      const color = STATUS_COLOR[p.node.status];
      // 圆角矩形
      roundRect(ctx, p.x, p.y, p.w, p.h, 8);
      ctx.setFillStyle(hexToRgba(color, 0.1));
      ctx.fill();
      ctx.setStrokeStyle(color);
      ctx.setLineWidth(1.5);
      ctx.stroke();
      // 名称（超长截断）
      const label = p.node.name.length > 8 ? p.node.name.slice(0, 7) + "…" : p.node.name;
      ctx.setFillStyle("#1F2937"); // $neutral-900
      ctx.setFontSize(12);
      ctx.setTextAlign("center");
      ctx.setTextBaseline("middle");
      ctx.fillText(label, p.x + p.w / 2, p.y + p.h / 2 - 3);
      // 题量小字
      if (p.node.question_count !== undefined) {
        ctx.setFontSize(10);
        ctx.setFillStyle("#6B7280"); // $neutral-500
        ctx.fillText(`${p.node.question_count}题`, p.x + p.w / 2, p.y + p.h / 2 + 10);
      }
      // 可展开标记（非叶子 + 有子节点）
      if (p.node.children && p.node.children.length > 0) {
        ctx.setFontSize(10);
        ctx.setFillStyle(color);
        const mark = collapsed.value[p.node.id] ? "＋" : "－";
        ctx.fillText(mark, p.x + p.w - 8, p.y + 8);
      }
    });

    ctx.draw();
  });
}

function roundRect(
  ctx: UniApp.CanvasContext,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function hexToRgba(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

/* ===== 命中检测 ===== */
function hitNode(x: number, y: number): GraphNode | null {
  for (const [id, box] of Object.entries(nodeBoxes.value)) {
    if (x >= box.x && x <= box.x + box.w && y >= box.y && y <= box.y + box.h) {
      return findNode(props.root, id);
    }
  }
  return null;
}

function findNode(node: GraphNode, id: string): GraphNode | null {
  if (node.id === id) return node;
  for (const c of node.children ?? []) {
    const found = findNode(c, id);
    if (found) return found;
  }
  return null;
}

let lastTouchAt = 0;
function onTouch(e: TouchEvent) {
  lastTouchAt = Date.now();
  // uni-app 小程序 canvas 触摸坐标在 touches[i].x/y；H5 走 click（offsetX/offsetY）
  const t = (e.touches as unknown as ArrayLike<{ x?: number; y?: number }>)?.[0];
  if (!t || t.x == null || t.y == null) return;
  handleTap(t.x, t.y);
}

function onClick(e: MouseEvent) {
  // 触摸已处理过则跳过 click（H5 双触发防护）
  if (Date.now() - lastTouchAt < 500) return;
  const x = (e as unknown as { offsetX?: number }).offsetX ?? 0;
  const y = (e as unknown as { offsetY?: number }).offsetY ?? 0;
  handleTap(x, y);
}

function handleTap(x: number, y: number) {
  const node = hitNode(x, y);
  if (!node) return;
  if (node.children && node.children.length > 0) {
    // 父节点：展开/收起
    collapsed.value = { ...collapsed.value, [node.id]: !collapsed.value[node.id] };
    selected.value = node;
    draw();
    return;
  }
  selected.value = node;
  emit("select", node);
}

function practiceNode() {
  if (selected.value) emit("select", selected.value);
}

function explainNode() {
  if (selected.value) emit("select", selected.value);
}

/* ===== 监听根变化重绘 ===== */
watch(
  () => props.root,
  () => {
    selected.value = null;
    collapsed.value = {};
    draw();
  },
  { deep: true, immediate: true }
);

onMounted(() => {
  draw();
});

watch(collapsed, () => draw(), { deep: true });

defineExpose({ draw, canvasId });
</script>

<style lang="scss">
.kg {
  padding-top: 8rpx;
}
.kg-legend {
  display: flex;
  gap: 24rpx;
  padding: 0 8rpx 16rpx;
  flex-wrap: wrap;
}
.kg-legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.kg-legend-dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
}
.kg-legend-text {
  font-size: 22rpx;
  color: $neutral-500;
}
.kg-scroll {
  width: 100%;
  border-radius: $radius-card;
  background: #ffffff;
  border: 2rpx solid $neutral-100;
}
.kg-detail {
  margin-top: 20rpx;
  padding: 24rpx;
}
.kg-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.kg-detail-name {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
}
.kg-detail-meta {
  display: flex;
  gap: 24rpx;
  margin-top: 12rpx;
}
.kg-detail-meta-text {
  font-size: $font-aux;
  color: $neutral-500;
}
.kg-detail-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 20rpx;
}
.kg-detail-btn {
  padding: 14rpx 40rpx;
  flex: 1;
}
.kg-detail-btn--ghost {
  background: $primary-100;
}
.kg-detail-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
}
.kg-detail-btn-ghost-text {
  color: $primary-600;
  font-size: $font-body;
  font-weight: 700;
}
</style>
