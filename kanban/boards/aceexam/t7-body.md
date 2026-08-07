项目：AceExam（大学生的 AI 备考教练，期末通关闭环：诊断→规划→练习→讲解→突击→复盘）。私有仓库，主干 main。你被分派为【架构师/技术负责人 ep-arch】。

【你的任务】输出 M2 的架构增量文档（M1 已交付 docs/architecture.md + 3 条 ADR，本任务在其之上增量，不重写）：
1. 更新 `docs/architecture.md`：新增 M2 五件套的模块设计——
   - 智能刷题：自适应选题算法设计（MVP 规则版：薄弱知识点优先 + 错误率加权，明确加权公式，后续可替换 IRT/DKT）
   - AI 讲解：RAG 管线的真实化路径（M1 是骨架，M2 要说明教材上传→切块→embedding→pgvector 检索→DeepSeek 讲解→引用溯源的完整数据流，标注各步骤所在代码文件）
   - 拍照录题：Pix2Text OCR 集成设计（前端上传→后端 OCR 服务→结构化题目入库→知识点归属）
   - 薄弱诊断：诊断引擎设计（做题记录→LLM 分析→薄弱地图 JSON 结构）
   - 备考计划：规则引擎设计（倒计时+薄弱点→每日任务→打卡，plans/study_sessions 表怎么用）
2. 新增 `docs/api.md`：M2 API 契约（前后端对接的唯一依据）——
   - 每个端点：方法/路径/请求体/响应体（Pydantic schema 级别的字段定义）
   - 必须覆盖：选题（带自适应参数）、提交答案、AI 讲解（SSE 流式）、OCR 上传、诊断自测、诊断报告、计划创建、每日任务、打卡
   - 标注与 M1 已有端点的差异（新增/修改/废弃）
3. 更新 `docs/ops/M1-taskgraph.md` 或新增 `docs/ops/M2-taskgraph.md`：M2 任务图（T7~T12 依赖关系）

【技术选型（context7 已验证，直接用）】PostgreSQL 16 + pgvector；FastAPI 0.127.x；SQLAlchemy 2.x + Alembic；uni-app Vue3+Vite+TS；DeepSeek deepseek-v4-flash（快/便宜，默认）与 deepseek-v4-pro（深度讲解）；Pix2Text（ONNX 本地部署）。科目模板化：高数+英语共用代码仅内容不同（ADR-0001）。

【仓库约定】你只写 docs/。其他角色并行写 backend/、frontend/，不要动他们的目录。

【交付要求】完成后：`git add docs/ && git commit -m "docs(arch): M2 五件套架构增量 + API 契约" && git push origin main`，卡片 comment 附提交 hash 和文档要点摘要（API 端点总数、新增设计要点）。
