# AceExam M5 任务图启动手册（kanban 多角色协作）

> **适用场景**：M4（专业选课 + 课程广场）已交付后，一键启动 M5 开发（题库策略落地：课程归一对齐 + 题库飞轮）。
> **前置**：6 个 ep-* 角色就绪，主 profile 网关在跑；board `aceexam` 已建；T28 已产出契约文档。
> **M5 目标**（`docs/product/题库策略.md`）：解决「每个学校课程不同，题库怎么完善」——课程三级归一对齐（course_aliases 映射 + subjects.level）+ 题库飞轮（UGC 传题 + AI 初审管线）。
> **契约来源**：模块设计见 `docs/architecture.md` §14（含决策锁定表 D19~D22）；API 契约见 `docs/api.md` §14（T28 产出，新增 5 端点，总计 52）；表结构增量见 `docs/database.md` §12（T29 产出，迁移 `0006_course_alias_level`）。

## 任务图设计

```
T28 ep-arch（架构师）                 ← root，本任务交付契约 + 任务图
├── T29 ep-db（数据库）               ← parent T28：course_aliases 新表 + subjects.level + 迁移 0006
├── T30 ep-backend（后端）            ← parent T28：课程对齐 API + UGC 审核流 API
│     └── T31 ep-ai（AI 工程师）      ← parent T30：课程名匹配 + AI 初审管线
├── T32 ep-frontend（前端）           ← parent T28：校本课程录入 + 题库共建入口
└── T33 ep-qa（测试）                 ← parents T30+T31+T32：M5 验收测试
```

**已建卡片 ID（2026-08-08，T28 任务图中捕获）**：

| 任务 | 卡片 ID | 备注 |
|---|---|---|
| T28 | t_37b117e3 | 本任务（架构增量 + API 契约 + 任务图），done 后解锁 T29/T30/T32 |
| T29 | 待建 | 待 T28 done 自动解锁 |
| T30 | 待建 | 待 T28 done 自动解锁 |
| T31 | 待建 | 待 T30 done 自动解锁 |
| T32 | 待建 | 待 T28 done 自动解锁 |
| T33 | 待建 | 待 T30+T31+T32 done 自动解锁 |

**并行规则**（沿用 M1~M4 验证结论）：

- T29/T30/T32 三个不同 profile → 可并行跑（各写各的目录：T29 写 backend alembic + database.md §12，T30 写 backend app，T32 写 frontend）
- T31 依赖 T30（接口先行，T31 写 AI 服务层）→ 无死锁
- T33 等 T30 + T31 + T32 → 依赖边建全后 dispatcher 自动解锁
- 同一 profile 绝不并行两个任务（会互相踩 git）

## 依赖说明

| 边 | 含义 | 满足方式 |
|---|---|---|
| T28 → T29/T30/T32 | 契约先行：`docs/architecture.md` §14 + `docs/api.md` §14（字段级契约） | 各任务开工前先读 §14；T29 按 §14 建表（0006 迁移），T30 按 api.md §14 实现路由，T32 按 §14 对接页面 |
| T30 → T31 | AI 服务依赖后端接口契约 | T30 交付后 dispatcher 自动解锁 T31 |
| T30+T31+T32 → T33 | 端到端验收需要前后端 + AI 联调 | dispatcher 自动解锁 |

## 文件边界（避免重名冲突）

| 角色 | 写入目录 | 关键文件 |
|---|---|---|
| T29 ep-db | `backend/alembic/`、`backend/app/db/`、`docs/database.md` | `alembic/versions/0006_course_alias_level.py`（course_aliases 表 + subjects.level + user_subjects.template_subject_id）；`db/seed.py`（公共课 level='public' 回填 + course_aliases 种子）；database.md §12 增量 |
| T30 ep-backend | `backend/app/api/`、`backend/app/schemas/`、`backend/app/models/` | `api/v1/courses.py`（14.1~14.3）+ `api/v1/ugc.py` 扩展（14.4~14.5）；schemas/courses.py；models：course_aliases / subjects.level / user_subjects.template_subject_id |
| T31 ep-ai | `backend/app/services/` | `services/course_matcher.py`（AI 课程名匹配）+ `services/ugc_review.py`（AI 初审管线）+ `services/ugc_service.py` 扩展（规则预检后接入 AI 初审） |
| T32 ep-frontend | `frontend/` | 校本课程录入页、课程广场按模板课展示、题库共建（投稿）入口；mock 保留在 `frontend/src/mock/` 做 fallback |
| T33 ep-qa | `backend/tests/`（除 test_ai_* 外）+ `docs/qa/` | 课程对齐验收测试 + UGC 审核流测试 + test-report.md 更新；只加测试不改业务代码（发现 bug 记录在案） |

## 执行步骤（个人电脑，git-bash）

### 1. 创建任务（ID 立即捕获，别手敲）

```bash
hermes kanban boards switch aceexam
hermes kanban create --title "T28 M5架构增量+API契约" --assignee ep-arch --body kanban/boards/aceexam/t28-body.md
# 依 T28 done 后解锁 T29/T30/T32；T31 parent=T30；T33 parents=T30+T31+T32
```

### 2. 监控（主控主动汇报，别等）

```bash
hermes kanban list           # 状态总览
hermes kanban log <t_id>     # 看 worker 实时在干什么
git log --oneline -5         # 新提交
```

**进度汇报节奏**：每 10~15 分钟给用户一个快照（✓ done / ● running / ⊘ blocked / ◻ todo + 各 worker 实际动作 + 新 commit）。

### 3. worker 异常恢复速查（沿用 M1~M4）

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

## 验收标准（M5 完成 = 全部满足）

- [ ] `docs/architecture.md` §14：课程归一对齐 + 题库飞轮模块设计 + 决策锁定表（D19~D22）
- [ ] `docs/api.md` §14：新端点字段级契约（课程别名查询/映射确认、校本课程录入、UGC 投稿 + AI 初审状态查询）
- [ ] Alembic 0006 迁移：`course_aliases` 表 + `subjects.level` + `user_subjects.template_subject_id`
- [ ] 种子数据：高数/英语等公共课 level='public'；course_aliases 种子（"高等数学A"/"高数上"→高数模板等）
- [ ] 课程映射：用户录入校本课程名 → AI 匹配到模板课程（含置信度），未匹配可手动建实例
- [ ] UGC 传题走 AI 初审：pending → active/rejected，审核结果可查
- [ ] 前端：校本课程录入 + 课程广场按模板课展示 + 题库共建入口，`npm run build` 通过（h5 + mp-weixin）
- [ ] pytest 全绿（含 M5 验收测试 + M1~M4 回归），`docs/qa/test-report.md` 更新
- [ ] 全部代码已 push，`git log --oneline` 每个任务一条以上 feature commit
