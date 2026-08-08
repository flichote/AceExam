项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【AI 工程师 ep-ai】。

【背景】M5「课程归一对齐 + 题库飞轮」（产品策略见 docs/product/题库策略.md，架构契约见 docs/architecture.md §14，API 契约见 docs/api.md §14，决策锁定 D19~D22）。ep-arch 已交付契约，你实现两个 AI 服务。**与 T30（ep-backend）并行，接口先行**——按 api.md §14 的 dict 契约实现服务，T30 联调你的接口。

【你的任务】在 M2 AI 服务（RAG 讲解/OCR/诊断/选题）基础上，实现 M5 的 AI 能力：
1. **course_matcher 服务**（`backend/app/services/ai/course_matcher.py`）：校本课程名 → 模板课程候选。
   - 输入：归一化课程名 + 可选学校名 + 可选教材
   - 输出契约（api.md §14.2）：`{"candidates": [{"template_subject_id", "name", "code", "confidence", "reason", "source"}], "strategy": "alias"|"ai"}`
   - 实现：先查 course_aliases 精确命中（source='alias'）；未命中 → DeepSeek flash 语义匹配（用 subjects 表现有模板列表做候选池，prompt 要求返回 JSON 候选 + confidence + reason）
   - confidence 归一化 0~1；注意 JSON 解析容错（LLM 可能返回非纯 JSON，用 json_parse 兜底）
2. **ugc_review 服务**（`backend/app/services/ai/ugc_review.py`）：UGC 投稿 AI 初审管线。
   - 输入：题目（content/options/answer/analysis/knowledge_point_id）
   - 输出：`{"verdict": "pass"|"reject", "confidence": 0~1, "issues": [{"field", "reason"}], "suggested_fix"?: str}`
   - 校验项：题干完整性、选项与答案一致性（选择题答案必须命中选项）、数值题反向代入验算（规则引擎 + LLM 双通道）、知识点归属合理性
   - verdict=pass → 投稿 status pending（等待人工/行为反馈）或直接 active？——按 D22 决策：**pass → pending（进人工抽检池），confidence≥0.95 才直接 active**；reject → rejected + reject_reason
3. 单测：`backend/tests/test_ai_course_matcher.py` + `backend/tests/test_ai_ugc_review.py`（mock LLM 响应，不真实调用 DeepSeek）

【技术选型】DeepSeek flash（默认，省钱）+ pro（低置信度复核时用）。**实现前用 context7 核对 DeepSeek API 最新写法**，查询记录写进 comment。

【仓库约定】你只写 backend/app/services/ai/、backend/tests/test_ai_*。不要动 app/api、app/models、frontend/。

【交付要求】完成后：`git add backend/app/services/ai backend/tests && git commit -m "feat(ai): M5 course_matcher + ugc_review 服务" && git push origin main`，卡片 comment 附提交 hash、两个服务的输入输出契约、测试结果。
