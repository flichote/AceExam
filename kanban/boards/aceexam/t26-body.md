项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【前端工程师 ep-frontend】。

【背景】产品需求调整：首页改为「用户自选课程」，公共课放课程广场。参照 ep-arch 的 docs/api.md 契约（若已存在）：
1. **选课引导**（首次使用流程，登录后判断）：
   - 用户未填专业/未选课时，引导页：输入专业名称 → 从课程广场勾选本学期课程（或先跳过，后续可改）
   - 已有专业+课程则直接进首页
2. **首页改版**：
   - 顶部：今日任务/倒计时/打卡（保留现有）
   - 中部：「我的课程」= 用户自选课程列表（GET /me/subjects，含每科掌握度/进度）
   - 新增「课程广场」入口卡片（点击进广场）
   - 挂科预警/薄弱知识点保留
3. **课程广场页**（新页面）：
   - 公共课列表（GET /subjects/plaza），显示加入状态
   - 「加入课程」按钮 → PUT /me/subjects 更新用户课程
4. 「我的」页：增加专业显示 + 修改专业/课程入口
5. mock 降级保留

【技术选型】uni-app Vue3+Vite+TS；Pinia。**实现前用 context7 核对 uni-app 最新 API**，查询记录写进 comment。

【仓库约定】你写 frontend/。ep-backend 在 backend/，不要动。mock 放 frontend/src/mock/ 作降级。

【交付要求】完成后：`git add frontend/ && git commit -m "feat(frontend): 首页选课改造 + 课程广场" && git push origin main`，卡片 comment 附提交 hash + 构建输出 + context7 查询记录。
