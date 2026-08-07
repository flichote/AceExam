# AceExam 架构设计（M1 基线）

> **状态**：M1 基线 v1.0（2026-08-07）｜**作者**：ep-arch
> **定位**：本文件是系统设计的事实来源。需求唯一事实来源是 [PRD](./PRD.md)；视觉/交互见 [design/](./design/)；表结构与 API 契约在 M1 内由本文给出骨架，落地后经 ep-arch 评审锁定（变更走文档）。
> **配套决策**：关键技术决策固化在 [docs/adr/](../adr/)（ADR-0001 ~ 0003）。

---

## 0. 文档地图（事实来源层级）

| 文档 | 内容 | 状态 |
|---|---|---|
| `docs/PRD.md` | 需求唯一事实来源（功能分层/核心闭环/题库策略） | v0.1 已定 |
| `docs/design/*` | 页面地图 / 设计系统 / 组件 / 交互流程 | 已定 |
| **`docs/architecture.md`（本文）** | 系统模块划分、科目模板、RAG 管线、LLM 分级、API 骨架、ADR 索引 | **M1 基线 v1.0** |
| `docs/database.md` | 表结构（T2 交付） | T2 产出，评审后锁定 |
| `docs/api.md` | API 契约详版（T3 落地后回填） | T3 产出，评审后锁定 |
| `docs/ops/M1-taskgraph.md` | M1 里程碑任务图与启动手册 | 已存在，T1 完善 |

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

- [ ] 自适应选题 MVP 规则版的具体加权公式（PRD §9）
- [ ] VECTOR 维度最终确认（DeepSeek Embedding 模型返回维度 vs T2 基线 1024）
- [ ] 引用溯源 UI 形态细节（CitationBlock 展示相关度分数？）
- [ ] 英语听力题型的交互扩展（是否 M1 纳入）
- [ ] 教材语料版权与来源（M1 先内置公共教材公开内容 + 用户上传）
