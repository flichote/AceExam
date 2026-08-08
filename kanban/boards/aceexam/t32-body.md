项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【前端工程师 ep-frontend】。

【背景】M5「课程归一对齐 + 题库飞轮」（产品策略见 docs/product/题库策略.md，架构契约见 docs/architecture.md §14，API 契约见 docs/api.md §14）。ep-arch 已交付契约，你实现页面。M4 已把首页改为「我的课程 + 课程广场」，M5 在其上增强。

【你的任务】在 M4 页面基础上，实现 M5 页面。参照 ep-arch 的 docs/api.md §14 契约：
1. **校本课程录入**（14.3）：用户添加本学期课程时，支持自由录入校本课程名 → 调 POST /courses/match 联想匹配 → 展示候选（confidence 徽标 + reason）→ 一键确认（≥0.85 自动选中可改选；0.60~0.85 展示候选列表；<0.60 引导手动建实例）。录入后展示「已映射到模板课程」标识。
2. **课程广场按模板课展示**（14.1）：广场页显示模板课程（高等数学/大学英语…），搜索框联想别名（GET /courses/aliases），加入后到「我的课程」。
3. **题库共建入口**（14.5）：UGC 投稿页——从已有题目「报错纠错」或直接上传新题（含拍照 OCR 复用）；提交后显示「AI 初审中」状态，可查审核结果（GET /ugc/status）。
4. mock 保留在 `frontend/src/mock/` 做 fallback（后端未就绪时可演示）。

【技术选型】uni-app Vue3+Vite+TS（h5 + mp-weixin 双端）。**实现前用 context7 核对 uni-app 最新写法**（如 request 封装、页面生命周期），查询记录写进 comment。

【仓库约定】你只写 frontend/。不要动 backend/、docs/。

【交付要求】完成后：`git add frontend/ && git commit -m "feat(frontend): M5 课程录入 + 广场模板展示 + 题库共建" && git push origin main`，卡片 comment 附提交 hash、新增页面清单、`npm run build` 结果。
