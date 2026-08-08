# AceExam M4 任务图启动手册（kanban 多角色协作）

> **适用场景**：M3.5（TTS/UGC/海报/班级）已交付后，一键启动 M4 开发（用户反馈驱动的产品调整：用户自填专业 + 自选本学期课程，公共课独立为「课程广场」）。
> **前置**：6 个 ep-* 角色就绪，主 profile 网关在跑；board `aceexam` 已建；T24 已产出契约文档。
> **M4 目标**：首页从「展示全部科目」改为「我的课程（用户自选）」+ 独立「课程广场」页；新增用户专业字段（major）与选课关联（user_subjects）。
> **契约来源**：模块设计见 `docs/architecture.md` §13（含决策锁定表 D15~D18）；API 契约见 `docs/api.md` §13（新增 4 端点，总计 47）；表结构增量见 `docs/database.md` §11（T25 产出，迁移 `0005_user_major_plaza`）。

## 任务图设计

```
T24 ep-arch（架构师）                 ← root，本任务已交付契约
├── T25 ep-backend（后端）            ← parent T24：专业/选课/广场 API + 迁移 0005 + 种子
└── T26 ep-frontend（前端）           ← parent T24：选课引导 + 首页「我的课程」改造 + 广场页
      └── T27 ep-qa（测试）           ← parents T25+T26：选课验收测试
```

**已建卡片 ID（2026-08-08，T24 任务图中捕获）**：

| 任务 | 卡片 ID | 备注 |
|---|---|---|
| T24 | t_fa49c3fb | 本任务（架构增量 + API 契约 + 任务图），done 后解锁 T25/T26 |
| T25 | t_1b4d7593 | 待 T24 done 自动解锁 |
| T26 | t_9c72c398 | 待 T24 done 自动解锁 |
| T27 | t_a3a033a2 | parents=T26（依赖边已补全）；T27 还应在 T25 完成后追加依赖边（见下方修订） |

> ⚠️ **T27 依赖边修订**：T27 body 写"等 ep-backend（T25）、ep-frontend（T26）交付后执行验收"，但创建时 parents 仅含 T26 与 T24。**主控需补一条依赖边 `T25 → T27`**：`hermes kanban link --parent t_1b4d7593 --child t_a3a033a2`（或等价的 board 操作），否则 T27 可能在 T25 未完成时提前解锁。若 link 不可用，可将 T27 的 parents 更新为 [T25, T26]。

**并行规则**（沿用 M1/M2/M3/M3.5 验证结论）：

- T25/T26 两个不同 profile → 可并行跑（各写各的目录：T25 写 backend + database.md §11，T26 写 frontend）
- T25 是纯 CRUD + 聚合，无 AI 服务依赖 → 无 T 级服务边界（ep-ai 本批不参与）
- T27 等 T25 + T26 → 依赖边补全后 dispatcher 自动解锁
- 同一 profile 绝不并行两个任务（会互相踩 git）

## 依赖说明

| 边 | 含义 | 满足方式 |
|---|---|---|
| T24 → T25/T26 | 契约先行：`docs/architecture.md` §13（模块设计 + 决策锁定 D15~D18 + 表增量约定）+ `docs/api.md` §13（字段级契约） | 各任务开工前先读 architecture.md §13 与 api.md §13；T25 按 §13.5 建表（0005 迁移）+ 按 api.md §13 实现路由，T26 按 §13 对接页面 |
| T25 + T26 → T27 | 端到端验收需要前后端联调 | dispatcher 自动解锁（需补 T25→T27 依赖边，见上） |

> ⚠️ **迁移编号修正（T24 评审结论）**：T25 body 草案写 `0004_user_major_plaza`，与既有 `backend/alembic/versions/0004_m35_classes_ugc.py` **编号冲突**。实际迁移必须为 `0005_user_major_plaza`（down_revision=`0004_m35_classes_ugc`）。T25 开工时以本任务图 + architecture.md §13.5 为准，body 草案作废。
> ⚠️ **database.md §11 待 T25 落地**：M3.5（T20）应交付 database.md §10（classes/class_id/questions 扩展）但**尚未同步**；T25 落地 §11 前需先补 §10 或与 ep-arch 确认编号（最低要求：§11 内容为 users.major + user_subjects + subjects.is_public，迁移 0005；若 §10 缺失由 T25 顺带补上并注明）。

