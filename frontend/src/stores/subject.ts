import { defineStore } from "pinia";
import { ref } from "vue";
import type { Subject } from "@/types";
import { fetchSubjects } from "@/api/subjects";

/** 科目状态：首页（选科）数据源 + 当前刷题科目 */
export const useSubjectStore = defineStore("subject", () => {
  const subjects = ref<Subject[]>([]);
  const loading = ref(false);
  const error = ref("");
  /** 当前刷题科目（tab 间传递：首页点科目 → switchTab 刷题） */
  const currentSubjectId = ref("");

  async function loadSubjects(force = false) {
    if (subjects.value.length > 0 && !force) return;
    loading.value = true;
    error.value = "";
    try {
      subjects.value = await fetchSubjects();
    } catch (e) {
      error.value = (e as Error).message || "加载失败";
    } finally {
      loading.value = false;
    }
  }

  function subjectById(id: string): Subject | undefined {
    return subjects.value.find((s) => s.id === id);
  }

  function selectSubject(id: string) {
    currentSubjectId.value = id;
  }

  return { subjects, loading, error, currentSubjectId, loadSubjects, subjectById, selectSubject };
});
