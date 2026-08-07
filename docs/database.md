# AceExam 数据库设计（M1）

> **状态**：M1 基线 v1.0（2026-08-07）｜**作者**：ep-db
> **定位**：表结构事实来源。需求见 [PRD](./PRD.md)；系统设计见 [architecture](./architecture.md)（subject 维度贯穿 / RAG 管线 / LLM 分级）；知识点状态机见 [flows](./design/flows.md)。
> **评审**：本文件与迁移脚本由 ep-arch 评审后锁定；任何表结构变更必须走 Alembic 迁移 + 同步更新本文档，禁止手改线上库。

---

## 0. 设计原则

1. **subject 是一等维度（ADR-0001）**：所有内容类表（`knowledge_points` / `questions` / `question_embeddings` / `document_chunks` / `wrong_answers`）带 `subject_id` 外键，两科数据物理隔离、逻辑同构。
2. **枚举字段全部用 VARCHAR + CHECK 约束**，取值集中列在本文档；不用 PG 原生 enum（后续加枚举值要 ALTER TYPE，迁移成本高）。
3. **向量列必须 `vector` 类型（pgvector）**，检索统一余弦距离 `<=>`（`cosine_distance`）；HNSW 索引 + `vector_cosine_ops`。
4. **幂等优先**：错题本 / 知识点状态 / 打卡等用户写操作全部加唯一约束（配合 `Idempotency-Key`，见 flows.md 跨流程约束）。
5. **时间统一 `TIMESTAMPTZ`**，主键统一 `UUID`（`gen_random_uuid()`，PG13+ 内置）。UUID 理由：UGC 拍照录题离线生成 ID、多端合并不冲突、防 ID 枚举爬取；与后端模型层（ep-backend）对齐。
6. **软删除不建**：用 `status` 字段（active/archived/draft 等）表达生命周期，减少查询噪音。

---

## 1. ER 总览

```
users 1 ──── n wrong_answers n ──── 1 questions n ──── 1 knowledge_points n ──── 1 subjects
users 1 ──── n user_knowledge_states n ──── 1 knowledge_points
users 1 ──── n plans / study_sessions
subjects 1 ──── n knowledge_points（自引用 parent_id 组成树）
subjects 1 ──── n document_chunks（教材向量，RAG 语料）
questions 1 ── 1 question_embeddings（题目向量）
questions 1 ──── n ai_explanations（讲解缓存）
users 1 ──── n chat_sessions / token_usage
```

| 表 | 职责 | 归属服务 |
|---|---|---|
| `users` | 用户 / 会员 | auth |
| `subjects` | 科目（含科目模板配置 config JSONB） | subjects |
| `knowledge_points` | 知识点图谱（章→节→知识点树） | knowledge-points / diagnosis |
| `questions` | 题库（题干 / 选项 / 答案 / 解析 / 难度） | questions / quiz |
| `question_embeddings` | 题目向量（相似题召回 / 去重） | quiz / rag |
| `document_chunks` | 教材向量库（RAG 语料，分块 + embedding + 出处） | rag |
| `wrong_answers` | 错题本（用户维度） | wrong-answers |
| `user_knowledge_states` | 知识点掌握状态（自适应选题核心） | quiz / diagnosis |
| `plans` | 备考计划（简化 study_plans） | plans |
| `study_sessions` | 学习记录 / 每日打卡 | plans / stats |
| `ai_explanations` | AI 讲解缓存（省钱，ADR-0002） | chat |
| `chat_sessions` | AI 追问会话（保留最近 N 轮上下文） | chat |
| `token_usage` | LLM token 计量（月度成本看板） | llm_gateway |

---

## 2. 表结构明细

