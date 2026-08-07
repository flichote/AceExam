import type { Subject } from "@/types";
import { request, USE_MOCK } from "@/utils/request";
import { mockSubjects } from "@/mock/subjects";

/**
 * 科目 API
 * 对接点：GET /api/v1/subjects（docs/architecture.md）
 */
export async function fetchSubjects(): Promise<Subject[]> {
  // TODO(ep-backend): 后端就绪后 USE_MOCK 置 false，走真实接口
  if (USE_MOCK) {
    return mockSubjects();
  }
  const data = await request<Subject[]>({
    url: "/subjects",
    method: "GET",
  });
  return data;
}
