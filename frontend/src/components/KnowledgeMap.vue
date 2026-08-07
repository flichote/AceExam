<template>
  <view class="km">
    <view class="km-legend">
      <view v-for="g in groups" :key="g.key" class="km-legend-item">
        <view class="km-legend-dot" :style="{ background: g.color }" />
        <text class="km-legend-text">{{ g.label }}</text>
      </view>
    </view>

    <view
      v-for="kp in sorted"
      :key="kpId(kp)"
      class="card km-item"
      @click="$emit('select', kp)"
    >
      <view class="km-item-head">
        <view class="km-item-dot" :style="{ background: colorOf(kp) }" />
        <text class="km-item-name">{{ kpName(kp) }}</text>
        <SubjectPill :label="statusText(statusOf(kp))" :type="statusType(statusOf(kp))" />
      </view>
      <view class="km-item-meta">
        <text class="km-item-meta-text">
          {{ kp.accuracy !== undefined ? `正确率 ${Math.round(kp.accuracy * 100)}%` : `难度 Lv.${kp.level ?? 3}` }}
        </text>
        <text class="km-item-arrow">›</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { WeakTop, KnowledgePointHit } from "@/types";
import SubjectPill from "./SubjectPill.vue";

type KpLike = WeakTop | KnowledgePointHit;

const props = defineProps<{
  /** 薄弱 Top5（诊断报告）或 weak_kps（计划快照） */
  items: KpLike[];
}>();

defineEmits<{ (e: "select", kp: KpLike): void }>();

const groups = [
  { key: "weak", label: "薄弱", color: "#EF4444" },
  { key: "consolidating", label: "待巩固", color: "#F59E0B" },
  { key: "mastered", label: "已掌握", color: "#10B981" },
  { key: "not_started", label: "未开始", color: "#9CA3AF" },
];

function statusOf(kp: KpLike): string {
  return (kp.status || "not_started") as string;
}
/** WeakTop 与 KnowledgePointHit 字段名差异归一 */
function kpId(kp: KpLike): string {
  return "id" in kp ? kp.id : kp.knowledge_point_id;
}
function kpName(kp: KpLike): string {
  return "name" in kp ? kp.name : kp.knowledge_point_name;
}
function colorOf(kp: KpLike): string {
  const g = groups.find((x) => x.key === statusOf(kp));
  return g ? g.color : "#9CA3AF";
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    weak: "薄弱",
    consolidating: "待巩固",
    mastered: "已掌握",
    not_started: "未开始",
  };
  return map[status] || status;
}
function statusType(status: string): string {
  const map: Record<string, string> = {
    weak: "danger",
    consolidating: "warning",
    mastered: "success",
    not_started: "neutral",
  };
  return map[status] || "neutral";
}

/** P1 简化：按状态分组排序（薄弱 → 待巩固 → 已掌握 → 未开始） */
const sorted = computed(() => {
  const order: Record<string, number> = { weak: 0, consolidating: 1, mastered: 2, not_started: 3 };
  return [...props.items].sort(
    (a, b) => (order[statusOf(a)] ?? 9) - (order[statusOf(b)] ?? 9)
  );
});
</script>

<style lang="scss">
.km {
  padding-top: 8rpx;
}
.km-legend {
  display: flex;
  gap: 24rpx;
  padding: 0 8rpx 20rpx;
  flex-wrap: wrap;
}
.km-legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.km-legend-dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
}
.km-legend-text {
  font-size: 22rpx;
  color: $neutral-500;
}

.km-item {
  padding: 24rpx;
  margin-bottom: 16rpx;
}
.km-item-head {
  display: flex;
  align-items: center;
}
.km-item-dot {
  width: 18rpx;
  height: 18rpx;
  border-radius: 50%;
  margin-right: 16rpx;
  flex-shrink: 0;
}
.km-item-name {
  flex: 1;
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.km-item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12rpx;
  padding-left: 34rpx;
}
.km-item-meta-text {
  font-size: 22rpx;
  color: $neutral-500;
}
.km-item-arrow {
  font-size: 32rpx;
  color: $neutral-300;
}
</style>
