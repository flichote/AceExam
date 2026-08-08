项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【架构师/技术负责人 ep-arch】。

【你的任务】输出 M3 的架构增量文档（M1/M2 已交付 docs/architecture.md + 3 条 ADR + docs/api.md，本任务在其之上增量，不重写）：
1. 更新 `docs/architecture.md`：新增 M3 功能模块设计——
   - **知识点图谱可视化**：knowledge_points 树形数据 → 前端可视化方案（ECharts 关系图/树图选型，节点状态着色：已掌握/薄弱/待巩固/未接触）
   - **考前突击模式**：考前 7 天自动激活（或手动开启）→ 高频考点题优先 + 个人错题回顾 + 模拟卷；说明数据来源（做题统计 → 高频考点识别）
   - **打卡连胜**：study_sessions 连续打卡天数统计逻辑（中断判定规则）
   - **学习数据看板**：做题量/正确率/掌握度曲线的聚合查询设计（时间维度：日/周/月）
   - **排行榜**：班级/全局排行（口径：做题量？正确率？连续天数？给出建议并定案）
   - **挂科预警**：薄弱知识点 + 考试倒计时 → 风险等级判定规则（如：薄弱点数量 + 剩余天数 → 高/中/低风险）
2. 更新 `docs/api.md`：M3 新增 API 契约——
   - 图谱：GET /subjects/{id}/knowledge-graph（树形，带节点状态）
   - 突击：GET /subjects/{id}/sprint/questions（高频考点+错题交集）、POST /subjects/{id}/sprint/activate
   - 看板：GET /me/dashboard（做题量/正确率/掌握度/连胜）、GET /me/dashboard/trend（时间序列）
   - 排行：GET /leaderboard（全局/科目维度）
   - 预警：GET /me/warnings（挂科风险列表）
3. 更新 `docs/ops/M2-taskgraph.md` 或新增 `docs/ops/M3-taskgraph.md`：M3 任务图（T13~T18 依赖关系）

【技术选型（context7 已验证，直接用）】PostgreSQL 16 + pgvector；FastAPI 0.127.x；uni-app Vue3+Vite+TS；ECharts（若 uni-app 支持）或 canvas 自绘图谱；DeepSeek flash/pro 分级。**实现前用 context7 核对相关库最新文档**（ECharts / uni-app），查询记录写进 comment。

【仓库约定】你只写 docs/。其他角色并行写 backend/、frontend/，不要动他们的目录。

【交付要求】完成后：`git add docs/ && git commit -m "docs(arch): M3 图谱/突击/看板/排行/预警架构增量 + API 契约" && git push origin main`，卡片 comment 附提交 hash 和文档要点摘要（API 端点总数、设计决策）。
