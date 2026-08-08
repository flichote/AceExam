# AceExam 架构设计（M1 基线）

> **状态**：M5 增量 v1.5（2026-08-08）｜**作者**：ep-arch
> **定位**：本文件是系统设计的事实来源。需求唯一事实来源是 [PRD](./PRD.md)；视觉/交互见 [design/](./design/)；表结构与 API 契约分别以 [database](./database.md) 与 [api](./api.md) 为准（评审后锁定，变更走文档）。
> **配套决策**：关键技术决策固化在 [docs/adr/](../adr/)（ADR-0001 ~ 0003）。
> **M2 增量说明**：M1 基线（§1~§9）保持不动；MVP 五件套（智能刷题/AI 讲解/拍照录题/薄弱诊断/备考计划）的模块设计在 §10 增量追加，API 契约详版见 [docs/api.md](./api.md)。
> **M3 增量说明**：§10 五件套保持不动；体验增强与增长功能（知识点图谱可视化 / 考前突击模式 / 打卡连胜 / 学习数据看板 / 排行榜 / 挂科预警）的模块设计在 §11 增量追加；API 契约增量见 [docs/api.md](./api.md) §11；表结构增量由 T14 落地 [docs/database.md](./database.md) §9；任务图见 [docs/ops/M3-taskgraph.md](./ops/M3-taskgraph.md)。
> **M3.5 增量说明**：§11 保持不动；M3 剩余功能（语音讲解 TTS / UGC 题库共建 / 成绩单海报分享 / 班级排行榜）的模块设计在 §12 增量追加；API 契约增量见 [docs/api.md](./api.md) §12；表结构增量由 T20 落地 [docs/database.md](./database.md) §10；任务图见 [docs/ops/M3.5-taskgraph.md](./ops/M3.5-taskgraph.md)。
> **M4 增量说明**：§12 保持不动；用户反馈驱动的产品调整（用户自填专业 + 自选本学期课程，公共课独立为课程广场）的模块设计在 §13 增量追加；API 契约增量见 [docs/api.md](./api.md) §13；表结构增量由 T25 落地 [docs/database.md](./database.md) §11（迁移 `0005_user_major_plaza`，修正 T25 body 中的 0004 编号冲突）；任务图见 [docs/ops/M4-taskgraph.md](./ops/M4-taskgraph.md)。
> **M5 增量说明**：§13 保持不动；产品策略落地的两件事（课程三级归一对齐：校本课程实例 → AI 映射模板课程；题库飞轮：UGC 拍照录题 + AI 初审管线 + 行为数据反哺）的模块设计在 §14 增量追加；API 契约增量见 [docs/api.md](./api.md) §14；表结构增量由 T29 落地 [docs/database.md](./database.md) §12（迁移 `0006_course_alias_level`）；任务图见 [docs/ops/M5-taskgraph.md](./ops/M5-taskgraph.md)。

---

## 0. 文档地图（事实来源层级）

| 文档 | 内容 | 状态 |
|---|---|---|
| `docs/PRD.md` | 需求唯一事实来源（功能分层/核心闭环/题库策略） | v0.1 已定 |
| `docs/design/*` | 页面地图 / 设计系统 / 组件 / 交互流程 | 已定 |
| **`docs/architecture.md`（本文）** | 系统模块划分、科目模板、RAG 管线、LLM 分级、API 骨架、ADR 索引、M2 五件套 + M3 图谱/突击/看板/排行/预警 + M3.5 TTS/UGC/海报/班级 + M4 专业选课/课程广场 + M5 课程归一对齐/题库飞轮模块设计 | **M5 增量 v1.5** |
| `docs/database.md` | 表结构（M1 基线；M2 §8 / M3 §9 / M3.5 §10 / M4 §11 / M5 §12 增量） | M1 锁定，M2 §8 已交付，M3 §9 已交付，M3.5 §10 由 T20，M4 §11 由 T25，M5 §12 由 T29 |
| `docs/api.md` | API 契约详版（Pydantic 级字段定义 + 各里程碑差异表） | **M5 v1.3（52 端点）** |
| `docs/ops/M1-taskgraph.md` | M1 里程碑任务图与启动手册 | 已存在，T1 完善 |
| `docs/ops/M2-taskgraph.md` | M2 里程碑任务图（T7~T12） | T7 产出 |
| `docs/ops/M3-taskgraph.md` | M3 里程碑任务图（T13~T18） | T13 产出 |
| `docs/ops/M3.5-taskgraph.md` | M3.5 里程碑任务图（T19~T23） | T19 产出 |
| `docs/ops/M4-taskgraph.md` | M4 任务图（T24~T27：专业选课 + 课程广场） | T24 产出 |
| `docs/ops/M5-taskgraph.md` | M5 任务图（T28~T33：课程归一对齐 + 题库飞轮） | T28 产出 |

**规则**：接口契约（API 字段、表结构）由 ep-arch 评审后锁定；任何变更必须同步修改本文档 + 对应交付文档，禁止只改代码。

---

## 1. 系统模块划分

### 1.1 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│  客户端 uni-app（Vue3 + Vite + TS）                            │
│  ┌──────────┬──────────┬──────────┬──────────┬─────────────┐ │
│  │ 首页      │ 刷题      │ 诊断      │ 我的      │ 拍照录题    │ │
│  │ (计划/打卡)│ (题卡+讲解)│ (自测/图谱)│ (看板/会员)│ (OCR modal)│ │
│  └──────────┴──────────┴──────────┴──────────┴─────────────┘ │
│  · KaTeX 公式渲染组件（统一走 KaTeX，禁止图片代公式）            │
│  · 请求层：api client + token 注入 + 错误兜底                   │
└───────────────┬──────────────────────────────────────────────┘
                │ HTTPS / JSON
┌───────────────▼──────────────────────────────────────────────┐
│  FastAPI 0.127.x（backend/）                                  │
│  ┌─────────── 路由层（/api/v1）────────────────────────────┐  │
│  │ auth · subjects · knowledge-points · questions · chat  │  │
│  │ wrong-answers · plans · diagnosis · ocr · healthz       │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────── 服务层 ──────────────────────────────────────┐  │
│  │ llm_gateway（分级调用+计量）  rag/（切块/embed/检索/生成）│  │
│  │ ocr_service（Pix2Text ONNX）  quiz 选题（自适应规则版）  │  │
│  │ diagnosis（薄弱点诊断）       plan（备考计划规则引擎）   │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────── 数据层（SQLAlchemy 2.x + Alembic）───────────┐  │
│  │ 关系表：users/subjects/knowledge_points/questions/       │  │
│  │         wrong_answers/plans/study_sessions/...           │  │
│  │ 向量表：question_embeddings / document_chunks            │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────┬──────────────────────────────────────────────┘
                │
┌───────────────▼───────────────┐   ┌──────────────────────────┐
│ PostgreSQL 16 + pgvector      │   │ 外部 AI 服务              │
│ · VECTOR(1024) 列 + cosine    │   │ · DeepSeek flash/pro      │
│ · 题库/图谱/向量一体           │   │ · DeepSeek Embedding API  │
└───────────────────────────────┘   │ · Pix2Text（自部署 ONNX） │
                                    └──────────────────────────┘
```

### 1.2 模块清单

| 模块 | 归属 | 职责 | 关键接口/产物 |
|---|---|---|---|
| 客户端 `frontend/` | ep-frontend | 页面、组件、状态、请求层 | uni-app Vue3+Vite+TS；页面见 `docs/design/pages.md` |
| 后端 API `backend/app/api/` | ep-backend | 路由、鉴权、参数校验、错误码 | 见 §6 API 路由规划 |
| LLM 网关 `backend/app/services/llm_gateway.py` | ep-backend | DeepSeek flash/pro 统一调用、分级路由、计量、重试 | `chat(model, messages, ...)` |
| RAG 引擎 `backend/app/services/rag/` | ep-ai | 切块→embedding→pgvector 检索→生成讲解（带引用） | `doc_processor / embedder / retriever / rag_engine` |
| OCR 服务 `backend/app/services/ocr_service.py` | ep-ai | Pix2Text 拍照录题（文字+公式混合） | `recognize(image) -> {markdown, latex, text}` |
| 选题算法 `quiz` | ep-ai | 薄弱知识点优先 + 错误率加权（MVP 规则版） | 见 PRD §3 / TBD 加权公式 |
| 诊断引擎 `diagnosis.py` | ep-ai | 自测记录 → LLM 薄弱点分析 → 薄弱地图 JSON | 见 `docs/design/flows.md` 流程 3 |
| 数据层 `backend/app/db/` + `backend/alembic/` | ep-db | 表结构、迁移、种子数据 | `docs/database.md` |
| 部署运维 `docker-compose.yml` | 运维（复用 CCN devops） | 单机 4C8G：FastAPI + Pix2Text + PG16 | `docs/ops/README.md`（规划中） |

### 1.3 关键设计原则

1. **科目是一等公民**：内容类实体全部带 `subject_id`，代码层抽"科目模板"，新增科目只加数据/配置（ADR-0001）。
2. **AI 讲解必须可溯源**：一律走 RAG，无引用命中明确提示"教材未覆盖"，禁止凭空编造（ADR-0003，硬性约束）。
3. **成本分级**：flash 快答 / pro 深度讲解，llm_gateway 统一路由 + 缓存 + 计量（ADR-0002）。
4. **文档先行**：接口契约先锁文档，代码实现与文档同步变更。
5. **mock 先行**：前端可并行用 mock 数据开发，不阻塞等后端。

---

## 2. 科目模板设计（核心）

> 目标：高数 + 英语两科并行，**知识点图谱 + 题库 + AI 讲解三件套共用代码、仅内容不同**；未来线代/概率论/大物/专业课按同一模板扩展，边际成本低。

### 2.1 概念：科目 = 数据维度 + 配置维度

"科目模板"不是代码继承，而是**数据模型的一个维度（subject_id）+ 一份科目级配置（subjects.config）**：

- **数据维度**：`knowledge_points`、`questions`、`document_chunks`（教材向量）、`question_embeddings` 全部带 `subject_id` 外键 → 两科数据物理隔离、逻辑同构。
- **配置维度**：`subjects.config`（JSONB）承载科目级差异 —— prompt 模板、题型枚举、默认难度、公式开关、章节结构等。

### 2.2 数据模型如何支持（subject 维度贯穿）

```
subjects
├── id, code (e.g. 'math_gaoshu' / 'eng_college'), name, description
├── is_active, sort_order
└── config JSONB          -- 科目模板配置（见 2.4）

knowledge_points          -- 知识点图谱（树形，按科目隔离）
├── id, subject_id FK, parent_id FK(自引用), name, content
├── level(章/节/知识点), sort_order
└── UNIQUE(subject_id, parent_id, name)

questions                 -- 题库（按科目隔离）
├── id, subject_id FK, knowledge_point_id FK
├── type(单选/多选/填空/大题；英语可扩展 阅读/完型/写作)
├── content TEXT(题干, 含 LaTeX), options JSONB, answer JSONB, analysis TEXT
├── difficulty(1-5), source(教材/真题/自建/UGC), status
└── INDEX(subject_id, knowledge_point_id, difficulty)

question_embeddings       -- 题目向量（用于相似题召回/去重）
└── id, question_id FK, subject_id FK, embedding VECTOR(1024), model, content_hash

document_chunks           -- 教材/课件向量（RAG 语料，按科目隔离）
├── id, subject_id FK, source(教材名), chapter, section, page
├── chunk_text TEXT, embedding VECTOR(1024), meta JSONB, content_hash
└── INDEX(subject_id) + 向量索引（HNSW/IVFFlat，T2 定）

wrong_answers             -- 错题本（用户维度）
└── id, user_id FK, question_id FK, subject_id FK, wrong_answer, wrong_reason,
    review_count, mastered, created_at
```

> 表结构细节、索引类型、VECTOR 维度以 **T2 的 `docs/database.md`** 为准（评审后锁定）。此处只锁定"subject 维度贯穿"这一结构约束。

### 2.3 三件套共用代码边界

| 能力 | 高数 | 英语 | 共用代码（仅内容/配置不同） |
|---|---|---|---|
| 知识点图谱 | 章→节→知识点（极限/导数/积分…） | 技能→题型→考点（听力/阅读/写作…） | 树形 CRUD、掌握度计算、薄弱地图渲染（`knowledge_points` 表同构） |
| 题库 | 公式题、证明题、计算题 | 词汇/语法/阅读/写作题 | 选题算法、刷题流程、错题本（`questions` 表同构，`type` 枚举按科目配置扩展） |
| AI 讲解 | 分步推导、公式演算 | 语法解析、阅读定位、写作点评 | 同一 RAG 管线 + `llm_gateway`；仅 prompt 模板不同（从 `subjects.config` 读取） |

**不因科目分支的代码**：路由、服务层、数据层、前端页面组件 —— 全部按 subject_id 参数化。前端在选科后携带科目上下文（`currentSubject`），所有列表/刷题请求带 `subject_id`。

### 2.4 科目级配置（subjects.config JSONB 草案）

```jsonc
{
  "prompt_templates": {
    "explain": "你是{subject_name}助教…请基于引用教材分步讲解…",
    "diagnosis": "根据做题记录分析薄弱知识点…",
    "quiz": "围绕知识点{name}出一道{difficulty}难度题…"
  },
  "question_types": ["single", "multi", "blank", "essay"],   // 英语可加 "reading","cloze","writing"
  "default_difficulty": 3,
  "formula_enabled": true,      // 高数 true；英语 false（节省渲染开销）
  "chapters": ["第1章 函数与极限", "第2章 导数与微分", "..."],
  "exam": {"duration_min": 120, "total_score": 100}
}
```

> 配置项在 M1 只落地 prompt_templates + question_types + formula_enabled 三个最小字段，其余留 TBD。

### 2.5 新增科目流程（模板化验证）

1. `subjects` 插一行（code/name/config）
2. `knowledge_points` 按该科图谱灌数据（T2 种子脚本模式）
3. `questions` 灌初始题库
4. `document_chunks` 灌该科教材语料（触发 embedding 任务）
5. **零后端代码改动**；仅当出现全新题型交互（如英语听力播放）才需前端扩展组件 —— 该情况在模板外显式评审

---

## 3. RAG 教材答疑管线

> 目标：AI 讲解基于用户教材回答，**可溯源、不编造**。硬性约束见 ADR-0003。

### 3.1 管线总览

```
教材/课件（PDF/Markdown/扫描）
  │ ① 文档切块 doc_processor（按标题层级+段落，≤500 tokens）
  ▼
