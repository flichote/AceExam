项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【数据库工程师 ep-db】。

【背景】M5「课程归一对齐 + 题库飞轮」（产品策略见 docs/product/题库策略.md，架构契约见 docs/architecture.md §14，决策锁定 D19~D22）。ep-arch 已交付契约，你落地表结构。

【你的任务】在 M1~M4 表结构基础上（现有 users/subjects/knowledge_points/questions/.../user_subjects 等），为 M5 增量建表与迁移：
1. **新表 `course_aliases`**（同课多名归一）：id UUID PK / alias VARCHAR(100) NOT NULL UNIQUE / template_subject_id UUID NOT NULL FK→subjects.id / source VARCHAR(20) NOT NULL DEFAULT 'seed'（'seed'/'ai'/'manual'）/ is_verified BOOLEAN NOT NULL DEFAULT false / created_at / updated_at（TIMESTAMPTZ DEFAULT now()）。索引：(template_subject_id)。
2. **`subjects.level` 增列**：VARCHAR(20) NOT NULL DEFAULT 'public'（'public'/'major'/'school' 课程分层）。
3. **`user_subjects.template_subject_id` 增列**：UUID NULL FK→subjects.id（NULL=未归一独立实例）。
4. 新增 Alembic 迁移 `0006_course_alias_level`（down_revision=`0005_user_major_plaza`，先确认既有最新版本号），并写 `docs/database.md` §12 增量（表结构、索引、迁移说明）。
5. 种子数据更新（`db/seed.py`）：公共课（高数/英语/线代/概率论/大物）level='public'；course_aliases 种子（"高等数学A"/"高数上"/"高数"→math_gaoshu，"大学英语"/"英语一"/"英语二"→english 等，source='seed'）。

【技术选型】PostgreSQL 16 + pgvector；SQLAlchemy 2.x + Alembic。**实现前用 context7 核对 Alembic/SQLAlchemy 最新写法**（如 Enum(name=)、mapped_column、迁移 autogenerate 与手写混合），查询记录写进 comment。

【仓库约定】你只写 backend/alembic/、backend/app/db/、docs/database.md。不要动 app/api、app/services、frontend/。

【交付要求】完成后：`git add backend/alembic backend/app/db docs/database.md && git commit -m "feat(db): M5 course_aliases + subjects.level + template_subject_id" && git push origin main`，卡片 comment 附提交 hash 和表结构要点摘要。
