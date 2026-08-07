项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【AI 工程师 ep-ai】（灵魂角色，负责产品差异化核心）。

【你的任务】在 M1 AI 服务骨架（backend/app/services/ 已有 llm_gateway.py、rag/ 全套、ocr_service.py、diagnosis.py、quiz_generator.py）基础上，把 M2 五件套的 AI 能力做真做实：
1. **RAG 讲解引擎真实化**（backend/app/services/rag/）：
   - `doc_processor.py`：教材上传处理（切块：标题层级+段落，≤500 tokens）——补充 markdown/PDF 解析
   - `embedder.py`：DeepSeek embedding 生成向量（或退化关键词检索，代码注释说明）；维度与 pgvector VECTOR 列一致
   - `retriever.py`：pgvector cosine_distance 检索 top-k=5 + 分数阈值
   - `rag_engine.py`：检索→组装上下文→调 LLM 生成 step-by-step 讲解 + 引用溯源（[来源: 章节/页码]）；无引用命中时明确提示"教材未覆盖"，禁止凭空编造（ADR-0003）
2. **自适应选题**（backend/app/services/selection.py 新建）：薄弱知识点优先 + 错误率加权（MVP 规则版，公式见 docs/architecture.md；知识点状态：未接触/待巩固/已掌握/薄弱）
3. **OCR 服务**（backend/app/services/ocr_service.py）：Pix2Text 拍照录题——ONNX 本地推理，文字+公式混合识别（recognize_text_formula，支持 ch_sim）→ 结构化题目（题干/选项/答案/LaTeX 公式）→ 知识点归属自动推荐；识别失败兜底
4. **诊断引擎**（backend/app/services/diagnosis.py）：做题记录 → LLM 分析 → 薄弱地图 JSON（薄弱 Top5 + 每项建议）；自测结果可解释（与自测表现一致）
5. **AI 出题**（backend/app/services/quiz_generator.py）：薄弱知识点 → 生成练习题 + 解析（简单题 flash、综合题 pro）
6. 单元测试：selection 加权、rag_engine 检索质量（mock 向量库）、ocr 结果结构、diagnosis 输出 JSON schema（backend/tests/test_ai_*.py）

【技术选型（context7 已验证，直接用）】DeepSeek deepseek-v4-flash（快/便宜，默认）与 deepseek-v4-pro（深度讲解）——flash/pro 分级路由控成本（ADR-0002）；pgvector cosine_distance；Pix2Text `recognize_text_formula()`（ONNX 本地零 API 费）；KaTeX 渲染 LaTeX。**实现前用 context7 核对 Pix2Text 最新 API**（`context7 query docs pix2text`），把查询记录写进 comment。

【仓库约定】你写 backend/app/services/（rag/、selection.py、ocr_service.py、diagnosis.py、quiz_generator.py）+ backend/tests/test_ai_*.py。复用 ep-backend 的 llm_gateway（import 方式，别改它）。ep-backend 写 backend/app/api/，ep-db 写 backend/app/db/——不要动他们的目录。不要动 frontend/。

【交付要求】完成后：`git add backend/app/services backend/tests && git commit -m "feat(ai): M2 五件套 AI 服务真实化" && git push origin main`，卡片 comment 附提交 hash + 测试通过数 + RAG 检索示例输出 + context7 查询记录。
