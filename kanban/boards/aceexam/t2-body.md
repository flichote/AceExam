项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【数据库工程师 ep-db】。

【你的任务】设计并落地 M1 数据库层（高数+英语两科并行的数据底座）：
1. `docs/database.md`：完整表设计（字段/类型/索引/关系），最少包含：
   - users（用户/会员：username, password_hash, role, is_member, created_at）
   - subjects（科目：name, description, is_active —— 高数/英语各一条）
   - knowledge_points（知识点图谱：subject_id FK, name, content, parent_id 层级, sort_order）
   - questions（题库：subject_id FK, knowledge_point_id FK, type, content, options JSON, answer, analysis, difficulty）
   - question_embeddings（向量表：question_id FK, embedding VECTOR(1024), model, content_hash —— pgvector）
   - wrong_answers（错题本：user_id FK, question_id FK, wrong_answer, wrong_reason, review_count, mastered）
   - study_sessions / study_plans（学习记录与备考计划，可简化为 plans 表）
2. Alembic 迁移脚本（backend/alembic/versions/ 下，初始 migration 建全部表 + 索引 + 向量扩展）
3. 种子数据脚本（backend/app/db/seed.py）：高数 + 英语两科知识点图谱（每科 ≥ 3 章 × ≥ 5 知识点）+ 初始题库（每科 ≥ 30 题，含答案和解析，直接可刷）

【技术选型（context7 已验证，直接用）】PostgreSQL 16 + pgvector（先 `CREATE EXTENSION vector`）；SQLAlchemy 2.x `VECTOR` 列类型 + `cosine_distance()`；Alembic 迁移；种子数据用纯 SQLAlchemy 脚本（不依赖 FastAPI）。

【仓库约定】你写 docs/database.md + backend/alembic/ + backend/app/db/seed.py。backend/ 是 ep-backend 的地盘，你只动 alembic 和 db 子目录，不要改其他后端文件；若 ep-backend 还没建 backend/ 骨架，你自己建目录结构。

【交付要求】完成后：`git add docs/database.md backend/alembic backend/app/db && git commit -m "feat(db): M1 表设计+Alembic+种子数据" && git push origin main`，卡片 comment 附提交 hash + 表清单 + 种子数据量。
