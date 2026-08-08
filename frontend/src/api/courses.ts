import type {
  CourseAliasItem,
  CourseMatchResponse,
  CreateCoursePayload,
  CreateCourseResult,
} from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockCourseAliases, mockCourseMatch, mockCreateCourse } from "@/mock/courses";

/**
 * M5 课程归一对齐 API（docs/api.md §14.1~14.3）
 *  - GET /courses/aliases   别名联想（录入时输入联想 / 广场搜索）
 *  - POST /courses/match    校本课程名 → 模板课程匹配（AI 候选 + 置信度，D21 阈值）
 *  - POST /me/courses       录入校本课程实例（映射模板或手动建实例）
 *
 * 阈值约定（D21）：confidence ≥ 0.85 自动采用 top1；0.60~0.85 展示候选列表；
 * < 0.60 或空候选 → matched=false，引导「手动建实例」/「手动指定模板」。
 */

/** GET /courses/aliases：q 为空返回 verified 别名种子；有 q 时归一化包含匹配 */
export async function fetchCourseAliases(
  q = "",
  limit = 10,
  templateSubjectId?: string
): Promise<CourseAliasItem[]> {
  const data: Record<string, unknown> = { q, limit };
  if (templateSubjectId) data.template_subject_id = templateSubjectId;
  return withFallback(
    () =>
      request<{ items: CourseAliasItem[]; total: number }>({
        url: "/courses/aliases",
        method: "GET",
        data,
      }).then((r) => r.items),
    () => mockCourseAliases(q)
  );
}

/** POST /courses/match：校本课程名 → 模板候选（AI 计算，网络失败可降级演示） */
export async function matchCourse(payload: {
  name: string;
  school?: string;
  textbook?: string;
  limit?: number;
}): Promise<CourseMatchResponse> {
  return withFallback(
    () =>
      request<CourseMatchResponse>({
        url: "/courses/match",
        method: "POST",
        data: payload,
      }),
    () => mockCourseMatch(payload)
  );
}

/** POST /me/courses：写操作，失败不降级 mock（409 ALREADY_EXISTS 如实抛出） */
export async function createMyCourse(
  payload: CreateCoursePayload
): Promise<CreateCourseResult> {
  return withFallback(
    () =>
      request<CreateCourseResult>({
        url: "/me/courses",
        method: "POST",
        data: { ...payload },
      }),
    () => mockCreateCourse(payload),
    "服务暂不可用，已加载演示数据",
    { write: true }
  );
}
