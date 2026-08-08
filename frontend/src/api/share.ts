import type { ShareCardData } from "@/types";
import { request, USE_MOCK, withFallback } from "@/utils/request";
import { mockShareCard } from "@/mock/share";

/**
 * 成绩单海报数据 API（docs/api.md §12.8）
 *  - GET /me/share-card  分享卡数据聚合（前端 canvas 生成海报，后端只聚合）
 */

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function fetchShareCard(): Promise<ShareCardData> {
  if (USE_MOCK) {
    await delay(400);
    return mockShareCard();
  }
  return withFallback(
    () => request<ShareCardData>({ url: "/me/share-card", method: "GET" }),
    () => mockShareCard()
  );
}