### 2.1 users —— 用户 / 会员

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| username | VARCHAR(50) | NOT NULL, UNIQUE | 登录名 |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt hash |
| role | VARCHAR(20) | NOT NULL, DEFAULT 'student', CHECK | 系统角色：`student` / `admin` |
| is_member | BOOLEAN | NOT NULL, DEFAULT false | 会员订阅状态（产品端"会员"） |
| member_expires_at | TIMESTAMPTZ | NULL | 会员到期时间（后续订阅用） |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

索引：`uq_users_username`（UNIQUE username）。

> 产品角色矩阵（访客/学生/会员）中，访客=未登录，学生=登录非会员，会员=is_member=true。`role` 是系统级角色，仅 admin 管理用。

### 2.2 subjects —— 科目（含模板配置）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| code | VARCHAR(50) | NOT NULL, UNIQUE | 机器码：`math_gaoshu` / `eng_college` |
| name | VARCHAR(100) | NOT NULL | 展示名：高等数学 / 大学英语 |
| description | TEXT | NULL | |
| config | JSONB | NOT NULL, DEFAULT '{}' | 科目模板配置（ADR-0001，见 §3.2） |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 是否上架 |
| sort_order | INT | NOT NULL, DEFAULT 0 | 排序 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

索引：`uq_subjects_code`（UNIQUE code）。

### 2.3 knowledge_points —— 知识点图谱（树）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| subject_id | UUID | NOT NULL, FK → subjects.id | 科目隔离（ADR-0001） |
| parent_id | UUID | NULL, FK → knowledge_points.id | 父节点；章级为 NULL |
| name | VARCHAR(200) | NOT NULL | 知识点名（章/节/知识点） |
| content | TEXT | NULL | 知识点说明 / 公式 / 核心概念 |
| level | SMALLINT | NOT NULL, DEFAULT 1, CHECK (1..3) | 1=章 2=节 3=知识点 |
| sort_order | INT | NOT NULL, DEFAULT 0 | 同父节点内排序 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

约束/索引：
- `uq_kp_subject_parent_name`：UNIQUE (subject_id, parent_id, name)（同级重名防呆）
- `ix_kp_subject_parent`：(subject_id, parent_id)（树查询）
- `ix_kp_subject_level`：(subject_id, level)

> level 三级（章/节/知识点）为 M1 粒度；若后续需要更细可扩展 level 4 或加 `path` 物化列，走迁移。

### 2.4 questions —— 题库

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| subject_id | UUID | NOT NULL, FK → subjects.id | 科目隔离 |
| knowledge_point_id | UUID | NOT NULL, FK → knowledge_points.id | 归属知识点（叶子级） |
| type | VARCHAR(20) | NOT NULL | 题型，见 §3.1 |
| content | TEXT | NOT NULL | 题干（含 LaTeX，如 `$\\lim_{x\\to0}\\frac{\\sin x}{x}$`） |
| options | JSONB | NULL | 选择题选项：`[{"key":"A","text":"..."}]`；填空/大题置 NULL |
| answer | JSONB | NOT NULL | 答案，见 §3.3 |
| analysis | TEXT | NULL | 解析（作答应答后返回） |
| difficulty | SMALLINT | NOT NULL, DEFAULT 3, CHECK (1..5) | 1 易 → 5 难 |
| source | VARCHAR(20) | NOT NULL, DEFAULT 'self_built', CHECK | `textbook` 教材 / `past_exam` 真题 / `self_built` 自建 / `ugc` 用户上传 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK | `draft` / `active` / `archived` |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

索引：
- `ix_questions_subject_kp_diff`：(subject_id, knowledge_point_id, difficulty)（题单 / 自适应选题）
- `ix_questions_subject_status`：(subject_id, status)（上架题过滤）

> 作答前 API 不返回 `answer` / `analysis`（architecture §5 契约要点）。

### 2.5 question_embeddings —— 题目向量

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| question_id | UUID | NOT NULL, FK → questions.id | |
| subject_id | UUID | NOT NULL, FK → subjects.id | 冗余，便于带科目过滤检索 |
| embedding | VECTOR(1024) | NOT NULL | DeepSeek Embedding 维度基线 1024 |
| model | VARCHAR(100) | NOT NULL | 生成向量用的 embedding 模型名 |
| content_hash | VARCHAR(64) | NOT NULL | 题干内容 sha256，防重复入库 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

