项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【测试工程师 ep-qa】。

【你的任务】建立 M1 测试门禁（三层：单元 / API / 烟测），等 ep-backend（T3）和 ep-frontend（T4）交付后执行：
1. `backend/tests/` pytest 体系：
   - 单元层：auth（注册/登录/重复用户名）、LLM 网关（mock 上游：超时/错误/内容安全拦截）、RAG 检索（mock 向量库）
   - API 层（TestClient）：/healthz 200、注册→登录→带 token 访问 /me、未登录 401、subjects CRUD、questions 筛选、wrong-answers、chat（mock LLM）
   - 数据库层：用独立测试库（test_aceexam），conftest 建表+种子，测试后清理
2. `backend/tests/conftest.py`：测试数据库 fixture（独立 SQLite 或 PG test 库均可，环境变量控制）
3. 前端冒烟：frontend/ 至少 `npm run build` 通过（如环境具备 node，否则记录在案并跳过，注明原因）
4. `docs/qa/test-report.md`：测试报告模板 + 本 M1 实测结果（通过数/失败数/覆盖率要点）

【技术选型（context7 已验证，直接用）】pytest + pytest-asyncio（SQLAlchemy async）；httpx TestClient（FastAPI 自带）；mock 库 mock 上游 DeepSeek/Pix2Text（测试不真调 API）。

【仓库约定】你写 backend/tests/、docs/qa/。可读 backend/ 和 frontend/ 的代码但只加测试文件，不改业务代码（发现 bug 就在 test-report.md 记录缺陷，卡片 comment 里列出来）。

【交付要求】完成后：`git add backend/tests docs/qa && git commit -m "test(qa): M1 三层测试门禁+测试报告" && git push origin main`，卡片 comment 附提交 hash + pytest 汇总输出（N passed）。
