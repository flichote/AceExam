<template>
  <view class="pill" :class="`pill--${type}`" :style="extraStyle">
    <text class="pill-text">{{ label }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    label: string;
    /** neutral | primary | success | danger | warning | info | cramming */
    type?: string;
    fontSize?: string;
  }>(),
  {
    label: "",
    type: "neutral",
    fontSize: "12px",
  }
);

const extraStyle = computed(() => ({ fontSize: props.fontSize }));
</script>

<style lang="scss">
.pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 12px;
  border-radius: $radius-tag;
  flex-shrink: 0;
}

.pill-text {
  font-size: inherit;
  font-weight: 500;
  line-height: 1;
}

/* 状态色一律取设计系统 token（docs/design/design-system.md） */
.pill--neutral {
  background: $neutral-100;
  .pill-text { color: $neutral-500; }
}
.pill--primary {
  background: $primary-100;
  .pill-text { color: $primary-600; }
}
.pill--success {
  background: rgba($success-500, 0.12);
  .pill-text { color: $success-500; }
}
.pill--danger {
  background: rgba($danger-500, 0.12);
  .pill-text { color: $danger-500; }
}
.pill--warning {
  background: $primary-100;
  .pill-text { color: $warning-500; }
}
.pill--info {
  background: rgba($info-500, 0.12);
  .pill-text { color: $info-500; }
}
/* 突击中：主色描边 */
.pill--cramming {
  background: #ffffff;
  border: 1px solid $primary-500;
  .pill-text { color: $primary-500; }
}
</style>
