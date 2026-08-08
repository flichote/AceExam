项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【后端工程师 ep-backend】。

【你的任务】在 M1~M3 API 基础上，实现 M3.5 剩余功能 API。参照 ep-arch 的 docs/api.md 契约（若已存在）：
1. **TTS 语音讲解**：
   - POST /chat/explain/{session_id}/tts：把讲解内容（steps+conclusion 文本）合成语音 → 返回音频（mp3/wav 流，StreamingResponse）
   - 调 ep-ai 的 tts_service（edge-tts 或等效实现）
2. **UGC 题库共建**：
   - POST /questions/ugc：提交待审题目（复用现有题目结构 + source=ugc + review_status=pending）
   - GET /admin/questions/ugc?status=pending：审核列表（管理员鉴权，MVP 用简单 role 检查）
   - POST /admin/questions/{id}/review：审核通过/拒绝（approved/rejected + 理由）
   - 与现有 /questions/from-ocr 的关系：OCR 确认入库的题标记 source=ugc + 默认 approved 或 pending（以架构定案为准）
3. **班级排行榜**：
   - POST /me/class：设置/加入班级（字段：class_name，MVP 简单方案）
   - GET /leaderboard?scope=class：班级维度排行（需用户有 class_name）
4. **分享卡聚合**：
   - GET /me/share-card：分享卡数据（连胜/掌握度/做题量/本周正确率聚合，供前端海报生成）

【技术选型（context7 已验证，直接用）】FastAPI 0.127.x；SQLAlchemy 2.x async；音频流 StreamingResponse。**实现前用 context7 核对 FastAPI 最新写法**（`context7 query docs fastapi`），查询记录写进 comment。

【仓库约定】你写 backend/app/api/、backend/app/schemas/。ep-db 的表结构若需新增（ugc 审核字段/班级字段）由你提需求或直接加 Alembic 迁移（小改动），ep-ai 写 backend/app/services/tts_service.py 等 AI 部分。不要动 frontend/。

【交付要求】完成后：`git add backend/app/api backend/app/schemas backend/alembic && git commit -m "feat(backend): M3.5 TTS/UGC/班级排行/分享卡 API" && git push origin main`，卡片 comment 附提交 hash + 端点清单 + 烟测输出 + context7 查询记录。
