项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。私有仓库，主干 main。你被分派为【AI 工程师 ep-ai】（灵魂角色，负责产品差异化核心）。

【你的任务】实现 M1 AI 服务层骨架（建立在 ep-backend 的 LLM 网关之上）：
1. `backend/app/services/rag/`：RAG 讲解引擎骨架——
   - `doc_processor.py`：教材/课件文档切块（chunk 策略：按标题层级 + 段落，≤500 tokens）
   - `embedder.py`：调用 DeepSeek embedding API 生成向量（复用 llm_gateway 的客户端模式）
   - `retriever.py`：pgvector 相似度检索（cosine_distance，top-k=5，带分数阈值）
   - `rag_engine.py`：检索 → 组装上下文 → 调 LLM 生成讲解（带引用溯源，输出格式：[来源: 章节/页码]）
2. `backend/app/services/ocr_service.py`：Pix2Text 拍照录题集成（ONNX 本地推理，文字+公式混合识别 → 结构化题目；MVP 阶段给接口 + 简单实现 + 错误兜底）
3. `backend/app/services/quiz_generator.py`：AI 出题（薄弱知识点 → 生成练习题 + 解析；调 LLM 分级：简单题 flash、综合题 pro）
4. `backend/app/services/diagnosis.py`：薄弱点诊断（做题记录 → LLM 分析薄弱知识点 → 输出薄弱地图 JSON）
5. 单元测试：rag_engine 检索质量、quiz_generator 输出结构（backend/tests/test_ai_*.py）

【技术选型（context7 已验证，直接用）】DeepSeek deepseek-v4-flash（快/便宜，默认）与 deepseek-v4-pro（深度讲解）；pgvector cosine_distance；Pix2Text `recognize_text_formula()`（支持 ch_sim、公式混合、ONNX 本地部署零 API 费）；Embedding 维度与 pgvector VECTOR 列一致（以 DeepSeek embedding 模型为准，若不可用退化为文档关键词检索并在代码注释说明）。

【仓库约定】你写 backend/app/services/（rag/、ocr_service.py、quiz_generator.py、diagnosis.py）+ backend/tests/test_ai_*.py。复用 ep-backend 的 llm_gateway（import 方式，别改它）。不要动 frontend/。

【交付要求】完成后：`git add backend/app/services backend/tests && git commit -m "feat(ai): M1 RAG讲解引擎+OCR+出题+诊断骨架" && git push origin main`，卡片 comment 附提交 hash + 测试通过数 + RAG 检索示例输出。
