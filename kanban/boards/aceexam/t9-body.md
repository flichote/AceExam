项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【后端工程师 ep-backend】。

【你的任务】在 M1 骨架（已有 auth/subjects/questions/wrong_answers/chat 端点 + llm_gateway）基础上，实现 M2 五件套的完整 API。参照 ep-arch 的 docs/api.md 契约（若该文档已存在），实现并挂载 /api/v1：
1. **智能刷题**：
   - GET /subjects/{id}/practice/questions：自适应选题（薄弱知识点优先 + 错误率加权，调 ep-ai 的 selection 服务或按 docs/architecture.md 的公式实现 MVP 规则版）
   - POST /questions/{id}/answers：提交答案 → 记录做题 + 更新 user_knowledge_states（连续 3 次正确→已掌握）
2. **AI 讲解**（M1 chat.py 已有 explain/followup，完善为完整闭环）：
   - POST /chat/explain：RAG 检索 + flash/pro 分级讲解，返回带引用的 step-by-step（调 ep-ai 的 rag_engine）
   - POST /chat/followup：追问（带上下文）
   - SSE 流式输出支持
3. **拍照录题**：
   - POST /ocr/upload：图片上传 → 调 ocr_service 识别 → 结构化题目（题干/选项/答案/知识点）→ 返回预览
   - POST /questions/from-ocr：确认入库（幂等：重复提交不产生重复记录）
4. **薄弱诊断**：
   - POST /diagnose/self-test：发起 10 题摸底自测（选题规则：覆盖主要章节）
   - GET /diagnose/self-test/{id}：取自测题
   - POST /diagnose/report：提交自测结果 → 调 diagnosis 引擎 → 返回薄弱地图 JSON（薄弱 Top5 + 建议）
5. **备考计划**：
   - POST /plans：创建计划（subject_id + 考试日期 → 倒计时 + 按薄弱点生成每日任务）
   - GET /plans/active：当前活跃计划 + 今日任务列表
   - POST /plans/{id}/checkin：打卡（乐观锁防并发重复）

【技术选型（context7 已验证，直接用）】FastAPI 0.127.x；SQLAlchemy 2.x async；pydantic v2；httpx 调 DeepSeek；SSE 用 sse-starlette 或 StreamingResponse。**实现前用 context7 核对 FastAPI 最新写法**（`context7 query docs fastapi`），把查询记录写进 comment。

【仓库约定】你写 backend/app/api/、backend/app/schemas/、backend/app/services/（除 rag/、ocr_service.py、diagnosis.py、quiz_generator.py 外——那些归 ep-ai）。ep-db 写 backend/app/db/ 和 backend/app/models/。不要动 frontend/。

【交付要求】完成后：`git add backend/app/api backend/app/schemas && git commit -m "feat(backend): M2 五件套完整 API" && git push origin main`，卡片 comment 附提交 hash + 端点清单 + 本地烟测输出（uvicorn 起服务，关键端点 curl 200 证明）+ context7 查询记录。
