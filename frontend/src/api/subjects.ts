import type { Subject, KnowledgePointHit, PlazaResponse } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockSubjects, mockPlaza } from "@/mock/subjects";

/**
 * 科目 API（docs/api.md §2 / §13.4）
 *  - GET /subjects（公开）
 *  - GET /subjects/{subject_id}/knowledge-points（知识点列表，刷题页标签映射用）
 *  - GET /subjects/plaza（课程广场，游客白名单：未登录 joined=false）
 */

export async function fetchSubjects(): Promise<Subject[]> {
  return withFallback(
    () => request<Subject[]>({ url: "/subjects", method: "GET", auth: false }),
    () => mockSubjects()
  );
}

/** 课程广场（§13.4）：is_public=true 的公共课 + 当前用户 joined 状态 */
export async function fetchPlazaSubjects(): Promise<PlazaResponse> {
  return withFallback(
    () => request<PlazaResponse>({ url: "/subjects/plaza", method: "GET", auth: false }),
    () => mockPlaza()
  );
}

export interface KnowledgePoint {
  id: string;
  name: string;
  parent_id?: string | null;
  level?: number;
  sort_order?: number;
}

/** mock 知识点列表（后端就绪后移除） */
function mockKnowledgePoints(subjectId: string): KnowledgePoint[] {
  const base: KnowledgePoint[] = [
    { id: "kp-lim", name: "极限", parent_id: null, level: 1 },
    { id: "kp-deriv", name: "导数", parent_id: null, level: 1 },
    { id: "kp-lhopital", name: "洛必达法则", parent_id: "kp-deriv", level: 2 },
    { id: "kp-integral", name: "定积分", parent_id: null, level: 1 },
  ];
  if (subjectId === "english") {
    return [
      { id: "kp-vocab", name: "词汇", parent_id: null, level: 1 },
      { id: "kp-reading", name: "阅读理解", parent_id: null, level: 1 },
    ];
  }
  if (subjectId === "linear-algebra") {
    return [{ id: "kp-det", name: "行列式", parent_id: null, level: 1 }];
  }
  return base;
}

export async function fetchKnowledgePoints(subjectId: string): Promise<KnowledgePoint[]> {
  return withFallback(
    () =>
      request<KnowledgePoint[]>({
        url: `/subjects/${subjectId}/knowledge-points`,
        method: "GET",
      }),
    () => mockKnowledgePoints(subjectId)
  );
}

/** 知识点 id → 名称 映射（策略 target_kps + 题目 knowledge_point_id 联合使用） */
export function buildKpNameMap(kps: KnowledgePoint[], hits: KnowledgePointHit[] = []): Map<string, string> {
  const map = new Map<string, string>();
  kps.forEach((kp) => map.set(kp.id, kp.name));
  hits.forEach((h) => map.set(h.id, h.name));
  return map;
}
