import type { ShareCardData } from "@/types";

/**
 * 分享卡数据 mock（docs/api.md §12.8）
 * TODO(ep-backend): GET /me/share-card 就绪后移除。
 * 口径：实时聚合（totals / recent_7d / streak / mastery / weak_points），
 * class / exam 演示非空（海报展示对应区块）。
 */

export function mockShareCard(): ShareCardData {
  return {
    username: "期末选手",
    generated_at: new Date().toISOString(),
    share_card_version: 1,
    totals: { questions_practiced: 1280, correct_count: 940, accuracy: 0.734 },
    recent_7d: { questions_practiced: 86, correct_count: 61, accuracy: 0.709 },
    streak: { current: 5, longest: 12 },
    mastery: {
      overall_pct: 0.321,
      best_subject: {
        subject_id: "subj-001",
        subject_name: "高等数学",
        mastery_pct: 0.42,
      },
    },
    weak_points: { weak: 6, consolidating: 4 },
    class: { id: "class-001", name: "计科2301" },
    exam: { subject_name: "高等数学", days_left: 7 },
  };
}