约束/索引：
- `uq_qemb_question_model`：UNIQUE (question_id, model)（同题同模型只存一份）
- `ix_qemb_subject`：(subject_id)
- 向量索引：HNSW `ix_qemb_embedding_hnsw` USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)

> 维度说明：architecture §3.3 基线 VECTOR(1024)；若 embedding 模型返回维度不同，走迁移 ALTER COLUMN 调整（同步更新本文档）。
> 检索 SQL：`SELECT * FROM question_embeddings WHERE subject_id=:sid ORDER BY embedding <=> :qvec LIMIT 10`。

### 2.6 document_chunks —— 教材向量库（RAG 语料）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| subject_id | UUID | NOT NULL, FK → subjects.id | 科目隔离 |
| source | VARCHAR(200) | NOT NULL | 教材名（如《高等数学 同济第七版》） |
| chapter | VARCHAR(100) | NULL | 章（元数据，展示用） |
| section | VARCHAR(100) | NULL | 节 |
| page | VARCHAR(20) | NULL | 页码（字符串，容忍"78-80"） |
| chunk_text | TEXT | NOT NULL | 分块原文（≤500 tokens / 约 1200 汉字） |
| embedding | VECTOR(1024) | NULL | 可空：embedding 任务后台生成，M1 允许降级关键词检索 |
| meta | JSONB | NOT NULL, DEFAULT '{}' | 额外元数据（标题层级、块序号等） |
| content_hash | VARCHAR(64) | NOT NULL | 正文 sha256，去重 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

约束/索引：
- `uq_doc_subject_hash`：UNIQUE (subject_id, content_hash)（防重复入库，架构 §3.2）
- `ix_doc_subject`：(subject_id)
- 向量索引：HNSW `ix_doc_embedding_hnsw` USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)

> 检索：`WHERE subject_id=:sid ORDER BY embedding <=> :qvec LIMIT 5`，相似度阈值 0.75（architecture §3.4）。

### 2.7 wrong_answers —— 错题本

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| user_id | UUID | NOT NULL, FK → users.id | |
| question_id | UUID | NOT NULL, FK → questions.id | |
| subject_id | UUID | NOT NULL, FK → subjects.id | 冗余，错题本按科分组 |
| wrong_answer | JSONB | NULL | 用户答错的答案（快照） |
| wrong_reason | TEXT | NULL | 错因（用户自填 / AI 分析） |
| review_count | INT | NOT NULL, DEFAULT 0 | 复习次数 |
| mastered | BOOLEAN | NOT NULL, DEFAULT false | 是否已掌握（错题本"标记已掌握"） |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

约束/索引：
- `uq_wrong_user_question`：UNIQUE (user_id, question_id)（幂等：重复提交不产生重复记录，flows.md）
- `ix_wrong_user_subject_mastered`：(user_id, subject_id, mastered)（错题本列表/分组）

### 2.8 user_knowledge_states —— 知识点掌握状态（自适应选题核心）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| user_id | UUID | NOT NULL, FK → users.id | |
| knowledge_point_id | UUID | NOT NULL, FK → knowledge_points.id | |
| subject_id | UUID | NOT NULL, FK → subjects.id | 冗余，自适应选题按科过滤 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'untouched', CHECK | 状态机，见 §3.4 |
| correct_count | INT | NOT NULL, DEFAULT 0 | 累计正确次数 |
| wrong_count | INT | NOT NULL, DEFAULT 0 | 累计错误次数 |
| last_practiced_at | TIMESTAMPTZ | NULL | 最近练习时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

