import { defineStore } from "pinia";
import type { OcrUploadResult } from "@/types";
import { uploadOcrImage, pollOcrUpload } from "@/api/ocr";

/**
 * 拍照录题状态（docs/api.md §6）
 * 拍照/相册 → 上传识别 → 结果预览（确认页编辑）→ 入库
 */
export const useOcrStore = defineStore("ocr", {
  state: () => ({
    subjectId: "",
    source: "photo" as "photo" | "album",
    uploading: false,
    uploadResult: null as OcrUploadResult | null,
    error: "",
  }),

  getters: {
    parsed: (state) => state.uploadResult?.status === "parsed",
    structured: (state) => state.uploadResult?.structured ?? null,
    suggestedKps: (state) => state.uploadResult?.suggested_kps ?? [],
  },

  actions: {
    async upload(filePath: string, subjectId: string, source: "photo" | "album" = "photo") {
      this.subjectId = subjectId;
      this.source = source;
      this.uploading = true;
      this.error = "";
      try {
        let res = await uploadOcrImage(filePath, subjectId, source);
        // 202 pending 兜底：轮询直到 parsed/failed
        if (res.status === "pending" && res.upload_id) {
          res = await pollOcrUpload(res.upload_id);
        }
        this.uploadResult = res;
        return res;
      } catch (e) {
        this.error = (e as Error).message || "识别失败";
        uni.showToast({ title: this.error, icon: "none" });
        return null;
      } finally {
        this.uploading = false;
      }
    },

    reset() {
      this.uploadResult = null;
      this.error = "";
    },
  },
});
