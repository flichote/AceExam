<template>
  <view class="page">
    <!-- 顶部说明 -->
    <view class="hero">
      <text class="hero-title">📥 录入校本课程</text>
      <text class="hero-desc">输入你们学校的课程名，AI 自动匹配到模板课程，题库跨校共享</text>
    </view>

    <!-- 录入流程（联想 → 匹配 → 确认/手动建实例） -->
    <view class="wrap">
      <CourseMatchPanel @added="onAdded" />
    </view>

    <view class="page-foot">
      <text class="page-foot-text">匹配到模板后，题目挂在模板课程上，任何学校的同学都能刷到</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import CourseMatchPanel from "@/components/CourseMatchPanel.vue";

/** 添加成功 → 返回上一页（选课引导 / 课程广场 onShow 刷新） */
function onAdded() {
  uni.showToast({ title: "已添加到我的课程 🎉", icon: "none" });
  setTimeout(() => {
    uni.navigateBack();
  }, 600);
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
  line-height: 1.6;
}

.wrap {
  padding: 32rpx;
}

.page-foot {
  padding: 24rpx 32rpx;
  display: flex;
  justify-content: center;
}
.page-foot-text {
  font-size: 22rpx;
  color: $neutral-300;
}
</style>
