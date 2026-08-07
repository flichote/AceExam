import type { Question } from "@/types";

/**
 * 题目 mock 库（高数题含 KaTeX 公式；英语题验证无公式渲染）
 * TODO(ep-backend): GET /api/v1/subjects/{id}/questions 就绪后移除
 */
export function mockQuestions(): Question[] {
  return [
    {
      id: "am-q001",
      subjectId: "advanced-math",
      type: "single",
      knowledgePoint: "极限",
      difficulty: 2,
      stem: "求极限 $\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x}$ 的值：",
      options: [
        { key: "A", text: "$0$" },
        { key: "B", text: "$1$" },
        { key: "C", text: "$\\infty$" },
        { key: "D", text: "不存在" },
      ],
      answer: ["B"],
      explanation:
        "这是第一个重要极限。当 $x \\to 0$ 时，$\\frac{\\sin x}{x} \\to 1$。\n\n证明思路（夹逼定理）：在单位圆内，$\\sin x < x < \\tan x$（$0<x<\\frac{\\pi}{2}$），于是 $\\cos x < \\frac{\\sin x}{x} < 1$，由夹逼定理取极限得 $\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x} = 1$。",
      citations: [
        {
          source: "同济《高等数学》第七版",
          chapter: "第一章 函数与极限 · 第六节 极限存在准则",
          snippet: "准则Ⅰ（夹逼准则）…由此可证 lim(x→0) sinx/x = 1，称为第一个重要极限。",
        },
      ],
    },
    {
      id: "am-q002",
      subjectId: "advanced-math",
      type: "single",
      knowledgePoint: "导数",
      difficulty: 3,
      stem: "设 $f(x) = x^2 e^x$，则 $f'(x) =$",
      options: [
        { key: "A", text: "$2x e^x$" },
        { key: "B", text: "$e^x (x^2 + 2x)$" },
        { key: "C", text: "$x^2 e^x + 1$" },
        { key: "D", text: "$2x e^x + x^2$" },
      ],
      answer: ["B"],
      explanation:
        "使用乘积求导法则：$(uv)' = u'v + uv'$。\n\n令 $u = x^2$，$v = e^x$，则 $u' = 2x$，$v' = e^x$，因此\n$$f'(x) = 2x \\cdot e^x + x^2 \\cdot e^x = e^x (x^2 + 2x)$$",
      citations: [
        {
          source: "同济《高等数学》第七版",
          chapter: "第二章 导数与微分 · 第二节 函数的求导法则",
          snippet: "两个函数乘积的导数等于第一个函数的导数乘第二个函数，再加上第一个函数乘第二个函数的导数。",
        },
      ],
    },
    {
      id: "am-q003",
      subjectId: "advanced-math",
      type: "single",
      knowledgePoint: "定积分",
      difficulty: 2,
      stem: "计算定积分 $\\int_0^1 x^2 \\, dx$ 的值：",
      options: [
        { key: "A", text: "$\\frac{1}{3}$" },
        { key: "B", text: "$\\frac{1}{2}$" },
        { key: "C", text: "$1$" },
        { key: "D", text: "$\\frac{2}{3}$" },
      ],
      answer: ["A"],
      explanation:
        "由微积分基本定理（牛顿-莱布尼茨公式）：$\\int_a^b f(x)\\,dx = F(b) - F(a)$，其中 $F$ 是 $f$ 的一个原函数。\n\n$x^2$ 的一个原函数为 $\\frac{x^3}{3}$，所以\n$$\\int_0^1 x^2 \\, dx = \\left[\\frac{x^3}{3}\\right]_0^1 = \\frac{1}{3} - 0 = \\frac{1}{3}$$",
      citations: [
        {
          source: "同济《高等数学》第七版",
          chapter: "第五章 定积分 · 第二节 微积分基本公式",
          snippet: "牛顿-莱布尼茨公式：∫ₐᵇ f(x)dx = F(b) − F(a)。",
        },
      ],
    },
    {
      id: "am-q004",
      subjectId: "advanced-math",
      type: "multiple",
      knowledgePoint: "连续性",
      difficulty: 3,
      stem: "下列函数中，在 $x = 0$ 处连续的有（多选）：",
      options: [
        { key: "A", text: "$f(x) = \\sin x$" },
        { key: "B", text: "$f(x) = \\frac{\\sin x}{x}$（补充定义 $f(0)=1$）" },
        { key: "C", text: "$f(x) = \\begin{cases} x, & x \\neq 0 \\\\ 1, & x = 0 \\end{cases}$" },
        { key: "D", text: "$f(x) = e^x$" },
      ],
      answer: ["A", "B", "D"],
      explanation:
        "连续的三要素：① $f(0)$ 有定义；② $\\lim\\limits_{x \\to 0} f(x)$ 存在；③ 两者相等。\n\n- A：$\\sin x$ 在 $0$ 处有定义且 $\\lim\\limits_{x\\to0}\\sin x = 0 = \\sin 0$ ✅\n- B：补充定义后 $\\lim\\limits_{x\\to0} \\frac{\\sin x}{x} = 1 = f(0)$ ✅\n- C：$\\lim\\limits_{x\\to0} f(x) = 0$，但 $f(0) = 1$，极限值 ≠ 函数值 ❌（可去间断点）\n- D：$e^x$ 处处连续 ✅",
    },
    {
      id: "en-q001",
      subjectId: "english",
      type: "single",
      knowledgePoint: "词汇",
      difficulty: 2,
      stem: "The professor's lecture was so ______ that every student took detailed notes.",
      options: [
        { key: "A", text: "insightful" },
        { key: "B", text: "ambiguous" },
        { key: "C", text: "tedious" },
        { key: "D", text: "superficial" },
      ],
      answer: ["A"],
      explanation:
        "句意：教授的讲座很有洞见，每个学生都做了详细笔记。\n\n- insightful 富有洞见的（符合语境）\n- ambiguous 含糊的\n- tedious 冗长乏味的\n- superficial 肤浅的",
    },
    {
      id: "en-q002",
      subjectId: "english",
      type: "single",
      knowledgePoint: "阅读理解",
      difficulty: 3,
      stem: "According to the passage, the main reason students procrastinate is ______.",
      options: [
        { key: "A", text: "a lack of time management skills" },
        { key: "B", text: "fear of failure and perfectionism" },
        { key: "C", text: "too many extracurricular activities" },
        { key: "D", text: "poor physical health" },
      ],
      answer: ["B"],
      explanation:
        "原文指出：拖延的核心心理机制是回避失败带来的负面情绪，与完美主义高度相关（fear of failure and perfectionism）。",
    },
    {
      id: "la-q001",
      subjectId: "linear-algebra",
      type: "single",
      knowledgePoint: "行列式",
      difficulty: 3,
      stem: "已知 $A$ 为 3 阶矩阵，$|A| = 2$，则 $|2A| = $",
      options: [
        { key: "A", text: "$4$" },
        { key: "B", text: "$8$" },
        { key: "C", text: "$16$" },
        { key: "D", text: "$2$" },
      ],
      answer: ["C"],
      explanation:
        "对 $n$ 阶矩阵有 $|kA| = k^n |A|$。这里 $n = 3$，$k = 2$：\n$$|2A| = 2^3 \\times 2 = 8 \\times 2 = 16$$",
    },
  ];
}