约束/索引：
- `uq_ukstate_user_kp`：UNIQUE (user_id, knowledge_point_id)（每用户每知识点一行）
- **`ix_ukstate_user_subject_status`：(user_id, subject_id, status)（自适应选题复合索引：先捞薄弱/待巩固知识点）**
- `ix_ukstate_user_subject_upd`：(user_id, subject_id, updated_at)（最近练习排序）

> 状态机（flows.md 状态流转表）：
> - `untouched` 未接触：初始；离开条件=首次做题
> - `consolidating` 待巩固：正确率 40%~70%；离开=连续 3 次正确 → mastered
> - `mastered` 已掌握：连续 3 次正确；离开=后续错误率回升 → consolidating/weak
> - `weak` 薄弱：正确率 < 40%；离开=连续 3 次正确 → mastered
>
> 正确率 = correct_count / (correct_count + wrong_count)。连续 3 次正确需要独立会话计数器（MVP 可用 correct_count 增量判断，严格版本后续加 streak 字段，走迁移）。

### 2.9 plans —— 备考计划（简化 study_plans）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| user_id | UUID | NOT NULL, FK → users.id | |
| subject_id | UUID | NOT NULL, FK → subjects.id | |
| title | VARCHAR(200) | NULL | 计划标题（如"期末冲刺计划"） |
| exam_date | DATE | NULL | 考试日期（倒计时） |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK | `active` / `completed` / `cancelled` |
| config | JSONB | NOT NULL, DEFAULT '{}' | 每日任务配置（题量、知识点集等） |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

索引：`ix_plans_user_subject_status`：(user_id, subject_id, status)

### 2.10 study_sessions —— 学习记录 / 每日打卡

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| user_id | UUID | NOT NULL, FK → users.id | |
| subject_id | UUID | NOT NULL, FK → subjects.id | |
| plan_id | UUID | NULL, FK → plans.id | 关联计划（可选） |
| session_date | DATE | NOT NULL | 打卡日期 |
| questions_practiced | INT | NOT NULL, DEFAULT 0 | 当日做题数 |
| correct_count | INT | NOT NULL, DEFAULT 0 | 当日正确数 |
| checked_in | BOOLEAN | NOT NULL, DEFAULT false | 是否打卡 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

约束/索引：
- `uq_session_user_date`：UNIQUE (user_id, session_date)（每日一行；打卡乐观锁= UPDATE ... WHERE checked_in=false 返回 0 行即已打卡）
- `ix_session_user_subject_date`：(user_id, subject_id, session_date)

### 2.11 ai_explanations —— AI 讲解缓存（省钱，ADR-0002）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| question_id | UUID | NOT NULL, FK → questions.id | |
| model | VARCHAR(20) | NOT NULL | flash / pro |
| content_hash | VARCHAR(64) | NOT NULL | 输入上下文（题目+追问）hash |
| explanation | JSONB | NOT NULL | 讲解产物：`{steps, conclusion, citations, uncovered}`（architecture §3.5） |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

约束/索引：`uq_expl_question_model_hash`：UNIQUE (question_id, model, content_hash)

### 2.12 chat_sessions —— AI 追问会话

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| user_id | UUID | NOT NULL, FK → users.id | |
| question_id | UUID | NULL, FK → questions.id | 起始题目（可选） |
| session_key | VARCHAR(64) | NOT NULL, UNIQUE | followup_session_id |
| messages | JSONB | NOT NULL, DEFAULT '[]' | 最近 N 轮消息 `[{role, content}]` |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

### 2.13 token_usage —— LLM 计量

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, gen_random_uuid() | |
| user_id | UUID | NULL, FK → users.id | 匿名调用可为 NULL |
| model | VARCHAR(20) | NOT NULL | flash / pro |
| scene | VARCHAR(30) | NOT NULL | explain / followup / quiz / diagnosis / embed |
| prompt_tokens | INT | NOT NULL, DEFAULT 0 | |
| completion_tokens | INT | NOT NULL, DEFAULT 0 | |
| cost_est | NUMERIC(10,6) | NOT NULL, DEFAULT 0 | 估算成本（元） |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

