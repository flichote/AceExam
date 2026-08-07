import type { KnowledgeGraphResponse } from "@/types";
import { request, withFallback } from "@/utils/request";
import { mockKnowledgeGraph } from "@/mock/graph";

/**
 * 知识点图谱 API（docs/api.md §11.1）
 *  - GET /subjects/{subject_id}/knowledge-graph  三级树 + 节点状态聚合 + 统计
 * 树形数据直接喂 ECharts series-tree（data=[root]）或自绘 canvas 树（T16 兜底）。
 */

export async function fetchKnowledgeGraph(
  subjectId: string,
  includeQuestions = true
): Promise<KnowledgeGraphResponse> {
  const qs = includeQuestions ? "?include_questions=true" : "";
  return withFallback(
    () =>
      request<KnowledgeGraphResponse>({
        url: `/subjects/${subjectId}/knowledge-graph${qs}`,
        method: "GET",
      }),
    () => mockKnowledgeGraph(subjectId)
  );
}
