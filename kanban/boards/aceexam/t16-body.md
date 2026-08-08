项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【前端工程师 ep-frontend】。

【你的任务】在 M2 五件套页面基础上，实现 M3 页面。参照 ep-arch 的 docs/api.md 契约（若已存在）：
1. **知识点图谱可视化**（诊断 Tab 内新增或独立页）：
   - 树形/关系图展示知识树（章→节→知识点），节点按状态着色（已掌握绿/薄弱红/待巩固橙/未接触灰）
   - 点击节点 → 对应知识点题目列表/讲解入口
   - 数据：GET /subjects/{id}/knowledge-graph
2. **考前突击模式**（刷题页新增入口）：
   - 考前 7 天自动提示激活（或手动开启）
   - 突击模式视觉（primary 描边 + 倒计时）
   - 突击题单：GET /subjects/{id}/sprint/questions，答题流程复用现有刷题组件
3. **学习数据看板**（我的 Tab 内）：
   - 汇总卡片（总做题量/正确率/掌握度/连胜天数）
   - 趋势折线图（近 30 天做题量/正确率）
   - 数据：GET /me/dashboard + /me/dashboard/trend
4. **排行榜**（新页面）：
   - 全局/科目维度切换，排名列表（名次/用户/做题量/正确率/连续天数）
   - 数据：GET /leaderboard
5. **挂科预警**（首页或诊断页展示）：
   - 风险列表（高/中/低 徽章 + 理由）
   - 数据：GET /me/warnings
6. **打卡连胜**：首页/我的展示连胜徽章（🔥 N 天）

【技术选型（context7 已验证，直接用）】uni-app Vue3+Vite+TS；图表用 ECharts（uni-app 适配：renderjs 方案或 canvas 手绘，H5 优先 ECharts，小程序降级）；KaTeX 公式渲染。**实现前用 context7 核对 uni-app/ECharts 最新 API**（`context7 query docs echarts` / uni-app），查询记录写进 comment。

【仓库约定】你写 frontend/。ep-backend/ep-db/ep-ai 在 backend/，不要动。mock 数据放 frontend/src/mock/ 作为降级，主路径走真实 API。

【交付要求】完成后：`git add frontend/ && git commit -m "feat(frontend): M3 图谱/突击/看板/排行/预警页面" && git push origin main`，卡片 comment 附提交 hash + 构建/运行输出 + context7 查询记录。
