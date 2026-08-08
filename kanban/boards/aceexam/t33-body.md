项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【测试工程师 ep-qa】。

【背景】M5「课程归一对齐 + 题库飞轮」（架构契约 docs/architecture.md §14，API 契约 docs/api.md §14）。ep-arch 已交付契约，ep-db（T29）、ep-backend（T30）、ep-ai（T31）、ep-frontend（T32）交付后你执行验收。

【你的任务】为 M5 建立验收测试。等 T29/T30/T31/T32 交付后执行：
1. **课程对齐测试**：
   - course_aliases 表结构（alias UNIQUE、template FK、source/is_verified 默认值）
   - POST /courses/match：别名精确命中（strategy=alias, confidence=1.0）；未命中走 AI（mock LLM）→ 候选按 confidence 降序；阈值边界（0.85/0.60）
   - POST /me/courses：录入映射到模板（template_subject_id 写入）；手动建 school 实例（level='school', template NULL）；命中沉淀 alias
   - GET /courses/aliases：q 过滤、is_verified 优先、limit 限制
2. **UGC 审核流测试**（mock ugc_review 服务）：
   - 投稿 → AI 初审 pass → pending（confidence<0.95）或直接 active（≥0.95）
   - 投稿 → AI 初审 reject → rejected + reject_reason
   - GET /ugc/status：审核状态可查
3. 回归：M1~M4 全量测试不破（尤其 subjects/user_subjects 相关）
4. 更新 `docs/qa/test-report.md`（M5 用例数、通过率）

【仓库约定】你只写 backend/tests/（除 test_ai_* 外）+ docs/qa/。只加测试不改业务代码（发现 bug 记录在案）。

【交付要求】完成后：`git add backend/tests docs/qa && git commit -m "test(qa): M5 课程对齐 + UGC 审核流验收测试" && git push origin main`，卡片 comment 附提交 hash、用例数、通过率、发现的 bug 清单。
