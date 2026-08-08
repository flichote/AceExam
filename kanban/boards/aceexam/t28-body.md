项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【架构师/技术负责人 ep-arch】。

【背景】产品策略（用户拍板，详见 `docs/product/题库策略.md`）：每个学校课程不同，题库无法人工覆盖长尾。M5 落地两件事——
1. **课程三级归一对齐**：「XX大学 高数A」等校本课程实例 → AI 映射到模板课程（高等数学）→ 题目挂在模板课程+知识点上跨校共享
2. **题库飞轮**：UGC 拍照录题（已有 OCR）+ **AI 初审管线**（自动校验 → pending → active/rejected）+ 行为数据反哺质量

【你的任务】输出 M5 的架构增量（增量文档，不重写，M1~M4 已交付 docs/architecture.md + docs/api.md）：
1. 更新 `docs/architecture.md`：新增「课程归一对齐 + 题库飞轮」模块设计——
   - 三级对齐模型：课程实例（user_subjects）→ 模板课程（subjects）→ 知识点（knowledge_points）映射关系
   - 数据模型增量：`course_aliases` 表（alias → template_subject_id，同课多名归一）；`subjects.level`（'public'/'major'/'school' 课程分层）；`user_subjects.template_subject_id`
   - 课程匹配流程：用户录入校本课程名 → AI 匹配模板课程（置信度阈值）→ 未匹配可手动建实例
   - UGC 审核流：投稿 → AI 初审（答案/题干完整性校验）→ pending → active/rejected（复用 questions.source='ugc' + status 审核流）
   - 决策锁定表（D19~D22）
2. 更新 `docs/api.md`：新增端点——
   - GET /courses/aliases：查询课程别名（供录入时联想）
   - POST /courses/match：校本课程名 → 匹配模板课程（AI，返回候选 + 置信度）
   - POST /me/courses：录入校本课程实例（映射到模板或手动新建）
   - POST /ugc/upload：UGC 投稿（含 AI 初审提交）
   - GET /ugc/status：投稿审核状态查询
3. 更新 `docs/ops/M5-taskgraph.md`：确认/修正任务图（T28~T33）

【技术选型】沿用现有 FastAPI/SQLAlchemy/uni-app/DeepSeek 栈。**实现前用 context7 核对 FastAPI/SQLAlchemy 最新写法**，查询记录写进 comment。

【仓库约定】你只写 docs/。不要动 backend/、frontend/。

【交付要求】完成后：`git add docs/ && git commit -m "docs(arch): M5 课程归一对齐 + 题库飞轮架构增量" && git push origin main`，卡片 comment 附提交 hash 和要点摘要（端点总数、新增设计要点）。
