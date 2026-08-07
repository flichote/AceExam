import type { WarningsResponse } from "@/types";

/**
 * 挂科预警 mock（docs/api.md §11.7）
 * TODO(ep-backend): GET /me/warnings 就绪后移除
 * 等级由规则层确定性计算；suggestion 为 LLM 措辞（mock 用固定文案）。
 */

export function mockWarnings(): WarningsResponse {
  return {
    overall_risk: "high",
    items: [
      {
        knowledge_point_id: "kp-lhopital",
        knowledge_point_name: "洛必达法则",
        risk_level: "high",
        reasons: ["正确率仅 20%（练习 5 次）", "距考试仅 7 天", "近 3 天未做题"],
        suggestion: "每天 2 道洛必达计算题，配合教材第 3 章例题；今晚先做一次 10 题小测",
        days_left: 7,
        accuracy: 0.2,
        practice_count: 5,
      },
      {
        knowledge_point_id: "kp-deriv-chain",
        knowledge_point_name: "链式法则",
        risk_level: "medium",
        reasons: ["正确率 33%（练习 6 次）", "距考试仅 7 天"],
        suggestion: "先回顾复合函数求导口诀，再练 5 道链式法则题",
        days_left: 7,
        accuracy: 0.33,
        practice_count: 6,
      },
      {
        knowledge_point_id: "kp-int-parts",
        knowledge_point_name: "分部积分法",
        risk_level: "medium",
        reasons: ["正确率 55%（练习 7 次）"],
        suggestion: "记住「反对幂指三」选 u 顺序，分步练习 4 道题",
        days_left: 7,
        accuracy: 0.55,
        practice_count: 7,
      },
    ],
    generated_at: new Date().toISOString(),
  };
}
