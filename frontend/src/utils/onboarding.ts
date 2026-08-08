/**
 * 选课引导状态（M4：docs/api.md §13 / architecture.md §13.3）
 *
 * 「跳过/完成」都会标记 onboarded，避免每次进首页重复弹引导；
 * 用户随时可从「我的」页进入引导页修改专业/课程。
 */

const ONBOARDED_KEY = "aceexam_onboarded";

export function isOnboarded(): boolean {
  return !!uni.getStorageSync(ONBOARDED_KEY);
}

export function markOnboarded() {
  uni.setStorageSync(ONBOARDED_KEY, "1");
}
