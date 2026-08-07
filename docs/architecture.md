# AceExam 架构设计（M1 基线）

> **状态**：M2 增量 v1.1（2026-08-07）｜**作者**：ep-arch
> **定位**：本文件是系统设计的事实来源。需求唯一事实来源是 [PRD](./PRD.md)；视觉/交互见 [design/](./design/)；表结构与 API 契约分别以 [database](./database.md) 与 [api](./api.md) 为准（评审后锁定，变更走文档）。
> **配套决策**：关键技术决策固化在 [docs/adr/](../adr/)（ADR-0001 ~ 0003）。
> **M2 增量说明**：M1 基线（§1~§9）保持不动；MVP 五件套（智能刷题/AI 讲解/拍照录题/薄弱诊断/备考计划）的模块设计在 §10 增量追加，API 契约详版见 [docs/api.md](./api.md)。

---

## 0. 文档地图（事实来源层级）

| 文档 | 内容 | 状态 |
|---|---|---|
| `docs/PRD.md` | 需求唯一事实来源（功能分层/核心闭环/题库策略） | v0.1 已定 |
| `docs/design/*` | 页面地图 / 设计系统 / 组件 / 交互流程 | 已定 |
| **`docs/architecture.md`（本文）** | 系统模块划分、科目模板、RAG 管线、LLM 分级、API 骨架、ADR 索引、M2 五件套模块设计 | **M2 增量 v1.1** |
| `docs/database.md` | 表结构（M1 基线；M2 增量由 T8 同步） | M1 已锁定，T8 增量 |
| `docs/api.md` | API 契约详版（Pydantic 级字段定义 + M1/M2 差异表） | **M2 v1.0 已交付** |
| `docs/ops/M1-taskgraph.md` | M1 里程碑任务图与启动手册 | 已存在，T1 完善 |
| `docs/ops/M2-taskgraph.md` | M2 里程碑任务图（T7~T12） | T7 产出 |

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
