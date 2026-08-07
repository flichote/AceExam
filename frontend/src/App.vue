<script setup lang="ts">
import { onLaunch } from "@dcloudio/uni-app";

onLaunch(() => {
  // TODO(ep-backend): 登录态恢复（M3）——读取 token 并拉取用户信息
  console.log("[AceExam] App Launch");
});
</script>

<style lang="scss">
/* 全局基础样式：清爽学习风（docs/design/design-system.md） */
page {
  background-color: $neutral-100;
  color: $neutral-900;
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  font-size: $font-body;
  line-height: 1.6;
}

/* 通用卡片 */
.card {
  background: #ffffff;
  border-radius: $radius-card;
  box-shadow: $shadow-card;
}

/* 通用按钮 */
.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: $radius-btn;
  transition: transform 100ms ease, opacity 100ms ease;
}
.btn:active {
  transform: scale(0.97);
  opacity: 0.9;
}
.btn--primary {
  background: $primary-500;
}
.btn--primary:active {
  background: $primary-600;
}
.btn--disabled {
  opacity: 0.45;
  pointer-events: none;
}
</style>