document_chunks（带 subject_id + 章节/页码元数据）
  │ ② embedding embedder（DeepSeek Embedding API → VECTOR(1024)）
  ▼
pgvector 向量库（HNSW/IVFFlat 索引，cosine_distance）
  │ ③ 检索 retriever（top-k=5 + 相似度阈值 0.75）
  ▼
上下文组装（chunk 原文 + 引用元数据）
  │ ④ 生成 rag_engine（DeepSeek pro，强制结构化引用输出）
  ▼
讲解响应：{steps: [...], citations: [{source, chapter, section, page, snippet}], followup_session_id}
  │
  ▼
前端 CitationBlock 渲染（教材名+章节+原文片段）
```

### 3.2 文档切块（doc_processor）

- **输入**：PDF（Pix2Text PDF→Markdown 能力）/ Markdown / 手动录入文本
- **策略**：先按标题层级（# → ## → ###）分节，再按段落切，单块 ≤ 500 tokens（约 1200 汉字）；保留元数据 `{source, chapter, section, page}`；块间重叠 1 句（防止切点截断语义）
- **去重**：`content_hash`（正文 hash）防重复入库
- **产出**：写入 `document_chunks`，随后触发 embedding

### 3.3 Embedding（embedder）

- 调用 DeepSeek Embedding API，维度以模型返回为准；**T2 基线用 VECTOR(1024)**，若模型维度不同则迁移调整（写进 T2 的 ADR/README 说明）
- **降级策略**（T5 骨架必须含）：若 Embedding API 不可用 → 退化为关键词检索（`chunk_text` 的 tsvector/GIN 或 ILIKE），代码注释说明；M1 可先降级跑通再补向量
- embedding 任务走后台队列（M1 用 FastAPI BackgroundTasks 即可），不入请求热路径

### 3.4 pgvector 检索（retriever）

- 查询向量 = 题目 content + 用户追问 的 embedding
- SQL：`ORDER BY embedding <=> :query_vec LIMIT 5`（cosine_distance，`<=>` 运算符）
- **阈值**：相似度 < 0.75 视为无命中 → 进入兜底（§3.6）；分数同时返回给前端（CitationBlock 可展示"相关度"）
- **过滤**：必须带 `subject_id = 当前科目`（科目模板隔离）

### 3.5 讲解生成与引用溯源（rag_engine）

- 组装上下文：top-5 chunk 原文（带元数据）按相似度排序进 prompt；prompt 明确要求"只依据引用内容讲解，未覆盖部分明说不知道"
- **输出结构**（JSON，非自由文本）：
  ```json
  {
    "steps": [{"title": "理解题意", "content": "..."}],
    "conclusion": "...",
    "citations": [{"source": "高等数学（同济第七版）", "chapter": "第2章 导数与微分", "section": "2.3 求导法则", "page": "78", "snippet": "…原文片段…"}],
    "uncovered": false
  }
  ```
- 讲解缓存：`(question_id, model, content_hash)` → 命中直接返回（省 token，ADR-0002）
- 追问：`followup_session_id` 挂会话（chat_sessions 表，保留最近 N 轮上下文）

### 3.6 兜底与质量保障

| 场景 | 行为 |
|---|---|
| 无引用命中（相似度 < 阈值） | `uncovered: true`，前端显示"教材未覆盖该知识点"，给出通用讲解但不伪装引用 |
| OCR 识别为空/模糊 | 引导重拍 / 手动录入（`docs/design/flows.md` 流程 2） |
| chunk 检索质量差 | T5 提供 RAG 质量评估脚本（ep-qa 配合），阈值可调 |
| 用户上传教材缺失 | 引导先上传教材（M2 会员功能） |

---

## 4. LLM 分级调用设计

> 目标：flash 快答（便宜）覆盖高频低价值调用，pro 深度讲解（贵）只在质量关键场景用。成本控制是创业项目生死线（ADR-0002）。

### 4.1 分级矩阵

| 场景 | 模型 | 理由 | 触发方 |
|---|---|---|---|
| 简单题/概念题解析（闪答） | **flash** | 单轮、答案短、质量要求低 | chat/explain |
| 复杂题/大题/综合题解析 | **pro** | 需要分步推导、质量要求高 | chat/explain（按题目 difficulty/type 路由） |
| RAG 教材深度讲解 | **pro** | 产品差异化核心，必须高质量 | chat/explain（默认） |
| 追问（对话式） | **flash** | 多轮闲聊式、上下文在会话里 | chat/followup |
| AI 出题-简单题 | **flash** | 批量生成、结构简单 | quiz_generator |
| AI 出题-综合题 | **pro** | 结构复杂、要区分度 | quiz_generator |
| 薄弱点诊断分析 | **pro** | 输出驱动备考计划，质量关键 | diagnosis |
| 诊断初筛/话题归类 | **flash** | 结构化低风险 | diagnosis（可选） |

**路由规则（llm_gateway 内置，可按 subject/config 覆盖）**：
- 默认 flash；`require_depth=true`（RAG 讲解、综合题、诊断报告）→ pro
- 题目维度：`difficulty >= 4` 或 `type in (essay, proof, writing, reading)` → pro
- 配置化：`subjects.config.llm_routing` 可覆盖该科目默认

### 4.2 成本控制策略

1. **分级路由**（§4.1）：flash 覆盖 ~70% 调用量
2. **讲解缓存**：`ai_explanations` 表（question_id + model + content_hash 唯一），命中零成本
3. **上下文裁剪**：RAG 只带 top-5 chunk（≤ 2500 tokens 上下文），不整书入 prompt
4. **max_tokens 预算**：flash ≤ 512、pro ≤ 2048（可按场景配置）
5. **计量**：llm_gateway 每次调用记 `token_usage` 日志/表（model, prompt_tokens, completion_tokens, cost_est）→ 月度看板（`docs/ops/README.md` 成本监控）
6. **重试与降级**：pro 超时/失败 → 降级 flash 重试 1 次并打标（保证可用性优先于质量）

### 4.3 llm_gateway 抽象（T3 交付，T5 复用）

```python
# backend/app/services/llm_gateway.py（接口草案）
class LLMGateway:
    def chat(self, model: Literal["flash", "pro"], messages: list[dict],
             max_tokens: int = 512, temperature: float = 0.3,
             require_depth: bool = False, **kw) -> ChatResult:
        # 分级路由 + 重试降级 + token 计量日志
        ...
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...
```

- 单例注入；所有 AI 服务（rag/quiz/diagnosis）只 import 它，不各自 new client
- **ep-ai 不得修改 llm_gateway**，只 import 复用（T5 body 已约定）

---

## 5. API 路由规划（骨架）

> 前缀统一 `/api/v1`。字段级契约由 T3 落地后回填 `docs/api.md`，此处锁定**路由结构与职责边界**。鉴权：JWT（access + refresh），游客白名单路由除外。

| 模块 | 路由 | 方法 | 职责 | 鉴权 |
|---|---|---|---|---|
| auth | `/auth/register` | POST | 注册（username/password_hash） | 公开 |
| | `/auth/login` | POST | 登录 → JWT | 公开 |
| | `/auth/me` | GET | 当前用户 + 会员状态 | 登录 |
| subjects | `/subjects` | GET | 科目列表（is_active） | 公开 |
| | `/subjects/{id}` | GET | 科目详情 + 统计（题数/掌握度概览） | 登录 |
| knowledge-points | `/knowledge-points` | GET | 知识点列表（?subject_id=&parent_id=） | 登录 |
| | `/knowledge-points/tree` | GET | 全科目图谱树（诊断地图用） | 登录 |
| questions | `/questions` | GET | 题单（?subject_id=&knowledge_point_id=&difficulty=&page=） | 登录 |
| | `/questions/{id}` | GET | 题目详情（含解析；作答前不返回 answer） | 登录 |
| | `/questions/{id}/submit` | POST | 提交作答 → 对错 + 错题入库 | 登录 |
| | `/questions/next` | GET | 自适应下一题（?subject_id=&knowledge_point_id=，规则版选题） | 登录 |
| chat | `/chat/explain` | POST | 请求 AI 讲解（{question_id, followup?}）→ steps+citations | 会员 |
| | `/chat/followup` | POST | 追问（{session_id, message}） | 会员 |
| wrong-answers | `/wrong-answers` | GET | 错题本（?subject_id=&status=，按知识点分组） | 登录 |
| | `/wrong-answers/{id}` | DELETE | 移除错题 | 登录 |
| | `/wrong-answers/{id}/mastered` | POST | 标记已掌握 | 登录 |
| plans | `/plans` | POST | 生成备考计划（诊断结果 + 考试日期） | 会员 |
| | `/plans/today` | GET | 今日任务 + 打卡状态 | 登录 |
| | `/plans/checkin` | POST | 打卡（乐观锁防重复） | 登录 |
| diagnosis | `/diagnosis/self-test` | POST | 提交摸底自测（10 题答案） | 登录 |
| | `/diagnosis/report` | GET | 薄弱 Top5 报告 + 建议 | 登录 |
| ocr | `/ocr/recognize` | POST | 上传图片 → Pix2Text 识别结果（可编辑） | 登录（免费限量/会员不限） |
| health | `/healthz` | GET | 存活探针（含 DB/pgvector 连通性） | 公开 |

> ⚠️ **M2 增量**：本节为 M1 骨架（含部分规划未落地路由）。M2 五件套端点契约与 M1/M2 差异（新增/修改/废弃）**以 [docs/api.md](./api.md) 为准**——主要变化：`/questions/next`（规划）→ `GET /subjects/{id}/practice/questions`；`POST /questions/{id}/submit`（M1）→ `POST /questions/{id}/answers`（完整作答链路）；`/diagnosis/*`（规划）→ `/diagnose/*`；`/ocr/recognize`（规划）→ `/ocr/upload`；`/plans/today`（规划）→ 并入 `GET /plans/active`。详见 api.md §10 差异表。

**契约要点**：
- 所有带 subject 语义的列表接口必须支持 `subject_id` 过滤（科目模板约束）
- `questions/{id}` 作答前不返回 `answer`/`analysis`；提交后才随反馈返回
- 错误码统一 `{code, message, detail?}`；分页统一 `{items, total, page, page_size}`
- 幂等：`submit`/`checkin`/`ocr` 支持 `Idempotency-Key` 头（`docs/design/flows.md` 跨流程约束）

---

## 6. 关键技术决策（ADR 索引）

| # | 决策 | 状态 | 文件 |
|---|---|---|---|
| ADR-0001 | 科目模板化：subject 作为一等数据维度，三件套共用代码 | Accepted（M1） | [0001-subject-template.md](../adr/0001-subject-template.md) |
| ADR-0002 | LLM 分级调用：flash/pro 按场景路由 + 缓存 + 计量 | Accepted（M1） | [0002-llm-tiering.md](../adr/0002-llm-tiering.md) |
| ADR-0003 | RAG 引用溯源为硬约束：AI 讲解必须可溯源，禁止编造 | Accepted（M1） | [0003-rag-citation.md](../adr/0003-rag-citation.md) |

---

## 7. 模块边界与仓库约定

| 目录 | 归属角色 | 说明 |
|---|---|---|
| `docs/` | ep-arch + 各角色文档 | T1 只写 docs/；T2 写 docs/database.md；接口契约评审后锁定 |
| `backend/` | ep-backend（主）+ ep-db（alembic/db 子目录）+ ep-ai（services/、tests） | 各角色按 T 任务 body 约定子目录，互不越界 |
| `frontend/` | ep-frontend | uni-app 工程，mock 先行 |
| `kanban/boards/aceexam/` | 主控 | 任务 body 文件，随仓库走 |

**协作纪律**：
- 接口契约（API 字段/表结构）由 ep-arch 评审锁定；变更必须更新文档 + 相关任务 body 同步
- 同一 profile 不并行两个任务（防 git 冲突）
- 提交规范：`<type>(<scope>): <中文描述>`，如 `docs(arch): M1 架构基线 + ADR`

---

## 8. 非功能性设计要点

- **部署**：Docker Compose 单机（4C8G）：FastAPI + Pix2Text（ONNX）+ PG16（pgvector）；复用 CCN/RehabFlow 经验（`docs/ops/README.md`）
- **并发**：打卡/进度写操作乐观锁；OCR 请求限流（免费用户限量）
- **安全**：JWT；密码 bcrypt；`.env` 不入库；私有仓库
- **可观测**：llm_gateway token 计量；`/healthz` 探针；日志结构化（M1 最小集：请求日志 + AI 调用日志）

---

## 9. 开放问题（TBD）

- [x] ~~自适应选题 MVP 规则版的具体加权公式~~ → 已定，见 §10.1（MVP 规则版 + 后续 IRT/DKT 替换路径）
- [x] ~~引用溯源 UI 形态细节~~ → CitationBlock（教材名+章节+原文片段+相关度），design/components.md 已定
- [x] ~~OCR 识别失败/手写题的兜底流程~~ → 已定，见 §10.3（failed 状态 + 手动录入/重拍）
- [ ] VECTOR 维度最终确认（DeepSeek Embedding 模型返回维度 vs 基线 1024）——仍待 embedding 实测
- [ ] 英语听力题型的交互扩展（是否 M3 纳入）
- [ ] 教材语料版权与来源（M1 先内置公共教材公开内容 + 用户上传；M2 教材上传落地后需评估审核）
- [ ] IRT/DKT 替换节奏与数据门槛（M3 评估：需积累每知识点 ≥ N 条作答数据）

---

## 10. M2 增量：MVP 五件套模块设计

> 本节是 M2 的模块级设计，在 M1 基线上增量追加（§1~§9 不重写）。**接口契约（字段级）以 [docs/api.md](./api.md) 为准；表结构变更以 [docs/database.md](./database.md)（T8 增量）为准。**
> 五件套对应 PRD §3 第一层：智能刷题 / AI 讲解 / 拍照录题 / 薄弱诊断 / 备考计划。

### 10.1 智能刷题：自适应选题算法（MVP 规则版）

**数据基础**：`user_knowledge_states`（status / correct_count / wrong_count / last_practiced_at，M2 新增 streak 字段，见 §10.6）+ `questions`（knowledge_point_id / difficulty）+ `subjects.config`（default_difficulty、selection_weights）。

**知识点状态机**（沿用 database.md §3.4，M2 补 streak）：

| status | 进入条件 | 离开条件 |
|---|---|---|
| `untouched` 未接触 | 初始 | 首次做题 |
| `consolidating` 待巩固 | 正确率 40%~70% | 连续 3 次正确 → mastered |
| `weak` 薄弱 | 正确率 < 40% | 连续 3 次正确 → mastered |
| `mastered` 已掌握 | streak ≥ 3 | 错误率回升 → consolidating/weak |

- 正确率 p = correct_count / (correct_count + wrong_count)（无作答记录按未接触处理）
- **streak（连续正确次数）**：M2 新增列；答对 +1，答错归 0；streak ≥ 3 且状态非 mastered → 置 mastered。状态机切换由提交答案服务统一维护（T9 路由调 T10 的 `knowledge_state.apply_answer()`，避免两处实现分叉）。

**打分公式（MVP 规则版，明确锁定）**：

```
score(kp) = 50·status_factor(status)
           + 35·error_factor(kp)
           + 10·recency_factor(kp)
           + 5·difficulty_factor(q)

status_factor:  weak=1.0, consolidating=0.6, untouched=0.35, mastered=0.05
error_factor:   (wrong_count+1) / (correct_count+wrong_count+2)   # Laplace 平滑，0~1
recency_factor: min(days_since_last_practice, 7) / 7              # 0~1；从未练习按 7 天（满分）
difficulty_factor: max(0, 1 - |q.difficulty - target_diff| / 4)   # target_diff 取 subject.config.default_difficulty
```

- 默认权重 (50, 35, 10, 5) 可通过 `subjects.config.selection_weights = {status, error, recency, difficulty}` 按科目覆盖（ADR-0001 配置维度）
- **选题流程**：
  1. 取该科目全部叶子知识点 + 用户状态快照
  2. 计算 score 降序；按 `探索率 ε=0.3`：70% 概率从 top-k（weak/consolidating）出题，30% 从其余知识点随机（防过拟合、防只刷薄弱点疲劳）
  3. 知识点确定后，题池 = `questions WHERE knowledge_point_id=:kp AND status='active'`；同知识点内按 difficulty_factor 排序取题；`exclude_ids`（前端传已展示题）过滤当前会话重复
  4. 题型混合按 `subjects.config.question_types` 比例（避免连续同题型）
  5. 返回 `items + strategy`（命中的知识点/分数/权重元数据，前端可展示"本次优先：洛必达法则"——可解释性）
- **自测选题**（供诊断用，独立函数）：分层抽样——各章（level=1）至少 1 题，剩余按薄弱 score 加权补足 count；保证覆盖主要章节（flows.md 流程 3 验收点）
- **可替换性**：选题内核收敛在 `backend/app/services/selection.py` 的纯函数 `select_questions()` / `select_self_test_questions()`（输入 = 知识点状态 + 题库快照，输出 = 题序）；后续 IRT/DKT 只替换 scorer 内核，API 与表结构不动。streak 字段为 IRT 预留状态增量。
- **代码文件**：`backend/app/services/selection.py`（T10 交付）；`backend/app/services/subject_config.py`（T10 交付，读取 subjects.config 的辅助函数，T9 复用）；路由 `backend/app/api/v1/questions.py`（T9，调用 selection 服务；若 T10 未交付，T9 先按本公式内联兜底实现，T10 落地后替换，禁止双实现长期并存）。

### 10.2 AI 讲解：RAG 管线真实化路径（M2）

> M1 只交付 RAG 骨架（chat 端点直接 prompt 题目、citations 恒为空）。M2 打通「教材上传 → 切块 → embedding → pgvector 检索 → DeepSeek 讲解 → 引用溯源」完整数据流，硬约束见 ADR-0003。

**数据流（各步骤代码文件标注）**：

| # | 步骤 | 说明 | 代码文件（归属） |
|---|---|---|---|
| ① | 教材/课件上传 | `POST /subjects/{subject_id}/textbooks`（multipart；PDF/Markdown；M2 会员功能）。写入 `textbook_uploads`（T8 表）并触发切块后台任务 | `backend/app/api/v1/textbooks.py`（T9） |
| ② | 切块 | 按标题层级（#→##→###）+ 段落切，单块 ≤ 500 tokens（约 1200 汉字），块间重叠 1 句；保留 `{source, chapter, section, page}` 元数据；`content_hash` 去重 → 写 `document_chunks` | `backend/app/services/rag/doc_processor.py`（T10） |
| ③ | embedding | DeepSeek Embedding API → `VECTOR(1024)` 写 embedding 列；API 不可用 → 降级关键词检索（chunk_text ILIKE/tsvector），代码注释标明（database.md §6 约定）；后台任务执行，不入请求热路径 | `backend/app/services/rag/embedder.py`（T10） |
| ④ | pgvector 检索 | `ORDER BY embedding <=> :qvec LIMIT 5`（cosine_distance）+ 相似度阈值 0.75；查询向量 = embed(题目 content + 用户追问)；**必须带 subject_id 过滤**（ADR-0001 防串科） | `backend/app/services/rag/retriever.py`（T10） |
| ⑤ | 上下文组装 | top-5 chunk 原文（带元数据）按相似度排序拼 prompt（≤ 2500 tokens，成本控制 ADR-0002） | `backend/app/services/rag/rag_engine.py`（T10） |
| ⑥ | 生成讲解 | llm_gateway（RAG 讲解默认 **pro**）→ 强制结构化 JSON `{steps, conclusion, citations, uncovered}`；prompt 明确"只依据引用内容讲解，未覆盖部分明说不知道" | `backend/app/services/rag/rag_engine.py`（T10）+ `llm_gateway.py`（M1，import 复用） |
| ⑦ | 缓存 | `ai_explanations`（question_id + model + content_hash 唯一）命中零成本返回 | 表 M1 已有 |
| ⑧ | SSE 输出 | `POST /chat/explain?stream=true` → `StreamingResponse`（text/event-stream，事件格式见 api.md §0.4）；追问 `POST /chat/followup` 用 `chat_sessions` 保留最近 N 轮上下文，并基于 session 关联 question 重新检索 | `backend/app/api/v1/chat.py`（T9，M1 已有改造） |

**兜底与质量**（沿用 §3.6）：

| 场景 | 行为 |
|---|---|
| 无引用命中（相似度 < 0.75） | `uncovered: true`，前端 CitationBlock 显示"教材未覆盖该知识点"，给通用讲解但不伪装引用（ADR-0003） |
| 教材未上传/切块未完成 | `textbook_uploads.status` 暴露处理进度；引导先上传教材 |
| chunk 检索质量差 | T10 提供 RAG 质量评估脚本（ep-qa 配合），阈值可调 |

**讲解响应结构**（M2 锁定，api.md §5.3）：

```json
{
  "session_id": "...",
  "steps": [{"title": "理解题意", "content": "..."}],
  "conclusion": "...",
  "citations": [{"source": "高等数学（同济第七版）", "chapter": "第2章 导数与微分", "section": "2.3 求导法则", "page": "78", "snippet": "…原文片段…", "score": 0.91}],
  "uncovered": false,
  "model": "pro"
}
```

### 10.3 拍照录题：Pix2Text OCR 集成

**数据流**：

```
前端（TabBar 中央拍照按钮）→ 拍照/相册 → 裁剪
  → POST /ocr/upload（multipart: file + subject_id）          [T9: api/v1/ocr.py]
  → ocr_service.recognize()：Pix2Text ONNX 本地推理            [T10: services/ocr_service.py]
      recognize_text_formula(image) → {markdown, latex, text}  # 文字+公式混合，ch_sim
  → 结构化：LLM flash 将 raw_text → 题目 JSON 候选             [T10: ocr_service 内调 llm_gateway]
      {type, content, options, answer, analysis, confidence}
  → 知识点归属：suggest_kp()                                  [T10: ocr_service / selection]
      embedding 余弦相似 top-3；降级关键词匹配 knowledge_points.name/content
  → 前端预览（可编辑 Markdown/LaTeX）→ 选知识点
  → POST /questions/from-ocr（确认入库，幂等）                 [T9: api/v1/questions.py]
      → questions 插入（source='ugc'）+ question_embeddings 异步生成
      → ocr_uploads.status='confirmed'、question_id 回填
```

**设计要点**：
- **OCR 记录落表**：`ocr_uploads`（T8 新表，§10.6）跟踪 pending → parsed/failed → confirmed；识别失败（OCR_EMPTY）→ 前端引导重拍/手动录入（flows.md 流程 2 兜底）
- **答案置信度**：`structured.confidence < 阈值`（默认 0.6）→ 前端提示人工核对；确认入库时 `confirm_answer=false` 可跳过答案字段（避免垃圾答案污染题库）
- **幂等**：`POST /questions/from-ocr` 支持 `Idempotency-Key` + content_hash 去重（重复入库返回既有 question，`duplicated=true`）
- **免费限量**：免费用户每日 OCR 次数限制（默认 5 次，`subjects.config` 或全局配置可调），超限 429；会员不限（PRD §6）
- **代码文件**：路由 `backend/app/api/v1/ocr.py`（T9）+ `backend/app/services/ocr_service.py`（T10 真实化）；确认入库路由 `backend/app/api/v1/questions.py`（T9）

### 10.4 薄弱诊断：诊断引擎

**设计原则（可解释硬约束）**：**排名由规则引擎计算，LLM 只做措辞与建议生成**——保证"薄弱 Top5 与自测表现一致"（flows.md 流程 3 验收点），禁止 LLM 编造数字或排名。

**两段式流水线**：

```
① 规则层（确定性，无 LLM）：
   输入：user_knowledge_states（实时）+ 自测批次 answers（diagnosis_reports 快照）
   输出：
     weak_top5  = 有练习记录（correct+wrong>0）且 status ∈ {weak, consolidating} 的叶子知识点，
                  按 (正确率升序, 练习数降序) 排序取 top5
     strengths  = 正确率 ≥ 0.8 且有练习记录
     not_started = untouched 且练习数 = 0（"还没练过"≠"薄弱"，单独列出供计划兜底）
② LLM 层（pro）：
   输入：① 的确定性数据 + subjects.config.prompt_templates.diagnosis
   输出：summary（整体掌握度）+ 每项 suggestion（怎么补、练什么、对应教材章节）+ suggested_next_steps
   约束：prompt 注入数据即最终事实，LLM 不得改写 accuracy/practice_count/status/rank
```

**自测流程（三端点，api.md §7）**：
1. `POST /diagnose/self-test`：创建 `diagnosis_reports`（in_progress）+ 分层抽样 10 题（§10.1 自测选题）→ 返回 report_id + 题目（不含答案）
2. `GET /diagnose/self-test/{report_id}`：取题/状态
3. `POST /diagnose/report`：判分 → 统一走 `knowledge_state.apply_answer()` 更新状态 + study_sessions（自测计入当日练习）+ 错题入库 → 规则层算排名 → LLM 层生成建议 → `diagnosis_reports` 置 completed、写 weak_top5 快照 → 返回薄弱地图 JSON

**薄弱地图 JSON 结构**（锁定，api.md §7.3）：

```json
{
  "report_id": "...",
  "status": "completed",
  "summary": "整体掌握度中等，薄弱集中在导数应用与积分计算…",
  "weak_top5": [
    {"rank": 1, "knowledge_point_id": "...", "knowledge_point_name": "洛必达法则",
     "level": 3, "accuracy": 0.25, "practice_count": 8, "status": "weak",
     "suggestion": "优先补练：每天 2 道洛必达计算题，配合教材第 3 章例题"}
  ],
  "strengths": [{"knowledge_point_name": "求导基本法则", "accuracy": 0.9}],
  "not_started": [{"knowledge_point_name": "定积分应用", "level": 3}],
  "suggested_next_steps": ["先完成今日计划中薄弱点任务", "周末做一次第 3 章小测"]
}
```

**代码文件**：`backend/app/services/diagnosis.py`（T10 真实化，规则层+LLM 层）；`backend/app/services/selection.py`（T10，select_self_test_questions）；路由 `backend/app/api/v1/diagnose.py`（T9）。ep-qa（T12）按"排名=规则计算"做断言校验。

### 10.5 备考计划：规则引擎

**核心设计决策**：**每日任务不落新表，由规则引擎实时推导**——`plans` 只存计划本体与规则配置，`study_sessions` 存每日学习统计与打卡状态。避免"任务表 vs 进度表"双写同步问题。

**plans / study_sessions 表怎么用**（明确）：

| 表 | 职责 | M2 写入方 |
|---|---|---|
| `plans` | 计划本体：exam_date、status（active/completed/cancelled）、config（daily_question_target、阶段规则覆盖等） | `POST /plans`（T9） |
| `study_sessions` | 每日一行（UNIQUE(user_id, session_date)）：questions_practiced / correct_count 累加；checked_in 打卡状态（乐观锁） | `POST /questions/{id}/answers`、`POST /diagnose/report`（累加统计）、`POST /plans/{id}/checkin`（置位） |

**每日任务推导规则**（plan_service，MVP 规则版）：

```
输入：plans（exam_date + config）+ user_knowledge_states（薄弱点）+ study_sessions（当日进度）
days_left = exam_date - today
阶段：days_left > 14  → daily        （weak_practice：薄弱点题为主）
      7 ≤ days_left ≤ 14 → intensify（weak_practice + review_wrong 混合）
      days_left < 7  → sprint       （review_wrong：错题回顾 + 高频考点，M3 完善模拟卷）
每日任务 = { date, target_questions(=config.daily_question_target 默认 10), 
            focus_kps(当日 selection score top-3), type, reason,
            done(从 study_sessions 当日行读) }
```

- 读取：`GET /plans/active` 实时推导返回今日任务 + 未来 3 天预告（upcoming）；无计划/计划完成 → 返回 null 引导创建
- 打卡：`POST /plans/{id}/checkin` → study_sessions 当日行 upsert + checked_in=true（乐观锁 `UPDATE ... WHERE checked_in=false` 返回 0 行 = 已打卡 → 幂等返回 `already_checked_in=true`，非错误）；M2 仅支持当天打卡（补卡 M3）
- 打卡不强制"当日已做题"（防挫败）；进度如实展示（done 可能 0/10）
- 免费/会员：计划创建为会员功能（PRD §6）；查看今日任务登录即可
- **代码文件**：`backend/app/services/plan_service.py`（T9 交付，与路由同层）；路由 `backend/app/api/v1/plans.py`（T9）

### 10.6 M2 表结构增量（与 ep-db 的约定，T8 实现）

> 架构层面锁定以下表/字段需求；DDL 与迁移由 T8 落地 `backend/alembic/versions/0002_*.py` 并同步更新 `docs/database.md`（评审后锁定，禁止手改）。

1. **`user_knowledge_states` 增列 `streak`**（INT NOT NULL DEFAULT 0，连续正确次数）：`apply_answer()` 规则——正确 +1（≥3 → mastered），错误归 0；状态机切换见 §10.1。索引维持 `ix_ukstate_user_subject_status`。
2. **`ocr_uploads`（新表）**：`id, user_id, subject_id, image_path, status('pending'|'parsed'|'failed'|'confirmed'), raw_text, structured(JSONB), suggested_kps(JSONB), knowledge_point_id(FK, 用户确认), question_id(FK NULL, 确认入库回填), error, created_at, updated_at`。索引 `(user_id, status)`。
3. **`diagnosis_reports`（新表）**：`id, user_id, subject_id, status('in_progress'|'completed'), questions(JSONB 题组快照), answers(JSONB 作答快照), weak_top5(JSONB), report_text(TEXT), created_at, updated_at`。索引 `(user_id, created_at)`。
4. **`textbook_uploads`（新表）**：`id, user_id, subject_id, filename, file_path, status('processing'|'ready'|'failed'), chunk_count, error, created_at, updated_at`。用于教材上传 → 切块 → embed 的状态跟踪（§10.2 ①）。
5. **`document_chunks.source` 扩展**：允许 `'user_upload'`（用户上传教材），与内置 `'textbook'` 区分（M1 CHECK 约束不含该值 → 需迁移放宽 CHECK 或改 VARCHAR 枚举表——由 T8 评估，倾向 CHECK 加值）。

### 10.7 M2 新增/调整的代码文件总览（角色边界）

| 文件 | 归属 | 说明 |
|---|---|---|
| `backend/app/services/selection.py` | T10 | 自适应选题 + 自测选题（纯函数内核） |
| `backend/app/services/subject_config.py` | T10 | subjects.config 读取辅助（T9 复用） |
| `backend/app/services/rag/*`（doc_processor/embedder/retriever/rag_engine） | T10 | M1 骨架 → M2 真实化 |
| `backend/app/services/ocr_service.py` | T10 | M1 骨架 → Pix2Text 真实集成 + 结构化 + 知识点推荐 |
| `backend/app/services/diagnosis.py` | T10 | M1 骨架 → 规则层 + LLM 层两段式 |
| `backend/app/services/quiz_generator.py` | T10 | AI 出题（薄弱点 → 练习题，flash/pro 分级） |
| `backend/app/services/plan_service.py` | T9 | 计划规则引擎（每日任务推导/打卡） |
| `backend/app/api/v1/ocr.py`、`diagnose.py`、`textbooks.py`、`plans.py` | T9 | 新增路由 |
| `backend/app/api/v1/questions.py`、`chat.py` | T9 | M1 改造：/answers、/practice/questions、/from-ocr、RAG+SSE |
| `backend/app/db/`、`backend/app/models/`、`backend/alembic/versions/0002_*.py` | T8 | M2 表迁移 |
| `frontend/` | T11 | 五件套页面 + 真实 API 对接（mock fallback） |
| `backend/tests/`、`docs/qa/` | T12 | 端到端验收测试 |

> 冲突规避：`selection.py`/`subject_config.py` 归 T10；T9 路由只 import 调用，若 T10 未交付先按 §10.1 公式内联兜底（接口先行），T10 落地后替换并删除内联实现（卡片 comment 注明）。

---

## 11. M3 增量：体验增强与增长功能模块设计

> 本节是 M3 的模块级设计，在 M1/M2 基线上增量追加（§1~§10 不重写）。**接口契约（字段级）以 [docs/api.md](./api.md) §11 为准；表结构变更以 [docs/database.md](./database.md)（T14 增量 §9）为准；任务图见 [docs/ops/M3-taskgraph.md](./ops/M3-taskgraph.md)。**
> 对应 PRD §3 第二/三层：知识点图谱可视化 / 考前突击模式 / 学习数据看板 / 打卡连胜（第二层 体验增强）+ 排行榜 / 挂科风险预警（第三层 增长与壁垒）。

**M3 设计总原则**：

1. **统计类功能全部实时推导、不落快照表**（打卡连胜 / 排行榜 / 挂科预警 / 高频考点识别），唯一例外是突击会话 `sprint_sessions`（题单需稳定快照防重复组卷）。理由：MVP 数据量小，聚合查询毫秒级返回；少一张表少一处双写同步问题（与 §10.5 每日任务不落表同一决策风格）。
2. **可解释硬约束延续**：排行榜口径、挂科风险等级全部由规则层确定性计算，LLM（flash）只生成措辞/建议，禁止编造数字（与 §10.4 诊断引擎同一原则）。
3. **会员边界**：考前突击模式为会员功能（PRD §5/§6，免费用户 403 + 激活入口做引导）；图谱 / 看板 / 排行 / 预警 / 连胜登录即可看（留存与获客），突击作为付费钩子。

### 11.1 知识点图谱可视化

**数据源**：`knowledge_points`（三级树：章 level=1 / 节 level=2 / 知识点 level=3）+ `user_knowledge_states`（叶子状态）+ `questions`（每节点题量）。

**节点状态聚合规则**（叶子 → 父节点）：

| 节点 | 状态来源 |
|---|---|
| level=3 叶子知识点 | 直接读 `user_knowledge_states.status`（无记录 = `untouched`） |
| level=2 节 / level=1 章 | 聚合子节点：任一子节点 `weak` → `weak`；否则任一 `consolidating` → `consolidating`；全部 `mastered` → `mastered`；否则 `untouched` |

> 聚合取"最差子节点优先"，语义是"该章/节下还有薄弱点没补"，引导用户点进去补。

**每节点附带统计**（叶子）：`question_count`（该知识点 active 题数）、`practice_count`、`accuracy`（correct/(correct+wrong)，无记录为 null）、`status`；父节点带 `question_count`（子树题量求和）。

**前端可视化方案（context7 验证 2026-08，查询记录见卡片 comment）**：

- 图表库选型：**ECharts `series-tree`**（官方 `/apache/echarts-doc` 确认：树图支持逐节点 `itemStyle.color`、`symbolSize`、`expandAndCollapse`、`initialTreeDepth`、`roam`——正好覆盖三级图谱 + 状态着色 + 展开收起）。**不选 `series-graph`**（关系图需手工 layout，树形数据无必要）。
- uni-app 适配（官方 `/dcloudio/unidocs-zh` 确认）：**renderjs 可让 ECharts 跑在 App/H5 视图层**（直接操作 canvas、无逻辑层通信折损），但**小程序端无 renderjs**，官方建议小程序用 canvas 图表组件。
- **定案**：H5 / App → `@xiaohe0601/uni-echarts`（context7 `/xiaohe0601/uni-echarts`：Vue3 封装、`setOption()` API、支持 web/mp-*/app 全端、`autoresize` + `click` 事件），内部走 renderjs + ECharts；mp-weixin → 同一组件降级 canvas 绘制（该库已支持 BuiltInPlatform 含 mp-weixin）；**最终兜底** = 自绘 canvas 树（三级固定布局，逻辑简单，T16 实现，不增包体）。
- **节点着色**（状态语义固定，色值以 design-system 语义 token 为准，T16 落地时若缺失则补充 token）：

