项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【数据库工程师 ep-db】。

【你的任务】在 M1/M2 表结构基础上（现有 users/subjects/knowledge_points/questions/wrong_answers/user_knowledge_states/plans/study_sessions 等），为 M3 增量设计表与迁移：
1. 审查现有模型覆盖度，为 M3 新增/调整表：
   - **打卡连胜**：确认 study_sessions 能否支撑连胜统计（连续打卡判定需要历史 session 日期序列）——若需新增 streak 快照表或字段，设计之
   - **排行榜**：排行榜聚合表（可选的物化视图/缓存表：用户维度做题量/正确率/连续天数快照）或纯查询方案（说明理由）
   - **挂科预警**：预警记录表（用户+知识点+风险等级+触发时间+处理状态）——是否复用现有表还是独立表，给出决策
   - **突击模式**：突击会话表（用户+科目+激活时间+题单快照+完成状态）——若需要
2. 新增 Alembic 迁移（backend/alembic/versions/0003_*.py），命名规范清晰
3. 种子数据：若 M3 功能需要演示数据（如打卡历史、做题记录样本），补充 backend/app/db/seed.py

【技术选型（context7 已验证，直接用）】PostgreSQL 16 + pgvector；SQLAlchemy 2.x async + Alembic。**实现前用 context7 核对 pgvector/Alembic 最新写法**（`context7 query docs pgvector-python`），查询记录写进 comment。

【仓库约定】你写 backend/app/db/、backend/app/models/、backend/alembic/。ep-backend 写 backend/app/api/ 和 backend/app/services/ 其他部分，ep-ai 写 backend/app/services/ 的 AI 部分——避免重名文件。不要动 frontend/。

【交付要求】完成后：`git add backend/app/db backend/app/models backend/alembic && git commit -m "feat(db): M3 连胜/排行榜/预警/突击表迁移" && git push origin main`，卡片 comment 附提交 hash + 新增/修改表清单 + context7 查询记录 + 迁移验证输出。
