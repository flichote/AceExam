import type {
  CourseAliasItem,
  CourseMatchResponse,
  CreateCoursePayload,
  CreateCourseResult,
} from "@/types";

/**
 * M5 课程归一对齐 mock（docs/api.md §14.1~14.3）
 * TODO(ep-backend): GET /courses/aliases、POST /courses/match、POST /me/courses 就绪后移除
 *
 * 种子别名与后端 T29 种子一致：高数/英语/线代/概率论/大物 → 模板公共课。
 * mockCourseMatch 覆盖 D21 三档阈值：≥0.85 自动 / 0.60~0.85 候选 / <0.60 未匹配。
 */

/** 种子别名表（source=seed, is_verified=true），与 docs/architecture.md §14.5 对齐 */
const ALIAS_SEED: CourseAliasItem[] = [
  { alias: "高等数学", template_subject_id: "advanced-math", template_name: "高等数学", template_code: "math_gaoshu", source: "seed", is_verified: true },
  { alias: "高等数学A", template_subject_id: "advanced-math", template_name: "高等数学", template_code: "math_gaoshu", source: "seed", is_verified: true },
  { alias: "高数A", template_subject_id: "advanced-math", template_name: "高等数学", template_code: "math_gaoshu", source: "seed", is_verified: true },
  { alias: "高数上", template_subject_id: "advanced-math", template_name: "高等数学", template_code: "math_gaoshu", source: "seed", is_verified: true },
  { alias: "高等数学（上）", template_subject_id: "advanced-math", template_name: "高等数学", template_code: "math_gaoshu", source: "seed", is_verified: true },
  { alias: "大学英语", template_subject_id: "english", template_name: "大学英语", template_code: "eng_college", source: "seed", is_verified: true },
  { alias: "英语", template_subject_id: "english", template_name: "大学英语", template_code: "eng_college", source: "seed", is_verified: true },
  { alias: "大学英语综合", template_subject_id: "english", template_name: "大学英语", template_code: "eng_college", source: "seed", is_verified: true },
  { alias: "线性代数", template_subject_id: "linear-algebra", template_name: "线性代数", template_code: "math_linear", source: "seed", is_verified: true },
  { alias: "线代", template_subject_id: "linear-algebra", template_name: "线性代数", template_code: "math_linear", source: "seed", is_verified: true },
  { alias: "概率论与数理统计", template_subject_id: "probability", template_name: "概率论与数理统计", template_code: "math_probability", source: "seed", is_verified: true },
  { alias: "概率论", template_subject_id: "probability", template_name: "概率论与数理统计", template_code: "math_probability", source: "seed", is_verified: true },
  { alias: "大学物理", template_subject_id: "physics", template_name: "大学物理", template_code: "phy_college", source: "seed", is_verified: true },
  { alias: "大物", template_subject_id: "physics", template_name: "大学物理", template_code: "phy_college", source: "seed", is_verified: true },
];

/** 归一化：去学期/年份/括号/空白噪声（对齐 api.md §14.2 应用层归一化） */
function normalize(name: string): string {
  return name
    .replace(/[（(].*?[)）]/g, "")
    .replace(/\d{4}\s*(春|秋)?/g, "")
    .replace(/学期|课程|班|(上|下)$/g, "")
    .replace(/\s+/g, "")
    .trim();
}

export function mockCourseAliases(q = ""): CourseAliasItem[] {
  const needle = normalize(q);
  if (!needle) return ALIAS_SEED;
  return ALIAS_SEED.filter((a) => normalize(a.alias).includes(needle));
}

