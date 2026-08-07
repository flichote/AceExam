<template>
  <view class="page">
    <view class="head">
      <text class="head-title">创建备考计划</text>
      <text class="head-sub">AI 教练根据考试日期自动生成每日任务</text>
    </view>

    <!-- 科目 -->
    <view class="card form-card">
      <view class="form-row">
        <text class="form-label">考试科目</text>
        <picker :range="subjectNames" :value="subjectIndex" @change="onSubjectChange">
          <view class="form-picker">
            <text class="form-picker-text">{{ currentSubjectName }}</text>
            <text class="form-picker-arrow">▾</text>
          </view>
        </picker>
      </view>

      <!-- 考试日期 -->
      <view class="form-row">
        <text class="form-label">考试日期</text>
        <picker mode="date" :value="examDate" :start="minDate" @change="onDateChange">
          <view class="form-picker">
            <text class="form-picker-text">{{ examDate || "选择日期" }}</text>
            <text class="form-picker-arrow">▾</text>
          </view>
        </picker>
      </view>

      <!-- 每日题量 -->
      <view class="form-row form-row--column">
        <view class="form-label-row">
          <text class="form-label">每日题量</text>
          <text class="form-value">{{ dailyTarget }} 题</text>
        </view>
        <slider
          :value="dailyTarget"
          :min="5"
          :max="50"
          :step="5"
          activeColor="#F59E0B"
          backgroundColor="#F3F4F6"
          block-size="20"
          @change="onTargetChange"
        />
      </view>

      <!-- 计划名 -->
      <view class="form-row form-row--column">
        <text class="form-label">计划名称</text>
        <input
          v-model="title"
          class="form-input"
          placeholder="如：期末冲刺计划"
          placeholder-class="form-placeholder"
        />
      </view>
    </view>

    <view class="foot">
      <view
        class="btn btn--primary create-btn"
        :class="{ 'btn--disabled': creating || !examDate }"
        @click="onCreate"
      >
        <text class="create-btn-text">{{ creating ? "创建中…" : "创建计划" }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { useSubjectStore } from "@/stores/subject";
import { usePlanStore } from "@/stores/plan";
import { createPlan } from "@/api/plans";

const subjectStore = useSubjectStore();
const planStore = usePlanStore();

const subjectId = ref("");
const examDate = ref("");
const dailyTarget = ref(10);
const title = ref("期末冲刺计划");
const creating = ref(false);

onLoad(async (options) => {
  await subjectStore.loadSubjects();
  const preset = (options?.subjectId as string) || "";
  subjectId.value = preset || subjectStore.subjects[0]?.id || "";
  // 默认日期：30 天后
  const d = new Date(Date.now() + 30 * 86400000);
  examDate.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
});

const minDate = computed(() => {
  const d = new Date(Date.now() + 86400000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
});

const subjectIndex = computed(() => {
  const idx = subjectStore.subjects.findIndex((s) => s.id === subjectId.value);
  return idx < 0 ? 0 : idx;
});
const subjectNames = computed(() => subjectStore.subjects.map((s) => s.name));
const currentSubjectName = computed(
  () => subjectStore.subjectById(subjectId.value)?.name ?? "请选择科目"
);

function onSubjectChange(e: { detail: { value: string | number } }) {
  const idx = Number(e.detail.value);
  const s = subjectStore.subjects[idx];
  if (s) subjectId.value = s.id;
}
function onDateChange(e: { detail: { value: string } }) {
  examDate.value = e.detail.value;
}
function onTargetChange(e: { detail: { value: string | number } }) {
  dailyTarget.value = Number(e.detail.value);
}

async function onCreate() {
  if (creating.value || !subjectId.value || !examDate.value) {
    uni.showToast({ title: "请选择科目与考试日期", icon: "none" });
    return;
  }
  creating.value = true;
  try {
    const res = await createPlan({
      subject_id: subjectId.value,
      exam_date: examDate.value,
      daily_question_target: dailyTarget.value,
      title: title.value.trim() || "期末冲刺计划",
    });
    planStore.setFromCreate(res);
    uni.showToast({ title: "计划创建成功 🎉", icon: "none" });
    setTimeout(() => uni.navigateBack(), 800);
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "创建失败", icon: "none" });
  } finally {
    creating.value = false;
  }
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}

.head {
  padding: 32rpx;
  display: flex;
  flex-direction: column;
}
.head-title {
  font-size: 40rpx;
  font-weight: 800;
  color: $neutral-900;
}
.head-sub {
  font-size: 24rpx;
  color: $neutral-500;
  margin-top: 4rpx;
}

.form-card {
  margin: 0 32rpx;
  padding: 8rpx 28rpx;
}
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 0;
  border-bottom: 2rpx solid $neutral-100;
}
.form-row:last-child {
  border-bottom: none;
}
.form-row--column {
  flex-direction: column;
  align-items: stretch;
}
.form-label {
  font-size: $font-body;
  font-weight: 600;
  color: $neutral-900;
}
.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.form-value {
  font-size: $font-body;
  font-weight: 700;
  color: $primary-600;
}
.form-picker {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.form-picker-text {
  font-size: $font-body;
  color: $primary-600;
  font-weight: 600;
}
.form-picker-arrow {
  color: $neutral-300;
  font-size: 24rpx;
}
.form-input {
  margin-top: 12rpx;
  background: $neutral-100;
  border-radius: $radius-btn;
  padding: 16rpx 20rpx;
  font-size: $font-body;
  color: $neutral-900;
}
.form-placeholder {
  color: $neutral-300;
}

.foot {
  padding: 32rpx;
}
.create-btn {
  padding: 22rpx 0;
}
.create-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}
</style>
