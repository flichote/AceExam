# AceExam M3 任务图启动手册（kanban 多角色协作）

> **适用场景**：M2（MVP 五件套）已交付后，一键启动 M3 开发（体验增强 + 增长功能）。
> **前置**：6 个 ep-* 角色就绪，主 profile 网关在跑；board `aceexam` 已建；T13 已产出契约文档。
> **M3 目标**（PRD §3 第二/三层）：知识点图谱可视化 / 考前突击模式 / 打卡连胜 / 学习数据看板 / 排行榜 / 挂科风险预警。
> **契约来源**：模块设计见 `docs/architecture.md` §11（含决策锁定表 D1~D8）；API 契约见 `docs/api.md` §11（新增 7 端点，总计 35）；表结构增量见 `docs/database.md` §9（T14 产出）。

## 任务图设计

```
T13 ep-arch（架构师）                 ← root，本任务已交付契约
├── T14 ep-db（数据库）               ← parent T13：sprint_sessions 新表迁移 + database.md §9 增量
├── T15 ep-backend（后端）            ← parent T13：M3 API（图谱/突击/看板/排行/预警 + 连胜统计）
│     └── T17 ep-ai（AI 工程师）      ← parent T15：sprint 题单 + warning 预警 + knowledge_graph 服务
├── T16 ep-frontend（前端）           ← parent T13：图谱可视化/突击页/看板/排行/预警/连胜徽章
└── T18 ep-qa（测试）                 ← parents T15 + T16 + T17：M3 验收测试
```

**已建卡片 ID（2026-08-08，T13 任务图中捕获）**：

| 任务 | 卡片 ID | 备注 |
|---|---|---|
| T13 | t_4348368e | 本任务（架构增量 + API 契约），done 后解锁 T14/T15/T16 |
| T14 | t_fdae6af1 | 待 T13 done 自动解锁 |
| T15 | t_e3b56bb9 | 待 T13 done 自动解锁 |
| T16 | t_a70a5ea7 | 待 T13 done 自动解锁 |
| T17 | t_6e419c19 | parent=T15，T15 done 后解锁 |
| T18 | t_58ef44da | parents=T15+T16+T17（T17→T18 依赖边由 T13 补充链接，见下） |

**并行规则**（沿用 M1/M2 验证结论）：
- T14/T15/T16 三个不同 profile → 可并行跑（各写各的目录）
- T15 → T17（AI 服务）串行依赖；T17 → T18 已在板上补充依赖边（kanban_link t_6e419c19 → t_58ef44da，因为 T18 的 sprint/warning 测试需要 T17 服务，原卡片 parents 漏了 T17，架构评审已补）
- T18 等 T15 + T16 + T17 → dispatcher 自动解锁
- 同一 profile 绝不并行两个任务（会互相踩 git）

## 依赖说明

| 边 | 含义 | 满足方式 |
|---|---|---|
| T13 → T14/T15/T16 | 契约先行：`docs/architecture.md` §11（模块设计 + 决策锁定 D1~D8 + 表增量约定）+ `docs/api.md` §11（字段级契约） | 各任务开工前先读 architecture.md §11 与 api.md §11；T14 按 §11.7 建表，T15 按 api.md §11 实现路由，T16 按 §11.1~11.3 对接页面 |
| T14 → T15/T17（文档依赖） | T15 的 sprint 端点、T17 的 sprint 服务依赖 `sprint_sessions` 表 | T14 优先产出 `docs/database.md` §9 增量（文档先行）；T15/T17 按文档并行开发，不等迁移脚本落地 |
| T15 → T17（服务边界） | `sprint.py`/`warning.py`/`knowledge_graph.py` 归 T17；T15 路由只 import 调用 | T15 若等不及 T17，先按 architecture.md §11.2/§11.6 规则内联兜底实现（接口先行），T17 落地后替换并删除内联（卡片 comment 注明），禁止双实现长期并存 |
| T15 + T16 + T17 → T18 | 端到端验收需要前后端 + AI 服务联调 | dispatcher 自动解锁（依赖边已补全） |

> ⚠️ **T18 隐含依赖**：AI 服务测试需要 mock 上游（DeepSeek），不真调 API；连胜/风险等级断言以 architecture.md §11.3/§11.6 的确定版规则为准（边界值写进测试用例）。

## 文件边界（避免重名冲突）

| 角色 | 写入目录 | 关键文件 |
|---|---|---|
| T14 ep-db | `backend/app/db/`、`backend/app/models/`、`backend/alembic/`、`docs/database.md` | `alembic/versions/0003_m3_sprint.py`（sprint_sessions 新表；连胜/排行/预警确认无新表，architecture.md §11.7） |
| T15 ep-backend | `backend/app/api/`、`backend/app/schemas/`、`backend/app/services/`（除 AI 专属外） | 新增 `api/v1/{sprint,dashboard,leaderboard,warnings,knowledge_graph}.py`（或 me.py 合并）；`services/streak.py`（连胜纯函数）；顺手修复 D-8/D-9/D-11/D-16 |
| T17 ep-ai | `backend/app/services/`（sprint.py、warning.py、knowledge_graph.py）+ `backend/tests/test_ai_m3.py` | 复用 ep-backend 的 `llm_gateway.py`（import 方式，别改它） |
| T16 ep-frontend | `frontend/` | 图谱可视化（uni-echarts / renderjs / canvas 降级）、突击页、看板页、排行榜页、预警卡片、连胜徽章；mock 保留在 `frontend/src/mock/` 做 fallback |
| T18 ep-qa | `backend/tests/`（除 test_ai_* 外）+ `docs/qa/` | M3 验收测试 + test-report.md 三里程碑汇总；只加测试不改业务代码 |

