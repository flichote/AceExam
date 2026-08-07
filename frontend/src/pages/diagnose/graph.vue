<template>
  <view class="page">
    <!-- 科目选择 -->
    <view class="subject-bar">
      <scroll-view scroll-x class="subject-scroll" :show-scrollbar="false">
        <view class="subject-list">
          <view
            v-for="s in subjects"
            :key="s.id"
            class="subject-chip"
            :class="{ 'subject-chip--active': s.id === currentSubjectId }"
            @click="switchSubject(s.id)"
          >
            <text class="subject-chip-text" :class="{ 'subject-chip-text--active': s.id === currentSubjectId }">
              {{ s.name }}
            </text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 统计条 -->
    <view v-if="graph" class="stats-bar">
      <view class="stat">
        <text class="stat-num">{{ graph.stats.leaf_count }}</text>
        <text class="stat-label">知识点</text>
      </view>
      <view class="stat">
        <text class="stat-num stat-num--success">{{ graph.stats.mastered_count }}</text>
        <text class="stat-label">已掌握</text>
      </view>
      <view class="stat">
        <text class="stat-num stat-num--danger">{{ graph.stats.weak_count }}</text>
        <text class="stat-label">薄弱</text>
      </view>
      <view class="stat">
        <text class="stat-num stat-num--warning">{{ graph.stats.consolidating_count }}</text>
        <text class="stat-label">待巩固</text>
      </view>
    </view>

    <!-- 加载 / 错误 -->
    <view v-if="loading" class="content">
      <LoadingSkeleton />
    </view>
    <view v-else-if="error" class="content">
      <EmptyState icon="⚠️" title="图谱加载失败" :desc="error" action-text="重试" @action="load" />
    </view>

    <!-- 图谱 -->
    <view v-else-if="graph" class="content">
      <view class="section-head">
        <text class="section-title">{{ graph.subject_name }} · 知识点图谱</text>
        <text class="section-sub">点击节点查看 / 练习</text>
      </view>
      <KnowledgeGraphTree
        ref="treeRef"
        :root="graph.root"
        @select="onNodeSelect"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import { fetchKnowledgeGraph } from "@/api/graph";
import type { GraphNode, KnowledgeGraphResponse } from "@/types";
import KnowledgeGraphTree from "@/components/KnowledgeGraphTree.vue";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";

const subjectStore = useSubjectStore();
const treeRef = ref<InstanceType<typeof KnowledgeGraphTree> | null>(null);

const currentSubjectId = ref("");
const graph = ref<KnowledgeGraphResponse | null>(null);
const loading = ref(false);
const error = ref("");

const subjects = computed(() => subjectStore.subjects);

onLoad((options) => {
  const sid = (options?.subjectId as string) || "";
  if (sid) currentSubjectId.value = sid;
});

onShow(async () => {
  await subjectStore.loadSubjects();
  if (!currentSubjectId.value && subjectStore.subjects.length) {
    currentSubjectId.value = subjectStore.subjects[0].id;
  }
  if (currentSubjectId.value) load();
});

function switchSubject(id: string) {
  if (id === currentSubjectId.value) return;
  currentSubjectId.value = id;
  load();
}

async function load() {
  if (!currentSubjectId.value) return;
  loading.value = true;
  error.value = "";
  try {
    graph.value = await fetchKnowledgeGraph(currentSubjectId.value, true);
  } catch (e) {
    error.value = (e as Error).message || "图谱加载失败";
  } finally {
    loading.value = false;
  }
}

/** 节点点击：叶子 → 对应知识点练习；父节点 → 组件内展开收起（emit 仅选中展示） */
function onNodeSelect(node: GraphNode) {
  // 跳转练习：按知识点过滤（practice 页支持 kpId 参数）
  subjectStore.selectSubject(currentSubjectId.value);
  uni.switchTab({
    url: `/pages/practice/index?subjectId=${encodeURIComponent(currentSubjectId.value)}&kpId=${encodeURIComponent(node.id)}`,
  });
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

/* 科目选择条 */
.subject-bar {
  padding: 24rpx 0 0;
}
.subject-scroll {
  white-space: nowrap;
  padding: 0 16rpx;
}
.subject-list {
  display: inline-flex;
  gap: 12rpx;
  padding: 0 16rpx;
}
.subject-chip {
  display: inline-flex;
  padding: 10rpx 28rpx;
  background: #ffffff;
  border-radius: $radius-btn;
  border: 2rpx solid $neutral-300;
}
.subject-chip--active {
  background: $primary-500;
  border-color: $primary-500;
}
.subject-chip-text {
  font-size: 24rpx;
  color: $neutral-500;
  font-weight: 600;
}
.subject-chip-text--active {
  color: #ffffff;
}

/* 统计条 */
.stats-bar {
  display: flex;
  background: #ffffff;
  margin: 24rpx 32rpx 0;
  border-radius: $radius-card;
  box-shadow: $shadow-card;
  padding: 24rpx 0;
}
.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stat-num {
  font-size: 32rpx;
  font-weight: 800;
  color: $neutral-900;
}
.stat-num--success {
  color: $success-500;
}
.stat-num--danger {
  color: $danger-500;
}
.stat-num--warning {
  color: $warning-500;
}
.stat-label {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 4rpx;
}

.content {
  padding: 24rpx 32rpx;
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20rpx;
}
.section-title {
  font-size: 32rpx;
  font-weight: 700;
  color: $neutral-900;
}
.section-sub {
  font-size: $font-aux;
  color: $neutral-500;
}
</style>