| status | 语义 | 颜色 |
|---|---|---|
| `mastered` | 已掌握 | 绿 |
| `weak` | 薄弱 | 红 |
| `consolidating` | 待巩固 | 橙 |
| `untouched` | 未接触 | 灰 |

- **交互**：点击叶子节点 → 该知识点题单（复用 `GET /questions?knowledge_point_id=`）或讲解入口；章/节节点展开/收起（ECharts `expandAndCollapse`，初始展开到第 2 级 `initialTreeDepth: 2`）。
- **API**：`GET /subjects/{subject_id}/knowledge-graph` 返回**嵌套 children 树**（ECharts tree 直接消费，前端零转换），见 api.md §11.1。
- **代码文件**：`backend/app/services/knowledge_graph.py`（T17，树组装 + 状态聚合）；路由（T15，api/v1 下新增或并入 subjects）。

### 11.2 考前突击模式（sprint）

**激活规则**：

- 自动激活：该科目存在 active 计划且 `days_left ≤ 7` → `GET /subjects/{subject_id}/sprint/questions` 首次访问时自动创建突击会话（`auto_activated=true`），前端提示"考前 7 天，进入突击模式"。
- 手动激活：`POST /subjects/{subject_id}/sprint/activate` 任意时间可开（考前 1 天也能开，不设限制）。
- 会员边界：**突击为会员功能**；免费用户 403（前端展示激活入口做会员引导）。自动激活对免费用户仅展示提示。
- 幂等：同科目已有 active 会话 → 返回既有（不重复创建）；考试日已过 → 旧会话置 `expired`，可重新激活。

