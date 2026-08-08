项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【测试工程师 ep-qa】。

【背景】产品需求调整：用户自选专业+课程，公共课放课程广场。等 ep-backend（T25）、ep-frontend（T26）交付后执行验收：
1. `backend/tests/` 新增测试（mock 上游）：
   - 专业：PUT /me/profile 更新 major、未登录 401
   - 选课：PUT /me/subjects 设置课程（幂等覆盖）、GET /me/subjects 返回自选课程+学习状态
   - 广场：GET /subjects/plaza 返回公共课 + 加入状态、未登录可看列表
   - 数据迁移：0004 迁移可执行（alembic upgrade head --sql 或等效）
2. 回归确认：现有 subjects/questions/practice 主链路不破坏
3. 前端冒烟：frontend/ `npm run build` 通过
4. `docs/qa/test-report.md` 更新：本改动实测结果

【技术选型】pytest + pytest-asyncio；httpx TestClient。**实现前用 context7 核对 pytest 最新用法**（如需要），查询记录写进 comment。

【仓库约定】你写 backend/tests/、docs/qa/。只加测试文件不改业务代码（发现 bug 记录在案）。

【交付要求】完成后：`git add backend/tests docs/qa && git commit -m "test(qa): 专业选课+课程广场验收测试" && git push origin main`，卡片 comment 附提交 hash + pytest 汇总 + 验收清单。
