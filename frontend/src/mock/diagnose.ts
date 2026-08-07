import type { SelfTestResult, DiagnosisReport, SelfTestQuestion } from "@/types";

/**
 * 摸底诊断 mock（docs/api.md §7）
 * TODO(ep-ai): POST /diagnose/self-test + /diagnose/report 就绪后移除，见 api/diagnose.ts
 */

function mockSelfTestQuestions(): SelfTestQuestion[] {
  return [
    {
      id: "mock-dg-q1",
      knowledge_point_id: "kp-lim",
      type: "single",
      content: "求极限 $\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x}$ 的值：",
      options: [
        { key: "A", text: "$0$" },
        { key: "B", text: "$1$" },
        { key: "C", text: "$\\infty$" },
        { key: "D", text: "不存在" },
      ],
      difficulty: 2,
    },
    {
      id: "mock-dg-q2",
      knowledge_point_id: "kp-deriv",
      type: "single",
      content: "设 $f(x) = x^2 e^x$，则 $f'(x) = $",
      options: [
        { key: "A", text: "$2x e^x$" },
        { key: "B", text: "$e^x(x^2+2x)$" },
        { key: "C", text: "$x^2 e^x + 1$" },
        { key: "D", text: "$2x e^x + x^2$" },
      ],
      difficulty: 3,
    },
    {
      id: "mock-dg-q3",
      knowledge_point_id: "kp-lhopital",
      type: "single",
      content: "用洛必达法则求 $\\lim\\limits_{x \\to 0} \\frac{1-\\cos x}{x^2}$：",
      options: [
        { key: "A", text: "$0$" },
        { key: "B", text: "$\\frac{1}{2}$" },
        { key: "C", text: "$1$" },
        { key: "D", text: "不存在" },
      ],
      difficulty: 3,
    },
    {
      id: "mock-dg-q4",
      knowledge_point_id: "kp-integral",
      type: "single",
      content: "计算 $\\int_0^1 x^2\\, dx$：",
      options: [
        { key: "A", text: "$\\frac{1}{3}$" },
        { key: "B", text: "$\\frac{1}{2}$" },
        { key: "C", text: "$1$" },
        { key: "D", text: "$\\frac{2}{3}$" },
      ],
      difficulty: 2,
    },
  ];
}

export function mockStartSelfTest(): SelfTestResult {
  return {
    report_id: `mock-report-${Date.now()}`,
    subject_id: "advanced-math",
    status: "in_progress",
    questions: mockSelfTestQuestions(),
    coverage: [
      { chapter_id: "ch1", chapter_name: "第1章 函数与极限", questions: 2 },
      { chapter_id: "ch2", chapter_name: "第2章 导数与微分", questions: 2 },
    ],
  };
}

export function mockDiagnosisReport(): DiagnosisReport {
  return {
    report_id: `mock-report-${Date.now()}`,
    status: "completed",
    summary: "整体掌握度中等偏下，薄弱集中在洛必达法则与导数应用，建议按薄弱点优先补练。",
    weak_top5: [
      {
        rank: 1,
        knowledge_point_id: "kp-lhopital",
        knowledge_point_name: "洛必达法则",
        level: 3,
        accuracy: 0.25,
        practice_count: 8,
        status: "weak",
        suggestion: "优先补练：每天 2 道洛必达计算题，配合教材第 3 章例题",
      },
      {
        rank: 2,
        knowledge_point_id: "kp-integral",
        knowledge_point_name: "定积分",
        level: 3,
        accuracy: 0.4,
        practice_count: 12,
        status: "weak",
        suggestion: "复习牛顿-莱布尼茨公式，先做基础计算题再上综合题",
      },
      {
        rank: 3,
        knowledge_point_id: "kp-deriv",
        knowledge_point_name: "导数",
        level: 2,
        accuracy: 0.55,
        practice_count: 15,
        status: "consolidating",
        suggestion: "掌握乘积/复合求导法则，注意链式法则不遗漏",
      },
    ],
    strengths: [
      { knowledge_point_name: "求导基本法则", accuracy: 0.9 },
      { knowledge_point_name: "连续性与间断点", accuracy: 0.85 },
    ],
    not_started: [{ knowledge_point_name: "定积分应用", level: 3 }],
    suggested_next_steps: [
      "先完成今日计划中薄弱点任务",
      "周末做一次第 3 章小测",
      "把洛必达法则的 3 道错题重做一遍",
    ],
  };
}
