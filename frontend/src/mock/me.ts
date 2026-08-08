import type { MeSubjectsResponse } from "@/types";

/**
 * M4 我的课程 mock（docs/api.md §13.3）
 * TODO(ep-backend): PUT /me/profile、PUT/GET /me/subjects 就绪后移除
 */

/** 我的课程（GET /me/subjects mock：已加入 高数 + 英语） */
export function mockMeSubjects(): MeSubjectsResponse {
  return {
    items: [
      {
        subject: {
          id: "advanced-math",
          code: "math_gaoshu",
          name: "高等数学（上）",
          description: "函数极限、导数与微分、定积分与不定积分",
          is_public: true,
          is_active: true,
        },
        joined_at: "2026-08-08T10:00:00Z",
        stats: {
          question_count: 128,
          correct_count: 76,
          accuracy: 0.594,
          mastery: 0.59,
          knowledge_points: { total: 18, mastered: 8, weak: 3 },
          streak: 7,
        },
      },
      {
        subject: {
          id: "english",
          code: "eng_college",
          name: "大学英语（四）",
          description: "词汇、阅读理解、翻译与写作",
          is_public: true,
          is_active: true,
        },
        joined_at: "2026-08-06T09:00:00Z",
        stats: {
          question_count: 201,
          correct_count: 145,
          accuracy: 0.721,
          mastery: 0.72,
          knowledge_points: { total: 22, mastered: 13, weak: 1 },
          streak: 7,
        },
      },
    ],
    total: 2,
  };
}
