项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【测试工程师 ep-qa】。

【你的任务】在 M1 测试门禁（backend/tests/ 已有 auth/LLM网关/RAG/API 测试 + docs/qa/test-report.md）基础上，为 M2 五件套建立端到端验收测试。等 ep-backend（T9）、ep-frontend（T11）交付后执行：
1. `backend/tests/` 新增测试（mock 上游 DeepSeek/Pix2Text，不真调 API）：
   - 智能刷题：自适应选题接口（薄弱知识点优先逻辑）、提交答案→knowledge state 更新（连续 3 次正确→已掌握）
   - AI 讲解：/chat/explain（mock RAG 检索：有引用命中/无命中兜底两条路径）、/chat/followup（上下文保持）
   - OCR：/ocr/upload + /questions/from-ocr（mock OCR 服务返回结构化题目；重复提交幂等）
   - 诊断：自测流程（发起→选题→提交→报告 JSON schema 校验：薄弱 Top5 + 建议）
   - 计划：创建→今日任务→打卡（重复打卡防抖）
2. 前端冒烟：frontend/ `npm run build` 通过（如环境具备 node，否则记录在案并注明原因）
3. `docs/qa/test-report.md` 更新：M2 实测结果（通过数/失败数 + 五件套逐项验收清单）
4. 缺陷记录：发现 bug 在 test-report.md 记录，卡片 comment 列出

【技术选型（context7 已验证，直接用）】pytest + pytest-asyncio；httpx TestClient（FastAPI 自带）；mock 库 mock 上游。**实现前用 context7 核对 pytest/FastAPI TestClient 最新用法**（如需要），把查询记录写进 comment。

【仓库约定】你写 backend/tests/、docs/qa/。可读 backend/ 和 frontend/ 代码但只加测试文件，不改业务代码（发现 bug 就记录，不修——修复由对应角色负责）。

【交付要求】完成后：`git add backend/tests docs/qa && git commit -m "test(qa): M2 五件套端到端验收测试" && git push origin main`，卡片 comment 附提交 hash + pytest 汇总输出（N passed）+ 五件套验收清单结果。