索引：`ix_token_usage_created`：(created_at)（月度看板）

---

## 3. 枚举 / 取值清单

### 3.1 questions.type（题型）

基线题型（两科通用）：
- `single` 单选
- `multi` 多选
- `blank` 填空
- `essay` 大题（计算/证明/翻译/写作）

英语科目通过 `subjects.config.question_types` 扩展（架构 §2.4）：
- `reading` 阅读理解（M1 用单选承载，passage 放 content）
- `cloze` 完形填空（M1 用 blank 承载）
- `writing` 写作（M1 用 essay 承载）

> 不设 CHECK 约束，题型扩展按科目配置读取（ADR-0001：不因科目分支代码）。

### 3.2 subjects.config（JSONB，M1 最小集）

```jsonc
{
  "prompt_templates": {
    "explain": "你是{subject_name}助教…",
    "diagnosis": "根据做题记录分析薄弱知识点…",
    "quiz": "围绕知识点{name}出一道{difficulty}难度题…"
  },
  "question_types": ["single", "multi", "blank", "essay"],  // 英语加 reading/cloze/writing
  "default_difficulty": 3,
  "formula_enabled": true,   // 高数 true；英语 false
  "chapters": ["第1章 函数与极限", "..."]
}
```

### 3.3 questions.answer（JSONB 格式）

| type | answer 格式 | 示例 |
|---|---|---|
| single | `"A"` | `"C"` |
| multi | `["A","C"]` | `["A","D"]` |
| blank | 字符串（多个空用数组） | `"3"` / `["1","2"]` |
| essay | 参考答案文本 | `"因为 $\\lim_{x\\to0}\\frac{\\sin x}{x}=1$，所以…"` |

### 3.4 user_knowledge_states.status（知识点状态机）

| 取值 | 中文 | 含义 |
|---|---|---|
| `untouched` | 未接触 | 初始状态 |
| `consolidating` | 待巩固 | 正确率 40%~70% |
| `mastered` | 已掌握 | 连续 3 次正确 |
| `weak` | 薄弱 | 正确率 < 40% |

CHECK：`status IN ('untouched','consolidating','mastered','weak')`

### 3.5 其他枚举

| 字段 | 取值 | CHECK |
|---|---|---|
| users.role | `student` / `admin` | `role IN ('student','admin')` |
| questions.difficulty | 1~5 | `difficulty BETWEEN 1 AND 5` |
| questions.source | `textbook` / `past_exam` / `self_built` / `ugc` | CHECK |
| questions.status | `draft` / `active` / `archived` | CHECK |
| knowledge_points.level | 1 章 / 2 节 / 3 知识点 | `level BETWEEN 1 AND 3` |
| plans.status | `active` / `completed` / `cancelled` | CHECK |

---

## 4. 索引策略汇总

