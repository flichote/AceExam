项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【前端工程师 ep-frontend】。

【你的任务】搭建 M1 uni-app 脚手架 + 三个核心页面（**mock 先行**：后端 API 未就绪就用本地 mock 数据，标注 TODO 对接点）：
1. frontend/ uni-app 项目（Vue3 + Vite + TypeScript），可 `npm run dev:h5` 跑起来
2. 三个页面：
   - 选科页（首页）：科目卡片列表（高数/英语），从 mock 读，设计成 API-ready（GET /api/v1/subjects 对接点）
   - 刷题页：题目展示 + 选项作答 + 对错反馈 + 查看解析；KaTeX 渲染数学公式（高数题必须有公式）；mock 题库
   - AI 对话页：聊天界面，输入问题 → 流式显示回答（SSE 对接点标注）；mock 回答先顶上
3. 底部 TabBar（选科 / 刷题 / 我的），状态管理（Pinia），请求封装（uni.request 统一拦截 + token 注入）
4. 视觉：主色 amber 橙（PRD 规定，橙=成功上岸），清爽学习风格，移动端优先

【技术选型（context7 已验证，直接用）】uni-app Vue3+Vite+TS；`uni -p h5` / `uni -p mp-weixin` 构建；uni-ui 组件；KaTeX（或 mp-html 插件）渲染公式；Pinia 状态管理。

【仓库约定】你写 frontend/。ep-backend/ep-db 在 backend/，不要动。mock 数据放 frontend/src/mock/。

【交付要求】完成后：`git add frontend/ && git commit -m "feat(frontend): M1 uni-app脚手架+三页面(mock先行)" && git push origin main`，卡片 comment 附提交 hash + 构建/运行输出（dev:h5 起来或 build 通过）。
