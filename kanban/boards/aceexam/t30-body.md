项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【后端工程师 ep-backend】。

【背景】M5「课程归一对齐 + 题库飞轮」（产品策略见 docs/product/题库策略.md，架构契约见 docs/architecture.md §14，API 契约见 docs/api.md §14，决策锁定 D19~D22）。ep-arch 已交付契约，你实现 API。

【你的任务】在 M1~M4 API 基础上，实现 M5 全部 API。参照 ep-arch 的 docs/api.md §14 契约（字段级）：
1. `GET /courses/aliases`（14.1）：课程别名联想查询（q 可选、limit 默认 10、is_verified 优先排序）
2. `POST /courses/match`（14.2）：校本课程名 → 匹配模板课程。策略：①归一化 → 精确命中 course_aliases（strategy=alias, confidence=1.0）；②未命中 → 调 course_matcher 服务（T31 提供，**接口先行**：按契约 dict 占位联调，服务未就绪时返回 503 或 mock）；③阈值决策（D21：≥0.85 自动 top1 / 0.60~0.85 候选列表 / <0.60 未匹配）
3. `POST /me/courses`（14.3）：录入校本课程实例（映射到模板或手动新建 level='school' 实例；命中时沉淀 alias source='ai' 或 'manual'）
4. `GET /me/courses`（14.4 如有）：我的课程实例列表（含 template 映射关系）
5. `POST /ugc/upload`（14.5 如有）：UGC 投稿 → AI 初审（T31 提供 ugc_review 服务，接口先行占位）→ pending
6. `GET /ugc/status`（14.5 如有）：投稿审核状态查询

【技术选型】FastAPI 0.127.x + SQLAlchemy 2.x + Pydantic v2。**实现前用 context7 核对 FastAPI/SQLAlchemy 最新写法**，查询记录写进 comment。

【仓库约定】你只写 backend/app/api/、backend/app/schemas/、backend/app/models/、backend/app/services/（除 ai 服务外）。不要动 frontend/、backend/alembic/（T29 负责）、backend/app/services/ai 相关（T31 负责）。

【交付要求】完成后：`git add backend/app && git commit -m "feat(backend): M5 课程对齐 + UGC 审核流 API" && git push origin main`，卡片 comment 附提交 hash、端点清单、与 T31 的接口约定。
