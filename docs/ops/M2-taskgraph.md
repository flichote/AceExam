# AceExam M2 任务图启动手册（kanban 多角色协作）

> **适用场景**：M1 已交付（表设计 + AI 服务骨架 + 脚手架 + 测试门禁）后，一键启动 M2 MVP 五件套开发。
> **前置**：6 个 ep-* 角色就绪，主 profile 网关在跑；board `aceexam` 已建。
> **M2 目标**（PRD §3 第一层）：智能刷题 / AI 讲解（RAG 真实化）/ 拍照录题 / 薄弱诊断 / 备考计划。
> **契约来源**：M2 模块设计见 `docs/architecture.md` §10；API 契约见 `docs/api.md`（前后端对接唯一依据，T7 产出）。

## 任务图设计

```
T7 ep-arch（架构师）                 ← root，本任务已派发
├── T8 ep-db（数据库）               ← parent T7：M2 表迁移（streak / ocr_uploads / diagnosis_reports / textbook_uploads）+ docs/database.md 增量
├── T9 ep-backend（后端）            ← parent T7：M2 API（按 docs/api.md：选题/提交答案/chat RAG+SSE/OCR/诊断/计划）
├── T10 ep-ai（AI 工程师）           ← parent T7：M2 AI 服务真实化（selection / rag 全套 / ocr_service / diagnosis / quiz_generator / subject_config）
└── T11 ep-frontend（前端）          ← parent T7：M2 五件套页面 + 真实 API 对接（mock fallback）
      └── T12 ep-qa（测试）          ← parents T9 + T10 + T11：M2 端到端验收测试
```

**并行规则**（沿用 M1 验证结论）：
- T8/T9/T10/T11 四个不同 profile → 可并行跑（各写各的目录）
- T12 等 T9 + T10 + T11 → dispatcher 自动解锁，无需手动派发
- 同一 profile 绝不并行两个任务（会互相踩 git）

## 依赖说明

| 边 | 含义 | 满足方式 |
|---|---|---|
| T7 → T8/T9/T10/T11 | 契约先行：`docs/architecture.md` §10（五件套模块设计 + 自适应公式 + 表结构增量约定）+ `docs/api.md`（字段级契约 + M1/M2 差异表） | 各任务开工前先读 architecture.md §10 与 api.md；T8 按 §10.6 建表，T9 按 api.md 实现路由，T10 按 §10.1~10.4 实现服务，T11 按 api.md 对接页面 |
| T8 → T9/T10（文档依赖） | T9 的 answers/诊断/OCR 端点、T10 的 selection/apply_answer 依赖 streak 字段与新表 | T8 优先产出 `docs/database.md` 增量（文档先行）；T9/T10 按文档并行开发，不等迁移脚本落地 |
| T9 ↔ T10（服务边界） | `selection.py`/`subject_config.py` 归 T10；T9 路由只 import 调用 | T9 若等不及 T10，先按 architecture.md §10.1 公式内联兜底实现（接口先行），T10 落地后替换并删除内联（卡片 comment 注明），禁止双实现长期并存 |
| T9 + T10 + T11 → T12 | 端到端验收需要前后端 + AI 服务联调 | dispatcher 自动解锁 |

> ⚠️ **T12 隐含依赖**：AI 服务测试需要 mock 上游（DeepSeek/Pix2Text），不真调 API；RAG 检索测试用内存/mock 向量库（沿用 M1 T5 模式）。

## 文件边界（避免重名冲突）

| 角色 | 写入目录 | 关键文件 |
|---|---|---|
| T8 ep-db | `backend/app/db/`、`backend/app/models/`、`backend/alembic/`、`docs/database.md` | `alembic/versions/0002_*.py`（streak 列 + ocr_uploads + diagnosis_reports + textbook_uploads） |
| T9 ep-backend | `backend/app/api/`、`backend/app/schemas/`、`backend/app/services/`（除 AI 专属外） | 新增 `api/v1/{ocr,diagnose,plans,textbooks}.py`；改造 `api/v1/{questions,chat}.py`；`services/plan_service.py` |
| T10 ep-ai | `backend/app/services/`（rag/、selection.py、ocr_service.py、diagnosis.py、quiz_generator.py、subject_config.py）+ `backend/tests/test_ai_*.py` | 复用 ep-backend 的 `llm_gateway.py`（import 方式，别改它） |
| T11 ep-frontend | `frontend/` | 五件套页面 + api client 对接；mock 保留在 `frontend/src/mock/` 做 fallback |
| T12 ep-qa | `backend/tests/`（除 test_ai_* 外）+ `docs/qa/` | 端到端验收测试 + test-report.md 更新；只加测试不改业务代码 |

