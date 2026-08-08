项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【架构师/技术负责人 ep-arch】。

【背景】产品需求调整（用户反馈）：首页不再直接展示全部科目。改为——
1. 用户根据自己的实际情况，先填写自己的**专业**（自由文本）
2. 用户选择/填写**本学期课程**（自由文本列表）
3. **公共课**（高等数学、大学英语等种子数据）单独放到首页的「课程广场」页

【你的任务】输出本改动的架构增量（增量文档，不重写）：
1. 更新 `docs/architecture.md`：新增「用户专业与选课」模块设计——
   - 数据模型：User 增加 major 字段（自由文本）+ user_subjects 关联表（用户自选课程，多对多）
   - 首页数据流：GET /me/subjects（用户自选课程）→ 首页展示；GET /subjects/plaza（课程广场=公共课）→ 广场页
   - 区分「用户自选课程」与「系统公共课程」（subject.is_public 或类型字段）
2. 更新 `docs/api.md`：新增端点——
   - PUT /me/profile：更新专业（major）
   - PUT /me/subjects：设置用户本学期课程（subject_ids 数组，幂等）
   - GET /me/subjects：用户自选课程列表（含学习状态）
   - GET /subjects/plaza：课程广场（公共课列表，含加入状态）
3. 更新任务图：本改动任务（T24~T27）

【技术选型】沿用现有 FastAPI/SQLAlchemy/uni-app 栈。**实现前用 context7 核对 FastAPI/SQLAlchemy 最新写法**，查询记录写进 comment。

【仓库约定】你只写 docs/。不要动 backend/、frontend/。

【交付要求】完成后：`git add docs/ && git commit -m "docs(arch): 用户专业选课 + 课程广场架构增量" && git push origin main`，卡片 comment 附提交 hash 和要点摘要。
