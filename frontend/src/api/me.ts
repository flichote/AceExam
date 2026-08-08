import type { MeSubjectsResponse, UserProfile } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockMeSubjects } from "@/mock/me";
import { mockPlaza } from "@/mock/subjects";

/**
 * M4 专业选课 / 我的课程 API（docs/api.md §13.1~13.3）
 *  - PUT /me/profile      更新专业（自由文本，1..100；空串 = 清除）
 *  - GET /me/subjects     用户自选课程列表（含每科学习状态聚合）
 *  - PUT /me/subjects     设置本学期课程（幂等全量覆盖；空数组 = 清空）
 */

export async function updateProfile(major: string): Promise<UserProfile> {
  return withFallback(
    () =>
      request<UserProfile>({
        url: "/me/profile",
        method: "PUT",
        data: { major },
      }),
    () => ({
      id: "mock-user",
      username: "期末选手",
      major,
      role: "student",
      is_member: false,
      member_expires_at: null,
      created_at: new Date().toISOString(),
    }),
    "服务暂不可用，已加载演示数据",
    { write: true } // PUT 写操作失败不降级 mock
  );
}

export async function fetchMeSubjects(): Promise<MeSubjectsResponse> {
  return withFallback(
    () => request<MeSubjectsResponse>({ url: "/me/subjects", method: "GET" }),
    () => mockMeSubjects()
  );
}

/** PUT /me/subjects：幂等覆盖（先删后插）；返回与 GET 同构 */
export async function updateMeSubjects(subjectIds: string[]): Promise<MeSubjectsResponse> {
  return withFallback(
    () =>
      request<MeSubjectsResponse>({
        url: "/me/subjects",
        method: "PUT",
        data: { subject_ids: subjectIds },
      }),
    // mock 降级：从广场数据里挑选对应课程作为「我的课程」
    () => {
      const { items } = mockMeSubjects();
      const kept = items.filter((it) => subjectIds.includes(it.subject.id));
      const plaza = mockPlaza().items.filter(
        (p) => subjectIds.includes(p.id) && !kept.some((k) => k.subject.id === p.id)
      );
      const joined: MeSubjectsResponse["items"] = [
        ...kept,
        ...plaza.map((p) => ({
          subject: {
            id: p.id,
            code: p.code,
            name: p.name,
            description: p.description,
            is_public: p.is_public,
            is_active: p.is_active,
          },
          joined_at: new Date().toISOString(),
          stats: {
            question_count: 0,
            correct_count: 0,
            accuracy: 0,
            mastery: 0,
            knowledge_points: { total: 0, mastered: 0, weak: 0 },
            streak: 0,
          },
        })),
      ];
      return { items: joined, total: joined.length };
    },
    "服务暂不可用，已加载演示数据",
    { write: true } // PUT 写操作失败不降级 mock
  );
}