## 执行步骤（个人电脑，git-bash）

### 1. 创建任务（ID 立即捕获，别手敲）

```bash
hermes kanban boards switch aceexam

# T7 架构师（root，本任务，已完成）
# T8 数据库（parent T7）
hermes kanban create "T8 数据库M2增量迁移" --profile ep-db --parent "$T7" --body "$(cat kanban/boards/aceexam/t8-body.md)"

# T9 后端（parent T7）
hermes kanban create "T9 后端M2五件套API" --profile ep-backend --parent "$T7" --body "$(cat kanban/boards/aceexam/t9-body.md)"

# T10 AI 服务（parent T7）
hermes kanban create "T10 AI服务M2真实化" --profile ep-ai --parent "$T7" --body "$(cat kanban/boards/aceexam/t10-body.md)"

# T11 前端（parent T7，mock fallback 可并行）
hermes kanban create "T11 前端M2五件套页面" --profile ep-frontend --parent "$T7" --body "$(cat kanban/boards/aceexam/t11-body.md)"

# T12 测试（parents T9+T10+T11，dispatcher 自动等待）
hermes kanban create "T12 QA端到端验收" --profile ep-qa --parent "$T9" --parent "$T10" --parent "$T11" --body "$(cat kanban/boards/aceexam/t12-body.md)"
```

### 2. 监控（主控主动汇报，别等）

```bash
hermes kanban list           # 状态总览
hermes kanban log <t_id>     # 看 worker 实时在干什么
git log --oneline -5         # 新提交
```

**进度汇报节奏**：每 10~15 分钟给用户一个快照（✓ done / ● running / ⊘ blocked / ◻ todo + 各 worker 实际动作 + 新 commit）。

### 3. worker 异常恢复速查（沿用 M1）

| 症状 | 处理 |
|---|---|
| 卡 `running` 但无日志 | 网关停了 → `hermes gateway status` + 重启，等 ~70s |
| 日志显示 API 连接错误（秒级失败） | 网络抖动 → `hermes kanban unblock <id> --reason "transient"` 重派一次 |
| 日志显示长上下文超时 | 别重派，主控收尾（M1-taskgraph §6 模式） |
| 迭代预算耗尽 | 主控收尾：log 看进度 → 本地验证 → 提交推送 → complete |

### 4. 主控收尾模式（worker 干不完时）

```bash
hermes kanban log <t_id> | tail -30
env -u PYTHONPATH -u VIRTUAL_ENV backend/.venv/Scripts/python.exe -m pytest -v
cd <repo> && git add <对应目录> && git commit -m "主控收尾: ..." && git push
hermes kanban comment <t_id> "✅ 收尾：<证据>"
hermes kanban complete <t_id>
```

## 验收标准（M2 完成 = 全部满足）

- [ ] `docs/architecture.md` §10：五件套模块设计（自适应公式 / RAG 真实化路径 / OCR 集成 / 诊断引擎 / 计划规则引擎）+ 表结构增量约定
- [ ] `docs/api.md`：28 端点契约（字段级）+ M1/M2 差异表（新增/修改/废弃标注）
- [ ] Alembic 0002 迁移：`user_knowledge_states.streak` + `ocr_uploads` + `diagnosis_reports` + `textbook_uploads`
- [ ] 智能刷题：`GET /subjects/{id}/practice/questions`（自适应，公式见 architecture.md §10.1）+ `POST /questions/{id}/answers`（streak 更新、连续 3 次正确 → mastered）
- [ ] AI 讲解：`POST /chat/explain` RAG 真实化（pgvector 检索 → pro 讲解 → citations 溯源 → uncovered 兜底）+ SSE 流式；追问有上下文
- [ ] 拍照录题：`POST /ocr/upload`（Pix2Text 识别 → 结构化 → 知识点推荐）+ `POST /questions/from-ocr`（幂等入库）
- [ ] 薄弱诊断：自测三端点（发起 → 取题 → 报告）；薄弱 Top5 与自测表现一致（规则计算排名，LLM 只润色建议）
- [ ] 备考计划：`POST /plans`（倒计时 + 每日任务）→ `GET /plans/active`（今日任务 + 预告）→ `POST /plans/{id}/checkin`（重复打卡幂等）
- [ ] 前端五件套页面 + 真实 API 对接（mock fallback 保留），`npm run build` 通过
- [ ] pytest 全绿（含 M2 端到端验收测试），`docs/qa/test-report.md` 更新
- [ ] 全部代码已 push，`git log --oneline` 每个任务一条以上 feature commit