export function mockCourseMatch(payload: {
  name: string;
  school?: string;
  textbook?: string;
  limit?: number;
}): CourseMatchResponse {
  const key = normalize(payload.name || "");

  const aliasHit = ALIAS_SEED.find((a) => normalize(a.alias) === key);
  if (aliasHit) {
    // ① 别名精确命中 → strategy=alias，confidence=1.0，仅 1 条候选（§14.2 语义）
    return {
      matched: true,
      strategy: "alias",
      candidates: [
        {
          template_subject_id: aliasHit.template_subject_id,
          name: aliasHit.template_name,
          code: aliasHit.template_code,
          confidence: 1.0,
          reason: `别名精确命中：${aliasHit.alias}`,
          source: "alias",
        },
      ],
    };
  }

  // ② AI 语义匹配（模拟）：关键词 → 高置信；模糊 → 中置信候选；未知 → 未匹配
  const contains = (words: string[]) => words.some((w) => key.includes(w));
  if (contains(["高数", "高等数学", "微积分", "数学"])) {
    return {
      matched: true,
      strategy: "ai",
      candidates: [
        {
          template_subject_id: "advanced-math",
          name: "高等数学",
          code: "math_gaoshu",
          confidence: 0.92,
          reason: "语义匹配：课程名高度相似（教材版本待确认）",
          source: "ai",
        },
        {
          template_subject_id: "linear-algebra",
          name: "线性代数",
          code: "math_linear",
          confidence: 0.62,
          reason: "同属数学公共课，名称含「数学」",
          source: "ai",
        },
      ],
    };
  }
  if (contains(["英语", "英文"])) {
    return {
      matched: true,
      strategy: "ai",
      candidates: [
        {
          template_subject_id: "english",
          name: "大学英语",
          code: "eng_college",
          confidence: 0.95,
          reason: "语义匹配：外语公共课",
          source: "ai",
        },
      ],
    };
  }
  if (contains(["线代", "线性代数", "矩阵"])) {
    return {
      matched: true,
      strategy: "ai",
      candidates: [
        {
          template_subject_id: "linear-algebra",
          name: "线性代数",
          code: "math_linear",
          confidence: 0.88,
          reason: "语义匹配：线性代数课程",
          source: "ai",
        },
      ],
    };
  }
  if (contains(["概率", "统计"])) {
    return {
      matched: true,
      strategy: "ai",
      candidates: [
        {
          template_subject_id: "probability",
          name: "概率论与数理统计",
          code: "math_probability",
          confidence: 0.86,
          reason: "语义匹配：概率统计课程",
          source: "ai",
        },
      ],
    };
  }
  if (contains(["物理", "大学物理"])) {
    return {
      matched: true,
      strategy: "ai",
      candidates: [
        {
          template_subject_id: "physics",
          name: "大学物理",
          code: "phy_college",
          confidence: 0.9,
          reason: "语义匹配：物理公共课",
          source: "ai",
        },
      ],
    };
  }
  if (contains(["数据结构", "C语言", "程序设计", "计算机"])) {
    // ③ 中置信候选：0.60~0.85，前端展示候选列表供用户选择
    return {
      matched: true,
      strategy: "ai",
      candidates: [
        {
          template_subject_id: "advanced-math",
          name: "高等数学",
          code: "math_gaoshu",
          confidence: 0.66,
          reason: "专业基础课常见公共数学关联",
          source: "ai",
        },
        {
          template_subject_id: "english",
          name: "大学英语",
          code: "eng_college",
          confidence: 0.61,
          reason: "专业基础课外语学分关联",
          source: "ai",
        },
      ],
    };
  }

  // ④ 未匹配：<0.60，引导手动建实例 / 手动指定模板
  return {
    matched: false,
    strategy: "ai",
    candidates: [
      {
        template_subject_id: "advanced-math",
        name: "高等数学",
        code: "math_gaoshu",
        confidence: 0.42,
        reason: "置信度过低，建议手动确认模板",
        source: "ai",
      },
    ],
  };
}

let mockCreateSeq = 0;
export function mockCreateCourse(payload: CreateCoursePayload): CreateCourseResult {
  mockCreateSeq += 1;
  const id = payload.template_subject_id || `school-${Date.now().toString(36)}`;
  return {
    user_subject: {
      user_id: "mock-user",
      subject_id: id,
      template_subject_id: payload.template_subject_id ?? null,
      created_at: new Date().toISOString(),
    },
    subject: {
      id,
      code: payload.template_subject_id ? "template" : `school_${Date.now().toString(36).slice(0, 8)}`,
      name: payload.name.trim(),
      description: payload.school ? `${payload.school}校本课程` : "校本课程",
      is_public: false,
      is_active: true,
    },
    matched: !!payload.template_subject_id,
  };
}
