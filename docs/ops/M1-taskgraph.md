# AceExam M1 任务图启动手册（kanban 多角色协作）

> **适用场景**：个人电脑（Win11）clone 仓库 + 重建角色后，一键启动 M1 开发。
> **前置**：`bash hermes/setup-roles.sh` 已跑通（6 个 ep-* 角色就绪），主 profile 网关在跑。
> **M1 目标**（PRD §8）：数据库表设计（题库/知识点图谱/向量表）+ AI 服务骨架 + uni-app 脚手架。
> **M2 任务图**：M1 完成后，M2（MVP 五件套，T7~T12）见 [M2-taskgraph](./M2-taskgraph.md)。

## 任务图设计

```
T1 ep-arch（架构师）                 ← root，先派发
├── T2 ep-db（数据库）               ← parent T1：表设计 + Alembic + 种子数据（高数+英语）
├── T3 ep-backend（后端）            ← parent T1：FastAPI 骨架 + LLM 网关 + auth/题库/错题 API
│     └── T5 ep-ai（AI 工程师）      ← parent T3：RAG 讲解引擎 + flash/pro 分级 + Pix2Text 服务
└── T4 ep-frontend（前端）           ← parent T1：uni-app 脚手架 + 页面（mock 先行）
      └── T6 ep-qa（测试）           ← parents T3 + T4：pytest 门禁 + 烟测 + 缺陷报告
```

**并行规则**（已验证 2026-08）：
- T2/T3/T4 三个不同 profile → 可并行跑（各写各的目录：backend/、frontend/、docs/database.md）
- T5 等 T3、T6 等 T3+T4 → dispatcher 自动解锁，无需手动派发
- 同一 profile 绝不并行两个任务（会互相踩 git）

### 依赖说明（T1 完善，2026-08-07）

| 边 | 含义 | 满足方式 |
|---|---|---|
| T1 → T2/T3/T4 | 架构基线先行：`docs/architecture.md` + ADR-0001~0003 定义 subject 维度数据模型方向、API 路由骨架、LLM 分级约束 | 三个任务开工前先读 architecture.md；T2 按 ADR-0001 建 subject_id 维度，T3 按 §6 路由骨架落地，T4 按 §2.3 前端参数化 |
| T1 → 全部 | 接口契约（API 字段/表结构）由 ep-arch 评审锁定，变更走文档 | 各任务交付时在卡片 comment 附 schema/API 摘要，ep-arch 评审后锁定 |
| T2 → T3/T5（文档依赖） | T3 的 auth/题库 API、T5 的 retriever 依赖表结构 | T2 优先产出 `docs/database.md`（文档先行）；T3/T5 可按文档并行开发，不等迁移脚本落地 |
| T3 → T5 | T5 复用 `llm_gateway`（T3 交付） | T5 body 已约定 import 复用、不改 gateway |
| T3 + T4 → T6 | 烟测需要前后端联调 | dispatcher 自动解锁 |

> ⚠️ **T5 隐含依赖**：retriever 依赖 pgvector 向量表（T2 产物）。若 T2 未完成，T5 先用 mock/内存向量跑通 RAG 骨架（接口先行），T2 落地后接真库 —— 不要阻塞等待。

### T1 交付物对下游的硬约束（下游开工前必读）

- `docs/architecture.md` §2：subject 维度贯穿 —— 所有内容表带 `subject_id`，代码不因科目分支
- `docs/architecture.md` §4：LLM 分级 —— llm_gateway 统一入口，flash/pro 按场景路由
- `docs/architecture.md` §3 + ADR-0003：AI 讲解必须 RAG 溯源，无命中兜底"教材未覆盖"，禁止编造
- `docs/architecture.md` §5：API 路由骨架 —— 列表接口必须支持 `subject_id` 过滤；作答前不返回 answer

## 执行步骤（个人电脑，git-bash）

### 0. 前置检查

```bash
hermes kanban boards         # 看现有 board
hermes gateway status        # 主 profile 网关必须在跑（dispatcher 靠它 tick）
hermes profile list          # 6 个 ep-* 角色，Gateway stopped = 正常
```

### 1. 建 board

```bash
hermes kanban boards create aceexam --name "AceExam M1 里程碑"
hermes kanban boards switch aceexam
```

### 2. 写任务 body 文件（放仓库 kanban/boards/aceexam/，随仓库走）

```bash
mkdir -p kanban/boards/aceexam
```

### 3. 按顺序创建任务（ID 立即捕获，别手敲）

