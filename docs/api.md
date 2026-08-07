# AceExam API 契约（M3）

> **状态**：M3.5 v1.1（2026-08-08）｜**作者**：ep-arch
> **定位**：前后端对接的唯一依据（Pydantic schema 级字段定义）。模块设计见 [architecture](./architecture.md)（§10 M2 五件套、§11 M3 图谱/突击/看板/排行/预警、§12 M3.5 TTS/UGC/海报/班级）；表结构见 [database](./database.md)；需求见 [PRD](./PRD.md)。
> **评审**：接口契约由 ep-arch 评审后锁定；任何变更必须同步修改本文档 + 相关代码，禁止只改代码。
> **覆盖范围**：M1 已交付端点（§1~§4 简述）+ M2 五件套端点（§5~§8 详述）+ 与 M1 差异总表（§9）+ M2 实现备注（§10）+ M3 新增端点（§11）+ M3.5 新增端点（§12）。

---

## 0. 通用约定

### 0.1 Base URL / 鉴权

- Base URL：`/api/v1`
- 鉴权：`Authorization: Bearer <JWT>`（登录后获取）。公开端点除外。
- 会员端点：除登录外还要求 `users.is_member = true`；免费用户访问返回 `403 PAYMENT_REQUIRED`（前端引导开通会员）。
- 游客白名单：`POST /auth/register`、`POST /auth/login`、`GET /subjects`、`GET /healthz`。

### 0.2 错误码格式

统一错误体：`{"code": "<CODE>", "message": "<人话>", "detail": {…}?}`

| HTTP | code | 场景 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | 参数/请求体校验失败（detail 含字段错误） |
| 401 | `UNAUTHORIZED` | 未登录 / token 失效 |
| 403 | `FORBIDDEN` | 无权限（非本人资源） |
| 403 | `PAYMENT_REQUIRED` | 会员功能免费用户访问 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 409 | `ALREADY_EXISTS` | 幂等冲突（如科目 code 重复） |
| 409 | `ALREADY_COMPLETED` | 诊断报告重复提交 |
| 422 | `UNPROCESSABLE_ENTITY` | 语义错误（如作答格式与题型不符） |
| 429 | `RATE_LIMITED` | 免费用户 OCR/刷题限流 |
| 500 | `INTERNAL_ERROR` | 服务端异常 |

### 0.3 分页 / 幂等 / 时区

- 分页响应统一：`{"items": [...], "total": int, "page": int, "page_size": int}`
- 写操作支持 `Idempotency-Key` 头：`POST /questions/{id}/answers`、`POST /questions/from-ocr`、`POST /diagnose/report`、`POST /plans`、`POST /plans/{id}/checkin`、`POST /ocr/upload`、`POST /questions/ugc`、`POST /me/class`、`POST /admin/questions/{id}/review`（M3.5 新增）。服务端对同 key 重放返回首次结果（不重复写）。
- 时间字段统一 ISO8601 UTC（`2026-08-07T12:00:00Z`）；日期字段 `YYYY-MM-DD`。
- 所有带 subject 语义的列表接口必须支持/必填 `subject_id`（ADR-0001 防串科）。

### 0.4 SSE 事件格式（AI 讲解流式）

`POST /chat/explain?stream=true` 与 `POST /chat/followup?stream=true` 返回 `text/event-stream`。**每事件一行 `data: {json}` + 空行分隔**（单事件类型 message，兼容小程序 chunked 请求逐行解析）：

```
data: {"type":"delta","content":"分步讲解文本增量"}

data: {"type":"step","step_index":0,"title":"理解题意"}

data: {"type":"citations","citations":[...]}

data: {"type":"done","session_id":"...","uncovered":false}
```

| type | 说明 |
|---|---|
| `delta` | 讲解文本增量（前端追加到当前步骤卡片） |
| `step` | 一个步骤结束（前端可折叠卡片） |
| `citations` | 引用溯源数组（与 §5.1 非流式 citations 同构） |
| `done` | 流结束：携带 session_id / uncovered / model |
| `error` | 流中错误：`{"type":"error","code":"RAG_NO_HIT","message":"..."}` 后终止 |

> 小程序客户端：用 `uni.request` 的 enableChunked 或轮询兼容实现，按 `\n\n` 切块、取每块 `data:` 行 JSON 分发。

---

## 1. auth —— 用户与鉴权（M1，无变更）

### 1.1 POST /auth/register（公开）

请求：`{"username": str(3..50), "password": str(6..128)}`
响应 201：`{"user": UserPublic, "access_token": str, "refresh_token": str}`
错误：409 ALREADY_EXISTS（用户名占用）

### 1.2 POST /auth/login（公开）

请求：`{"username": str, "password": str}`
响应 200：`{"access_token": str, "refresh_token": str, "user": UserPublic}`
错误：401 UNAUTHORIZED（用户名或密码错误）

### 1.3 GET /auth/me（登录）

响应 200：

```json
{
  "id": "uuid",
  "username": "zhangsan",
  "role": "student",
  "is_member": false,
  "member_expires_at": null,
  "created_at": "2026-08-07T12:00:00Z"
}
```

---

## 2. subjects / knowledge-points —— 科目与知识点（M1，无变更）

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | `/subjects` | 公开 | 科目列表（is_active=true，按 sort_order） |
| GET | `/subjects/{subject_id}/knowledge-points?parent_id=` | 登录 | 知识点列表（可选按父节点过滤） |
| GET | `/knowledge-points/tree?subject_id=` | 登录 | 全科目图谱树（诊断地图用） |
| POST | `/subjects` | 登录 | 创建科目（管理用，保留） |

SubjectPublic：`{id, code, name, description, is_active, sort_order, config}`（config 为 JSONB 模板配置，前端不消费则忽略）。

> M1 §5 规划 `GET /subjects/{id}`（科目详情+统计）未落地，M2 不新增；前端以 `/subjects` 列表 + 刷题统计替代。

---

## 3. questions —— 题库与刷题（M1 保留 + M2 变更）

### 3.1 M1 端点（保留）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/questions?subject_id=&knowledge_point_id=&difficulty=&page=&page_size=` | 题单（不含 answer/analysis） |
| GET | `/questions/{question_id}` | 题目详情（作答前不含 answer/analysis） |
| POST | `/questions` | 创建题目（管理/种子用，保留） |
| POST | `/questions/{question_id}/submit` | **废弃（deprecated）**：M2 由 `POST /questions/{id}/answers` 取代；M3 前保留兼容（仅判分+错题入库，不更新知识状态/学习统计）。前端 M2 起统一走 `/answers`。 |