## 执行步骤（个人电脑，git-bash）

### 1. 创建/补全任务（ID 立即捕获，别手敲）

```bash
hermes kanban boards switch aceexam

# T14/T15/T16 已建（parent T13）；若缺失按 M2 模式补建：
# hermes kanban create "T14 M3表迁移" --profile ep-db --parent "$T13" --body "$(cat kanban/boards/aceexam/t14-body.md)"
# hermes kanban create "T15 M3全部API" --profile ep-backend --parent "$T13" --body "$(cat kanban/boards/aceexam/t15-body.md)"
# hermes kanban create "T16 M3页面" --profile ep-frontend --parent "$T13" --body "$(cat kanban/boards/aceexam/t16-body.md)"

# T17（parent T15）与 T18（parents T15+T16+T17）：
# hermes kanban create "T17 AI突击+预警服务" --profile ep-ai --parent "$T15" --body "$(cat kanban/boards/aceexam/t17-body.md)"
# hermes kanban create "T18 M3验收测试" --profile ep-qa --parent "$T15" --parent "$T16" --parent "$T17" --body "$(cat kanban/boards/aceexam/t18-body.md)"
```

> 当前板上 T17（t_6e419c19）、T18（t_58ef44da）已存在；T18 的 T17 依赖边已由 T13 通过 `kanban_link` 补上（架构评审确认 T18 body 需要 T17 的 sprint/warning 服务）。

### 2. 监控（主控主动汇报，别等）

```bash
hermes kanban list           # 状态总览
hermes kanban log <t_id>     # 看 worker 实时在干什么
git log --oneline -5         # 新提交
```

**进度汇报节奏**：每 10~15 分钟给用户一个快照（✓ done / ● running / ⊘ blocked / ◻ todo + 各 worker 实际动作 + 新 commit）。

### 3. worker 异常恢复速查（沿用 M1/M2）

| 症状 | 处理 |
|---|---|
| 卡 `running` 但无日志 | 网关停了 → `hermes gateway status` + 重启，等 ~70s |
| 日志显示 API 连接错误（秒级失败） | 网络抖动 → `hermes kanban unblock <id> --reason "transient"` 重派一次 |
| 日志显示长上下文超时 | 别重派，主控收尾（M2-taskgraph §4 模式） |
| 迭代预算耗尽 | 主控收尾：log 看进度 → 本地验证 → 提交推送 → complete |

### 4. 主控收尾模式（worker 干不完时）

```bash
hermes kanban log <t_id> | tail -30
env -u PYTHONPATH -u VIRTUAL_ENV backend/.venv/Scripts/python.exe -m pytest -v
cd <repo> && git add <对应目录> && git commit -m "主控收尾: ..." && git push
hermes kanban comment <t_id> "✅ 收尾：<证据>"
hermes kanban complete <t_id>
```

## 验收标准（M3 完成 = 全部满足）

- [ ] `docs/architecture.md` §11：图谱可视化 / 突击模式 / 连胜 / 看板 / 排行 / 预警六模块设计 + 决策锁定表（D1~D8）
- [ ] `docs/api.md` §11：7 个新端点字段级契约，端点总数 28 → 35
- [ ] Alembic 0003 迁移：`sprint_sessions` 新表；连胜/排行榜/预警确认无新表（architecture.md §11.7 决策）
- [ ] 图谱：`GET /subjects/{id}/knowledge-graph`（三级树 + 节点状态聚合：任一 weak→weak 等；叶子带 practice_count/accuracy）
- [ ] 突击：`POST /subjects/{id}/sprint/activate`（幂等 + 会员边界）+ `GET /subjects/{id}/sprint/questions`（高频考点 + 个人错题交集、去重、限量、快照稳定；`mode=mock` 模拟卷元数据）
- [ ] 看板：`GET /me/dashboard`（做题量/正确率/掌握度/连胜/薄弱计数）+ `GET /me/dashboard/trend`（day/week/month 桶、空数据边界）
- [ ] 排行：`GET /leaderboard`（global/subject 维度；主=累计正确题数、次=正确率≥30 门槛、<30 题不进榜；`me` 排名）
- [ ] 预警：`GET /me/warnings`（风险等级边界 high/medium/low 按 architecture.md §11.6 表；reasons 规则层生成、suggestion LLM 措辞）
- [ ] 打卡连胜：current/longest 计算正确（连续/中断边界；Asia/Shanghai 日界）
- [ ] 前端五页面 + 真实 API 对接（图谱 uni-echarts + canvas 降级、趋势折线图），`npm run build` 通过（h5 + mp-weixin）
- [ ] pytest 全绿（含 M3 验收测试 + M1/M2 回归），`docs/qa/test-report.md` 更新三里程碑汇总
- [ ] 全部代码已 push，`git log --oneline` 每个任务一条以上 feature commit
