# ADR-0002：LLM 分级调用 —— flash 快答 / pro 深度讲解

- **状态**：Accepted（M1 基线）
- **日期**：2026-08-07
- **决策者**：ep-arch（评审：ep-ai / ep-backend）

## 背景（Context）

AceExam 是创业项目，商业模式 Freemium 订阅制，**AI 调用成本直接影响毛利**（PRD §5）。AI 讲解、出题、诊断等场景质量要求差异大：简单题解析与 RAG 深度讲解对模型能力要求完全不同。全部用 pro 会导致成本失控；全部用 flash 会损害差异化核心（AI 讲解质量）。

## 决策（Decision）

1. **llm_gateway 统一入口**：所有 AI 服务只经 `LLMGateway.chat(model, ...)` 调用，禁止各自 new client；gateway 内置分级路由、重试降级、token 计量。
2. **按场景分级**（见 architecture.md §4.1 矩阵）：
   - **flash**：默认；简单题解析、追问、简单出题、诊断初筛 —— 覆盖 ~70% 调用量
   - **pro**：RAG 教材深度讲解、综合题/大题/写作题解析、综合出题、诊断报告 —— 质量关键场景
3. **路由规则**：默认 flash；`require_depth=true`（RAG 讲解/综合题/诊断）→ pro；`difficulty >= 4` 或题型 ∈ {essay, proof, writing, reading} → pro；支持 `subjects.config.llm_routing` 覆盖。
4. **成本控制配套**：
   - 讲解缓存表 `ai_explanations`（question_id + model + content_hash 唯一），命中零成本
   - RAG 上下文只带 top-5 chunk（≤2500 tokens），不做整书入 prompt
   - max_tokens 预算：flash ≤ 512、pro ≤ 2048（可配置）
   - token 计量日志（model/prompt/completion/cost_est）→ 月度看板
5. **降级策略**：pro 超时/失败 → 降级 flash 重试 1 次并打标（可用性优先）。

## 备选方案（Considered）

- **全部 pro**：质量稳但成本不可控，否决。
- **全部 flash**：差异化核心（AI 讲解）质量不足，否决。
- **无 gateway 各服务直连**：分级逻辑散落、无法统一计量，否决。

## 后果（Consequences）

- **正面**：成本可控（~70% flash）；计量数据支撑定价与预算；质量关键场景有 pro 兜底。
- **代价/风险**：分级路由规则需要维护（配置化降低硬编码）；降级路径可能导致质量波动，须在日志打标便于复盘；缓存表需清理策略（按题目内容 hash 失效）。

## 验收标准（Verification）

- [ ] llm_gateway 单例注入，rag/quiz/diagnosis 均经它调用
- [ ] 同一题二次讲解命中缓存（零 token 消耗）
- [ ] token 计量日志可聚合出"flash/pro 占比 + 月度成本估算"
