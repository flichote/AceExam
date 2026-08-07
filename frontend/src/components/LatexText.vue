<template>
  <!-- #ifdef H5 || APP-PLUS -->
  <view class="latex-text" :style="styleStr" v-html="html"></view>
  <!-- #endif -->
  <!-- #ifdef MP-WEIXIN -->
  <!--
    TODO(前端): 小程序端公式渲染 —— 接入 mp-html 插件（components.md 公式约束：禁止图片代替公式）
    当前为纯文本兜底，保证内容可见；math 片段保留 $...$ 原文。
  -->
  <text class="latex-text" :style="styleStr" user-select>{{ text }}</text>
  <!-- #endif -->
</template>

<script setup lang="ts">
import { computed } from "vue";
import katex from "katex";

const props = withDefaults(
  defineProps<{
    /** 支持 $inline$ 与 $$display$$ 两种 LaTeX 语法 */
    text: string;
    fontSize?: string;
    color?: string;
  }>(),
  {
    text: "",
    fontSize: "15px",
    color: "#1F2937", // = $neutral-900
  }
);

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br/>");
}

/** 对已转义文本做极简 markdown：加粗 / 斜体 / 行内代码 */
function richText(s: string): string {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

function renderLatex(latex: string, display: boolean): string {
  try {
    const html = katex.renderToString(latex, {
      displayMode: display,
      throwOnError: false,
      output: "html",
    });
    return display ? `<div class="math-block">${html}</div>` : html;
  } catch {
    return escapeHtml(latex);
  }
}

/** 解析 $...$ / $$...$$，其余文本转义 */
function parse(text: string): string {
  let out = "";
  let i = 0;
  while (i < text.length) {
    const dollar = text.indexOf("$", i);
    if (dollar === -1) {
      out += richText(escapeHtml(text.slice(i)));
      break;
    }
    out += richText(escapeHtml(text.slice(i, dollar)));
    const display = text.startsWith("$$", dollar);
    const openLen = display ? 2 : 1;
    const closeToken = display ? "$$" : "$";
    const closeIdx = text.indexOf(closeToken, dollar + openLen);
    if (closeIdx === -1) {
      out += richText(escapeHtml(text.slice(dollar)));
      break;
    }
    const latex = text.slice(dollar + openLen, closeIdx);
    out += renderLatex(latex, display);
    i = closeIdx + openLen;
  }
  return out;
}

const html = computed(() => parse(props.text));
const styleStr = computed(() => `font-size:${props.fontSize};color:${props.color};`);
</script>

<style lang="scss">
/* #ifdef H5 || APP-PLUS */
@import "katex/dist/katex.min.css";
/* #endif */

.latex-text {
  display: block;
  line-height: 1.6;
  word-break: break-word;
}

/* #ifdef H5 || APP-PLUS */
.latex-text ::v-deep code {
  background: rgba($neutral-500, 0.12);
  border-radius: 4px;
  padding: 0 6px;
  font-size: 0.9em;
}

.latex-text ::v-deep .math-block {
  margin: 8px 0;
  text-align: center;
  overflow-x: auto;
}
/* #endif */
</style>
