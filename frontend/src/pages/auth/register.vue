<template>
  <view class="page">
    <view class="logo">
      <text class="logo-text">🎓</text>
      <text class="logo-title">AceExam</text>
      <text class="logo-sub">注册账号，开启上岸之旅</text>
    </view>

    <view class="card form-card">
      <view class="field">
        <text class="field-label">用户名</text>
        <input
          v-model="username"
          class="field-input"
          placeholder="2-50 个字符"
          placeholder-class="field-placeholder"
          :maxlength="50"
        />
      </view>
      <view class="field">
        <text class="field-label">密码</text>
        <input
          v-model="password"
          class="field-input"
          password
          placeholder="至少 6 位"
          placeholder-class="field-placeholder"
          :maxlength="128"
        />
      </view>
      <view class="field">
        <text class="field-label">确认密码</text>
        <input
          v-model="confirmPassword"
          class="field-input"
          password
          placeholder="再次输入密码"
          placeholder-class="field-placeholder"
          :maxlength="128"
          confirm-type="done"
          @confirm="onRegister"
        />
      </view>
    </view>

    <view class="foot">
      <view
        class="btn btn--primary login-btn"
        :class="{ 'btn--disabled': !canSubmit }"
        @click="onRegister"
      >
        <text class="login-btn-text">注册</text>
      </view>
      <view class="switch-row" @click="goLogin">
        <text class="switch-text">已有账号？去登录</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useAuthStore } from "@/stores/auth";
import { register as apiRegister } from "@/api/auth";
import { isOnboarded } from "@/utils/onboarding";

const auth = useAuthStore();
const username = ref("");
const password = ref("");
const confirmPassword = ref("");
const submitting = ref(false);

const canSubmit = computed(
  () =>
    username.value.trim().length >= 2 &&
    password.value.length >= 6 &&
    password.value === confirmPassword.value &&
    !submitting.value
);

async function onRegister() {
  if (!canSubmit.value) return;
  submitting.value = true;
  try {
    const res = await apiRegister(username.value.trim(), password.value);
    auth.user = res.user;
    uni.showToast({ title: "注册成功，欢迎加入 🎉", icon: "none" });
    setTimeout(() => {
      // 新注册用户：无专业/课程 → 引导选课（docs/api.md §13）
      if (!isOnboarded()) {
        uni.reLaunch({ url: "/pages/onboarding/index" });
      } else {
        uni.switchTab({ url: "/pages/subjects/index" });
      }
    }, 600);
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "注册失败", icon: "none" });
  } finally {
    submitting.value = false;
  }
}

function goLogin() {
  uni.navigateBack({ fail: () => uni.reLaunch({ url: "/pages/auth/login" }) });
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
.switch-row {
  margin-top: 24rpx;
  padding: 8rpx 16rpx;
}
.switch-text {
  font-size: 26rpx;
  color: $primary-500;
  font-weight: 600;
}
</style>
