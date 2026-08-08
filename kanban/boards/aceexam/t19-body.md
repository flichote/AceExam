项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【架构师/技术负责人 ep-arch】。

【你的任务】输出 M3 剩余功能（M3.5）的架构增量文档（M1/M2/M3 已交付架构+API 契约，本任务增量）：
1. 更新 `docs/architecture.md`，新增模块设计——
   - **语音讲解（TTS）**：AI 讲解结果 → 语音播放。选型评估：edge-tts（微软免费，后端生成 mp3）vs 前端 Web Speech API；说明后端 TTS 端点设计（讲解文本 → mp3 流）与前端播放集成（音频组件）
   - **UGC 题库共建**：学生上传题目 → 自动解析（复用 OCR/LLM）→ **审核流**（状态机：pending → approved/rejected，管理员或规则审核）；说明与现有 /questions/from-ocr 的关系（UGC 题独立标记 source + 审核状态）
   - **成绩单海报分享**：学习数据（连胜/掌握度/做题量）→ 前端 canvas 生成海报图 → 保存/分享（小程序保存相册 / H5 下载）
   - **班级排行榜**：现有 /leaderboard 增加 scope=class 维度——班级从哪来（用户可选填班级字段？邀请码？给出建议并定案）
2. 更新 `docs/api.md`，新增端点——
   - TTS：POST /chat/explain/{session_id}/tts（生成讲解音频）或 GET 音频流
   - UGC：POST /questions/ugc（提交待审题）、GET /admin/questions/ugc（审核列表）、POST /admin/questions/{id}/review（通过/拒绝）
   - 班级：GET /leaderboard?scope=class、POST /me/class（加入班级）
   - 海报：GET /me/share-card（分享卡数据聚合）
3. 更新任务图文档：M3.5 任务（T19~T23）

【技术选型（context7 已验证，直接用）】edge-tts 或系统 TTS；FastAPI StreamingResponse 音频流；uni-app canvas 海报生成（小程序 saveImageToPhotosAlbum / H5 下载）。**实现前用 context7 核对相关库最新文档**，查询记录写进 comment。

【仓库约定】你只写 docs/。不要动 backend/、frontend/。

【交付要求】完成后：`git add docs/ && git commit -m "docs(arch): M3.5 TTS/UGC/海报/班级排行架构增量 + API 契约" && git push origin main`，卡片 comment 附提交 hash 和要点摘要。
