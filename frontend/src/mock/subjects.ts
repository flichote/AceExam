import type { Subject } from "@/types";

/**
 * 科目 mock 数据
 * TODO(ep-backend): GET /api/v1/subjects 就绪后移除本文件引用（见 api/subjects.ts）
 */
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