**高频考点识别（数据来源 = 做题统计，规则版，无新表）**：

```
输入：user_knowledge_states（全体用户，按科目过滤）实时聚合
  heat_kp(kp)  = SUM(correct_count + wrong_count)   -- 全体作答热度（出现频次）
  avg_acc(kp)  = SUM(correct_count) / heat_kp       -- 全体平均正确率
真题权重：questions.source='past_exam' 且 knowledge_point_id=kp 的题数
高频考点 top-N = 按 heat_kp 降序取 heat_kp ≥ 阈值(默认 20 次) 且 avg_acc < 0.75 的知识点；
              叠加真题权重（有真题的考点升序档位）→ 综合排序
冷启动兜底：全体作答不足 → 退化为"题库中 source='past_exam' 题量最多的知识点"（真题即高频的合理代理）；
          仍无 → 全部薄弱/待巩固知识点。
```

> 数据规模说明：不做离线批处理，实时聚合（MVP 量级 OK）；后续数据量大再上缓存表（§11.5 预留 `leaderboard_snapshots` 同机制）。

**突击题单生成**（sprint.py，T17）：

```
题单 = 高频考点题 ∪ 个人错题（交集去重、限量、按考点分布）
1. 高频考点题：每个高频考点从 questions(active) 抽 difficulty 适配题（复用 §10.1 difficulty_factor 排序），每考点 ≤ 3 题
2. 个人错题：wrong_answers 未 mastered 且属于该科目 → 按考点去重，每考点 ≤ 2 题（错题必须优先，用户已错过）
3. 合并去重（question_id 唯一），限量 count（默认 20，1..50）
4. 分布约束：高频考点覆盖 ≥ 70% 题量，剩余给错题
5. 快照：生成结果写 sprint_sessions.question_snapshot（题单稳定，重复请求返回同一快照）
```

