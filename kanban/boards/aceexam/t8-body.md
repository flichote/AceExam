项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【数据库工程师 ep-db】。

【你的任务】在 M1 表结构（users/subjects/knowledge_points/questions/question_embeddings/document_chunks/wrong_answers/user_knowledge_states/plans/study_sessions/ai_explanations/chat_sessions/token_usage）基础上，为 M2 五件套增量设计表与迁移：
1. 审查现有 models（backend/app/db/models.py）覆盖度，为 M2 新增/调整表：
   - **诊断**：诊断结果表（自测批次、薄弱 Top5 快照、诊断报告 JSON）——若 user_knowledge_states 够用则说明理由并只加诊断快照表
   - **打卡/计划**：确认 plans + study_sessions 表能支撑每日任务+打卡（倒计时、任务列表、完成状态、打卡日期）——缺字段就补 Alembic 迁移
   - **OCR 录题**：OCR 上传记录表（原始图片引用、识别结果、结构化题目 JSON、知识点归属、状态：pending/parsed/failed）——确认是否复用 questions 表还是独立表
2. 新增 Alembic 迁移（backend/alembic/versions/0002_*.py），命名规范清晰
3. 种子数据补充：若 M2 需要（如自测题组/知识点图谱补全），补充 backend/app/db/seed.py

【技术选型（context7 已验证，直接用）】PostgreSQL 16 + pgvector（VECTOR 列 + cosine_distance）；SQLAlchemy 2.x async + Alembic。**实现前用 context7 核对 pgvector/Alembic 最新写法**（`context7 query docs pgvector-python` 或 `/pgvector/pgvector`），把查询记录写进 comment。

【仓库约定】你写 backend/app/db/、backend/alembic/、backend/app/models/。ep-backend 写 backend/app/api/ 和 backend/app/services/ 其他部分，ep-ai 写 backend/app/services/rag 和 ocr/诊断——避免重名文件。不要动 frontend/。

【交付要求】完成后：`git add backend/app/db backend/app/models backend/alembic && git commit -m "feat(db): M2 诊断/打卡/OCR 表迁移" && git push origin main`，卡片 comment 附提交 hash + 新增/修改表清单 + context7 查询记录 + 迁移执行验证输出（alembic upgrade head 或等效证明）。
