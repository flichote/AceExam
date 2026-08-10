<template>
  <view class="page">
    <view class="logo">
      <text class="logo-text">🎓</text>
      <text class="logo-title">AceExam</text>
      <text class="logo-sub">登录后同步你的刷题进度</text>
    </view>

    <view class="card form-card">
      <view class="field">
        <text class="field-label">用户名</text>
        <input
          v-model="username"
          class="field-input"
          placeholder="请输入用户名"
          placeholder-class="field-placeholder"
        />
      </view>
      <view class="field">
        <text class="field-label">密码</text>
        <input
          v-model="password"
          class="field-input"
          password
          placeholder="请输入密码"
          placeholder-class="field-placeholder"
          confirm-type="done"
          @confirm="onLogin"
        />
      </view>
    </view>

    <view class="foot">
      <view
        class="btn btn--primary login-btn"
        :class="{ 'btn--disabled': !username || !password || auth.loggingIn }"
        @click="onLogin"
      >
        <text class="login-btn-text">{{ auth.loggingIn ? "登录中…" : "登录" }}</text>
      </view>
      <view
        class="btn demo-btn"
        :class="{ 'btn--disabled': auth.loggingIn }"
        @click="onDemoLogin"
      >
        <text class="demo-btn-text">✨ 一键体验演示账号（demo_student1）</text>
      </view>
      <view class="switch-row" @click="goRegister">
        <text class="switch-text">还没有账号？去注册</text>
      </view>
      <view class="switch-row" @click="goForgotPassword">
        <text class="switch-text forgot-text">忘记密码？</text>
      </view>
      <text class="login-tip">演示账号数据齐全：高数+英语、挂科预警、连胜记录</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "@/stores/auth";
import { fetchMe } from "@/api/auth";
import { fetchMeSubjects } from "@/api/me";
import { isOnboarded } from "@/utils/onboarding";

const auth = useAuthStore();
const username = ref("zhangsan");
const password = ref("123456");

async function onLogin() {
  if (!username.value.trim() || !password.value || auth.loggingIn) return;
  const ok = await auth.login(username.value.trim(), password.value);
  if (!ok) return;
  uni.showToast({ title: "登录成功 🎉", icon: "none" });
  // 首次使用：未配置专业/课程 → 选课引导（docs/api.md §13 / architecture.md §3.3）
  const needsOnboarding = await checkNeedsOnboarding();
  setTimeout(() => {
    if (needsOnboarding) {
      uni.reLaunch({ url: "/pages/onboarding/index" });
      return;
    }
    // 退出登录用 reLaunch 清空过页面栈（栈内仅 login 页），navigateBack 会失败；
    // 此时应切回 tabBar 首页。
    if (getCurrentPages().length > 1) {
      uni.navigateBack();
    } else {
      uni.switchTab({ url: "/pages/subjects/index" });
    }
  }, 600);
}

/** 一键体验：填入演示账号 demo_student1 并登录（后端 seed 数据齐全） */
async function onDemoLogin() {
  if (auth.loggingIn) return;
  username.value = "demo_student1";
  password.value = "demo123456";
  await onLogin();
}

/** 跳转注册页（无页面栈时用 reLaunch 兜底） */
function goRegister() {
  uni.navigateTo({ url: "/pages/auth/register" });
}

/** 跳转找回密码页 */
function goForgotPassword() {
  uni.navigateTo({ url: "/pages/auth/forgot-password" });
}

/** 登录后判断：major 为空 或 未选课 → 引导页；否则直接返回 */
async function checkNeedsOnboarding(): Promise<boolean> {
  if (isOnboarded()) return false;
  try {
    const [me, subjects] = await Promise.all([fetchMe(), fetchMeSubjects()]);
    const hasMajor = !!me.major?.trim();
    return !hasMajor && subjects.total === 0;
  } catch {
    return false;
  }
}
</script>

<style lang="scss">
.page {
  min-height: 100vh;
  background: $neutral-100;
  padding-top: 120rpx;
  padding-bottom: 48rpx;
}

.logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 48rpx;
}
.logo-text {
  font-size: 80rpx;
}
.logo-title {
  font-size: 44rpx;
  font-weight: 800;
  color: $neutral-900;
  margin-top: 12rpx;
}
.logo-sub {
  font-size: 24rpx;
  color: $neutral-500;
  margin-top: 4rpx;
}

.form-card {
  margin: 0 48rpx;
  padding: 32rpx;
}
.field {
  margin-bottom: 24rpx;
}
.field:last-child {
  margin-bottom: 0;
}
.field-label {
  display: block;
  font-size: 24rpx;
  font-weight: 600;
  color: $neutral-500;
  margin-bottom: 8rpx;
}
.field-input {
  background: $neutral-100;
  border-radius: $radius-btn;
  padding: 18rpx 20rpx;
  font-size: $font-body;
  color: $neutral-900;
}
.field-placeholder {
  color: $neutral-300;
}

.foot {
  margin: 32rpx 48rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.login-btn {
  width: 100%;
  padding: 20rpx 0;
}
.login-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}
.demo-btn {
  width: 100%;
  margin-top: 20rpx;
  padding: 18rpx 0;
  background: $neutral-100;
  border: 2rpx solid $primary-100;
}
.demo-btn-text {
  color: $primary-500;
  font-size: 26rpx;
  font-weight: 600;
}
.switch-row {
  margin-top: 24rpx;
  padding: 8rpx 16rpx;
}
.switch-text {
  font-size: 26rpx;
  color: $primary-500;
  font-weight: 600;
}
.forgot-text {
  color: $neutral-500;
  font-weight: 400;
  font-size: 24rpx;
}
.login-tip {
  margin-top: 16rpx;
  font-size: 22rpx;
  color: $neutral-300;
  text-align: center;
}
</style>
