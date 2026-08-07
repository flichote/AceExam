项目：AceExam（大学生的 AI 备考教练，期末通关闭环：诊断→规划→练习→讲解→突击→复盘）。私有仓库，主干 main。你被分派为【架构师/技术负责人 ep-arch】。

【你的任务】输出 M1 的架构基线文档（这是全项目的事实来源，后续所有任务都依赖它）：
1. `docs/architecture.md`：
   - 系统模块划分（uni-app 客户端 / FastAPI 后端 / PG16+pgvector / DeepSeek / Pix2Text）
   - **科目模板设计**（关键！）：高数+英语两科并行，知识点图谱+题库+AI讲解三件套共用代码、仅内容不同，说明数据模型如何支持（subject 维度）
   - RAG 教材答疑管线方案（文档切块→embedding→pgvector 检索→DeepSeek 讲解→引用溯源）
   - LLM 分级调用设计（flash 快答 / pro 深度讲解，控成本）
   - API 路由规划（auth/subjects/knowledge-points/questions/chat/wrong-answers/plans）
   - 关键技术决策写成 ADR（至少 2 条：科目模板化、LLM 分级）
2. 把 M1 的里程碑拆解补充到 `docs/ops/M1-taskgraph.md`（如果已有任务图，检查并完善依赖）

【技术选型（context7 已验证，直接用）】PostgreSQL 16 + pgvector（VECTOR 列 + cosine_distance）；FastAPI 0.127.x；SQLAlchemy 2.x + Alembic；uni-app Vue3+Vite+TS；DeepSeek deepseek-v4-flash / deepseek-v4-pro；Pix2Text（ONNX 本地部署）。

【仓库约定】你只写 docs/ 目录。其他角色并行写 backend/、frontend/，不要动他们的目录。

【交付要求】完成后：`git add docs/ && git commit -m "docs(arch): M1 架构基线 + ADR" && git push origin main`，然后在卡片 comment 附提交 hash 和文档要点摘要。