```bash
# T1 架构师（root）
hermes kanban create "T1 架构与里程碑拆解" --profile ep-arch --body "$(cat kanban/boards/aceexam/t1-body.md)"
T1=$(hermes kanban list | grep "T1 " | grep -oE 't_[a-f0-9]+' | head -1)

# T2 数据库（parent T1）
hermes kanban create "T2 数据库设计+迁移+种子" --profile ep-db --parent "$T1" --body "$(cat kanban/boards/aceexam/t2-body.md)"

# T3 后端（parent T1）
hermes kanban create "T3 FastAPI骨架+LLM网关+核心API" --profile ep-backend --parent "$T1" --body "$(cat kanban/boards/aceexam/t3-body.md)"

# T4 前端（parent T1，mock 先行可并行）
hermes kanban create "T4 uni-app脚手架+页面" --profile ep-frontend --parent "$T1" --body "$(cat kanban/boards/aceexam/t4-body.md)"

# T5 AI 服务（parent T3）
hermes kanban create "T5 AI服务骨架(RAG+分级+OCR)" --profile ep-ai --parent "$T3" --body "$(cat kanban/boards/aceexam/t5-body.md)"

# T6 测试（parents T3+T4）
hermes kanban create "T6 测试门禁+烟测" --profile ep-qa --parent "$T3" --parent "$T4" --body "$(cat kanban/boards/aceexam/t6-body.md)"
```

> ⚠️ 若 `kanban create` 后需要确认 ID：`hermes kanban list` 查看，T1 的 ID 以实际输出为准。
> ⚠️ 若某个 ID 手滑填错，重新 create 该任务并带正确 `--parent` 即可，别 edit。

### 4. 监控（主控主动汇报，别等）

```bash
hermes kanban list           # 状态总览
hermes kanban log <t_id>     # 看 worker 实时在干什么（最后几行 = 真实进展）
hermes kanban diag           # 诊断
git log --oneline -5         # 新提交
```

**进度汇报节奏**：每 10~15 分钟给用户一个快照（✓ done / ● running / ⊘ blocked / ◻ todo + 各 worker 实际动作 + 新 commit）。用户明确要求：不能黑盒。

### 5. worker 异常恢复速查

| 症状 | 处理 |
|---|---|
| 卡 `running` 但无日志 | 网关停了 → `hermes gateway status` + 重启，等 ~70s |
| 日志显示 API 连接错误（秒级失败） | 网络抖动 → `hermes kanban unblock <id> --reason "transient"` 重派一次 |
| 日志显示 200-280s 超时 + 大上下文 | 长上下文超时 → 别重派，主控收尾（见下） |
| 迭代预算 90/90 耗尽 | 主控收尾：log 看进度 → 本地验证 → 提交推送 → complete |
| `done` 但 git 没提交 | `git status --porcelain` + `git log --diff-filter=A` 检查 → 主控提交收尾 |

### 6. 主控收尾模式（worker 干不完时）

```bash
hermes kanban log <t_id> | tail -30     # 看到哪了
# 本地验证（注意 PYTHONPATH 污染）：
env -u PYTHONPATH -u VIRTUAL_ENV backend/.venv/Scripts/python.exe -m pytest -v
# 提交推送：
cd <repo> && git add <对应目录> && git commit -m "主控收尾: ..." && git push
hermes kanban comment <t_id> "✅ 收尾：<证据>"
hermes kanban complete <t_id>
```

## 验收标准（M1 完成 = 全部满足）

- [ ] `docs/architecture.md` 存在：模块划分 + 科目模板设计（subject 维度）+ RAG 管线方案 + LLM 分级；ADR-0001~0003 在 `docs/adr/`
- [ ] `docs/database.md` + Alembic 迁移：users/subjects/knowledge_points/questions/vector_embeddings/wrong_answers 表
- [ ] 种子数据：高数 + 英语两科的知识点图谱 + 初始题库（每科 ≥ 30 题）
- [ ] FastAPI 骨架：`/healthz` 200、auth 注册/登录、题库/错题 API、LLM 网关（flash/pro 分级）
- [ ] AI 服务：RAG 讲解引擎骨架（pgvector 检索 → DeepSeek 讲解）、Pix2Text OCR 集成方案
- [ ] uni-app 脚手架：选科页 + 刷题页 + 对话页（mock 先行，KaTeX 渲染公式）
- [ ] pytest 全绿（三层门禁：单元/API/烟测）
- [ ] 全部代码已 push，`git log --oneline` 每个任务一条以上 feature commit