| 索引 | 表 | 列 | 用途 |
|---|---|---|---|
| `uq_users_username` | users | username | 登录 |
| `uq_subjects_code` | subjects | code | 科目查询 |
| `uq_kp_subject_parent_name` | knowledge_points | (subject_id, parent_id, name) | 同级防重 |
| `ix_kp_subject_parent` | knowledge_points | (subject_id, parent_id) | 图谱树查询 |
| `ix_kp_subject_level` | knowledge_points | (subject_id, level) | 章节过滤 |
| `ix_questions_subject_kp_diff` | questions | (subject_id, knowledge_point_id, difficulty) | 题单/选题 |
| `ix_questions_subject_status` | questions | (subject_id, status) | 上架过滤 |
| `uq_qemb_question_model` | question_embeddings | (question_id, model) | 向量幂等 |
| `ix_qemb_subject` | question_embeddings | subject_id | 向量按科过滤 |
| `ix_qemb_embedding_hnsw` | question_embeddings | embedding (HNSW, cosine) | 相似题检索 |
| `uq_doc_subject_hash` | document_chunks | (subject_id, content_hash) | RAG 入库去重 |
| `ix_doc_subject` | document_chunks | subject_id | RAG 按科过滤 |
| `ix_doc_embedding_hnsw` | document_chunks | embedding (HNSW, cosine) | 教材检索 |
| `uq_wrong_user_question` | wrong_answers | (user_id, question_id) | 错题幂等 |
| `ix_wrong_user_subject_mastered` | wrong_answers | (user_id, subject_id, mastered) | 错题本 |
| `uq_ukstate_user_kp` | user_knowledge_states | (user_id, knowledge_point_id) | 状态唯一 |
| **`ix_ukstate_user_subject_status`** | user_knowledge_states | **(user_id, subject_id, status)** | **自适应选题** |
| `ix_ukstate_user_subject_upd` | user_knowledge_states | (user_id, subject_id, updated_at) | 最近练习 |
| `ix_plans_user_subject_status` | plans | (user_id, subject_id, status) | 计划查询 |
| `uq_session_user_date` | study_sessions | (user_id, session_date) | 打卡幂等 |
| `ix_session_user_subject_date` | study_sessions | (user_id, subject_id, session_date) | 学习记录 |
| `uq_expl_question_model_hash` | ai_explanations | (question_id, model, content_hash) | 缓存命中 |
| `ix_token_usage_created` | token_usage | created_at | 成本看板 |

> 向量 HNSW 参数：`m=16, ef_construction=64`（pgvector 默认推荐），数据量增长后可按需调整 `ef_search`（查询时指定）。

---

## 5. 迁移与种子

- 迁移：Alembic（`backend/alembic/`），初始迁移 `versions/0001_initial.py` 建全部表 + 索引 + `CREATE EXTENSION IF NOT EXISTS vector`。
- 配置：`DATABASE_URL` 环境变量（如 `postgresql+psycopg://aceexam:aceexam@localhost:5432/aceexam`），`.env` 不入库。
- 种子：`backend/app/db/seed.py`（纯 SQLAlchemy 脚本，不依赖 FastAPI），幂等（已存在科目则跳过或 --reset 清空重建）。
- 种子内容（M1）：
  - 高数 + 英语两科 `subjects`（含 config）
  - 每科知识点图谱：≥ 3 章 × ≥ 5 知识点（章 → 知识点两级，节级留空待扩展）
  - 每科题库：≥ 30 题（含答案 + 解析，直接可刷）

---

## 6. 与 ep-ai 的向量表约定

| 事项 | 约定 |
|---|---|
| embedding 维度 | VECTOR(1024) 基线；若 DeepSeek Embedding 返回维度不同 → 迁移调整 + 更新本文档 |
| 分块粒度 | 单块 ≤ 500 tokens（约 1200 汉字），按标题层级+段落切，块间重叠 1 句（architecture §3.2） |
| 去重 | `content_hash`（正文 sha256）+ UNIQUE(subject_id, content_hash) |
| 检索 | `ORDER BY embedding <=> :qvec LIMIT 5`，阈值 0.75，必须带 subject_id 过滤 |
| 降级 | embedding 不可用 → `chunk_text` ILIKE / tsvector 关键词检索（M1 可先降级跑通） |
| 题目向量 | `question_embeddings` 与 `document_chunks` 分表；题目向量用于相似题召回/去重，教材向量用于 RAG 讲解 |

---

## 7. TBD / 开放项

- [ ] 自适应选题加权公式（MVP 规则版）落地后，可能需要给 `user_knowledge_states` 加 `streak`（连续正确）字段 → 走迁移
- [ ] 会员订阅明细表（支付流水）M1 不做，用 `users.is_member` + `member_expires_at` 占位
- [ ] 题目 UGC 审核流（status=draft → active）M1 只建字段，不建审核表
- [ ] `document_chunks` 的 title 层级元数据（meta JSONB 已预留）
