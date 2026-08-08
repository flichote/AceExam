项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【AI 工程师 ep-ai】。

【你的任务】实现 M3.5 的 AI 能力：
1. **TTS 语音合成服务**（backend/app/services/tts_service.py 新建）：
   - 输入：讲解文本（steps + conclusion 纯文本，去 LaTeX 标记或保留中文朗读）
   - 输出：音频字节流（mp3）
   - 实现：edge-tts（微软免费接口，`edge_tts` Python 库）或等效方案；无网络时降级返回 501/明确错误
   - 中文语音优先（zh-CN 音色）
2. **UGC 题目自动解析增强**（backend/app/services/ocr_service.py 或 ugc_service.py 增量）：
   - 学生提交的 UGC 题（文字/图片）→ 自动结构化（题干/选项/答案/知识点归属）
   - 与现有 OCR 流程复用，标注 source=ugc
3. 单元测试：tts_service（输入文本→音频字节非空、参数校验）、ugc 解析（mock OCR，输出结构正确）（backend/tests/test_ai_m35.py）

【技术选型（context7 已验证，直接用）】edge-tts 库（`pip install edge-tts`）；现有 llm_gateway/OCR 复用。**实现前用 context7 核对 edge-tts 最新用法**（如 context7 有收录，否则查官方文档），查询记录写进 comment。

【仓库约定】你写 backend/app/services/（tts_service.py、ugc_service.py 增量）+ backend/tests/test_ai_m35.py。复用现有 llm_gateway/ocr_service（import 方式）。ep-backend 写 backend/app/api/。不要动 frontend/。

【交付要求】完成后：`git add backend/app/services backend/tests && git commit -m "feat(ai): M3.5 TTS语音+UGC自动解析" && git push origin main`，卡片 comment 附提交 hash + 测试通过数 + TTS 示例输出（音频字节数）+ context7 查询记录。
