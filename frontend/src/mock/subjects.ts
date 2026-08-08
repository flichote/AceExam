import type { Subject, PlazaResponse } from "@/types";

/**
 * 科目 mock 数据
 * TODO(ep-backend): GET /api/v1/subjects 就绪后移除本文件引用（见 api/subjects.ts）
 */

/** 课程广场 mock（docs/api.md §13.4：is_public=true 的公共课） */
export function mockPlaza(): PlazaResponse {
  return {
    items: [
      {
        id: "advanced-math",
        code: "math_gaoshu",
        name: "高等数学（上）",
        description: "函数极限、导数与微分、定积分与不定积分",
        is_public: true,
        is_active: true,
        joined: true,
        question_count: 216,
      },
      {
        id: "english",
        code: "eng_college",
        name: "大学英语（四）",
        description: "词汇、阅读理解、翻译与写作",
        is_public: true,
        is_active: true,
        joined: true,
        question_count: 280,
      },
      {
        id: "linear-algebra",
        code: "math_linear",
        name: "线性代数",
        description: "行列式、矩阵、线性方程组与特征值",
        is_public: true,
        is_active: true,
        joined: false,
        question_count: 90,
      },
      {
        id: "probability",
        code: "math_probability",
        name: "概率论与数理统计",
        description: "随机事件、随机变量、数字特征与数理统计",
        is_public: true,
        is_active: true,
        joined: false,
        question_count: 64,
      },
      {
        id: "physics",
        code: "phy_college",
        name: "大学物理",
        description: "力学、电磁学、波动与光学",
        is_public: true,
        is_active: true,
        joined: false,
        question_count: 0, // 建设中：题量为 0，前端降级展示
      },
    ],
    total: 5,
  };
}

export function mockSubjects(): Subject[] {
  const today = new Date();
  const daysFromNow = (n: number) => {
    const d = new Date(today.getTime() + n * 86400000);
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${mm}-${dd}`;
  };

  return [
    {
      id: "advanced-math",
      name: "高等数学（上）",
      emoji: "📐",
      examDate: daysFromNow(45),
      examCountdown: 45,
      mastery: { mastered: 128, total: 216, percent: 59 },
      status: "consolidating", // 待巩固
      todayTask: { done: 3, total: 5 },
      streak: 7,
    },
    {
      id: "english",
      name: "大学英语（四）",
      emoji: "🇬🇧",
      examDate: daysFromNow(41),
      examCountdown: 41,
      mastery: { mastered: 201, total: 280, percent: 72 },
      status: "mastered", // 已掌握
      todayTask: { done: 1, total: 4 },
      streak: 7,
    },
    {
      id: "linear-algebra",
      name: "线性代数",
      emoji: "🧮",
      examDate: daysFromNow(52),
      examCountdown: 52,
      mastery: { mastered: 34, total: 90, percent: 38 },
      status: "weak", // 薄弱
      todayTask: { done: 0, total: 6 },
      streak: 2,
    },
  ];
}
