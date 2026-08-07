项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【前端工程师 ep-frontend】。

【你的任务】在 M1 uni-app 脚手架（已有 subjects/practice/chat/mine 四页面 + mock 数据 + Pinia + 请求封装）基础上，实现 M2 五件套页面并把 mock 切换为真实 API 对接。参照 ep-arch 的 docs/api.md 契约（若已存在）：
1. **智能刷题页**（practice）：M1 mock → 真实 API（GET /subjects/{id}/practice/questions 自适应选题）；提交答案 → POST /questions/{id}/answers；对错反馈 + "AI 讲解"入口；KaTeX 公式渲染
2. **AI 讲解页**（chat）：SSE 流式显示（POST /chat/explain + /chat/followup）；step-by-step 分步卡片（可折叠）；教材引用块 CitationBlock（教材名+章节+原文）；"还不懂？追问"输入框（对话式）
3. **拍照录题**（新页面，TabBar 中央凸起按钮入口）：拍照/相册选图 → POST /ocr/upload 上传 → 识别结果预览（Markdown/LaTeX，可编辑）→ 知识点归属（自动推荐+手动调整）→ POST /questions/from-ocr 确认入库
4. **诊断页**（新页面）：摸底自测（10 题快速定位）→ 提交 → 诊断报告展示（薄弱 Top5 + 建议）；薄弱知识点地图（P1 可简化先做列表）
5. **备考计划/今日任务**（首页升级）：考试科目 + 日期设置 → POST /plans 创建 → 首页今日任务卡片（倒计时 + 每日任务 + 打卡按钮）→ POST /plans/{id}/checkin
6. 请求层：token 注入（已有 uni.request 封装基础上补全）、错误处理（401 跳登录、网络错误 toast）

【技术选型（context7 已验证，直接用）】uni-app Vue3+Vite+TS；KaTeX（或 mp-html）渲染公式；Pinia；SSE 用 uni.request 流式或 EventSource 适配（小程序限制注意）。**实现前用 context7 核对 uni-app 最新 API**（`context7 query docs uni-app`），把查询记录写进 comment。

【仓库约定】你写 frontend/。ep-backend/ep-db/ep-ai 在 backend/，不要动。mock 数据保留在 frontend/src/mock/ 作为降级（API 未就绪时可用），但页面主路径走真实 API，mock 只做 fallback。

【交付要求】完成后：`git add frontend/ && git commit -m "feat(frontend): M2 五件套页面+真实API对接" && git push origin main`，卡片 comment 附提交 hash + 构建/运行输出（dev:h5 起来或 build 通过）+ context7 查询记录。