- **模拟卷**：`GET /subjects/{subject_id}/sprint/questions?mode=mock` → 从快照按 `subjects.config.exam`（duration_min/total_score）组卷返回（同结构 items + `mock` 元数据），前端计时答题；MVP 复用刷题提交链路（`POST /questions/{id}/answers`），不做独立判卷。
- **API**：见 api.md §11.2/§11.3；**表**：`sprint_sessions`（§11.7）。
- **代码文件**：`backend/app/services/sprint.py`（T17，高频识别 + 题单生成 + 激活）；路由 `backend/app/api/v1/sprint.py`（T15，调用 T17 服务；T17 未交付先按本规则内联兜底，T17 落地后替换并删除内联——沿用 §10.1 约定，禁止双实现长期并存）。

### 11.3 打卡连胜（streak）

**数据结构确认**：现有 `study_sessions` 已可支撑连胜统计（**T14 无需新表**）——

- `UNIQUE(user_id, session_date)`：每用户每天至多一行；
- `checked_in` + `checked_in_at`（M2 已加）：打卡事实；
- 判定只需要"按日期的 checked_in=true 序列"，无需额外快照。

**连续打卡判定规则（确定版，T18 断言依据）**：

```
输入：用户 checked_in=true 的 session_date 集合 S（升序）
current_streak（当前连胜）：
  1. 取最近打卡日 last = max(S)
  2. 若 last == today 或 last == yesterday → 连胜未断，从 last 往前数连续天数
  3. 若 last < yesterday（昨天和今天都没打）→ current_streak = 0（中断）
longest_streak（历史最佳）：S 按日期排序，相邻日期间隔 == 1 天则累计，否则断开重计，取最大段长
中断判定规则（一句话）：相邻两次打卡间隔 ≥ 2 天即断；今天还没打不算断（今天打了/昨天打了都算未断）
```

- 时区：`session_date` 为 DATE，日界按**用户时区**（MVP 固定 Asia/Shanghai；`checked_in_at` 落库为 UTC，展示与"今天/昨天"计算统一按东八区——与 api.md 时间约定一致，T15 实现时统一 `tz=Asia/Shanghai`）。
- 实现：单用户 `SELECT session_date FROM study_sessions WHERE user_id=:uid AND checked_in=true ORDER BY session_date DESC` → 内存 O(n) 遍历（n=打卡天数，MVP 毫秒级）；不需要 SQL 窗口函数（可读性优先）。抽纯函数 `streak.py: compute_streak(dates: list[date]) -> (current, longest)` 便于 T18 单测。
- 展示：首页/我的 Tab 连胜徽章 `🔥 N 天`（T16）；数据来自 `GET /me/dashboard`（api.md §11.4）。

### 11.4 学习数据看板（dashboard）

**汇总（GET /me/dashboard）聚合查询设计**：

| 指标 | 数据来源 | 计算 |
|---|---|---|
| 总做题量 | study_sessions | `SUM(questions_practiced)`（可带 subject_id 过滤） |
| 总正确数 / 正确率 | study_sessions | `SUM(correct_count) / SUM(questions_practiced)` |
| 掌握度 | user_knowledge_states | 叶子知识点中 `mastered` 占比（按科 = 该科叶子 KP 数） |
| 当前连胜 / 历史最佳 | §11.3 | 实时推导 |
| 薄弱点计数 | user_knowledge_states | status ∈ {weak, consolidating} 的叶子 KP 数 |
| 每科目分解 | 同上按 subject_id GROUP BY | `per_subject[]`（做题量 / 正确率 / 掌握度） |

**时间序列（GET /me/dashboard/trend）聚合查询设计**：

```
按粒度 group by 桶（date_trunc）：
  granularity=day   → date_trunc('day', session_date)    （days ≤ 31）
  granularity=week  → date_trunc('week', session_date)   （ISO 周，周一为界）
  granularity=month → date_trunc('month', session_date)
每桶指标：questions_practiced / correct_count / accuracy
掌握度曲线（as-of 近似，MVP 无历史状态快照）：
  mastered_kp_count(bucket) = COUNT(user_knowledge_states WHERE status='mastered'
                                    AND updated_at <= bucket_end)   -- 以状态最后更新时间近似"当时掌握度"
  mastery_pct = mastered_kp_count / 该科叶子 KP 总数
空数据边界：无记录的桶返回 0 值行（questions_practiced=0, accuracy=null；前端补零，接口只返回有数据 + 首尾桶）
```

- SQL 骨架（T15 参考）：`SELECT date_trunc(:gran, session_date) AS bucket, SUM(questions_practiced), SUM(correct_count) FROM study_sessions WHERE user_id=:uid [AND subject_id=:sid] AND session_date >= :start GROUP BY bucket ORDER BY bucket`。
- **API**：见 api.md §11.4/§11.5。**无新表**。

### 11.5 排行榜（leaderboard）

**口径定案（评审决策 2026-08-08，T15/T18 依据）**：

- **主排序 = 累计正确题数**（total_correct，全科目或按科过滤）；**次排序 = 正确率**（accuracy，仅当样本量 ≥ 30 题才参与排序，<30 视为 0）；展示列：名次 / 用户 / 做题量 / 正确率 / 连续天数（连胜仅展示，不参与排序）。
- 理由：纯做题量 → 鼓励刷水题刷量，噪音大；纯正确率 → 1 题 100% 就霸榜，无意义；纯连续天数 → 只奖励打卡不奖励产出。累计正确题数 = "有效产出"，最接近产品目标（通过考试靠做对题），且天然防"刷量不改对"；同分用正确率打破平局（≥30 题门槛保证样本可信）。
- 防作弊/防噪音：**做题量 < 30 题的用户不进榜**（新用户保护）；正确率 < 0.1 视为异常（疑似乱答），标 `suspicious` 不参与排序。
- **维度**：`scope=global`（全部用户）｜`scope=subject`（按科目过滤，`subject_id` 必填）。**班级维度 M3 不做，M3.5 实现**：§11.9 D3 原判"班级维度 V2"被 §12.4 修订——M3.5 采用 classes 表 + 邀请码模型落地 `scope=class`（详见 §12.4 / 决策 D10）。
- **实现方案（T14 决策输入）**：**纯查询方案，不建聚合表/物化视图**。MVP 用户量小，实时聚合（study_sessions 按用户 GROUP BY + §11.3 连胜）毫秒级；缓存收益低。预留：用户量 > 1k 或查询 > 100ms 时加 `leaderboard_snapshots`（每日快照：user_id / subject_id / total_correct / accuracy / streak，定时任务刷新，接口只读快照）——M3 不建，见 §11.7 预留项。
- **API**：见 api.md §11.6；分页沿用统一格式。

### 11.6 挂科预警（warning）

**设计原则**：与诊断引擎同构——**风险等级由规则层确定性计算，LLM（flash）只生成理由措辞**；每条预警必须可解释（为什么是这个等级）。

**输入**：该科目 active 计划的 `exam_date`（无计划则无预警，前端引导建计划）+ `user_knowledge_states`（薄弱/待巩固点）+ 近 7 天练习趋势（study_sessions）。

**风险等级判定规则（确定版，T17 实现 + T18 断言边界）**：

```
基础分 base = f(weak_count, days_left)：
  weak_count = 该科 status ∈ {weak, consolidating} 的叶子知识点数

  days_left ≤ 7:
      weak_count ≥ 3        → 高
      weak_count ∈ [1,2]    → 中
      weak_count = 0        → 低
  7 < days_left ≤ 14:
      weak_count ≥ 6        → 高
      weak_count ∈ [3,5]    → 中
      weak_count ≤ 2        → 低
  days_left > 14:
      weak_count ≥ 10       → 高
      weak_count ∈ [5,9]    → 中
      weak_count ≤ 4        → 低

修正（加减一档，clamp 到 [低, 高]）：
  +1 档：近 7 天有 ≥ 3 天未做任何题（做题量 = 0）→ 停滞
  -1 档：近 7 天做题 ≥ 目标量且正确率 ≥ 0.8 → 趋势向好
科目整体风险 = max(各条目风险)；同时输出条目级预警
```

- 条目级输出：`{knowledge_point_id, name, risk_level, reasons[]（规则生成：正确率 x%、练习 y 次、距考 z 天、近 7 天做题 w 题）, suggestion（LLM flash 生成，如"每天 2 道洛必达 + 教材 3.2 节回顾"）}`。
- **不落表**：预警是实时推导的瞬态视图（每天看结果一致），无历史/推送需求 → 复用现有表实时计算；若 V2 要"预警推送/历史趋势"再建 `risk_alerts` 表（§11.7 预留项）。
- **API**：见 api.md §11.7；**代码文件**：`backend/app/services/warning.py`（T17，规则层 + LLM flash 措辞）；路由 `backend/app/api/v1/warnings.py`（T15，或并入 me 路由）。

### 11.7 M3 表结构增量（与 ep-db 的约定，T14 实现）

> 架构层面锁定以下表/字段需求；DDL 与迁移由 T14 落地 `backend/alembic/versions/0003_*.py` 并同步更新 `docs/database.md` §9（评审后锁定，禁止手改）。

1. **`sprint_sessions`（新表，M3 唯一新表）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| subject_id | UUID FK → subjects.id | |
| activated_at | TIMESTAMPTZ | 激活时间 |
| auto_activated | BOOL DEFAULT false | 自动（考前 7 天）/ 手动 |
| status | VARCHAR(20) CHECK | `active` / `completed` / `expired` |
| expires_at | DATE | 考试日（关联计划 exam_date 快照） |
| question_snapshot | JSONB | 题单快照（items 题 id 列表，防重复组卷/题目下线漂移） |
| high_freq_kps | JSONB | 高频考点 top-N 快照（展示"本卷覆盖高频考点"） |
| stats | JSONB | 完成统计（做题数/正确数/正确率，可选） |
| created_at / updated_at | TIMESTAMPTZ | |

索引：`ix_sprint_user_subject_status (user_id, subject_id, status)`。同一时刻每用户每科目至多一个 `active`（T15 先查后建 + 幂等；不建部分唯一索引，简单为先）。

2. **打卡连胜**：**无新表无新字段**（确认 study_sessions 支撑，§11.3）。
3. **排行榜**：**无新表**（纯查询，§11.5）；预留 `leaderboard_snapshots` 字段草案：`(user_id, subject_id, total_correct, accuracy, current_streak, snapshot_date)` + UNIQUE(user_id, subject_id, snapshot_date)——M3 不建。
4. **挂科预警**：**无新表**（实时推导，§11.6）；预留 `risk_alerts` 字段草案：`(user_id, subject_id, knowledge_point_id, risk_level, reasons JSONB, triggered_at, handled)`——M3 不建。
5. **高频考点识别**：**无新表**（从 user_knowledge_states 实时聚合，§11.2）。

### 11.8 M3 新增/调整的代码文件总览（角色边界）

| 文件 | 归属 | 说明 |
|---|---|---|
| `backend/app/services/knowledge_graph.py` | T17 | 图谱树组装（三级）+ 节点状态聚合（§11.1） |
| `backend/app/services/sprint.py` | T17 | 高频考点识别 + 突击题单生成 + 激活逻辑（§11.2） |
| `backend/app/services/warning.py` | T17 | 挂科风险规则层 + LLM flash 措辞（§11.6） |
| `backend/app/services/streak.py` | T15 | 连胜统计纯函数（§11.3，独立纯函数便于 T18 单测） |
| `backend/app/api/v1/sprint.py`、`dashboard.py`（或 me.py）、`leaderboard.py`、`warnings.py`、`knowledge_graph.py` | T15 | M3 新路由（§11 各小节 + api.md §11） |
| `backend/app/db/`、`backend/app/models/`、`backend/alembic/versions/0003_*.py` | T14 | sprint_sessions 新表迁移 |
| `frontend/` | T16 | 图谱可视化（uni-echarts/renderjs/canvas）、突击页、看板页、排行榜页、预警卡片、连胜徽章 |
| `backend/tests/`、`docs/qa/` | T18 | M3 验收测试（含 §11.3 连胜中断 / §11.6 风险边界断言） |

