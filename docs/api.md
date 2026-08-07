# AceExam API 契约（M2）

> **状态**：M2 v1.0（2026-08-07）｜**作者**：ep-arch
> **定位**：前后端对接的唯一依据（Pydantic schema 级字段定义）。模块设计见 [architecture](./architecture.md)（§10 M2 五件套）；表结构见 [database](./database.md)；需求见 [PRD](./PRD.md)。
> **评审**：接口契约由 ep-arch 评审后锁定；任何变更必须同步修改本文档 + 相关代码，禁止只改代码。
> **覆盖范围**：M1 已交付端点（§1~§4 简述）+ M2 五件套端点（§5~§8 详述）+ 与 M1 差异总表（§9）。

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
- 写操作支持 `Idempotency-Key` 头：`POST /questions/{id}/answers`、`POST /questions/from-ocr`、`POST /diagnose/report`、`POST /plans`、`POST /plans/{id}/checkin`、`POST /ocr/upload`。服务端对同 key 重放返回首次结果（不重复写）。
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
