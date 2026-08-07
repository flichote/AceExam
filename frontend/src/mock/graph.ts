import type { GraphNode, KnowledgeGraphResponse } from "@/types";

/**
 * 知识点图谱 mock（docs/api.md §11.1）
 * TODO(ep-backend): GET /subjects/{id}/knowledge-graph 就绪后移除
 * 三级树：章(level=1) → 节(level=2) → 知识点(level=3)，父节点状态按子聚合。
 */

/** 章 1 极限与连续 */
const chapter1: GraphNode = {
  id: "ch1",
  name: "第1章 函数与极限",
  level: 1,
  status: "consolidating",
  question_count: 22,
  children: [
    {
      id: "ch1-s1",
      name: "1.1 函数",
      level: 2,
      status: "mastered",
      question_count: 6,
      children: [
        { id: "kp-func-basic", name: "函数概念", level: 3, status: "mastered", question_count: 3, practice_count: 9, accuracy: 0.89 },
        { id: "kp-func-compose", name: "复合函数", level: 3, status: "mastered", question_count: 3, practice_count: 7, accuracy: 0.86 },
      ],
    },
    {
      id: "ch1-s2",
      name: "1.2 极限",
      level: 2,
      status: "weak",
      question_count: 10,
      children: [
        { id: "kp-lim-basic", name: "极限概念", level: 3, status: "consolidating", question_count: 4, practice_count: 6, accuracy: 0.5 },
        { id: "kp-lim-sinx", name: "第一个重要极限", level: 3, status: "mastered", question_count: 3, practice_count: 8, accuracy: 0.88 },
        { id: "kp-lim-squeeze", name: "夹逼准则", level: 3, status: "weak", question_count: 3, practice_count: 5, accuracy: 0.2 },
      ],
    },
    {
      id: "ch1-s3",
      name: "1.3 连续",
      level: 2,
      status: "untouched",
      question_count: 6,
      children: [
        { id: "kp-cont-def", name: "连续性定义", level: 3, status: "untouched", question_count: 3, practice_count: 0, accuracy: null },
        { id: "kp-cont-removable", name: "间断点分类", level: 3, status: "untouched", question_count: 3, practice_count: 0, accuracy: null },
      ],
    },
  ],
};

/** 章 2 导数与微分 */
const chapter2: GraphNode = {
  id: "ch2",
  name: "第2章 导数与微分",
  level: 1,
  status: "weak",
  question_count: 37,
  children: [
    {
      id: "ch2-s1",
      name: "2.1 导数概念",
      level: 2,
      status: "mastered",
      question_count: 10,
      children: [
        { id: "kp-deriv-def", name: "导数定义", level: 3, status: "mastered", question_count: 5, practice_count: 12, accuracy: 0.92 },
        { id: "kp-deriv-geom", name: "导数的几何意义", level: 3, status: "mastered", question_count: 5, practice_count: 9, accuracy: 0.9 },
      ],
    },
    {
      id: "ch2-s2",
      name: "2.2 求导法则",
      level: 2,
      status: "weak",
      question_count: 15,
      children: [
        { id: "kp-deriv-product", name: "乘积求导", level: 3, status: "consolidating", question_count: 5, practice_count: 8, accuracy: 0.62 },
        { id: "kp-deriv-chain", name: "链式法则", level: 3, status: "weak", question_count: 5, practice_count: 6, accuracy: 0.33 },
        { id: "kp-deriv-implicit", name: "隐函数求导", level: 3, status: "weak", question_count: 5, practice_count: 4, accuracy: 0.25 },
      ],
    },
    {
      id: "ch2-s3",
      name: "2.3 微分",
      level: 2,
      status: "consolidating",
      question_count: 12,
      children: [
        { id: "kp-diff-def", name: "微分概念", level: 3, status: "consolidating", question_count: 5, practice_count: 7, accuracy: 0.57 },
        { id: "kp-lhopital", name: "洛必达法则", level: 3, status: "weak", question_count: 7, practice_count: 5, accuracy: 0.2 },
      ],
    },
  ],
};

/** 章 3 定积分 */
const chapter3: GraphNode = {
  id: "ch3",
  name: "第3章 定积分",
  level: 1,
  status: "mastered",
  question_count: 16,
  children: [
    {
      id: "ch3-s1",
      name: "3.1 定积分概念",
      level: 2,
      status: "mastered",
      question_count: 8,
      children: [
        { id: "kp-int-def", name: "定积分定义", level: 3, status: "mastered", question_count: 4, practice_count: 10, accuracy: 0.9 },
        { id: "kp-int-newton", name: "牛顿-莱布尼茨公式", level: 3, status: "mastered", question_count: 4, practice_count: 9, accuracy: 0.87 },
      ],
    },
    {
      id: "ch3-s2",
      name: "3.2 换元与分部",
      level: 2,
      status: "mastered",
      question_count: 8,
      children: [
        { id: "kp-int-subst", name: "换元积分法", level: 3, status: "mastered", question_count: 4, practice_count: 8, accuracy: 0.85 },
        { id: "kp-int-parts", name: "分部积分法", level: 3, status: "mastered", question_count: 4, practice_count: 6, accuracy: 0.83 },
      ],
    },
  ],
};

