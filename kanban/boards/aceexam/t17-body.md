项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【AI 工程师 ep-ai】（灵魂角色）。

【你的任务】在 M2 AI 服务（RAG 讲解/OCR/诊断/选题）基础上，实现 M3 的 AI 能力：
1. **突击题单生成**（backend/app/services/sprint.py 新建）：
   - 高频考点识别：从做题统计（正确率低 + 出现频次高）识别高频考点
   - 突击题单 = 高频考点题 + 个人错题交集（去重、限量、按考点分布）
   - 考前 7 天激活逻辑支持（或手动）
2. **挂科预警分析**（backend/app/services/warning.py 新建）：
   - 输入：薄弱知识点列表 + 考试倒计时 + 近期练习趋势
   - 输出：风险等级（高/中/低）+ 每项理由（可解释），JSON 结构设计清晰
3. **图谱状态增强**（backend/app/services/knowledge_graph.py 新建，可选）：
   - 知识点树组装（三级层级）+ 节点状态着色数据（已掌握/薄弱/待巩固/未接触）
4. 单元测试：sprint 题单生成（高频+错题交集）、warning 风险分级（各等级边界）、knowledge_graph 树结构（backend/tests/test_ai_m3.py）

【技术选型（context7 已验证，直接用）】DeepSeek flash/pro 分级（简单规则 flash、分析 pro）；现有 llm_gateway 复用。**实现前用 context7 核对相关库最新文档**，查询记录写进 comment。

【仓库约定】你写 backend/app/services/（sprint.py、warning.py、knowledge_graph.py）+ backend/tests/test_ai_m3.py。复用 ep-backend 的 llm_gateway（import 方式，别改它）。ep-backend 写 backend/app/api/，ep-db 写 backend/app/db/——不要动他们的目录。不要动 frontend/。

【交付要求】完成后：`git add backend/app/services backend/tests && git commit -m "feat(ai): M3 突击题单+挂科预警+图谱服务" && git push origin main`，卡片 comment 附提交 hash + 测试通过数 + 示例输出 + context7 查询记录。
