项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【测试工程师 ep-qa】。

【你的任务】在 M1/M2 测试体系基础上，为 M3 建立验收测试。等 ep-backend（T15）、ep-frontend（T16）、ep-ai（T17）交付后执行：
1. `backend/tests/` 新增 M3 测试（mock 上游 DeepSeek，不真调 API）：
   - 图谱：GET /subjects/{id}/knowledge-graph（树结构完整性、节点状态正确映射）
   - 突击：激活（考前 7 天/手动）、题单生成（高频考点+错题交集、去重、限量）
   - 看板：/me/dashboard 汇总正确性、/me/dashboard/trend 时间序列（含空数据边界）
   - 排行：排序正确性（做题量/正确率/连续天数口径）、分页
   - 预警：风险等级边界（高/中/低判定）、理由可解释
   - 打卡连胜：连续/中断判定
2. 回归确认：M1/M2 主链路测试仍通过（重点 chat/practice/diagnose）
3. 前端冒烟：frontend/ `npm run build` 通过
4. `docs/qa/test-report.md` 更新：M3 实测结果 + 三里程碑汇总

【技术选型（context7 已验证，直接用）】pytest + pytest-asyncio；httpx TestClient；mock 库 mock 上游。**实现前用 context7 核对 pytest/FastAPI TestClient 最新用法**（如需要），查询记录写进 comment。

【仓库约定】你写 backend/tests/、docs/qa/。可读 backend/ 和 frontend/ 代码但只加测试文件，不改业务代码（发现 bug 记录在案）。

【交付要求】完成后：`git add backend/tests docs/qa && git commit -m "test(qa): M3 图谱/突击/看板/排行/预警验收测试" && git push origin main`，卡片 comment 附提交 hash + pytest 汇总输出 + 三里程碑验收清单。
