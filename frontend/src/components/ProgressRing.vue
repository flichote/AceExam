<template>
  <view class="ring" :style="wrapStyle">
    <!-- #ifdef H5 -->
    <view class="ring-track ring-track--h5" :style="ringStyle" />
    <!-- #endif -->
    <!-- #ifndef H5 -->
    <!-- TODO(前端): 小程序端进度环待 canvas 实现（400ms ease-out 动效），当前为占位环 -->
    <view class="ring-track ring-track--fallback" :style="fallbackStyle" />
    <!-- #endif -->
    <view class="ring-hole" :style="holeStyle">
      <text class="ring-percent" :style="textStyle">{{ percent }}%</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    /** 0-100 */
    percent: number;
    /** px */
    size?: number;
    /** px */
    strokeWidth?: number;
    /** 进度色，默认主色 $primary-500 */
    color?: string;
    /** 轨道色，默认 $neutral-100 */
    trackColor?: string;
  }>(),
  {
    percent: 0,
    size: 72,
    strokeWidth: 6,
    color: "#F59E0B", // = $primary-500
    trackColor: "#F3F4F6", // = $neutral-100
  }
);

const clamped = computed(() => Math.max(0, Math.min(100, props.percent)));

const wrapStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
}));

// H5：conic-gradient 环形进度
const ringStyle = computed(() => ({
  background: `conic-gradient(${props.color} ${clamped.value * 3.6}deg, ${props.trackColor} 0deg)`,
}));

const fallbackStyle = computed(() => ({
  background: props.trackColor,
  border: `${props.strokeWidth}px solid ${props.color}`,
  opacity: 0.85,
}));

const holeStyle = computed(() => ({
  top: `${props.strokeWidth}px`,
  left: `${props.strokeWidth}px`,
  width: `${props.size - props.strokeWidth * 2}px`,
  height: `${props.size - props.strokeWidth * 2}px`,
}));

const textStyle = computed(() => ({
  fontSize: `${Math.round(props.size * 0.24)}px`,
}));
</script>

<style lang="scss">
.ring {
  position: relative;
  flex-shrink: 0;
}
.ring-track {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
}
.ring-hole {
  position: absolute;
  border-radius: 50%;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ring-percent {
  color: $neutral-500;
  font-weight: 600;
}
</style>
