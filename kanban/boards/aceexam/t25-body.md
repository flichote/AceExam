项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【后端工程师 ep-backend】。

【背景】产品需求调整：用户自选专业+课程，公共课放课程广场。参照 ep-arch 的 docs/api.md 契约（若已存在）：
1. **数据模型**（与 ep-db 协作，或直接完成小改动）：
   - User 增加 `major` 字段（String，可空，自由文本）
   - 新增 `user_subjects` 关联表（user_id + subject_id，用户自选课程多对多）
   - Subject 增加 `is_public` 字段（Bool，True=课程广场公共课）
2. **API**：
   - PUT /me/profile：更新专业（body: {major: str}）
   - PUT /me/subjects：设置本学期课程（body: {subject_ids: [uuid]}，幂等：重复提交覆盖）
   - GET /me/subjects：用户自选课程列表（含每科学习状态：做题量/正确率/掌握度）
   - GET /subjects/plaza：课程广场（is_public=True 的课程 + 当前用户是否已加入）
3. 种子数据：现有 2 科（高数/英语）标 is_public=True；补齐几门常见公共课（线性代数/概率论/大学物理）为 is_public=True 便于广场展示（有题目最好，无题仅展示也可）
4. 现有端点兼容：GET /subjects 保持可用（广场数据源）

【技术选型】FastAPI 0.127.x；SQLAlchemy 2.x async + Alembic 迁移（0004_user_major_plaza）。**实现前用 context7 核对 FastAPI 最新写法**，查询记录写进 comment。

【仓库约定】你写 backend/app/api/、backend/app/schemas/、backend/app/models/、backend/alembic/。ep-ai 写 backend/app/services/ 的 AI 部分，ep-db 若并行处理 db 目录则协调避免冲突。不要动 frontend/。

【交付要求】完成后：`git add backend/ && git commit -m "feat(backend): 用户专业选课 + 课程广场 API" && git push origin main`，卡片 comment 附提交 hash + 端点清单 + 烟测输出 + context7 查询记录。
