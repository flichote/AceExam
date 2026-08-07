项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【后端工程师 ep-backend】。

【你的任务】搭建 M1 FastAPI 后端骨架 + 核心 API（高数+英语共用一套，subject_id 区分）：
1. backend/ 项目骨架：FastAPI app 结构（app/core 配置安全 / app/api/v1 路由 / app/models SQLAlchemy / app/schemas Pydantic / app/services 业务 / app/db 会话与迁移）
2. `backend/app/core/config.py`：pydantic-settings 读 .env（DATABASE_URL, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, JWT_SECRET）
3. `backend/app/services/llm_gateway.py`：LLM 网关（服务端唯一接触 DeepSeek 的地方）——Key 只从环境变量读、支持 flash/pro 模型切换、流式 SSE 输出、超时与错误包装。**参考：RehabFlow/CCN 项目已有成熟实现，模式相同**
4. API 路由（挂 /api/v1）：
   - auth：POST /register、POST /login（JWT）、GET /me
   - subjects：GET/POST /subjects（列表/创建）
   - knowledge-points：GET /subjects/{id}/knowledge-points
   - questions：GET /subjects/{id}/questions（可按知识点/难度筛选）、POST /questions（录题）
   - wrong-answers：GET/POST /wrong-answers（错题本增查）
   - chat：POST /chat（对话，调 LLM 网关，支持 stream）
   - /healthz 健康检查
5. 依赖注入 + 全局异常处理 + CORS

【技术选型（context7 已验证，直接用）】FastAPI 0.127.x；SQLAlchemy 2.x async + Alembic；pydantic v2 + pydantic-settings；python-jose 或 pyjwt 做 JWT；httpx 调 DeepSeek；uvicorn 运行。

【仓库约定】你写 backend/（ep-db 会写 backend/alembic/ 和 backend/app/db/seed.py，ep-ai 会写 app/services/rag 相关——避免与他们重名文件，若冲突以你为准做目录归并）。ep-frontend 在 frontend/，不要动。

【交付要求】完成后：`git add backend/ && git commit -m "feat(backend): M1 FastAPI骨架+LLM网关+核心API" && git push origin main`，卡片 comment 附提交 hash + 接口清单 + 本地烟测输出（uvicorn 起服务 /healthz 返回 200 的证明）。