> 冲突规避：`sprint.py`/`warning.py`/`knowledge_graph.py` 归 T17；T15 路由只 import 调用，若 T17 未交付先按 §11.2/§11.6 规则内联兜底（接口先行），T17 落地后替换并删除内联实现（卡片 comment 注明）。

### 11.9 M3 决策锁定表

| # | 决策 | 定案 |
|---|---|---|
| D1 | 图谱可视化选型 | ECharts `series-tree` + uni-echarts（renderjs：H5/App；canvas：mp-weixin），兜底自绘 canvas |
| D2 | 排行榜口径 | 主=累计正确题数，次=正确率（≥30 题门槛），连胜仅展示；做题量 < 30 不进榜 |
| D3 | 排行榜维度 | global + subject（M3）；**班级维度 M3.5 实现**（classes 表 + 邀请码 + users.class_id，见 §12.4 / D10） |
| D4 | 统计类是否落表 | 连胜 / 排行榜 / 预警 / 高频考点全部实时推导不落表；唯一新表 `sprint_sessions`（题单快照） |
| D5 | 突击会员边界 | 突击为会员功能（免费 403）；自动激活对免费用户仅展示引导 |
| D6 | 挂科预警判定 | 规则层 base(weak_count × days_left) + 趋势修正 ±1，clamp 低~高；LLM 只生成理由措辞 |
| D7 | 连胜判定 | 最近打卡日 = today 或 yesterday 则未断；间隔 ≥ 2 天即断；时区 Asia/Shanghai 日界 |
| D8 | 掌握度曲线口径 | as-of 近似：mastered 状态 `updated_at ≤ 桶末` 计数 |

---

## 12. M3.5 增量：TTS 语音讲解 / UGC 题库共建 / 成绩单海报分享 / 班级排行榜

> 本节是 M3.5 的模块级设计，在 M1~M3 基线上增量追加（§1~§11 不重写）。**接口契约（字段级）以 [docs/api.md](./api.md) §12 为准；表结构变更以 [docs/database.md](./database.md)（T20 增量 §10）为准；任务图见 [docs/ops/M3.5-taskgraph.md](./ops/M3.5-taskgraph.md)。**
> 对应 PRD §3：语音讲解（TTS，第二层）+ 班级排行榜 / 成绩单海报分享 / UGC 题库共建（第三层）。挂科预警已随 M3 交付，M3.5 补齐 M3 剩余功能。

**M3.5 设计总原则**：

1. **延续 M3 的"实时推导不落快照"**：分享卡 / 班级榜全部实时聚合，无新统计表；唯一新表 `classes`（成员关系必须持久化）。
2. **AI 边界延续**：TTS 用 edge-tts 合成（非 LLM，零 token 成本）；UGC 自动解析复用 M2 OCR 管线（Pix2Text + LLM 结构化，§10.3），不新增 AI 服务。
3. **可信度优先**：UGC 进公共题库必须过审核门控（防题库污染）；班级榜必须基于真实成员关系（邀请码），否决自由填班名（防串班/刷榜）。
4. **会员边界**：TTS 跟随 AI 讲解为会员功能（免费 403）；UGC 投稿、班级、海报分享登录即可用（增长钩子，与 §11 M3 原则一致）。

### 12.1 语音讲解（TTS）

**选型评估（context7 验证 2026-08-08，查询记录见卡片 comment）**：

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **后端 edge-tts**（`/rany2/edge-tts`，High 信誉，425 snippets） | 免费零 token；跨端一致（小程序/App/H5 全支持）；音色可控（zh-CN 音色白名单）；可缓存/保存；异步流式 `Communicate.stream()` 产出 mp3 chunk | 微软非官方端点（ToS 灰度、可能限流）；依赖外网（需代理配置） | **定案（D9）** |
| 前端 Web Speech API | 零后端成本；浏览器原生 | 微信小程序无 `speechSynthesis`；音色随 OS 漂移；无法缓存/保存；不可控 | 否决 |

**方案定案（D9）**：后端 edge-tts 生成 mp3（24kHz / 48kbps CBR mono，edge-tts 默认输出），FastAPI `FileResponse` 音频流；前端 `uni.createInnerAudioContext()` 播放。

**管线**：

```
POST /chat/explain/{session_id}/tts
  1. 取 chat_sessions 最近一条 assistant 消息 content（讲解全文；无则 404 EXPLANATION_NOT_FOUND）
  2. 文本清洗：拼接 steps 标题+内容+conclusion 为纯文本；去 LaTeX 标记（公式 MVP 边界：省略或中文口语近似）
  3. key = sha256(text + voice)；磁盘缓存 backend/media/tts/{key}.mp3 命中 → 直接返回（cache_hit=true）
  4. 未命中 → edge_tts.Communicate(text, voice, rate) → stream() 逐块写文件 → 返回
  5. 失败（无网络/微软限流）→ 502 TTS_UNAVAILABLE（前端提示稍后重试）
GET /tts/audio/{file_hash}.mp3
  FileResponse（media_type audio/mpeg, Content-Disposition inline；Starlette 自动支持 Range，可拖动进度）
```

- **voice 白名单**：`zh-CN-XiaoxiaoNeural`（晓晓，默认）/ `zh-CN-YunxiNeural`（云希，男声）；MVP 前端不提供切换（固定默认），接口预留参数。
- **代理**：edge-tts 访问微软端点，生产环境经 `HTTPS_PROXY` 环境变量注入（`Communicate(proxy=...)` 支持）；国内部署必需。
- **缓存清理**：定时任务按 mtime 清理 30 天前的 mp3（ops 手册）；MVP 不建表，文件名即 key 自描述（决策 D14）。
- **会员边界**：与 AI 讲解一致（api.md §5.1，免费 403 PAYMENT_REQUIRED）——TTS 是讲解的语音化，跟随讲解付费。
- **代码文件**：`backend/app/services/tts_service.py`（T21，edge-tts 封装 + 文本清洗 + 缓存读写）；路由 `backend/app/api/v1/chat.py` 增量（T20）。
- **API**：见 api.md §12.1/§12.2。

### 12.2 UGC 题库共建

**与现有 /questions/from-ocr 的关系（D13）**：

| 通道 | 目的 | 入库门控 | questions.status |
|---|---|---|---|
| `POST /questions/from-ocr`（M2 已有） | 个人录题（错题/拍照，自己的学习闭环） | 直接 active | `active` |
| `POST /questions/ugc`（M3.5 新增） | 投稿共建公共题库 | **审核门控** | `pending` → `active` / `rejected` |

两者共用同一解析管线（Pix2Text OCR + LLM 结构化 + 知识点建议，§10.3）与同一来源标记（`source='ugc'`）；差异只在**审核门控**。前端在 OCR 预览页提供"投稿共建"入口——用户确认结构化结果后调 `/questions/ugc` 而非 `from-ocr`。

**审核状态机（D11）**：

```
[提交] POST /questions/ugc
  规则预检（必做）：
    - content ≥ 15 字；type 合法；answer 结构与题型匹配（选择→options 的 key；填空/大题→文本）
    - 重复检测：content_hash 命中题库已有题 → 409 DUPLICATE（返回既有 question_id）
    - 通过 → 插入 questions(source='ugc', status='pending', submitted_by=当前用户)
[审核] POST /admin/questions/{id}/review（users.role='admin'）
    action=approve → status='active'（进公共题池，可被选题/搜索命中），reviewed_by/reviewed_at 落库
    action=reject   → status='rejected'（reject_reason 必填 ≥5 字，前端对提交者展示理由）
  已审核题目重复审核 → 409 ALREADY_REVIEWED
[规则自动审核]（可选，默认关）
    subjects.config.ugc_auto_approve=true 时：提交者累计被 approve ≥5 题且通过率 ≥90% → 自动置 active（可信贡献者）
```

- **表结构（§12.5）**：`questions.status` CHECK 扩展 `pending` / `rejected`；新增 `submitted_by` / `reviewed_by` / `reviewed_at` / `reject_reason` 列；`ix_questions_status_created (status, created_at)` 索引（审核列表查询）。
- **管理端形态**：MVP 提供 H5 管理页（T22，admin 角色登录可见）或直接调 API；不建独立管理后台。
- **API**：见 api.md §12.3~§12.5；**代码文件**：`backend/app/services/ugc_service.py`（T21，预检规则 + 自动审核），路由 `backend/app/api/v1/questions.py` 增量 + `backend/app/api/v1/admin.py`（T20）。

### 12.3 成绩单海报分享

**方案定案（D12）**：**前端 canvas 生成海报图，后端只做数据聚合**（`GET /me/share-card` 一次性返回全部指标）。理由：海报样式迭代快、视觉强绑定设计系统（amber 主色），前端 canvas 灵活；后端渲染需 headless/图片合成栈，重且没必要。

**数据聚合（GET /me/share-card）**：

| 区块 | 字段 | 来源 |
|---|---|---|
| 用户 | username | users |
| 学习总量 | questions_practiced / correct_count / accuracy | study_sessions 实时聚合 |
| 连胜 | current / longest | §11.3 streak 纯函数 |
| 掌握度 | overall_mastery_pct + best_subject {name, mastery_pct} | user_knowledge_states 实时聚合 |
| 薄弱点 | weak_count（weak+consolidating 叶子数） | user_knowledge_states |
| 近 7 天 | questions_practiced_7d / accuracy_7d | study_sessions 近 7 天 |
| 班级（可选） | class_name | users.class_id → classes |
| 考试（可选） | exam_subject / days_left | active 计划 |
| 元信息 | generated_at / share_card_version | — |

**前端生成与保存（context7 验证 uni-app 2026-08）**：

- 绘制：uni-app canvas —— 小程序/App 用 `<canvas type="2d">`（新版 canvas 2d 接口），H5 用 HTML canvas；同一 draw 函数按平台条件编译（T22）。
- 导出：`uni.canvasToTempFilePath`（H5 返回 base64；小程序返回临时文件路径）。
- 保存/分享：
  - 小程序：`uni.saveImageToPhotosAlbum({filePath})`（filePath 必须本地临时/永久路径，不支持网络路径；需授权 `scope.writePhotosAlbum`）+ `onShareAppMessage` 转发带图。
  - H5：canvas `toDataURL('image/png')` → `<a download>` 下载 / 新页展示长按保存。
  - App：`uni.saveImageToPhotosAlbum`（App 3.0.5+）。
- 视觉：海报模板固定尺寸（750×1334 逻辑像素），主色 amber `--primary-500`，语义色复用 design-system token；`share_card_version` 用于海报模板迭代缓存失效。
- **API**：见 api.md §12.8；**无新表**（实时聚合）。

### 12.4 班级排行榜

**班级来源定案（D10，修订 §11.5 D3）**：采用 **classes 表 + 6 位邀请码 + users.class_id 单班制（可空）**。

对比评估：

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| 自由填 class_name（T20 草案） | 零建模 | 无法验证成员关系；撞名即串班；榜单一被污染产品信任崩 | **否决** |
| **classes 表 + 邀请码** | 成员关系真实；防串班；榜单只对班内成员可见；建班一次永久归属 | 多一张表 + 建班流程（一次性成本） | **定案** |
| 教学班多对多（class_members 中间表） | 支持多班（高数教学班+英语教学班） | 中间表 + 加入/退出复杂度 | V2 |

- **流程**：班长 `POST /me/class {name}` 建班（生成 6 位 `invite_code`）→ 分享码 → 同学 `POST /me/class {invite_code}` 加入 → `users.class_id` 落库 → `GET /leaderboard?scope=class` 按 class_id 过滤。
- **隐私**：`class_id` 默认 NULL（未加入不进班榜）；退出 = 清空 class_id（V2 提供 DELETE /me/class，MVP 用"换班覆盖"）。
- **权限**：仅班内成员可见本班榜单（接口校验请求者 class_id 与榜单 class_id 一致）；admin 可见全部。
- **口径**：沿用 §11.5 D2（主=累计正确题数、次=正确率 ≥30 题门槛、<30 题不进榜）；`scope=class` 可叠加 `subject_id` 过滤。
- **表结构（§12.5）**：`classes` 新表 + `users.class_id` 列 + 索引。
- **API**：见 api.md §12.6/§12.7；**代码文件**：路由 `backend/app/api/v1/me.py` 增量 + `leaderboard.py` 增量（T20）；无 AI 服务。

### 12.5 M3.5 表结构增量（与 ep-db 的约定，T20 落地）

> 架构层面锁定以下表/字段需求；DDL 与迁移由 T20 落地（`backend/alembic/versions/0004_m35_*.py`）并同步更新 `docs/database.md` §10（评审后锁定，禁止手改）。

1. **`classes`（新表，M3.5 唯一新表）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(100) NOT NULL | 班级名（如"计科 2301"） |
| invite_code | VARCHAR(6) NOT NULL UNIQUE | 6 位邀请码（字母+数字，建班时生成，可重发） |
| created_by | UUID FK → users.id | 建班人（班长） |
| created_at / updated_at | TIMESTAMPTZ | |

索引：`uq_classes_invite_code`（UNIQUE invite_code）。成员数实时推导（COUNT users.class_id），不落列。

