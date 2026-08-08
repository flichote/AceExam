项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【后端工程师 ep-backend】。

【你的任务】在 M2 五件套 API 基础上，实现 M3 全部 API。参照 ep-arch 的 docs/api.md 契约（若已存在），实现并挂载 /api/v1：
1. **知识点图谱**：
   - GET /subjects/{id}/knowledge-graph：知识树（章→节→知识点三级），每个节点带状态（已掌握/薄弱/待巩固/未接触，来自 user_knowledge_states）
2. **考前突击模式**：
   - POST /subjects/{id}/sprint/activate：激活突击（校验考前 7 天内或手动开启）
   - GET /subjects/{id}/sprint/questions：高频考点题优先 + 个人错题交集题单（调 ep-ai 的 sprint 服务）
3. **学习数据看板**：
   - GET /me/dashboard：汇总（总做题量/正确率/掌握度/连胜天数/薄弱点计数）
   - GET /me/dashboard/trend?days=30：时间序列（每日做题量/正确率，供折线图）
4. **排行榜**：
   - GET /leaderboard?subject_id=&scope=global|subject：按做题量/正确率/连续天数排序（口径以 docs/api.md 定案为准）
5. **挂科预警**：
   - GET /me/warnings：风险列表（薄弱知识点 + 考试倒计时 → 高/中/低风险，调 ep-ai 的 warning 服务）
6. 现有 M2 缺陷顺手修复（如遇且确认根因）：
   - D-8 判分载荷（前端 {type,value} 信封）
   - D-9 knowledge_state 响应滞后
   - D-11 诊断 Top5 排序反转
   - D-16 /questions 详情 list options 500

【技术选型（context7 已验证，直接用）】FastAPI 0.127.x；SQLAlchemy 2.x async；pydantic v2；聚合查询用 SQLAlchemy func。**实现前用 context7 核对 FastAPI 最新写法**（`context7 query docs fastapi`），查询记录写进 comment。

【仓库约定】你写 backend/app/api/、backend/app/schemas/。ep-db 写 backend/app/db/ 和 backend/app/models/，ep-ai 写 backend/app/services/ 的 AI 部分（sprint/warning 服务）——你调它们，不要重写。不要动 frontend/。

【交付要求】完成后：`git add backend/app/api backend/app/schemas && git commit -m "feat(backend): M3 图谱/突击/看板/排行/预警 API" && git push origin main`，卡片 comment 附提交 hash + 端点清单 + 本地烟测输出 + context7 查询记录。