const graphBySubject: Record<string, { name: string; root: GraphNode }> = {
  "advanced-math": { name: "高等数学（上）", root: { ...chapter1, children: [chapter1, chapter2, chapter3] } },
  english: {
    name: "大学英语（四）",
    root: {
      id: "en-root",
      name: "大学英语（四）",
      level: 0,
      status: "consolidating",
      question_count: 40,
      children: [
        {
          id: "en-ch1",
          name: "词汇与语法",
          level: 1,
          status: "consolidating",
          question_count: 18,
          children: [
            { id: "en-s1", name: "高频词汇", level: 2, status: "weak", question_count: 10, children: [
              { id: "kp-vocab-core", name: "核心词汇 500", level: 3, status: "weak", question_count: 6, practice_count: 5, accuracy: 0.3 },
              { id: "kp-vocab-phrase", name: "固定搭配", level: 3, status: "consolidating", question_count: 4, practice_count: 7, accuracy: 0.55 },
            ] },
            { id: "en-s2", name: "语法点", level: 2, status: "mastered", question_count: 8, children: [
              { id: "kp-grammar-tense", name: "时态语态", level: 3, status: "mastered", question_count: 4, practice_count: 9, accuracy: 0.9 },
              { id: "kp-grammar-clause", name: "从句", level: 3, status: "mastered", question_count: 4, practice_count: 8, accuracy: 0.88 },
            ] },
          ],
        },
        {
          id: "en-ch2",
          name: "阅读理解",
          level: 1,
          status: "mastered",
          question_count: 22,
          children: [
            { id: "en-s3", name: "细节题", level: 2, status: "mastered", question_count: 12, children: [
              { id: "kp-read-detail", name: "细节定位", level: 3, status: "mastered", question_count: 12, practice_count: 15, accuracy: 0.93 },
            ] },
            { id: "en-s4", name: "主旨题", level: 2, status: "mastered", question_count: 10, children: [
              { id: "kp-read-main", name: "主旨归纳", level: 3, status: "mastered", question_count: 10, practice_count: 12, accuracy: 0.91 },
            ] },
          ],
        },
      ],
    },
  },
  "linear-algebra": {
    name: "线性代数",
    root: {
      id: "la-root",
      name: "线性代数",
      level: 0,
      status: "weak",
      question_count: 34,
      children: [
        {
          id: "la-ch1",
          name: "行列式",
          level: 1,
          status: "weak",
          question_count: 15,
          children: [
            { id: "la-s1", name: "行列式计算", level: 2, status: "weak", question_count: 10, children: [
              { id: "kp-det-def", name: "行列式定义", level: 3, status: "weak", question_count: 5, practice_count: 4, accuracy: 0.25 },
              { id: "kp-det-expand", name: "按行展开", level: 3, status: "weak", question_count: 5, practice_count: 3, accuracy: 0.2 },
            ] },
            { id: "la-s2", name: "克拉默法则", level: 2, status: "untouched", question_count: 5, children: [
              { id: "kp-cramer", name: "克拉默法则", level: 3, status: "untouched", question_count: 5, practice_count: 0, accuracy: null },
            ] },
          ],
        },
        {
          id: "la-ch2",
          name: "矩阵",
          level: 1,
          status: "consolidating",
          question_count: 19,
          children: [
            { id: "la-s3", name: "矩阵运算", level: 2, status: "consolidating", question_count: 10, children: [
              { id: "kp-matrix-mult", name: "矩阵乘法", level: 3, status: "consolidating", question_count: 5, practice_count: 6, accuracy: 0.6 },
              { id: "kp-matrix-inverse", name: "逆矩阵", level: 3, status: "consolidating", question_count: 5, practice_count: 5, accuracy: 0.65 },
            ] },
            { id: "la-s4", name: "秩", level: 2, status: "untouched", question_count: 9, children: [
              { id: "kp-rank", name: "矩阵的秩", level: 3, status: "untouched", question_count: 9, practice_count: 0, accuracy: null },
            ] },
          ],
        },
      ],
    },
  },
};

export function mockKnowledgeGraph(subjectId: string): KnowledgeGraphResponse {
  const entry = graphBySubject[subjectId] ?? graphBySubject["advanced-math"];
  const root = entry.root;

  // 统计：叶子状态计数（示例数据，真实由后端聚合）
  const leaves: GraphNode[] = [];
  const walk = (n: GraphNode) => {
    if (!n.children || n.children.length === 0) leaves.push(n);
    else n.children.forEach(walk);
  };
  walk(root);
  const count = (s: string) => leaves.filter((l) => l.status === s).length;

  return {
    subject_id: subjectId,
    subject_name: entry.name,
    generated_at: new Date().toISOString(),
    root,
    stats: {
      total_nodes: leaves.length + 8,
      leaf_count: leaves.length,
      mastered_count: count("mastered"),
      weak_count: count("weak"),
      consolidating_count: count("consolidating"),
      untouched_count: count("untouched"),
    },
  };
}
