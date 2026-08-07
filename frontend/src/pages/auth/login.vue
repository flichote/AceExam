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
      <text class="login-tip">后端未就绪时使用演示账号自动登录（mock 兜底）</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const username = ref("zhangsan");
const password = ref("123456");

async function onLogin() {
  if (!username.value.trim() || !password.value || auth.loggingIn) return;
  const ok = await auth.login(username.value.trim(), password.value);
  if (!ok) return;
  uni.showToast({ title: "登录成功 🎉", icon: "none" });
  setTimeout(() => {
    uni.navigateBack();
  }, 600);
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
.login-tip {
  margin-top: 16rpx;
  font-size: 22rpx;
  color: $neutral-300;
  text-align: center;
}
</style>