## 文件边界（避免重名冲突）

| 角色 | 写入目录 | 关键文件 |
|---|---|---|
| T25 ep-backend | `backend/app/api/`、`backend/app/schemas/`、`backend/app/models/`、`backend/alembic/`、`docs/database.md` | `api/v1/me.py`（13.1~13.3）+ `api/v1/subjects.py` 扩展（13.4）；`schemas/me.py`（ProfileUpdate/SubjectIdsUpdate/UserSubjectItem/PlazaSubject）；models：users.major / subjects.is_public / user_subjects；`alembic/versions/0005_user_major_plaza.py`；`db/seed.py` 种子更新；database.md §11 增量 |
| T26 ep-frontend | `frontend/` | 选课引导页（PUT /me/profile + PUT /me/subjects）、首页「我的课程」（GET /me/subjects）、课程广场页（GET /subjects/plaza + 加入按钮）、「我的」页专业编辑入口；mock 保留在 `frontend/src/mock/` 做 fallback |
| T27 ep-qa | `backend/tests/`（除 test_ai_* 外）+ `docs/qa/` | 选课验收测试 + test-report.md 更新；只加测试不改业务代码（发现 bug 记录在案） |

## 执行步骤（个人电脑，git-bash）

### 1. 创建/补全任务（ID 立即捕获，别手敲）

```bash
hermes kanban boards switch aceexam

# T25/T26/T27 已建（parent T24）；T27 需补 T25 依赖边：
hermes kanban link --parent t_1b4d7593 --child t_a3a033a2   # 若该子命令可用；否则更新 T27 parents=[T25, T26]
```

> 当前板上 T25（t_1b4d7593）、T26（t_9c72c398）、T27（t_a3a033a2）已存在；T27 的 parents 仅含 T26/T24，需补 T25。

### 2. 监控（主控主动汇报，别等）

```bash
hermes kanban list           # 状态总览
hermes kanban log <t_id>     # 看 worker 实时在干什么
git log --oneline -5         # 新提交
```

**进度汇报节奏**：每 10~15 分钟给用户一个快照（✓ done / ● running / ⊘ blocked / ◻ todo + 各 worker 实际动作 + 新 commit）。

### 3. worker 异常恢复速查（沿用 M1/M2/M3/M3.5）

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

## 验收标准（M4 完成 = 全部满足）

- [ ] `docs/architecture.md` §13：专业选课 + 课程广场模块设计 + 决策锁定表（D15~D18）
- [ ] `docs/api.md` §13：4 个新端点字段级契约（PUT /me/profile、PUT /me/subjects、GET /me/subjects、GET /subjects/plaza），端点总数 43 → 47
- [ ] Alembic 0005 迁移：`users.major` + `user_subjects` 新表（复合主键）+ `subjects.is_public`（编号修正为 0005，非 body 草案的 0004）
- [ ] 种子数据：高数/英语 is_public=true 回填；新增线代/概率论/大物公共课种子
- [ ] `PUT /me/profile`：更新 major（1..100 自由文本，空串清除），未登录 401、非法 400
- [ ] `PUT /me/subjects`：幂等全量覆盖（先删后插同事务）、重复 id 去重、空数组=清空、422 SUBJECT_NOT_JOINABLE（is_public=false/不存在/未激活）
- [ ] `GET /me/subjects`：返回自选课程 + 学习状态（做题量/正确率/掌握度/薄弱数/连胜，口径与 dashboard 一致）
- [ ] `GET /subjects/plaza`：is_public=true 列表 + joined 状态；未登录可看（游客白名单）、joined 恒 false
- [ ] 前端：选课引导（首次未配置）+ 首页「我的课程」+ 课程广场页 + 「我的」页专业编辑，`npm run build` 通过（h5 + mp-weixin）
- [ ] pytest 全绿（含 M4 验收测试 + M1~M3.5 回归），`docs/qa/test-report.md` 更新
- [ ] 全部代码已 push，`git log --oneline` 每个任务一条以上 feature commit