2. **`users.class_id`（新列）**：`UUID NULL FK → classes.id`（单班制，可空）；索引 `ix_users_class_id (class_id)`。

3. **`questions` 扩展（UGC 审核）**：

- `status` CHECK 扩展：`draft / pending / active / rejected / archived`
- 新列：`submitted_by UUID NULL FK → users.id`（投稿人）、`reviewed_by UUID NULL FK → users.id`（审核人）、`reviewed_at TIMESTAMPTZ NULL`、`reject_reason TEXT NULL`
- 新索引：`ix_questions_status_created (status, created_at)`（审核列表）

> 状态机语义：`pending` = 待审核（不进公共题池）；`active` = 已通过（= approved，进公共题池）；`rejected` = 已拒绝（保留原题，前端对提交者展示理由）；`draft` / `archived` 沿用管理端语义。公共题池查询保持 `WHERE status='active'` 不变。

4. **TTS**：**无新表**（磁盘缓存 key=sha256(text+voice)，§12.1；mtime 定时清理）。
5. **分享卡**：**无新表**（实时聚合，§12.3）。

### 12.6 M3.5 新增/调整的代码文件总览（角色边界）

| 文件 | 归属 | 说明 |
|---|---|---|
| `backend/app/services/tts_service.py` | T21 | edge-tts 封装 + 文本清洗 + 磁盘缓存（§12.1） |
| `backend/app/services/ugc_service.py` | T21 | UGC 预检规则 + 可选自动审核（§12.2） |
| `backend/app/api/v1/chat.py`、`questions.py`、`admin.py`、`me.py`、`leaderboard.py` | T20 | M3.5 端点增量（api.md §12）；admin 角色依赖 `users.role='admin'` |
| `backend/alembic/versions/0004_m35_*.py`、`backend/app/models/`、`docs/database.md` §10 | T20 | classes 新表 + users.class_id + questions 扩展（§12.5） |
| `frontend/` | T22 | 语音播放（createInnerAudioContext）、UGC 投稿入口、班级榜切换 + 加入页、海报 canvas（type=2d / H5 canvas） |
| `backend/tests/`、`docs/qa/` | T23 | M3.5 验收测试（TTS mock / UGC 状态机 / 班级边界 / 分享卡聚合） |

> 冲突规避：`tts_service.py` / `ugc_service.py` 归 T21；T20 路由只 import 调用，若 T21 未交付先返回 501 或 mock 兜底（接口先行，沿用 §10.1 约定），T21 落地后替换并删除内联实现（卡片 comment 注明）。

### 12.7 M3.5 决策锁定表

| # | 决策 | 定案 |
|---|---|---|
| D9 | TTS 方案 | 后端 edge-tts 生成 mp3（zh-CN 音色白名单）+ FileResponse 音频流；否决前端 Web Speech API（小程序无、音色不可控）；磁盘缓存 key=sha256(text+voice) |
| D10 | 班级模型（修订 D3） | classes 表 + 6 位邀请码 + users.class_id 单班制；否决自由填 class_name（成员关系不可验证）；教学班多班 V2 |
| D11 | UGC 审核状态机 | questions.status 扩展 pending/rejected（approved=active）；提交预检必做；自动审核默认关；重复审核 409 |
| D12 | 海报生成 | 前端 canvas 生成（type=2d / H5 canvas），后端只聚合（GET /me/share-card）；小程序 saveImageToPhotosAlbum / H5 toDataURL 下载 |
| D13 | UGC 与 from-ocr 关系 | 共用 OCR 管线与 source='ugc'；from-ocr=个人录题直接 active，/questions/ugc=投稿进审核流 |
| D14 | TTS 缓存存储 | 磁盘文件缓存（sha256 文件名），不建表（无 LLM 成本，mtime 清理） |

---

## 13. M4 增量：用户专业与选课 / 课程广场

> 本节是 M4 的模块级设计，在 M3.5 基线上增量追加（§1~§12 不重写）。**接口契约（字段级）以 [docs/api.md](./api.md) §13 为准；表结构变更以 [docs/database.md](./database.md)（T25 增量）为准。**
> 触发背景（用户反馈）：首页不再直接展示全部科目，改为"用户自填专业 + 自选本学期课程"，公共课独立成「课程广场」页。

### 13.1 概念：两个课程域（用户自选 vs 系统公共）

首页信息架构调整后，`subject` 概念拆分为两个视图域，**同一张 `subjects` 表、同一个 subject_id 维度**：

| 域 | 来源 | 展示位置 | 数据来源 |
|---|---|---|---|
| **用户自选课程**（我的课程） | 用户在选课引导/广场加入的课程 | 首页「我的课程」区块 | `user_subjects` 关联表（用户维度） |
| **系统公共课程**（课程广场） | 平台内置/管理的公共课种子（高数、英语、线代、概率论、大物…） | 「课程广场」页 | `subjects` 表 `is_public=true` |

- 一个科目可以同时属于两个域：用户加入公共课后，既在广场出现（可再次看到/移出），也在「我的课程」出现。
- **不加科目类型枚举**，只加 `is_public` 布尔：本阶段所有科目都是公共课候选，`is_public` 只决定是否出现在广场；未来若有"用户私有/专业定制课"再扩展类型字段（ADR-0001 模板约束下属于配置维度，不破坏本设计）。

### 13.2 数据模型（T25 落地）

```
users
└── major VARCHAR(100) NULL          -- 新增：专业自由文本（用户自填，不建专业表/字典）

user_subjects                         -- 新增：用户自选课程关联表（多对多）
├── user_id    UUID FK → users.id
├── subject_id UUID FK → subjects.id
├── created_at TIMESTAMPTZ NOT NULL DEFAULT now()   -- 加入时间（排序用）
└── PRIMARY KEY (user_id, subject_id)               -- 同一课程不可重复加入
    INDEX ix_user_subjects_user (user_id, created_at)

subjects
└── is_public BOOLEAN NOT NULL DEFAULT false        -- 新增：true=出现在课程广场（公共课）
```

要点：
- **幂等覆盖**：`PUT /me/subjects` 传 `subject_ids` 数组 = 全量覆盖（先删后插同事务），重复提交结果一致；不提供增量增删（MVP 简化，前端一次勾选提交）。
- **不加 semester/学期字段**：MVP 单学期制，`user_subjects` 即"本学期课程"；多学期切换 V2 再评估（决策 D18）。
- 学习状态（做题量/正确率/掌握度）**不落关联表**：实时聚合 `user_knowledge_states` / `study_sessions` / `wrong_answers`（口径沿用 §11.4 dashboard 定义），关联表只管"选了什么课"。

### 13.3 首页数据流

```
首次登录（major 为空 或 user_subjects 为空）
   └─▶ 选课引导页：输入专业（PUT /me/profile {major}）→ 从广场勾选课程（PUT /me/subjects {subject_ids}）
        └─▶ 完成进入首页；可跳过（后续「我的」页可改）

首页加载（已配置）
   ├─ GET /me/subjects      → 「我的课程」卡片列表（含每科掌握度/进度）
   ├─ GET /plans/active     → 今日任务/倒计时/打卡（保留 §8.2）
   └─ GET /me/warnings      → 挂科预警（保留 §11.7）
   「课程广场」入口卡片 → GET /subjects/plaza → 广场页（公共课列表 + 加入状态 + 加入按钮）
```

- `GET /subjects/plaza` 返回 `is_public=true` 的科目 + 当前用户是否已加入（`joined` 布尔）；未登录可看列表（游客白名单），`joined` 恒 false。
- `GET /me/subjects` 仅返回用户已加入的科目（按 `user_subjects.created_at` 排序），每项含学习状态聚合（做题量 / 正确率 / 掌握度）。
- `GET /subjects`（M1）保持兼容不动，作为广场数据源/管理端通用列表。

### 13.4 边界与规则

1. **加入校验**：`PUT /me/subjects` 的 subject_ids 必须存在且 `is_active=true`；`is_public=false` 的科目**不允许**用户自选加入（管理端专用，防越权）→ 422 `SUBJECT_NOT_JOINABLE`。
2. **空数组** = 清空本学期课程（合法，前端引导页"跳过"语义由前端控制，后端不强制非空）。
3. **major 约束**：自由文本，长度 1..100，去首尾空白；空串/全空白 → 400 `VALIDATION_ERROR`；不做专业枚举校验（V2 可选联想）。
4. **对既有链路影响**：`GET /subjects` 语义不变；刷题/诊断/计划等所有带 `subject_id` 的接口不受影响（用户从「我的课程」进入刷题，subject_id 照常传）。

### 13.5 表结构增量（与 ep-db 的约定，T25 落地）

> 架构层面锁定以下表/字段需求；DDL 与迁移由 T25 落地（`backend/alembic/versions/0005_user_major_plaza.py`）并同步更新 `docs/database.md` §11（评审后锁定，禁止手改）。
> ⚠️ **迁移编号修正**：T25 body 草案写的 `0004_user_major_plaza` 与既有 `0004_m35_classes_ugc.py` 冲突，**实际迁移必须为 `0005_user_major_plaza`**（down_revision=0004_m35_classes_ugc）。

1. **`users.major`（新列）**：`VARCHAR(100) NULL`（自由文本，可空）。
2. **`user_subjects`（新表）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | UUID FK → users.id | 复合主键 |
| subject_id | UUID FK → subjects.id | 复合主键 |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | 加入时间（列表排序） |

索引：`PRIMARY KEY (user_id, subject_id)` + `ix_user_subjects_user (user_id, created_at)`（按用户取列表）。级联删除：user_id → CASCADE（删用户清选课）；subject_id → CASCADE（删科目清关联）。

3. **`subjects.is_public`（新列）**：`BOOLEAN NOT NULL DEFAULT false`；索引 `ix_subjects_is_public (is_public, is_active, sort_order)`（广场列表）。
4. **种子数据（seed 更新）**：现有高数（math_gaoshu）/英语（eng_college）标 `is_public=true`；新增线性代数、概率论、大学物理为 `is_public=true` 公共课（有题最好，无题仅展示也可，题量不足时前端展示"建设中"）。

### 13.6 M4 新增/调整的代码文件总览（角色边界）

| 文件 | 归属 | 说明 |
|---|---|---|
| `backend/app/api/v1/me.py`（新增/扩展）、`backend/app/schemas/me.py`（或 profile.py） | T25 | PUT /me/profile、PUT /me/subjects、GET /me/subjects（§13.3 + api.md §13） |
| `backend/app/api/v1/subjects.py`（扩展） | T25 | GET /subjects/plaza（广场列表 + joined 状态） |
| `backend/app/models/`（users/subjects/user_subjects）、`backend/alembic/versions/0005_user_major_plaza.py`、`docs/database.md` §11 | T25 | 表增量（§13.5） |
| `backend/app/services/`（如需要） | T25 | 学习状态聚合纯函数（做题量/正确率/掌握度，口径复用 dashboard 定义；若已有现成聚合则直接复用） |
| `backend/app/db/seed.py`（或种子脚本） | T25 | is_public 回填 + 新增公共课种子 |
| `frontend/` | T26 | 选课引导页、首页「我的课程」改造、课程广场页、「我的」页专业编辑入口（设计见 design/pages.md，T26 同步） |
| `backend/tests/`、`docs/qa/` | T27 | 专业/选课/广场验收测试 + 迁移可执行验证（api.md §13 用例） |

> 冲突规避：无 AI 服务新文件（选课/广场为纯 CRUD + 聚合），T25 一人完成 API + 迁移 + 种子即可；若 ep-db 并行处理 db 目录需按 T25 body 约定协调避免冲突。

### 13.7 M4 决策锁定表

| # | 决策 | 定案 |
|---|---|---|
| D15 | 课程域建模 | 单一 `subjects` 表 + `is_public` 布尔区分广场公共课；不建独立类型枚举/第二张科目表（ADR-0001 模板约束下是配置维度） |
| D16 | 用户选课建模 | `user_subjects` 多对多关联表（复合主键防重复）；幂等覆盖式 PUT（先删后插同事务）；学习状态实时聚合不落表 |
| D17 | 广场游客边界 | `GET /subjects/plaza` 游客白名单可看（joined=false）；加入/修改必须登录 |
| D18 | 学期维度 | MVP 单学期制，`user_subjects` 即本学期课程，不建 semester 字段；多学期切换 V2 再评估（加 `semester` 列或独立选课记录表） |

---

## 14. M5 增量：课程归一对齐 + 题库飞轮

> 本节是 M5 的模块级设计，在 M4 基线上增量追加（§1~§13 不重写）。**接口契约（字段级）以 [docs/api.md](./api.md) §14 为准；表结构变更以 [docs/database.md](./database.md)（T29 增量）为准。**
> 触发背景（产品策略，见 [docs/product/题库策略.md](../product/题库策略.md)）：每个学校课程不同，题库无法人工覆盖长尾。M5 落地两件事——①课程三级归一对齐：校本课程实例 → AI 映射到模板课程 → 题目跨校共享；②题库飞轮：UGC 拍照录题（已有 OCR）+ **AI 初审管线**（自动校验 → pending → active/rejected）+ 行为数据反哺质量。

### 14.1 概念：课程三级归一对齐

