import type { ChatExplainResult, ChatMessage, Citation, StepCard } from "@/types";

/**
 * AI 对话 mock：自由问答流式 + 题目分步讲解（docs/api.md §5）
 * TODO(ep-ai): POST /chat/explain + /chat/followup（SSE）就绪后移除，见 api/chat.ts
 */

/** 关键词 → 回复模板 */
function pickReply(text: string): string {
  const t = text.toLowerCase();
  if (t.includes("极限") || t.includes("sin") || t.includes("洛必达")) {
    return "这道极限题的关键是识别**重要极限**。\n\n先看 $\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x}$：当 $x \\to 0$ 时分子分母都趋于 0，属于 $\\frac{0}{0}$ 型，但不能直接代值。\n\n思路①（推荐）：**夹逼定理**。单位圆中 $\\sin x < x < \\tan x$，同除以 $\\sin x$ 得 $\\cos x < \\frac{x}{\\sin x} < 1$，取倒数再夹逼即得极限为 $1$。\n\n思路②：洛必达法则，分子分母分别求导：$\\lim\\limits_{x \\to 0} \\frac{\\cos x}{1} = 1$。\n\n记忆口诀：**「同阶替换，极限值就是系数比」**。这类题期末必考，务必练熟。";
  }
  if (t.includes("导数") || t.includes("求导") || t.includes("乘积")) {
    return "求导题先判断结构，再选法则。\n\n$f(x) = x^2 e^x$ 是**乘积结构**，用乘积法则：\n$$(uv)' = u'v + uv'$$\n\n代入 $u = x^2$（$u' = 2x$），$v = e^x$（$v' = e^x$）：\n$$f'(x) = 2x \\cdot e^x + x^2 \\cdot e^x = e^x(x^2 + 2x)$$\n\n易错点：别漏掉 $e^x$ 的链式法则（这里 $e^x$ 的导数就是自身）。\n\n你可以试着再算一遍，或者问我配套的**复合函数求导**题。";
  }
  if (t.includes("积分") || t.includes("定积分")) {
    return "定积分优先用**牛顿-莱布尼茨公式**：\n$$\\int_a^b f(x)\\,dx = F(b) - F(a)$$\n\n对 $\\int_0^1 x^2 \\, dx$：先找原函数 $F(x) = \\frac{x^3}{3}$，再代入上下限：\n$$\\int_0^1 x^2\\,dx = \\left[\\frac{x^3}{3}\\right]_0^1 = \\frac{1}{3} - 0 = \\frac{1}{3}$$\n\n如果被积函数是**偶函数**，还可以利用对称区间性质快速计算——这也是期末常考技巧。";
  }
  if (t.includes("单词") || t.includes("词汇") || t.includes("英语")) {
    return "背单词建议用**语境记忆**而不是孤立背词表：\n\n1. 把生词放进真题句子，结合搭配（collocation）记；\n2. 按**词根词缀**分组：如 -tion 名词后缀、in-/im- 否定前缀；\n3. 每天睡前用 10 分钟复习当天新词（间隔重复效果最好）。\n\n你刚做的那道题 insight 相关的词可以一起背：insight（洞见）、insightful（富有洞见的）、perceptive（敏锐的）。";
  }
  return "收到！这道题我建议这样入手：\n\n1. 先定位**考察的知识点**（极限/导数/积分/语法/词汇）；\n2. 回忆对应的**标准方法**，不要跳步；\n3. 做完后用**自己话复述一遍步骤**，能讲出来才算真的会。\n\n你可以把题目截图发我（拍照录题入口马上就来），或者直接告诉我是哪一章的内容，我给出 step-by-step 讲解。";
}

/** 教材引用（mock RAG 溯源，ADR-0003） */
const mockCitations: Citation[] = [
  {
    source: "同济《高等数学》第七版",
    chapter: "第一章 函数与极限 · 第六节 极限存在准则",
    section: "1.6.2 夹逼准则",
    page: "52",
    snippet: "准则Ⅰ（夹逼准则）：如果数列/函数满足 g(x) ≤ f(x) ≤ h(x) 且 lim g = lim h = A，则 lim f = A。",
    score: 0.91,
  },
];

/** 题目讲解分步（mock，模拟 SSE 的 step 事件序列） */
export function mockExplain(): ChatExplainResult {
  const steps: StepCard[] = [
    {
      title: "理解题意",
      content: "题目要求计算 $\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x}$。当 $x \\to 0$ 时分子分母均趋于 0，是 $\\frac{0}{0}$ 型未定式，不能直接代入。",
    },
    {
      title: "方法一：夹逼定理",
      content: "单位圆中 $\\sin x < x < \\tan x$（$0 < x < \\frac{\\pi}{2}$）。同除以 $\\sin x$ 得 $\\cos x < \\frac{x}{\\sin x} < 1$，取倒数：$1 < \\frac{\\sin x}{x} < \\frac{1}{\\cos x}$。由夹逼定理，$\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x} = 1$。",
    },
    {
      title: "方法二：洛必达法则",
      content: "$\\frac{0}{0}$ 型可直接洛必达：分子分母分别求导 $\\lim\\limits_{x \\to 0} \\frac{\\cos x}{1} = \\cos 0 = 1$。",
    },
    {
      title: "易错提醒",
      content: "⚠️ 该极限是**第一个重要极限**，可直接作为结论使用；但不能把 $x \\to \\infty$ 下的 $\\frac{\\sin x}{x}$ 混为一谈（后者极限为 0）。",
    },
  ];
  return {
    session_id: `mock-session-${Date.now()}`,
    steps,
    conclusion: "综上，$\\lim\\limits_{x \\to 0} \\frac{\\sin x}{x} = 1$（第一个重要极限）。",
    citations: mockCitations,
    uncovered: false,
    model: "pro",
  };
}

/** 追问回复（mock，基于会话上下文关键词） */
export function mockFollowup(message: string): ChatExplainResult {
  const steps: StepCard[] = [
    {
      title: "针对追问",
      content: `关于「${message}」，核心是回到定义：`,
    },
    {
      title: "补充说明",
      content: "夹逼定理要求两边极限存在且相等；洛必达要求分子分母可导且分母导数不为 0。两者都能得到同一结论，选择更熟练的方法即可。",
    },
  ];
  return {
    session_id: `mock-session-${Date.now()}`,
    steps,
    conclusion: "还有不清楚的地方可以继续追问，我会基于教材再展开。",
    citations: mockCitations,
    uncovered: false,
    model: "pro",
  };
}

/**
 * 模拟 SSE 流式输出：按块回调。
 * @param messages 当前对话上下文
 * @param onChunk 每收到一个文本块回调一次
 */
export function mockStreamReply(
  messages: ChatMessage[],
  onChunk: (chunk: string) => void
): Promise<void> {
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const full = pickReply(lastUser?.content ?? "");

  // 把回复切块，模拟网络流
  const chunks: string[] = [];
  let i = 0;
  while (i < full.length) {
    const size = 4 + Math.floor(Math.random() * 8); // 4~12 字符一块
    chunks.push(full.slice(i, i + size));
    i += size;
  }

  return new Promise((resolve) => {
    let idx = 0;
    const timer = setInterval(() => {
      if (idx >= chunks.length) {
        clearInterval(timer);
        resolve();
        return;
      }
      onChunk(chunks[idx]);
      idx += 1;
    }, 90);
  });
}

export { mockCitations };