### 3.2 GET /subjects/{subject_id}/practice/questions（新增，自适应选题）

Query 参数：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| knowledge_point_id | string | 否 | null | 限定知识点（空 = 全科自适应） |
| count | int | 否 | 10 | 题量 1..20（题池不足返回实际数量） |
| exclude_ids | string[] | 否 | [] | 已展示题 id（防会话内重复），可重复传 |
| difficulty | int | 否 | null | 目标难度 1..5（默认取 subject config.default_difficulty） |

鉴权：登录（免费可用）。
响应 200：

```json
{
  "items": [
    {"id": "uuid", "subject_id": "uuid", "knowledge_point_id": "uuid", "type": "single",
     "content": "求 $\\lim_{x\\to0}\\frac{\\sin x}{x}$", "options": [{"key": "A", "text": "1"}],
     "difficulty": 3, "source": "textbook", "created_at": "..."}
  ],
  "strategy": {
    "target_kps": [
      {"id": "uuid", "name": "洛必达法则", "level": 3, "status": "weak",
       "score": 78.5, "reason": "正确率 25%，薄弱优先"}
    ],
    "weights": {"status": 50, "error": 35, "recency": 10, "difficulty": 5}
  },
  "requested_at": "2026-08-07T12:00:00Z"
}
```

- `items` 为 QuestionPublic（不含 answer/analysis），作答前不暴露答案（契约要点）。
- `strategy.target_kps` 为本次命中知识点（可解释性，前端可展示"本次优先：洛必达法则"）。
- 算法与加权公式见 architecture.md §10.1；服务实现 `backend/app/services/selection.py`（T10）。
- 错误：404 NOT_FOUND（科目不存在）、422（count/difficulty 越界）。

### 3.3 POST /questions/{question_id}/answers（新增，完整作答链路）

请求体：

```json
{
  "answer": {"type": "single", "value": "C"},
  "time_spent_seconds": 45,
  "source": "practice"
}
```

- `answer`：与题型对应的作答结构——`single`：`"C"`；`multi`：`["A","C"]`；`blank`：`"3"` 或 `["1","2"]`；`essay`：文本串。M1 的 `answer` 字段为 JSONB（`{"type":…}` 包裹为 M2 兼容格式，T9 与前端按 database.md §3.3 的 answer 格式对齐，此处保留宽松：`answer: any`，由后端按题型校验）。
- `source`：`practice`（默认）| `review`（错题重做）；自测走 `/diagnose/report`，不直接调本端点。

鉴权：登录。
响应 200：

```json
{
  "correct": false,
  "correct_answer": "C",
  "analysis": "洛必达法则：$\\lim\\frac{f}{g}=\\lim\\frac{f'}{g'}$…",
  "knowledge_point": {"id": "uuid", "name": "洛必达法则", "level": 3},
  "knowledge_state": {"status": "weak", "correct_count": 2, "wrong_count": 3, "streak": 0},
  "wrong_answer_id": "uuid",
  "explanation_available": true
}
```

- `knowledge_state`：作答后知识点最新状态（正确率、连续正确次数），前端可提示"连续 3 次正确，已掌握！"
- `explanation_available`：该题是否可进入 AI 讲解（true = 有缓存讲解或用户为会员；免费用户无缓存时仍返回 true 但讲解端点会 403，由前端按会员态引导）。
- 事务副作用：判分 → `user_knowledge_states` upsert（streak 规则见 architecture.md §10.1）→ 错误则 `wrong_answers` upsert（幂等）→ `study_sessions` 当日行累加。
- 错误：404、422（answer 与题型不符）、409 ALREADY_EXISTS（配合 Idempotency-Key 重放）。

### 3.4 POST /questions/from-ocr（新增，OCR 确认入库）

请求体：

```json
{
  "upload_id": "uuid",
  "subject_id": "uuid",
  "knowledge_point_id": "uuid",
  "structured": {
    "type": "single",
    "content": "题干（可含 LaTeX）",
    "options": [{"key": "A", "text": "选项A"}],
    "answer": "C",
    "analysis": "解析"
  },
  "confirm_answer": true
}
```

- `structured`：前端编辑后的最终题目（覆盖 OCR 识别结果，是入库事实源）。
- `confirm_answer=false`：答案置信度过低时跳过答案入库（`questions.answer` 置空，避免污染题库）。

鉴权：登录。
响应 200/201：

```json
{
  "question_id": "uuid",
  "upload_id": "uuid",
  "status": "confirmed",
  "duplicated": false
}
```

- 幂等：`Idempotency-Key` 或 content_hash 命中 → 返回既有 `question_id` + `duplicated: true`（不新增记录）。
- 副作用：`questions` 插入（source='ugc'、status='active'）→ `question_embeddings` 异步生成 → `ocr_uploads.status='confirmed'`、`question_id` 回填。
- 错误：404（upload_id/subject/kp 不存在）、422（structured 缺字段或题型非法）。

---

## 4. wrong-answers —— 错题本（M1，无变更）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/wrong-answers?subject_id=&status=&group_by=knowledge_point&page=` | 错题列表（可分组） |
| DELETE | `/wrong-answers/{id}` | 移除错题 |
| POST | `/wrong-answers/{id}/mastered` | 标记已掌握（幂等） |

---

## 5. chat —— AI 讲解（M1 已有 → M2 修改：RAG 真实化 + SSE）

> 行为变化（vs M1）：M1 直接 prompt 题目、citations 恒为空；M2 走 rag_engine（pgvector 检索 → DeepSeek 讲解 → 引用溯源），无命中 `uncovered=true` 兜底（ADR-0003）。M1 的 `stream` query 参数保留兼容。

### 5.1 POST /chat/explain（修改）

Query：`stream: bool = false`（M1 兼容，SSE 时传 `?stream=true`）
请求体：

```json
{"question_id": "uuid", "followup_session_id": "uuid|null"}
```

鉴权：会员（免费 403 PAYMENT_REQUIRED）。
非流式响应 200（stream=false）：

