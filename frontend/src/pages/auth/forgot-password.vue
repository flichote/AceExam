<template>
  <view class="page">
    <view class="logo">
      <text class="logo-text">🔑</text>
      <text class="logo-title">找回密码</text>
      <text class="logo-sub">通过手机号验证码重置密码</text>
    </view>

    <view class="card form-card">
      <view class="field">
        <text class="field-label">手机号</text>
        <input
          v-model="phone"
          class="field-input"
          type="number"
          :maxlength="11"
          placeholder="请输入注册时的手机号"
          placeholder-class="field-placeholder"
        />
      </view>
      <view class="field code-field">
        <text class="field-label">验证码</text>
        <view class="code-row">
          <input
            v-model="code"
            class="field-input code-input"
            type="number"
            :maxlength="6"
            placeholder="6 位验证码"
            placeholder-class="field-placeholder"
          />
          <view
            class="btn code-btn"
            :class="{ 'btn--disabled': !canSend || countdown > 0 }"
            @click="onSendCode"
          >
            <text class="code-btn-text">{{ countdown > 0 ? `${countdown}s` : "获取验证码" }}</text>
          </view>
        </view>
        <text v-if="debugCode" class="debug-tip">开发模式验证码：{{ debugCode }}</text>
      </view>
      <view class="field">
        <text class="field-label">新密码</text>
        <input
          v-model="newPassword"
          class="field-input"
          password
          placeholder="至少 6 位"
          placeholder-class="field-placeholder"
          :maxlength="128"
        />
      </view>
      <view class="field">
        <text class="field-label">确认新密码</text>
        <input
          v-model="confirmPassword"
          class="field-input"
          password
          placeholder="再次输入新密码"
          placeholder-class="field-placeholder"
          :maxlength="128"
          confirm-type="done"
          @confirm="onReset"
        />
      </view>
    </view>

    <view class="foot">
      <view
        class="btn btn--primary login-btn"
        :class="{ 'btn--disabled': !canSubmit }"
        @click="onReset"
      >
        <text class="login-btn-text">{{ submitting ? "提交中…" : "重置密码" }}</text>
      </view>
      <view class="switch-row" @click="goLogin">
        <text class="switch-text">想起密码了？去登录</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from "vue";
import { requestPwdCode, resetPassword } from "@/api/auth";

const phone = ref("");
const code = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const debugCode = ref("");
const countdown = ref(0);
const submitting = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;

const canSend = computed(() => /^1\d{10}$/.test(phone.value));
const canSubmit = computed(
  () =>
    canSend.value &&
    code.value.length >= 4 &&
    newPassword.value.length >= 6 &&
    newPassword.value === confirmPassword.value &&
    !submitting.value
);

async function onSendCode() {
  if (!canSend.value || countdown.value > 0) return;
  try {
    const res = await requestPwdCode(phone.value);
    if (res.debug_code) {
      debugCode.value = res.debug_code;
      uni.showToast({ title: `验证码已发送（开发模式：${res.debug_code}）`, icon: "none", duration: 3000 });
    } else {
      uni.showToast({ title: "验证码已发送，请查收短信", icon: "none" });
    }
    startCountdown();
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "发送失败", icon: "none" });
  }
}

function startCountdown() {
  countdown.value = 60;
  timer = setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  }, 1000);
}

async function onReset() {
  if (!canSubmit.value) return;
  submitting.value = true;
  try {
    const res = await resetPassword(phone.value, code.value, newPassword.value);
    uni.showToast({ title: "密码已重置，请登录 🎉", icon: "none" });
    setTimeout(() => {
      uni.reLaunch({ url: "/pages/auth/login" });
    }, 800);
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "重置失败", icon: "none" });
  } finally {
    submitting.value = false;
  }
}

function goLogin() {
  uni.reLaunch({ url: "/pages/auth/login" });
}

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
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
.code-field {
  margin-bottom: 24rpx;
}
.code-row {
  display: flex;
  gap: 16rpx;
}
.code-input {
  flex: 1;
}
.code-btn {
  width: 220rpx;
  padding: 18rpx 0;
  background: $neutral-100;
  border: 2rpx solid $primary-100;
  display: flex;
  align-items: center;
  justify-content: center;
}
.code-btn-text {
  color: $primary-500;
  font-size: 26rpx;
  font-weight: 600;
}
.debug-tip {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $primary-500;
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