**问题**：「XX大学 高数A」和「YY大学 高等数学（上）」是同一门课，但名字、教材、章节全不同。若每校独立题库 → 碎片化不可用。

**解法**：三级对齐模型——课程实例（用户侧）→ 模板课程（题库挂载点）→ 知识点（对齐单元）：

```
课程实例（学校特有）         课程模板（归一）          知识点（对齐）
┌─────────────┐           ┌─────────────┐         ┌─────────────┐
│ 清华·高数A   │──┐        │             │         │ 函数与极限   │
│ 北大·高数上  │──┼───────►│ 高等数学     │────────►│ 导数与微分   │
│ 某职校·高数  │──┘        │  (code: ma) │         │ 积分学       │
└─────────────┘           └─────────────┘         └─────────────┘
    user_subjects             subjects               kp_tree
```

- **用户侧**：选「本校课程实例」（`user_subjects` 行）→ 系统自动**映射到模板课程**（AI 做课程名匹配 + 教材版本识别）。
- **题库侧**：题目挂在**模板课程 + 知识点**上，不挂在某校实例 → 清华学生传的题，北大/职校学生都能刷到；同一知识点跨校共享，题库规模放大。
- **`subjects` 分层（新字段 `level`）**：`public`（公共课）/ `major`（专业基础课）/ `school`（校本特色课，未归一化前的长尾实例）。公共课（高数、英语、线代、大物…）为 `public`；专业基础课（数据结构、电路…）为 `major`；学校自创课（某职校·机床维修）为 `school`。`is_public`（M4）继续控制是否上广场；`level` 是课程性质标签（题库策略/供给方式用）。

### 14.2 数据模型增量（T29 落地）

| 对象 | 变更 | 说明 |
|---|---|---|
| `course_aliases`（新表） | 新表 | 同课多名归一：alias（如 "高等数学A"/"高数上"/"高数"）→ template_subject_id |
| `subjects.level`（新列） | 增列 | `public` / `major` / `school` 课程分层（NOT NULL DEFAULT 'public'） |
| `user_subjects.template_subject_id`（新列） | 增列 | 用户所选课程实例映射到的模板课程外键（NULL=未归一，独立实例） |

**course_aliases 设计要点**：

```sql
course_aliases
├── id              UUID PK
├── alias           VARCHAR(100) NOT NULL        -- 归一化课程名（去空格/括号/学期/教材版本噪声）
├── template_subject_id UUID NOT NULL FK → subjects.id
├── source          VARCHAR(20) NOT NULL DEFAULT 'seed'   -- 'seed'(种子) / 'ai'(AI 匹配沉淀) / 'manual'(人工录入)
├── is_verified     BOOLEAN NOT NULL DEFAULT false        -- 是否人工/高分确认（未确认仅候选，不直接采用）
├── created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
├── updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
└── UNIQUE (alias)  -- 同课多名→同一模板；不同 alias 可指向同一模板（多对一）
```

- **写入时机**：①种子数据（高数/英语等公共课别名，`source='seed'`）；②用户录入时 AI 匹配命中 → 沉淀一条 `source='ai'`（幂等，命中即 upsert）；③匹配失败用户手动确认模板 → `source='manual'` + `is_verified=true`。
- **查询语义**：录入联想/匹配时先查别名（精确命中 → 直接映射，置信度 1.0），未命中再走 AI 语义匹配 → 降低 AI 调用成本、匹配越来越准（飞轮）。

**user_subjects.template_subject_id 语义**：

- 用户添加校本课程实例（如「清华·高数A」）→ 若匹配到模板「高等数学」：写入 `user_subjects(user_id, subject_id=校本实例或模板?, template_subject_id=模板id)`。
- **subject_id 存什么**：为保持「题目挂模板」且「用户课程列表显示校本名」，约定——`subject_id` 指向实际展示课程（`subjects` 行，可能 `level='school'`），`template_subject_id` 指向题目来源模板（可为 `subject_id` 自身，若该课程本身就是模板）。刷题/检索一律按 `template_subject_id`（NULL 时回退 `subject_id`）取题。
- 未匹配（无模板）→ `template_subject_id=NULL`，独立实例（`level='school'`）只能靠自身 UGC 攒题，后续被匹配到模板时回填外键（升级路径）。

### 14.3 课程匹配流程（AI 匹配 + 置信度阈值）

```
用户录入校本课程名（如「清华 2026春 高等数学A」）
   │
   ├─ 1. 归一化：去空白/学期/括号/教材版本 → 「高等数学A」
   ├─ 2. 精确命中 course_aliases.alias？
   │      ├─ 是 → 直接映射模板（confidence=1.0，返回候选 1 条）→ 前端可一键确认
   │      └─ 否 → 3. AI 语义匹配（course_matcher 服务，DeepSeek flash）
   │                输入：归一化名 + 可选学校名 + 可选教材
   │                输出：候选模板列表 [{template_subject_id, name, code, confidence, reason}]
   ├─ 4. 阈值决策（D21）：
   │      confidence ≥ 0.85 → 自动采用 top1（前端显示匹配结果，用户可改选）
   │      0.60 ≤ confidence < 0.85 → 返回候选供用户选择（确认后按 D20 沉淀 alias）
   │      < 0.60 或 AI 无法判定 → 未匹配
   └─ 5. 未匹配处理：
          ├─ 手动建实例：POST /me/courses {name, template_subject_id: null} → subjects 插入 level='school' 行 + user_subjects 关联（template_subject_id=NULL）
          └─ 或手动指定模板：用户在候选列表找不到时，可搜索广场课程手动确认模板（POST /me/courses {template_subject_id: 指定}）
```

- **教材版本识别**：AI 匹配时若用户提供教材名（如「同济第七版」），作为匹配特征之一；教材文本入库后（已有 textbook_uploads）知识点结构天然对齐模板课程。
- **幂等**：同用户同校本课程名重复添加 → 返回已有 `user_subjects` 记录（409 `ALREADY_EXISTS` 语义，前端提示「已在你的课程中」）。
- **约束**：`user_subjects` 复合主键 (user_id, subject_id) 防重复；校本实例 `subjects` 行 `is_active=true` 才可关联。

### 14.4 UGC 审核流：AI 初审管线（题库飞轮）

**与 M3.5 的关系**（§12.2 已有规则预检 + 人工审核；M5 增量 = AI 初审自动化）：

```
投稿 POST /ugc/upload（M5 新增，含 AI 初审）
   │
   ├─ 规则预检（复用 ugc_service，§12.2）：
   │      content ≥ 15 字；type 合法；answer 结构与题型匹配；content_hash 去重
   │      → 不通过 400/409 DUPLICATE（不落库）
   │
   ├─ AI 初审（ugc_review 服务，DeepSeek flash，新增）：
   │      · 题干完整性校验（有无题意、选项是否齐全）
   │      · 答案正确性校验（选择/填空可规则抽检：AI 自算 + 反向代入）
   │      · 知识点归属校验（挂载的 knowledge_point_id 是否属于模板课程）
   │      → 输出 verdict（pass / flag）+ confidence + reasons[]
   │
   ├─ 落库 questions(source='ugc')：
   │      · verdict=pass 且 confidence ≥ 0.85 → status='pending'（进人工抽查队列，小流量自动放行）
   │      · verdict=flag 或 confidence < 0.85 → status='pending' + reject_reason 预填 AI 理由
   │        （人工复核后置 active / rejected；AI 只预筛不终审——质量兜底 D22）
   │
   └─ 行为数据反哺（M5 预留字段，落地可选）：
          active 后刷题正确率 < 40% → 标记「有争议」，进入复核队列（D22）
```

- **与 M3.5 `POST /questions/ugc` 的关系**：M3.5 端点保留（个人录题/兼容旧客户端）；M5 推荐走 `POST /ugc/upload`（AI 初审内置）。两者最终都进 `questions(status='pending')` 同一审核队列。
- **AI 审核不直接置 active**（除非 `subjects.config.ugc_ai_auto_approve=true` 且 confidence ≥ 0.9，D22 决策）：AI 幻觉风险下，人工抽查是质量底线；自动放行仅对可信贡献者开放（M3.5 已有贡献者积分逻辑可复用）。
- **状态机**（复用 M3.5 §12.2）：`pending` → `active` / `rejected`；`GET /ugc/status` 供投稿者查询状态与拒绝理由。
- **AI 初审结果落库**：不新建审核表；`reject_reason` 存 AI 理由文本（人工改判时覆盖），`reviewed_by/reviewed_at` 由人工审核时填写（AI 预筛阶段为 NULL）。

### 14.5 表结构增量（与 ep-db 的约定，T29 落地）

> 架构层面锁定以下表/字段需求；DDL 与迁移由 T29 落地（`backend/alembic/versions/0006_course_alias_level.py`，**down_revision=0005_user_major_plaza**）并同步更新 `docs/database.md` §12（评审后锁定，禁止手改）。

1. **`course_aliases`（新表）**：字段见 §14.2（alias / template_subject_id / source / is_verified / created_at / updated_at，UNIQUE(alias)）；索引 `ix_course_aliases_template (template_subject_id)`（按模板查别名）。
2. **`subjects.level`（新列）**：`VARCHAR(20) NOT NULL DEFAULT 'public'`，CHECK `IN ('public','major','school')`；`ix_subjects_level (level, is_active)`（分层列表/广场过滤）。
3. **`user_subjects.template_subject_id`（新列）**：`UUID NULL FK → subjects.id`；索引 `ix_user_subjects_template (user_id, template_subject_id)`（用户课程→模板题源）。
4. **种子数据（seed 更新）**：高数/英语/线代/概率论/大物等公共课 `level='public'`（`is_public=true` 保持）；`course_aliases` 种子：高等数学←"高等数学A"/"高数A"/"高数上"/"高等数学（上）"、大学英语←"大学英语"/"英语"/"大学英语综合" 等（`source='seed', is_verified=true`）。

### 14.6 M5 新增/调整的代码文件总览（角色边界）

| 文件 | 归属 | 说明 |
|---|---|---|
| `backend/app/models/`（course_aliases / subjects.level / user_subjects.template_subject_id）、`backend/alembic/versions/0006_course_alias_level.py`、`docs/database.md` §12 | T29 | 表增量（§14.5）+ 种子（公共课 level + aliases 种子） |
| `backend/app/api/v1/courses.py`（新增，14.1~14.3）、`backend/app/schemas/courses.py`（新增） | T30 | GET /courses/aliases、POST /courses/match、POST /me/courses（§14.3 + api.md §14） |
| `backend/app/api/v1/ugc.py`（扩展，14.4~14.5）、`backend/app/schemas/ugc.py`（扩展） | T30 | POST /ugc/upload、GET /ugc/status |
| `backend/app/services/course_matcher.py`（新增） | T31 | AI 课程名匹配（别名命中 + DeepSeek 语义匹配 + 阈值决策，§14.3） |
| `backend/app/services/ugc_review.py`（新增） | T31 | AI 初审管线（题干/答案/知识点校验 + verdict + confidence，§14.4） |
| `backend/app/services/ugc_service.py`（扩展） | T31 | 规则预检复用 + 接入 AI 初审（在投稿落库前调用 ugc_review） |
| `backend/app/db/seed.py`（或种子脚本） | T29 | level 回填 + course_aliases 种子 |
| `frontend/` | T32 | 校本课程录入页（联想 /courses/aliases + 匹配确认 /courses/match + 提交 /me/courses）、课程广场按模板课展示（保持 is_public 语义）、题库共建入口（投稿 /ugc/upload + 状态 /ugc/status） |
| `backend/tests/`、`docs/qa/` | T33 | 课程对齐验收测试 + UGC AI 审核流测试 + test-report.md 更新（api.md §14 用例） |

> 冲突规避：T29（ep-db）只写 models/alembic/seed/database.md；T30（ep-backend）写 api/schemas；T31（ep-ai）写 services（course_matcher / ugc_review / ugc_service 扩展）——services 与 api 目录隔离，T30 在 T31 交付前用接口占位（AI 匹配结果 dict 约定见 api.md §14.2），联调在 T33。

### 14.7 M5 决策锁定表

| # | 决策 | 定案 |
|---|---|---|
| D19 | 三级对齐建模 | 校本课程实例 = `user_subjects` 行 + `subjects.level='school'`（未归一实例）；题目挂**模板课程 + 知识点**，检索按 `template_subject_id`（NULL 回退 subject_id）；不建独立实例表/独立题池 |
| D20 | course_aliases 学习机制 | 别名表（alias → template_subject_id，UNIQUE(alias)）作为匹配缓存与飞轮：种子 + AI 命中沉淀 + 人工确认三级来源；`is_verified` 控制是否直接采用 |
| D21 | 匹配阈值 | confidence ≥ 0.85 自动采用 top1；0.60~0.85 候选供用户选择；< 0.60 未匹配 → 手动建 `level='school'` 实例或手动指定模板（不阻塞用户） |
| D22 | AI 初审边界 | AI 只做预筛（题干/答案/知识点校验，verdict + confidence），落 pending + 预填 reject_reason；**不直接置 active**（除非 subjects.config.ugc_ai_auto_approve=true 且 confidence ≥ 0.9）；行为数据（正确率<40%）标记争议复核（M5 预留） |