```json
{
  "session_id": "uuid",
  "steps": [{"title": "理解题意", "content": "…"}, {"title": "套用洛必达", "content": "…"}],
  "conclusion": "综上，极限值为 1。",
  "citations": [
    {"source": "高等数学（同济第七版）", "chapter": "第2章 导数与微分",
     "section": "2.3 求导法则", "page": "78", "snippet": "…原文片段…", "score": 0.91}
  ],
  "uncovered": false,
  "model": "pro"
}
```

- `citations[].score`：检索相似度（0.75~1.0，阈值以下即 uncovered，不返回伪引用）。
- 流式（stream=true）：SSE 事件见 §0.4，结束事件 `done` 携带 `session_id/uncovered/model`。
- 副作用：`ai_explanations` 缓存写入（question_id+model+content_hash 唯一）；`chat_sessions` 建会话（无 followup_session_id 时）。
- 错误：404（题目不存在）、403 PAYMENT_REQUIRED、503（RAG 服务不可用 → 降级通用讲解 + `uncovered=true`，不得编造引用）。

### 5.2 POST /chat/followup（修改）

Query：`stream: bool = false`
请求体：`{"session_id": "uuid", "message": str(1..2000)}`
鉴权：会员。
响应 200：同 §5.1 非流式结构（`steps` 为本次追问回答）。
行为：从 `chat_sessions.messages` 取最近 N 轮上下文（默认 10 轮）；基于 session 关联的 question_id 重新 RAG 检索（上下文更新）。
错误：404（会话不存在或非本人）、403 PAYMENT_REQUIRED。

---

## 6. ocr —— 拍照录题（M2 新增）

### 6.1 POST /ocr/upload（新增）

Content-Type：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | 图片 (jpg/png/webp ≤ 10MB) | 是 | 题目照片 |
| subject_id | string | 是 | 目标科目 |
| source | string | 否 | `photo`（默认）/ `album` |

鉴权：登录（免费每日 5 次，超限 429；会员不限）。
响应 200（识别完成）：

```json
{
  "upload_id": "uuid",
  "status": "parsed",
  "raw_text": "Pix2Text 输出 Markdown（含 LaTeX）",
  "structured": {
    "type": "single",
    "content": "题干（LaTeX）",
    "options": [{"key": "A", "text": "…"}],
    "answer": "C",
    "analysis": "…",
    "confidence": 0.82
  },
  "suggested_kps": [{"id": "uuid", "name": "洛必达法则", "score": 0.93}]
}
```

响应 200（识别失败）：`{"upload_id": "uuid", "status": "failed", "error": "OCR_EMPTY", "message": "未识别到有效题目，请重拍或手动录入"}`
响应 202（超时兜底，前端轮询 §6.2）：`{"upload_id": "uuid", "status": "pending"}`

- `structured.confidence`：0~1；< 0.6 前端提示人工核对（确认入库时可 `confirm_answer=false`）。
- `suggested_kps`：知识点归属 top-3（embedding 相似 + 关键词降级，architecture.md §10.3）。
- 副作用：写 `ocr_uploads`（pending → parsed/failed）。

### 6.2 GET /ocr/upload/{upload_id}（新增，轮询）

响应 200：

```json
{"upload_id": "uuid", "status": "pending|parsed|failed",
 "raw_text": null, "structured": null, "suggested_kps": null, "error": null}
```

错误：404（不存在或非本人）。

---

## 7. diagnose —— 薄弱诊断（M2 新增）

> 设计：排名由规则引擎计算、LLM 只生成建议（可解释硬约束，architecture.md §10.4）。前缀沿用 t8/t9 任务约定的 `/diagnose/*`（M1 §5 规划为 `/diagnosis/*`，M1 未落地、无兼容负担）。

### 7.1 POST /diagnose/self-test（新增，发起自测）

请求体：

```json
{"subject_id": "uuid", "count": 10, "include_weak": true}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| subject_id | string | 是 | — | 科目 |
| count | int | 否 | 10 | 题量 5..20 |
| include_weak | bool | 否 | true | 是否按薄弱点加权补题 |

鉴权：登录。
响应 201：

```json
{
  "report_id": "uuid",
  "subject_id": "uuid",
  "status": "in_progress",
  "questions": [
    {"id": "uuid", "knowledge_point_id": "uuid", "type": "single",
     "content": "…", "options": [{"key": "A", "text": "…"}], "difficulty": 3}
  ],
  "coverage": [{"chapter_id": "uuid", "chapter_name": "第2章 导数与微分", "questions": 3}]
}
```

- `questions` 不含 answer/analysis；选题 = 分层抽样（各章 ≥ 1 题 + 薄弱加权，architecture.md §10.1）。
- 副作用：创建 `diagnosis_reports`（in_progress，题组快照）；选题本身不更新知识状态。

### 7.2 GET /diagnose/self-test/{report_id}（新增，取题/状态）

响应 200：`{"report_id", "subject_id", "status": "in_progress|completed", "questions": [...]}`（completed 时附 `weak_top5` 快照）。
错误：404（不存在或非本人）。

### 7.3 POST /diagnose/report（新增，提交自测 → 薄弱地图）

请求体：

```json
{
  "report_id": "uuid",
  "answers": [
    {"question_id": "uuid", "answer": "C"}
  ]
}
```

鉴权：登录。
响应 200：

```json
{
  "report_id": "uuid",
  "status": "completed",
  "summary": "整体掌握度中等，薄弱集中在导数应用与积分计算…",
  "weak_top5": [
    {"rank": 1, "knowledge_point_id": "uuid", "knowledge_point_name": "洛必达法则",
     "level": 3, "accuracy": 0.25, "practice_count": 8, "status": "weak",
     "suggestion": "优先补练：每天 2 道洛必达计算题，配合教材第 3 章例题"}
  ],
  "strengths": [{"knowledge_point_name": "求导基本法则", "accuracy": 0.9}],
  "not_started": [{"knowledge_point_name": "定积分应用", "level": 3}],
  "suggested_next_steps": ["先完成今日计划中薄弱点任务", "周末做一次第 3 章小测"]
}
```

- **可解释性校验（T12 QA 断言）**：`rank/accuracy/practice_count/status` 为规则计算值，必须与 `user_knowledge_states` 一致；LLM 仅生成 `summary/suggestion/suggested_next_steps` 措辞。
- 事务副作用：判分 → 统一走 `knowledge_state.apply_answer()`（更新状态 + streak）+ `study_sessions` 当日累加（自测计入练习）+ 错误题入错题本 → 规则层排名 → LLM 层建议 → `diagnosis_reports` 置 completed、写 weak_top5/report 快照。
- 错误：404（报告不存在或非本人）、409 ALREADY_COMPLETED（已提交；配合 Idempotency-Key 幂等重放返回既有报告）、422（answers 与题组不匹配）。

---

## 8. plans —— 备考计划（M2 新增）

> 设计：每日任务不落表，由规则引擎实时推导（architecture.md §10.5）；进度/打卡落 `study_sessions`。

### 8.1 POST /plans（新增，创建计划）

请求体：

```json
{
  "subject_id": "uuid",
  "exam_date": "2026-08-28",
  "daily_question_target": 10,
  "title": "期末冲刺计划"
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| subject_id | string | 是 | — | 科目 |
| exam_date | date | 是 | — | 考试日期（> 今天） |
| daily_question_target | int | 否 | 10 | 每日题量 5..50 |
| title | string | 否 | "期末冲刺计划" | 展示名 |

鉴权：会员（免费 403 PAYMENT_REQUIRED）。
响应 201：

```json
{
  "plan": {"id": "uuid", "subject_id": "uuid", "title": "期末冲刺计划",
           "exam_date": "2026-08-28", "days_left": 21, "status": "active",
           "daily_question_target": 10},
  "weak_kps": [{"id": "uuid", "name": "洛必达法则", "status": "weak", "accuracy": 0.25}],
  "today_task": {
    "date": "2026-08-07",
    "target_questions": 10,
    "focus_kps": [{"id": "uuid", "name": "洛必达法则", "reason": "薄弱，正确率 25%"}],
    "type": "weak_practice",
    "reason": "距考试 21 天，优先巩固薄弱点",
    "done": {"questions_practiced": 0, "correct_count": 0, "checked_in": false}
  }
}
```

- `weak_kps`：创建时薄弱点快照（top-5）。
- 副作用：`plans` 插入（status='active'，config 存 daily_question_target 等规则）；**不预生成任务行**。
- 错误：403 PAYMENT_REQUIRED、422（exam_date ≤ 今天）、409（同科目已有 active 计划 → 提示先完成/取消旧的）。

### 8.2 GET /plans/active（新增，今日任务 + 预告）

Query：`subject_id: string?`（缺省取最近活跃计划）
鉴权：登录。
响应 200：

```json
{
  "plan": {"id": "uuid", "subject_id": "uuid", "title": "期末冲刺计划",
           "exam_date": "2026-08-28", "days_left": 21, "status": "active"},
  "today_task": {
    "date": "2026-08-07",
    "target_questions": 10,
    "focus_kps": [{"id": "uuid", "name": "洛必达法则", "reason": "薄弱，正确率 25%"}],
    "type": "weak_practice",
    "reason": "距考试 21 天，优先巩固薄弱点",
    "done": {"questions_practiced": 3, "correct_count": 2, "checked_in": false}
  },
  "upcoming": [
    {"date": "2026-08-08", "target_questions": 10,
     "focus_kps": [{"id": "uuid", "name": "洛必达法则"}], "type": "weak_practice"}
  ]
}
```

- 无 active 计划 → 200 返回 `{"plan": null, "today_task": null, "upcoming": []}`（前端引导创建）。
- `today_task.done` 从 `study_sessions` 当日行实时读取；`type` 按 days_left 阶段切换（daily/intensify/sprint，architecture.md §10.5）。

### 8.3 POST /plans/{plan_id}/checkin（新增，打卡）

请求体：`{}`（M2 仅支持当天打卡；补卡 M3）
鉴权：登录（计划属主）。
响应 200：

```json
{
  "checked_in": true,
  "already_checked_in": false,
  "session": {"session_date": "2026-08-07", "questions_practiced": 3,
              "correct_count": 2, "checked_in": true, "checked_in_at": "2026-08-07T22:00:00Z"}
}
```

- 幂等：重复打卡（乐观锁 `UPDATE ... WHERE checked_in=false` 返回 0 行）→ `already_checked_in: true`，HTTP 200 非错误。
- 打卡不校验当日做题数（防挫败）；进度如实展示。
- 错误：404（计划不存在或非本人）、409（计划非 active）。

---

## 9. 差异总表（vs M1）

### 9.1 端点变化

| 端点 | M1 | M2 | 说明 |
|---|---|---|---|
| `POST /questions/{id}/submit` | 有 | **废弃**（M3 前兼容） | 由 `/answers` 取代（不更新知识状态/统计） |
| `GET /questions/next` | §5 规划未落地 | **不实现** | 由 `GET /subjects/{id}/practice/questions` 取代 |
| `GET /subjects/{id}` | §5 规划未落地 | **不新增** | 前端以 `/subjects` 列表替代 |
| `POST /chat/explain` | 有（无 RAG） | **修改** | RAG 真实化 + SSE + citations/uncovered |
| `POST /chat/followup` | 有 | **修改** | SSE + 会话上下文 + 可选 RAG 重检索 |
| `POST /ocr/recognize` | §5 规划未落地 | **改名落地** | 落地为 `POST /ocr/upload`（上传+结构化预览） |
| `POST /diagnosis/self-test` | §5 规划未落地 | **改名落地** | 落地为 `POST /diagnose/self-test`（前缀 diagnosis→diagnose） |
| `GET /diagnosis/report` | §5 规划未落地 | **改为 POST** | 落地为 `POST /diagnose/report`（提交制） |
| `POST /plans` | §5 规划未落地 | **落地** | 见 §8.1 |
| `GET /plans/today` | §5 规划未落地 | **并入** | 并入 `GET /plans/active` |
| `POST /plans/checkin` | §5 规划未落地 | **改名落地** | 落地为 `POST /plans/{id}/checkin`（携带 plan_id） |

### 9.2 新增端点（11 个）

`GET /subjects/{subject_id}/practice/questions`、`POST /questions/{question_id}/answers`、`POST /questions/from-ocr`、`GET /ocr/upload/{upload_id}`、`POST /diagnose/self-test`、`GET /diagnose/self-test/{report_id}`、`POST /diagnose/report`、`POST /plans`、`GET /plans/active`、`POST /plans/{plan_id}/checkin`、`POST /subjects/{subject_id}/textbooks`（教材上传，RAG 语料入口，§5 前置）。

> 注：`POST /subjects/{subject_id}/textbooks` 为 M2 RAG 真实化的语料入口（architecture.md §10.2 ①）；T9 排期冲突时可先以种子教材跑通 RAG，接口保留。

### 9.3 无变更（14 个）

`POST /auth/register`、`POST /auth/login`、`GET /auth/me`、`GET /subjects`、`GET /subjects/{subject_id}/knowledge-points`、`GET /knowledge-points/tree`、`POST /subjects`、`GET /questions`、`GET /questions/{question_id}`、`POST /questions`、`GET /wrong-answers`、`DELETE /wrong-answers/{id}`、`POST /wrong-answers/{id}/mastered`、`GET /healthz`

> 合计：**28 端点**（14 不变 + 11 新增 + 2 修改 + 1 废弃）。

---

## 10. 实现备注（各角色）

- **T9（ep-backend）**：按本契约实现路由与 schema；`backend/app/schemas/` 新增 `practice.py`（3.2/3.3）、`ocr.py`（§6）、`diagnose.py`（§7）、`plans.py`（§8）；复用/扩展 `chat.py`（§5）。写操作统一支持 `Idempotency-Key`。
- **T10（ep-ai）**：`selection.py`（§3.2 算法）、`rag/*` 真实化（§5）、`ocr_service.py`（§6）、`diagnosis.py`（§7 规则层+LLM 层）。
- **T11（ep-frontend）**：按本契约对接；SSE 用 chunked 请求解析（§0.4）；错误码映射统一 toast；401 → 登录页。
- **T12（ep-qa）**：按 §7.3 可解释性断言 + 五件套逐项验收（见 docs/ops/M2-taskgraph.md 验收清单）。
- 变更流程：改端点/字段必须先改本文档 + architecture.md 对应小节，再改代码；评审由 ep-arch。

---

## 11. M3 增量：图谱 / 突击 / 看板 / 排行 / 预警 API

> 本节是 M3 新增端点契约，在 M2（§1~§10）之上增量追加，不重写既有章节。模块设计见 architecture.md §11；表结构增量见 database.md §9（T14）。突击相关端点为会员功能（PRD §5/§6），免费用户 403 PAYMENT_REQUIRED。

### 11.1 GET /subjects/{subject_id}/knowledge-graph（新增，知识点图谱）

Query：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| include_questions | bool | 否 | true | 节点带 question_count / practice_count / accuracy 统计；false 只返回树骨架 |

鉴权：登录。
响应 200：

```json
{
  "subject_id": "uuid",
  "subject_name": "高等数学",
  "generated_at": "2026-08-08T12:00:00Z",
  "root": {
    "id": "uuid", "name": "第2章 导数与微分", "level": 1,
    "status": "weak", "question_count": 37,
    "children": [
      {
        "id": "uuid", "name": "2.3 求导法则", "level": 2, "status": "consolidating",
        "question_count": 12,
        "children": [
          {
            "id": "uuid", "name": "洛必达法则", "level": 3, "status": "weak",
            "question_count": 8, "practice_count": 5, "accuracy": 0.2,
            "children": []
          }
        ]
      }
    ]
  },
  "stats": {
    "total_nodes": 96, "leaf_count": 28,
    "mastered_count": 9, "weak_count": 6, "consolidating_count": 4, "untouched_count": 9
  }
}
```

- `status`：叶子 = `user_knowledge_states` 实时状态（无记录 = `untouched`）；父节点 = 子节点聚合（任一 weak→weak，任一 consolidating→consolidating，全部 mastered→mastered，否则 untouched；architecture.md §11.1）。
- `accuracy`：仅叶子有练习记录时返回（0~1），未接触为 null；父节点为 null。
- 前端可直接用 `root` 喂 ECharts `series-tree`（`data=[root]`，节点 `itemStyle.color` 按 status 映射）。
- 错误：404（科目不存在）。

### 11.2 POST /subjects/{subject_id}/sprint/activate（新增，手动激活突击）

请求体：`{}`
鉴权：会员（免费 403 PAYMENT_REQUIRED）。
响应 200（幂等：同科目已有 active 会话返回既有）：

```json
{
  "sprint": {
    "id": "uuid", "subject_id": "uuid", "status": "active",
    "activated_at": "2026-08-08T12:00:00Z",
    "auto_activated": false,
    "exam_date": "2026-08-15", "days_left": 7, "expires_at": "2026-08-15"
  },
  "created": true
}
```

- 手动激活不限制距考试天数；无 active 计划时 `exam_date`/`days_left` 为 null（只开题单不联动倒计时）。
- 幂等：同科目已有 active 会话 → `created: false` 返回既有；考试日已过 → 旧会话置 `expired` 并新建。
- 错误：403 PAYMENT_REQUIRED、404（科目不存在）。

### 11.3 GET /subjects/{subject_id}/sprint/questions（新增，突击题单）

Query：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| mode | string | 否 | review | `review` 混合题单 / `mock` 模拟卷 |
| count | int | 否 | 20 | 题量 1..50（题池不足返回实际数量） |

鉴权：会员。
行为：无 active 会话且 `days_left ≤ 7` → 自动创建（`auto_activated=true`，architecture.md §11.2）。
响应 200：

```json
{
  "sprint_id": "uuid",
  "status": "active",
  "days_left": 7,
  "high_freq_kps": [
    {"id": "uuid", "name": "洛必达法则", "heat": 128, "avg_accuracy": 0.42, "has_past_exam": true}
  ],
  "items": [
    {"id": "uuid", "subject_id": "uuid", "knowledge_point_id": "uuid", "type": "single",
     "content": "…", "options": [{"key": "A", "text": "…"}], "difficulty": 3,
     "source": "past_exam", "tag": "high_freq"}
  ],
  "summary": {"high_freq_questions": 14, "wrong_review_questions": 6, "deduped": 2, "total": 20},
  "mock": null
}
```

- `items` 为 QuestionPublic（不含 answer/analysis）；`tag`：`high_freq`（高频考点题）/ `wrong_review`（个人错题），前端可展示"本卷含 6 道你的错题"。
- 题单快照：重复请求返回 `sprint_sessions.question_snapshot` 同一份题单（`sprint_id` 稳定）。
- `mode=mock`：`mock` 返回 `{"duration_min": 120, "total_score": 100, "started_at": null}`（从 `subjects.config.exam` 读取），前端计时；判分仍走 `POST /questions/{id}/answers`。
- 错误：403 PAYMENT_REQUIRED、404（科目不存在）、422（mode/count 非法）。

### 11.4 GET /me/dashboard（新增，学习数据看板汇总）

Query：`subject_id: string?`（缺省 = 全部科目汇总）
鉴权：登录。
响应 200：

```json
{
  "totals": {"questions_practiced": 1280, "correct_count": 940, "accuracy": 0.734},
  "mastery": {"leaf_total": 28, "mastered": 9, "mastery_pct": 0.321},
  "streak": {"current": 5, "longest": 12},
  "weak_points": {"weak": 6, "consolidating": 4},
  "per_subject": [
    {"subject_id": "uuid", "subject_name": "高等数学", "questions_practiced": 680,
     "correct_count": 470, "accuracy": 0.691, "mastery_pct": 0.32}
  ],
  "exam": {"has_active_plan": true, "days_left": 7}
}
```

- `mastery` 按叶子知识点口径（architecture.md §11.4）；`streak` 按 §11.3 连胜规则实时计算。
- `exam.days_left`：最近 active 计划倒计时；无计划为 null（前端引导建计划）。
- 错误：404（subject_id 不存在，若传）。

### 11.5 GET /me/dashboard/trend（新增，时间序列）

Query：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| days | int | 否 | 30 | 回溯天数 1..180 |
| subject_id | string | 否 | null | 缺省 = 全部科目 |
| granularity | string | 否 | day | `day` / `week` / `month`（date_trunc 桶） |

鉴权：登录。
响应 200：

```json
{
  "granularity": "day",
  "items": [
    {"bucket_start": "2026-07-10", "questions_practiced": 20, "correct_count": 15,
     "accuracy": 0.75, "mastered_kp_count": 4, "mastery_pct": 0.14},
    {"bucket_start": "2026-07-11", "questions_practiced": 0, "correct_count": 0,
     "accuracy": null, "mastered_kp_count": 4, "mastery_pct": 0.14}
  ]
}
```

- 桶无做题记录：`questions_practiced=0`、`accuracy=null`（前端折线图跳过 null 或补 0，T16 定）。
- `mastered_kp_count`：as-of 近似（状态 `updated_at ≤ 桶末` 计数，architecture.md §11.4），单调不减。
- 桶按时间升序；`bucket_start` 格式 YYYY-MM-DD（week 桶为周一、month 桶为 1 号）。

### 11.6 GET /leaderboard（新增，排行榜）

Query：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| scope | string | 否 | global | `global` / `subject` |
| subject_id | string | subject 时必填 | null | 科目维度过滤 |
| page / page_size | int | 否 | 1 / 20 | 分页（page_size ≤ 50） |

鉴权：登录。
> **M3.5 修订**：`scope` 枚举新增 `class`（班级维度，按请求者 `users.class_id` 过滤），契约见 §12.7；未加入班级返回 422 `CLASS_NOT_JOINED`。
响应 200：

```json
{
  "scope": "global",
  "items": [
    {"rank": 1, "user_id": "uuid", "username": "zhangsan",
     "total_correct": 860, "questions_practiced": 1150, "accuracy": 0.748,
     "current_streak": 8}
  ],
  "page": 1, "page_size": 20, "total": 156,
  "me": {"rank": 42, "total_correct": 180, "questions_practiced": 260, "accuracy": 0.692}
}
```

- **口径（architecture.md §11.5 定案）**：主排序 `total_correct` 降序，次排序 `accuracy` 降序（样本 ≥ 30 题才计，<30 视为 0）；做题量 < 30 的用户不进榜；`accuracy < 0.1` 标 `suspicious` 不参与排序。
- `me`：当前用户排名（不在榜时 `rank=null` 但附统计，前端显示"再对 N 题进榜"）。
- 错误：422（scope=subject 缺 subject_id）。

### 11.7 GET /me/warnings（新增，挂科预警）

Query：`subject_id: string?`（缺省 = 全部有 active 计划的科目）
鉴权：登录。
响应 200：

```json
{
  "overall_risk": "high",
  "items": [
    {
      "knowledge_point_id": "uuid", "knowledge_point_name": "洛必达法则",
      "risk_level": "high",
      "reasons": ["正确率仅 20%（练习 5 次）", "距考试仅 7 天", "近 3 天未做题"],
      "suggestion": "每天 2 道洛必达计算题，配合教材第 3 章例题；今晚先做一次 10 题小测",
      "days_left": 7, "accuracy": 0.2, "practice_count": 5
    }
  ],
  "generated_at": "2026-08-08T12:00:00Z"
}
```

- 判定规则（architecture.md §11.6）：base(weak_count × days_left) + 趋势修正 ±1，clamp 低~高。
- `reasons` 为规则层生成的确定性理由；`suggestion` 为 LLM（flash）措辞。可解释硬约束：等级/数字全部来自规则层，LLM 不得改写（与 §7.3 诊断同一原则）。
- 无 active 计划：`{"overall_risk": null, "items": [], "generated_at": "…"}`（前端引导建计划）。
- 错误：404（subject_id 不存在，若传）。

### 11.8 差异总表（vs M2）与端点总数

新增 7 个端点（全部新增，无修改/废弃）：

`GET /subjects/{subject_id}/knowledge-graph`、`POST /subjects/{subject_id}/sprint/activate`、`GET /subjects/{subject_id}/sprint/questions`、`GET /me/dashboard`、`GET /me/dashboard/trend`、`GET /leaderboard`、`GET /me/warnings`

> 合计：**35 端点**（M2 28 + M3 新增 7）。§9 差异表为 M2 快照，M3 增量以本节为准；M3.5 增量见 §12（新增 8 端点 + 修订 1，总计 43）。

### 11.9 实现备注（各角色）

- **T15（ep-backend）**：按本契约实现路由与 schema；新增 `backend/app/schemas/`：`graph.py`（11.1）、`sprint.py`（11.2/11.3）、`dashboard.py`（11.4/11.5）、`leaderboard.py`（11.6）、`warnings.py`（11.7）。聚合查询用 SQLAlchemy `func.sum/date_trunc`；连胜统计抽纯函数 `streak.py`（便于 T18 单测，architecture.md §11.3）。顺手修复 M2 缺陷 D-8/D-9/D-11/D-16（见 T15 body）。
- **T14（ep-db）**：仅 `sprint_sessions` 新表（architecture.md §11.7），其余 M3 功能无新表；迁移 `0003_m3_sprint`。
- **T17（ep-ai）**：`knowledge_graph.py`（树组装+状态聚合）、`sprint.py`（高频识别+题单）、`warning.py`（风险规则+LLM 措辞）；单测覆盖 §11.6 风险边界与 §11.2 高频+错题交集。
- **T16（ep-frontend）**：按本契约对接；图谱用 uni-echarts（H5/App renderjs，mp-weixin canvas 降级），节点点击 → 题单；趋势折线图用 ECharts line（uni-echarts 同组件）；`accuracy: null` 桶前端补零。
- **T18（ep-qa）**：按 §11.6 风险等级边界、§11.3 连胜连续/中断、§11.2 高频+错题交集去重、§11.5 排序口径写断言（见 docs/ops/M3-taskgraph.md 验收清单）。
- 变更流程：改端点/字段必须先改本文档 + architecture.md §11 对应小节，再改代码；评审由 ep-arch。

## 12. M3.5 增量：TTS / UGC / 班级 / 海报 API

> 本节是 M3.5 新增端点契约，在 M3（§1~§11）之上增量追加，不重写既有章节。模块设计见 architecture.md §12；表结构增量见 database.md §10（T20）。TTS 端点为会员功能（跟随 AI 讲解，免费 403 PAYMENT_REQUIRED）；UGC 投稿 / 班级 / 海报分享登录即可。

### 12.1 POST /chat/explain/{session_id}/tts（新增，生成讲解语音）

请求体（可选）：

```json
{"voice": "zh-CN-XiaoxiaoNeural"}
```

鉴权：会员（免费 403 PAYMENT_REQUIRED）。
行为：

1. 校验会话归属（chat_sessions.id + user_id）→ 404 不存在或非本人
2. 取最近一条 assistant 消息 content（讲解全文）→ 无 assistant 消息 → 404 `EXPLANATION_NOT_FOUND`
3. 文本清洗 + key=sha256(text+voice) → 磁盘缓存命中 → `cache_hit=true`
4. 未命中 → edge-tts 生成 mp3 → 落盘 → `cache_hit=false`
5. 失败（无网络/服务不可用）→ 502 `TTS_UNAVAILABLE`（前端提示稍后重试）

响应 200：

```json
{
  "session_id": "uuid",
  "audio_url": "/api/v1/tts/audio/3f9c8e2a....mp3",
  "voice": "zh-CN-XiaoxiaoNeural",
  "text_preview": "第一步，我们先理解题意：题干给出极限式……",
  "cache_hit": false,
  "created_at": "2026-08-08T12:00:00Z"
}
```

- `voice` 白名单：`zh-CN-XiaoxiaoNeural`（默认）/ `zh-CN-YunxiNeural`；非法 → 422。
- 同文本同 voice 幂等（缓存天然幂等，无需 Idempotency-Key）。
- 错误：403 PAYMENT_REQUIRED、404、422（voice 非法）、502（TTS 服务不可用）。

### 12.2 GET /tts/audio/{file_hash}.mp3（新增，音频流）

鉴权：登录。
响应 200：`audio/mpeg` 音频流（FileResponse，Content-Disposition inline，Starlette 自动支持 Range 拖动播放）。
错误：404（缓存文件不存在 → 前端提示重新生成，调 §12.1）。

### 12.3 POST /questions/ugc（新增，提交待审题）

请求体：

```json
{
  "subject_id": "uuid",
  "knowledge_point_id": "uuid",
  "type": "single",
  "content": "题干（≥15 字）",
  "options": [{"key": "A", "text": "选项A"}],
  "answer": "C",
  "analysis": "解析（可选）",
  "ocr_upload_id": "uuid|null"
}
```

鉴权：登录。支持 `Idempotency-Key`。
规则预检（architecture.md §12.2）：content ≥ 15 字；answer 与 type 匹配；options 数量与 type 匹配；content_hash 重复检测（命中题库已有题 → 409 `DUPLICATE` + detail 既有 question_id）。
响应 201：

```json
{"question_id": "uuid", "status": "pending", "duplicated": false}
```

- 幂等 key 重放：返回首次结果（`duplicated: true`，同 §3.4 from-ocr 语义）；内容重复（不同提交者同题）→ 409 `DUPLICATE`。
- 副作用：questions 插入（source='ugc'、status='pending'、submitted_by=当前用户）→ `question_embeddings` 异步生成（仅 approved 后需要，MVP 可延后到审核通过时生成）。
- 错误：404（subject/kp/ocr_upload 不存在）、409 DUPLICATE、422（预检失败，detail 含字段错误）。

### 12.4 GET /admin/questions/ugc（新增，审核列表）

Query：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| status | string | 否 | pending | `pending` / `active` / `rejected` |
| page / page_size | int | 否 | 1 / 20 | 分页（page_size ≤ 50） |

鉴权：admin（users.role='admin'，非 admin → 403 FORBIDDEN）。
响应 200（统一分页格式）：

```json
{
  "items": [
    {
      "question_id": "uuid", "subject_id": "uuid", "subject_name": "高等数学",
      "knowledge_point_id": "uuid", "knowledge_point_name": "洛必达法则",
      "type": "single", "content": "…", "options": [{"key": "A", "text": "…"}],
      "answer": "C", "analysis": "…",
      "submitted_by": {"user_id": "uuid", "username": "zhangsan"},
      "status": "pending", "created_at": "2026-08-08T12:00:00Z",
      "reject_reason": null
    }
  ],
  "page": 1, "page_size": 20, "total": 3
}
```

- 列表按 created_at 升序（最旧待审先处理）；admin 可看全部状态，非 admin 一律 403。

### 12.5 POST /admin/questions/{id}/review（新增，审核通过/拒绝）

请求体：

```json
{"action": "approve", "reject_reason": null}
```

或

```json
{"action": "reject", "reject_reason": "答案有误，请核对后重新提交"}
```

鉴权：admin（非 admin → 403 FORBIDDEN）。支持 `Idempotency-Key`。
行为：题目必须 source='ugc' 且 status='pending'；否则 409 `ALREADY_REVIEWED`（已审核）或 422（非 UGC 题）。

- approve → status='active'，reviewed_by/reviewed_at 落库（进公共题池，可被选题命中）。
- reject → status='rejected'，reject_reason 必填（≥5 字）。

响应 200：

```json
{"question_id": "uuid", "status": "active", "reviewed_at": "2026-08-08T12:00:00Z"}
```

错误：403 FORBIDDEN、404（题目不存在）、409 ALREADY_REVIEWED、422（action 非法 / reject 缺理由 / 非 UGC 题）。

### 12.6 POST /me/class（新增，建班/加入班级）

请求体（二选一）：

```json
{"name": "计科2301"}
```

或

```json
{"invite_code": "A1B2C3"}
```

鉴权：登录。支持 `Idempotency-Key`。
行为：

- 建班（有 name）：classes 插入（name + 6 位 invite_code 唯一生成）→ users.class_id 指向新班 → 成为班长（is_creator=true）。
- 加入（有 invite_code）：invite_code 查 classes → users.class_id 指向（覆盖旧班；已在同班幂等返回既有）。
- name 与 invite_code 都传或都不传 → 422。

响应 200：

```json
{
  "class": {"id": "uuid", "name": "计科2301", "invite_code": "A1B2C3",
            "member_count": 12, "is_creator": true},
  "joined": true
}
```

- `member_count` 实时 COUNT（users.class_id）；`invite_code` 仅建班人返回（加入者返回 null）。
- 错误：404（邀请码不存在）、422（参数缺失/非法）。

### 12.7 GET /me/class（新增，我的班级）+ GET /leaderboard?scope=class（修订 §11.6）

GET /me/class 响应 200：

```json
{
  "class": {"id": "uuid", "name": "计科2301", "invite_code": "A1B2C3",
            "member_count": 12, "is_creator": false},
  "my_rank": {"rank": 3, "total_correct": 180}
}
```

- 未加入班级：`{"class": null, "my_rank": null}`。
- `my_rank`：班榜中我的名次（口径同 §11.6；不在榜 rank=null）。

GET /leaderboard?scope=class（§11.6 修订，M3.5 新增 scope 枚举值）：

- `scope` 枚举：`global` / `subject` / `class`（class 为 M3.5 新增，§11.6 已加修订指针）。
- `scope=class`：按请求者 users.class_id 过滤（未加入班级 → 422 `CLASS_NOT_JOINED`，前端引导加入）；`subject_id` 可选（缺省 = 全科目，叠加科目过滤）。
- 响应在 §11.6 基础上增加 class 元信息：

```json
{
  "scope": "class",
  "class": {"id": "uuid", "name": "计科2301", "member_count": 12},
  "items": [
    {"rank": 1, "user_id": "uuid", "username": "lisi",
     "total_correct": 860, "questions_practiced": 1150, "accuracy": 0.748,
     "current_streak": 8}
  ],
  "page": 1, "page_size": 20, "total": 12,
  "me": {"rank": 3, "total_correct": 180, "questions_practiced": 260, "accuracy": 0.692}
}
```

- 口径沿用 §11.6（主=total_correct 降序、次=accuracy 降序 ≥30 题门槛、<30 题不进榜；`accuracy < 0.1` 标 suspicious 不参与排序）。
- 错误：422 CLASS_NOT_JOINED、422（scope=subject 缺 subject_id）。

### 12.8 GET /me/share-card（新增，分享卡数据聚合）

Query：无（MVP 缺省全部科目）。
鉴权：登录。
响应 200：

```json
{
  "username": "zhangsan",
  "generated_at": "2026-08-08T12:00:00Z",
  "share_card_version": 1,
  "totals": {"questions_practiced": 1280, "correct_count": 940, "accuracy": 0.734},
  "recent_7d": {"questions_practiced": 86, "correct_count": 61, "accuracy": 0.709},
  "streak": {"current": 5, "longest": 12},
  "mastery": {
    "overall_pct": 0.321,
    "best_subject": {"subject_id": "uuid", "subject_name": "高等数学", "mastery_pct": 0.42}
  },
  "weak_points": {"weak": 6, "consolidating": 4},
  "class": {"id": "uuid", "name": "计科2301"},
  "exam": {"subject_name": "高等数学", "days_left": 7}
}
```

- 口径与 §11.4 dashboard 一致（实时聚合，architecture.md §12.3）；`recent_7d` 近 7 天（含今天）做题统计。
- `class` / `exam` 无数据时返回 null（前端海报隐藏对应区块或展示引导）。
- 无数据边界：全零用户返回 0 值（前端海报可展示"开始第一题"引导）。

### 12.9 差异总表（vs M3）与端点总数

新增 8 个端点（全部新增，无废弃）：

`POST /chat/explain/{session_id}/tts`、`GET /tts/audio/{file_hash}.mp3`、`POST /questions/ugc`、`GET /admin/questions/ugc`、`POST /admin/questions/{id}/review`、`POST /me/class`、`GET /me/class`、`GET /me/share-card`

修订 1 个端点：`GET /leaderboard`（scope 枚举增加 `class`，§12.7）。

> 合计：**43 端点**（M3 35 + M3.5 新增 8）。§11 为 M3 快照，M3.5 增量以本节为准。

### 12.10 实现备注（各角色）

- **T20（ep-backend）**：按本契约实现路由与 schema；新增 `backend/app/schemas/`：`tts.py`（12.1/12.2）、`ugc.py`（12.3~12.5）、`classroom.py`（12.6/12.7）、`share_card.py`（12.8）；`leaderboard.py` 增量（scope=class）。admin 依赖注入（users.role='admin'）。小表迁移见 architecture.md §12.5（classes / users.class_id / questions 扩展，`0004_m35_*` 迁移 + database.md §10）。
- **T21（ep-ai）**：`tts_service.py`（edge-tts 封装 + 文本清洗 + 磁盘缓存）、`ugc_service.py`（预检规则 + 可选自动审核）；单测覆盖 TTS 字节非空与参数校验、UGC 预检规则边界（backend/tests/test_ai_m35.py）。
- **T22（ep-frontend）**：按本契约对接；语音播放 `uni.createInnerAudioContext()`；UGC 投稿入口（OCR 预览页"投稿共建"）；班级页（建班/加入/展示）+ 排行榜 scope 切换；海报 canvas（type=2d / H5 canvas → saveImageToPhotosAlbum / toDataURL 下载）；mock 保留降级（frontend/src/mock/）。
- **T23（ep-qa）**：按 §12.5 UGC 状态机边界、§12.6/§12.7 班级加入与未加入边界、§12.1 TTS mock 生成与参数校验、§12.8 分享卡聚合口径写断言（见 docs/ops/M3.5-taskgraph.md 验收清单）。
- 变更流程：改端点/字段必须先改本文档 + architecture.md §12 对应小节，再改代码；评审由 ep-arch。

---
