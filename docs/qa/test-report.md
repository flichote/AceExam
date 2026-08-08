# AceExam 测试报告（M1）

> 文档归属：`docs/qa/`（ep-qa 测试工程师产出）
> 关联任务：T6 测试门禁+烟测（kanban t_a2880f6b）
> 基线：`backend @ 0ef5133 + acd2679`、`frontend @ bb466b8`
> 执行环境：Windows / backend/.venv (Python 3.12.9) / node v22.23.1

---

## 1. 测试范围与分层

M1 三层质量门禁：

| 层 | 内容 | 文件 |
|---|---|---|
| 单元层 | auth 注册/登录/重复用户名、LLM 网关 mock 上游（超时/错误/内容安全/降级）、RAG 检索 mock 向量库（阈值/过滤/uncovered） | `tests/test_api_auth.py`(部分)、`tests/test_llm_gateway_mock.py`、`tests/test_rag_retriever_mock.py` |
| API 层 | /healthz、注册→登录→/me、401、subjects、questions、wrong-answers、chat（mock LLM） | `tests/test_api_auth.py`、`tests/test_api_subjects.py`、`tests/test_api_questions.py`、`tests/test_api_wrong_answers.py`、`tests/test_api_chat.py` |
| 数据库层 | 独立测试库建表/种子/清理、知识点状态机约束、幂等性（DB 唯一约束） | `tests/test_db_layer.py` |
| 前端烟测 | `npm run build` | frontend/ |

测试基础库：pytest + pytest-asyncio（asyncio_mode=auto）+ httpx ASGITransport（FastAPI TestClient 等价物）+ unittest.mock / httpx.MockTransport。

---

## 2. 执行结果（M1 实测）

### 2.1 后端 pytest

```
178 passed in 59.50s
```

- 新增用例：**81 个**（T6 交付前基线 97 → 交付后 178）
- 失败：0；跳过：0；xfail：0
- 覆盖要点：
  - auth：注册 201 / 重复用户名 409 / 登录成功 / 密码错误 401 / 未知用户 401 / /me 带 token 200 / 无 token 401 / 无效 token 401
  - subjects：列表（空、种子、公开访问）、创建（需鉴权、成功、重复 code 409、缺字段 422）、知识点列表、知识点树
  - questions：列表（鉴权、空、按 difficulty/kp 筛选、分页）、详情（不含答案）、404、创建、提交判定（正确/错误）、**幂等性**（重复提交错误只产生 1 条错题）
  - wrong-answers：列表、创建、重复 409、删除、删除他人记录 404、标记掌握、状态过滤
  - chat：非会员 403、未登录 401、讲解成功、404、追问上下文、跨用户 session 404、SSE 流式
  - LLM 网关：成功解析、flash 5xx→LLMError、pro 5xx→flash 降级、超时→LLMError、pro 超时降级、流式降级
  - RAG：低于阈值过滤、全部低于阈值→空、subject 过滤 SQL、top_k LIMIT、无命中→uncovered=true、有命中→citations
  - DB：13 张表建表、用户名/科目 code 唯一、状态机枚举约束、状态机 user+kp 唯一、错题 user+question 唯一、种子可见、drop 清理

### 2.2 前端烟测

```
cd frontend && npm run build
→ DONE  Build complete.
```

uni-app `npm run build`（H5 默认平台）通过。仅有 Dart Sass legacy-js-api 弃用警告（不影响构建）。

### 2.3 运行方式（复现）

```bash
cd backend
PYTHONPATH= .venv/Scripts/python.exe -m pytest -q     # 全量
# 数据库层默认使用独立 SQLite：backend/test_aceexam.db（测试结束自动删除）
# 如需切换 PG 测试库：
#   TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/test_aceexam PYTHONPATH= .venv/Scripts/python.exe -m pytest -q
```

> ⚠️ 环境注意：本机 shell 的 PYTHONPATH 注入过宿主 hermes venv，运行 pytest 前必须 `PYTHONPATH=` 清空，否则 SQLAlchemy/pydantic_core 版本串扰导致 ImportError。

---

## 3. 验收点对照（docs/design/flows.md）

| 验收点 | 状态 | 说明 |
|---|---|---|
| 流程1：错题自动入错题本 | ✅ 通过 | submit 错误 → wrong_answer_id 非空，错题本可见 |
| 流程1：追问有上下文 | ✅ 通过 | explain 返回 session_id，followup 复用 messages |
| 流程1：AI 讲解引用教材片段（CitationBlock 可见） | ✅ 通过（引擎层） | RAG explain 组装 citations（测试层断言 source/chapter）；chat API 目前 citations 恒为空数组，见缺陷 D-4 |
| 跨流程：入库幂等 | ✅ 通过 | 重复提交错误不产生重复错题；错题重复创建 409 |
| 状态机：未接触/待巩固/已掌握/薄弱 | ✅ 约束层通过 | DB CheckConstraint + 唯一约束验证；状态流转逻辑 M1 未实现（见 D-5） |
| 拍照录题 OCR 精度 | ⏸ 部分 | 本卡片仅覆盖 OCR 服务单元/降级测试（既有 test_ai_ocr.py）；真实 Pix2Text 精度样本集待 M2（本地无 pix2text 模型） |
| 打卡乐观锁并发 | ⏸ 未测 | M1 无打卡 API（study_sessions 表已建，接口未交付），并发乐观锁测试列入 M2 |

---

## 4. 缺陷记录（M1）

> 按工作约定，只记录不修改业务代码；以下缺陷需 ep-backend / ep-ai 修复。

### D-1 [P1] 创建题目缺少 knowledge_point_id 时 500
- **复现**：`POST /api/v1/questions?subject_id=<sid>`，body 不含 `knowledge_point_id`（schema 中该字段 `str | None = None` 可选）
- **实际**：`sqlite3.IntegrityError: NOT NULL constraint failed: questions.knowledge_point_id` → 全局异常处理器兜底 500
- **期望**：422 校验错误（schema 应要求必填）或后端默认关联；至少不 500
- **根因**：`QuestionCreate.knowledge_point_id` 声明可选，但 `questions.knowledge_point_id` 列 NOT NULL
- **影响**：前端未选知识点就创建题目必现 500

### D-2 [P2] 知识点树接口路径与 REST 规范不一致
- **说明**：`GET /api/v1/knowledge-points/tree` 与 `GET /api/v1/subjects/{id}/knowledge-points` 并存，tree 放在顶层路由而非 subject 子资源；当前可用，建议 M2 对齐（不影响 M1 功能）。

### D-3 [P2] questions 列表分页 total 使用 count 全量查询
- **说明**：`list_questions` 对 count 使用 `select(Question)` 后 `len(scalars().all())`，大表下有性能风险；M1 可接受，建议后续改 `func.count()`。

### D-4 [P2] chat API 未接入 RAG 引擎
- **说明**：`/chat/explain` 直接走 `llm_gateway.chat`，未调用 `RagEngine.explain`，响应中 `citations` 恒为空、`uncovered` 恒为 False——与 PRD「AI 讲解一律走 RAG、无引用命中提示教材未覆盖」不符。
- **影响**：流程1 验收点「引用教材片段」在 API 层未真正实现（引擎层已具备）。

### D-5 [P2] 知识点状态机流转逻辑未实现
- **说明**：`UserKnowledgeState` 表 + CheckConstraint 已建（DB 层测试验证），但 M1 无服务层实现「连续 3 次正确 → 已掌握」「正确率<40% → 薄弱」等流转规则；提交答案后不更新状态。
- **影响**：自适应出题/诊断依赖状态数据，M2 需补齐。

### D-6 [P3] LLM 网关无内容安全拦截层
- **说明**：网关对上游返回内容原样透传，无 moderation/敏感词过滤（`test_llm_gateway_mock.py` 已固化现状行为）。
- **建议**：M2 在上游响应/请求侧加内容安全策略（或交给 DeepSeek 官方 moderation 能力），并翻转 `test_llm_gateway_mock.py::TestContentSafety` 断言。

### D-7 [P3] SQLite 测试库需 bind_processor shim（仅测试环境）
- **说明**：`postgresql.UUID(as_uuid=True)` 在 SQLite 下 bind str 报 `'str' has no attribute 'hex'`（生产 asyncpg 会自动转 UUID）。conftest 已做测试专用 shim 对齐；若后续切换到 PG 测试库可移除。

---

## 5. 覆盖率要点与遗留

- 后端覆盖率：核心 API（auth/subjects/questions/wrong-answers/chat/healthz）全路由覆盖；AI 服务（OCR 单元、诊断解析、出题解析、RAG 引擎）由既有用例 + 本批次补齐。
- 未覆盖（明确列入 M2）：
  - Pix2Text 真实 OCR 精度样本集（公式题/文字+公式混合/手写兜底）
  - RAG 引用溯源正确性端到端（真实 pgvector + 教材片段）
  - 备考计划生成 / 打卡接口（M1 未交付 API）
  - 乐观锁并发打卡
- 测试隔离：每个用例独立 drop_all→create_all→种子，互不污染；测试库文件测试后自动删除。

---

## 6. 质量门禁结论

| 门禁 | 结果 |
|---|---|
| pytest 单元/集成 | ✅ 178 passed |
| 前端构建烟测 | ✅ npm run build DONE |
| 缺陷阻断 | ⚠️ D-1 为 P1（创建题目可 500），建议 M1 修复后合入；其余为 P2/P3 可带病发布并排期 M2 |

**发布建议**：D-1 修复前不建议放开「拍照录题/手动录题」创建题目链路；刷题/错题/讲解主链路可正常使用。

---

# AceExam 测试报告（M2 五件套验收）

> 文档归属：`docs/qa/`（ep-qa 测试工程师产出）
> 关联任务：T12 五件套验收测试（kanban t_b406629a）
> 基线：`backend @ 2912c48`、`frontend @ fa86e0f`（T9/T11 交付后）
> 执行环境：Windows / backend/.venv (Python 3.11.15) / node v22.23.1
> 范围：智能刷题 / AI 讲解 / 拍照录题 / 摸底诊断 / 备考计划 五件套端到端验收

---

## 7. M2 测试范围与新增用例

| 模块 | 验收点（flows.md） | 新增测试文件 | 用例数 |
|---|---|---|---|
| 智能刷题 | 薄弱优先自适应选题、提交答案→知识状态机、幂等 | `tests/test_m2_practice_flow.py` | 13（3 xfail） |
| AI 讲解 | 引用命中/无命中兜底、追问上下文、SSE、tier 路由 | `tests/test_m2_chat_rag.py` | 14 |
| 拍照录题 | 上传→结构化预览、轮询、确认入库、幂等、限流 | `tests/test_m2_ocr_flow.py` | 10（1 xfail） |
| 摸底诊断 | 自测→报告 JSON schema、薄弱 Top5、幂等 | `tests/test_m2_diagnose_flow.py` | 9（2 xfail） |
| 备考计划 | 创建→今日任务→打卡、幂等防抖、乐观锁 | `tests/test_m2_plan_flow.py` | 11（1 xfail） |
| 合计 | | | 59（10 xfail） |

实现说明：
- 上游 DeepSeek / Pix2Text 一律 mock（`monkeypatch` llm_gateway / 内联 OCR mock），不真调 API。
- 技术选型经 context7 核对：FastAPI 官方推荐 `httpx.AsyncClient(transport=ASGITransport(app))` + pytest-asyncio（asyncio_mode=auto），与现有 conftest 一致（查询记录见卡片 comment）。
- 数据格式按生产事实（database.md §3.3 / seed.py）：`options` 为 `[{key,text}]` 列表、`answer` 为纯字符串；与 conftest 的 M1 遗留 dict 格式区分。

## 8. 执行结果（M2 实测）

### 8.1 后端 pytest（全量）

```
274 passed, 10 xfailed, 2 failed in 158.02s
```

- M1 基线（T12 开工前）：`225 passed, 2 failed`（2 个失败为 T9 引入的 chat 回归，见 D-12）
- M2 新增：**49 个通过 + 10 个 xfail**（xfail 均为固化缺陷契约，缺陷清单见 §9）
- 失败 2 个：`tests/test_api_chat.py::TestChatExplain::test_explain_success`、`TestChatStream::test_explain_stream` —— **预存回归（D-12），非本次引入**

### 8.2 前端烟测

```
cd frontend && npm run build:h5
→ (T11 已通过；T12 复测结果见卡片 comment)
```

### 8.3 运行方式（复现）

```bash
cd backend
PYTHONPATH= .venv/Scripts/python.exe -m pytest -q          # 全量
# 单独跑五件套：
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_m2_*.py -q
```

## 9. 五件套逐项验收清单（对照 flows.md）

| 验收点 | 状态 | 说明 |
|---|---|---|
| 流程1 智能刷题：自适应选题薄弱优先 | ❌ 阻断（D-15） | `GET /subjects/{id}/practice/questions` 因 ORDER BY pgvector `<=>` 运算符直接 500，无法出题 |
| 流程1 提交答案→知识状态机（3 连对→已掌握） | ✅ 通过（落库） | 纯字符串载荷下 3 连对 → DB `mastered/streak=3`；答错 streak 归零、正确率<40%→weak（xfail D-9 记录响应滞后） |
| 流程1 判分正确性（前端实际载荷） | ❌ 阻断（D-8） | 前端发 `{type,value}` 信封，后端整 dict 全等比较 → 正确答案恒判错 |
| 流程1 AI 讲解引用教材片段 | ⚠️ 部分（D-4 遗留） | chat 未接 RagEngine；mock LLM 载荷下 citations/uncovered 契约层通过（2 用例） |
| 流程1 追问有上下文 | ✅ 通过 | explain→followup 复用 session messages；跨用户 404 |
| 流程2 拍照录题：上传→结构化预览 | ✅ 通过 | mock OCR 返回结构化题目 + suggested_kps；非法类型 400 |
| 流程2 确认入库 + 幂等 | ✅ 通过 | 入库 source=ugc；同一 upload 重复确认 duplicated=True 不重复建题 |
| 流程2 入库后可查看 | ❌ 阻断（D-16） | `GET /questions/{id}` 对 list 格式 options 500（QuestionResponse.options 声明 dict） |
| 流程2 免费用户限流 | ✅ 通过 | 第 6 次上传 429；会员不限 |
| 流程3 自测发起（章节覆盖） | ✅ 通过 | 生产格式数据下 201 + questions + coverage；count<5 → 422 |
| 流程3 报告 JSON schema（薄弱 Top5+建议） | ✅ 通过 | weak_top5 字段齐全、accuracy/status 与作答一致；strengths/not_started 正确 |
| 流程3 薄弱 Top5 排序 | ❌ 阻断（D-11） | 排序布尔 ASC → weak 排最后而非最前 |
| 流程3 计划创建→今日任务 | ✅ 通过 | 会员 201 + today_task；重复 409；过去日期 422 |
| 流程3 打卡持久化 + 防抖 | ✅ 通过 | 首次 checked_in；重复 already_checked_in=True |
| 打卡乐观锁 | ✅ 通过 | `UPDATE ... WHERE checked_in=false` 第二次 rowcount=0；并发双请求仅 1 个首次置位者 |
| 跨流程幂等（错题/报告/OCR/打卡） | ✅ 通过 | 重复提交不产生重复记录 |
| 今日任务反映练习进度 | ⚠️ 部分（D-17） | 统计落库正确；但 plan 用本地日、统计用 UTC 日，跨时区下今日任务显示 0 |

## 10. 缺陷记录（M2）

> 按工作约定只记录不修改业务代码；以下缺陷需 ep-backend / ep-ai 修复。

### D-8 [P1] 智能刷题判分载荷不匹配 → 前端作答恒判错
- **现象**：`POST /questions/{id}/answers` 对前端实际载荷 `{"type":"single","value":"C"}`（api.md §3.3 / frontend `buildAnswerValue`）判 `correct=False`；仅纯字符串 `"C"` 或 M1 遗留 `{"correct":"C"}` 且题目恰为 dict 答案时才判对。
- **根因**：`questions.py submit_answer` 直接 `correct = body.answer == question.answer` 整 dict 全等，未按题型解包信封；生产题库 answer 为纯字符串（seed.py / database.md §3.3）。
- **影响**：前端刷题正确率恒 0%，知识状态无法通过刷题进步；错题本被正确作答污染。
- **用例**：`test_m2_practice_flow.py::test_envelope_grading_contract`（xfail）。

### D-9 [P1] /answers 响应 knowledge_state 滞后一次作答
- **现象**：连续 3 次答对，响应依次返回 `untouched/0/0` → `consolidating/1/0` → `consolidating/2/0`（应 `mastered/3/0`）；DB 落库正确（`mastered/3/3`）。
- **根因**：`apply_answer` 在 `expire_on_commit=False` 的同一会话内 re-fetch，identity map 返回过期对象；Core upsert 不同步 ORM 属性。
- **影响**：前端展示的状态/streak 落后一次；「已掌握」提示延迟一轮。
- **用例**：`test_m2_practice_flow.py::test_response_knowledge_state_reflects_submission`（xfail）。

### D-10 [P2] /diagnose/self-test 对 dict 格式 options 500
- **现象**：题库题目 `options` 为 dict（M1 遗留 conftest 格式）时，自测发起返回 500（pydantic ValidationError：`SelfTestQuestionItem.options` 要求 list）。
- **根因**：schema 类型（list[dict]）与 M1 遗留数据格式（dict）不一致，未做归一化。
- **影响**：混合格式题库自测必现 500；生产 seed 为 list 格式不受影响。
- **用例**：`test_m2_diagnose_flow.py::test_self_test_handles_dict_options_gracefully`（xfail）。

### D-11 [P2] 诊断报告薄弱 Top5 排序反转
- **现象**：答错知识点（weak）排在答对知识点（consolidating）之后，`weak_top5[0]` 为强项而非薄弱项。
- **根因**：`order_by(UserKnowledgeState.status=="weak", status=="consolidating")` 默认 ASC，布尔 True(weak) 排最后。
- **影响**：报告推荐与自测表现相悖，薄弱项未优先。
- **用例**：`test_m2_diagnose_flow.py::test_report_weak_top5_ranks_weakest_first`（xfail）。

### D-12 [P2] M1 chat 测试回归（预存，T9 引入）✅ 已修复（8a10e08）
- **现象**：全量 2 个失败均为 `tests/test_api_chat.py`：`test_explain_success` 断言步骤标题 `讲解`、`test_explain_stream` 断言 SSE 明文 `片段A`。
- **根因**：T9 修改 `chat.py`：非流式 fallback 标题 `讲解`→`Explanation`、SSE delta 用 `json.dumps`（ensure_ascii）转义非 ASCII。
- **处置**：2026-08-08 确认 T9 变更为有意行为（SSE JSON 事件格式 + 模型未返回结构化 steps 时的英文 fallback 标题），同步更新测试断言以匹配新契约。chat 套件 8 passed。

### D-15 [P1] 自适应选题接口 500（ORDER BY pgvector `<=>`）
- **现象**：`GET /subjects/{id}/practice/questions` 一旦有题即 500：`ORDER BY questions.difficulty <=> ?` 语法错误（SQLite 与 PostgreSQL integer 列均不支持）。
- **根因**：`selection.py` 把 pgvector 余弦距离运算符 `<=>` 用在 integer 列上。
- **影响**：智能刷题出题链路完全不可用。
- **用例**：`test_m2_practice_flow.py::TestAdaptiveSelection` 4 个集成用例（xfail）。

### D-16 [P2] /questions 详情对 list 格式 options 500
- **现象**：`GET /questions/{id}`（及列表/创建）对生产格式 `options=[{key,text}]` 返回 500：`QuestionResponse.options` 声明 dict。
- **根因**：`schemas/questions.py QuestionResponse.options: dict` 与生产 list 格式冲突（practice/diagnose schema 用 list，跨端点不一致）。
- **影响**：生产格式题目无法通过 questions 端点查看；拍照录题确认后前端详情页 500。
- **用例**：`test_m2_ocr_flow.py::test_confirmed_question_viewable`（xfail）。

### D-17 [P3] 计划与刷题统计日期口径不一致
- **现象**：plan/checkin 用 `date.today()`（本地日），刷题统计用 `datetime.now(timezone.utc).date()`（UTC 日）；本机 UTC+8 深夜（本地 08-08 / UTC 08-07）时今日任务 `questions_practiced` 显示 0。
- **根因**：两处日期来源不统一。
- **影响**：UTC+8 每日 0-8 点刷题不计入当日任务。
- **用例**：`test_m2_plan_flow.py::test_today_task_reflects_practice`（xfail）。

### D-18 [P3] OCR from-ocr content_hash 死代码 + LIKE 前缀幂等
- **说明**：`questions.py confirm_ocr_question` 计算 `content_hash` 后未使用（死代码）；幂等判断用 `content LIKE %前30字符%`，同一内容的不同 upload 不会去重（重复拍照同题会建重复题）。M2 仅保证同 upload 幂等（已测通过）。

### D-19 [P3] M1 诊断 smoke 用例为盲区
- **说明**：`test_m2_smoke.py::test_m2_diagnose_self_test` 未 seed 题目，`questions=[]` 仅验证状态字段，未覆盖真实题组路径（D-10 因此未被发现）。本批次已用生产格式数据补齐真实路径用例。

---

## 11. M2 质量门禁结论

| 门禁 | 结果 |
|---|---|
| pytest 单元/集成 | ⚠️ 274 passed / 10 xfailed / 2 failed（2 failed 为预存回归 D-12） |
| 前端构建烟测 | ✅ npm run build:h5（T11 已过，T12 复测结果见卡片） |
| 五件套主链路 | ❌ 阻断：D-8（判分恒错）、D-15（出题 500）、D-16（题目详情 500）三个 P1/P2 阻断智能刷题与拍照录题主链路 |

**发布建议**：D-8/D-15/D-16 修复前不建议放开「智能刷题」「拍照录题确认后查看」；AI 讲解（含追问/SSE）、诊断报告（schema/幂等）、计划打卡（幂等/乐观锁）主链路可正常使用。缺陷用例已用 xfail 固化，ep-backend 修复后自动转 XPASS 验证。

---

# AceExam 测试报告（M3 图谱/突击/看板/排行/预警验收）

> 文档归属：`docs/qa/`（ep-qa 测试工程师产出）
> 关联任务：T18 M3 验收测试（kanban t_58ef44da）
> 基线：`backend @ eaa4a30`、`frontend @ 9fa1690`（T15/T16/T17 交付后）
> 执行环境：Windows / backend/.venv (Python 3.12.9) / node v22.23.1
> 范围：知识图谱 / 考前突击 / 学习看板 / 排行榜 / 挂科预警 / 打卡连胜 六模块验收 + 全量回归

---

## 12. M3 测试范围与新增用例

| 模块 | 验收点（flows.md / architecture.md §11） | 新增测试文件 | 用例数 |
|---|---|---|---|
| 知识图谱 | 树结构完整性（章→节→叶子）、节点状态映射、父节点 worst-child-wins 聚合、stats 叶子统计、question_count 聚合、include_questions | `tests/test_m3_knowledge_graph.py` | 11（1 xfail D-20） |
| 考前突击 | 手动激活（计划 exam_date/days_left 快照）、幂等、自动激活（≤7 天）、题单生成（高频+错题、去重、限量、快照稳定、mock 模式、真题兜底） | `tests/test_m3_sprint.py` | 18（2 xfail D-21/D-22） |
| 学习看板 | /me/dashboard 汇总（totals/mastery/streak/weak_points/per_subject/exam）、subject 过滤、/trend 按日/周/月分桶、空数据边界 | `tests/test_m3_dashboard.py` | 10 |
| 排行榜 | 入围过滤（≥30 题且正确率≥0.1）、排序（correct DESC→accuracy DESC）、分页 rank 连续、me、scope=subject | `tests/test_m3_leaderboard.py` | 7 |
| 挂科预警 | 风险等级三档边界（≤7/8-14/>14 天）、趋势调整（不活跃+1、向好-1）、理由可解释、overall 取最高、多计划/无计划边界 | `tests/test_m3_warnings.py` | 11 |
| 打卡连胜 | compute_streak 纯函数：连续/中断判定、longest 保留、乱序防御 | `tests/test_m3_streak.py` | 10 |
| 合计 | | | **67（3 xfail）** |

实现说明：
- 上游 DeepSeek 不真调：M3 七个端点在 API 层均为规则实现（LLM 增强函数由 T17 单独测试 `test_ai_m3.py` 覆盖，mock llm_gateway），本批 API 测试无需 mock 上游。
- 技术选型沿用 M1/M2：pytest + pytest-asyncio（asyncio_mode=auto）+ httpx ASGITransport + 直接入库种子（与 `test_m2_*` 一致）。
- 发现的 3 个新缺陷（D-20/D-21/D-22）按约定用非严格 xfail 固化契约，修复后自动转 XPASS 验证。

## 13. 执行结果（M3 实测）

### 13.1 M3 专项套件

```
64 passed, 3 xfailed in 71.33s
```

### 13.2 后端 pytest 全量回归

```
383 passed, 1 failed, 5 xfailed, 8 xpassed in 259.74s
```

- T18 开工前基线：`319 passed, 1 failed, 2 xfailed, 8 xpassed`（330 项）
- M3 新增：**64 通过 + 3 xfail**（合计 67 项，全量 397 项）
- 唯一失败：`tests/test_config.py::test_default_database_url` —— **预存环境性失败**（本地开发配置 `DATABASE_URL=sqlite+aiosqlite:///./aceexam.db`，测试断言默认应为 asyncpg PG 串），与 T17 交接记录一致，非本次引入。
- **8 个 XPASS = M2 缺陷契约自动验证通过**：D-8（判分信封）、D-9（状态滞后）、D-11（weak_top5 排序）、D-15×4（自适应出题 500）、D-16（题目详情 options 500）—— 全部由 T15/T17 修复，旧 xfail 用例转 XPASS 确认，M2 三个 P1 阻断全部解除。
- 5 个 xfail 剩余：D-10（dict options 自测 500）、D-17（本地日 vs UTC 日）、D-20/D-21/D-22（本批新增，见 §15）。

> ⚠️ 测试基建偶发（非业务缺陷）：第一次全量回归出现 `test_api_questions.py` 2 失败 + 1 错误（`sqlite3.OperationalError: no such table`），单测隔离均通过；重跑全量未复现（383 passed）。根因是 conftest `reset_db` 逐用例 drop_all/create_all 与 aiosqlite 连接池快照的竞态，属测试基建 flake，与 M3 业务代码无关。

### 13.3 前端烟测

```
cd frontend && npm run build
→ DONE  Build complete.   (dist/build/h5 2.2M；仅 Dart Sass legacy-js-api 弃用警告)
```

### 13.4 运行方式（复现）

```bash
cd backend
PYTHONPATH= .venv/Scripts/python.exe -m pytest -q                 # 全量
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_m3_*.py -q   # M3 专项
```

## 14. M3 验收点清单（对照 flows.md / architecture.md §11）

| 验收点 | 状态 | 说明 |
|---|---|---|
| 图谱：三级树结构完整（章→节→知识点） | ✅ 通过 | root=章，children=节，叶子 level=3；节点 id/name/level/question_count 正确 |
| 图谱：节点状态正确映射 | ✅ 通过 | weak/mastered/consolidating/untouched 四态落到叶子；practice_count/accuracy 正确 |
| 图谱：父节点自底向上聚合 | ✅ 通过 | worst-child-wins：任一 weak→weak；全 mastered→mastered；根随最差子节点 |
| 图谱：stats 只统计叶子 | ✅ 通过 | total_nodes/leaf_count/mastered/weak/consolidating/untouched 计数正确 |
| 图谱：多章（多 root）科目 | ❌ 阻断（D-20） | len(roots)>1 时 root=None，整棵树对前端不可见（xfail 固化） |
| 突击：手动激活（会员） | ✅ 通过 | 200 + created=True；计划 exam_date/days_left 快照正确；无计划 days_left=null |
| 突击：激活幂等 | ✅ 通过 | 重复激活 created=False，DB 仅 1 条 active 记录 |
| 突击：自动激活（考前 ≤7 天） | ✅ 通过 | GET questions 自动激活 auto_activated=True；考试 >7 天 → 403 不激活 |
| 突击：题单=高频考点+错题交集 | ✅ 通过 | heat≥20 且 avg_acc<0.75 的考点题 tag=high_freq；未掌握错题 tag=wrong_review |
| 突击：去重 | ✅ 通过（行为） | 同题既是高频题又是错题 → 只出现一次；但 summary.deduped 恒 0（D-21） |
| 突击：限量 | ⚠️ 部分（D-22） | 错题阶段严格限量；高频阶段单考点可超出 count（count=2 返 3 题） |
| 突击：快照稳定 | ✅ 通过 | 重复请求返回同一题单快照；DB question_snapshot 落库 |
| 突击：真题兜底 / mock 模式 | ✅ 通过 | 无高频状态时 past_exam 考点兜底；mode=mock 返回 duration/score |
| 看板：汇总正确性 | ✅ 通过 | totals 求和、mastery_pct=叶子掌握率、streak 当前/最长、weak_points、exam 倒计时 |
| 看板：per_subject 分解 + subject 过滤 | ✅ 通过 | 多科目分解正确；subject_id 过滤只统计该科目 |
| 看板：trend 时间序列 | ✅ 通过 | 按日/周/月分桶；命中桶数据正确；空桶 accuracy=None |
| 看板：trend 空数据边界 | ✅ 通过 | 无 session → 全 0 / accuracy=None / mastery_pct=0，不炸 |
| 排行：入围过滤 | ✅ 通过 | <30 题剔除；正确率 <0.1 剔除 |
| 排行：排序 | ✅ 通过 | total_correct DESC → accuracy DESC 两级排序；同正确数正确率高者优先 |
| 排行：分页 | ✅ 通过 | page/page_size、rank 连续、total 正确、越界空页 |
| 排行：me / scope=subject | ✅ 通过 | me 排名正确；无数据 me=null；subject 范围只聚合该科目 |
| 预警：风险等级边界 | ✅ 通过 | ≤7 天（0.4/0.7 分界）、8-14 天（0.3/0.6）、>14 天（0.2/0.5）三档正确 |
| 预警：趋势调整 | ✅ 通过 | 近 7 天活跃 ≤4 天 +1 级；≥70 题且正确率 ≥0.8 -1 级 |
| 预警：理由可解释 | ✅ 通过 | reasons 含正确率/练习次数/倒计时/活跃天数人类可读文案；suggestion 非空 |
| 预警：overall 取最高 + 边界 | ✅ 通过 | 多计划 max；无计划/无日期/过期考试/无薄弱各边界正确 |
| 打卡连胜：连续/中断判定 | ✅ 通过 | 今天/昨天打卡→存活；<昨天→current=0；longest 保留历史最长段 |

## 15. M3 缺陷记录（新增）

> 按工作约定只记录不修改业务代码；以下缺陷需 ep-backend 修复。

### D-20 [P2] 多章科目知识图谱 root 丢失
- **现象**：科目含 ≥2 个一级章时 `GET /subjects/{id}/knowledge-graph` 返回 `root: null`，整棵树（全部章/节/知识点）对前端不可见；仅 stats 仍正确。
- **根因**：`build_knowledge_graph` 中 `root = roots[0] if len(roots) == 1 else None`，多 root 场景直接丢弃所有节点。
- **影响**：真实科目（通常多章）图谱页面空白，ECharts series-tree 无根可渲染。
- **用例**：`test_m3_knowledge_graph.py::TestMultiRoot::test_multi_root_keeps_all_roots`（xfail）。

### D-21 [P3] 突击题单 summary.deduped 恒为 0
- **现象**：同一题既是高频考点题又是错题时，题单正确去重（只出现一次），但 `summary.deduped` 恒为 0。
- **根因**：实现为 `high_freq_questions + wrong_review_questions - total`，而两个计数与 `items.append` 严格同步，恒等于 total，从未统计被去重跳过的错题数。
- **影响**：前端「去重 N 题」提示恒为 0，与实际去重行为不符（轻微展示问题）。
- **用例**：`test_m3_sprint.py::test_summary_deduped_metric_counts_skipped_wrong`（xfail）。

### D-22 [P2] 突击题单 count 限量不严格（高频阶段可超出）
- **现象**：`GET /sprint/questions?count=2` 在高频考点各有 3 题时返回 3 题；count 仅是软上限。
- **根因**：高频阶段 SQL `LIMIT 3` 每次取满 3 题，`break` 判断在考点循环顶部而非逐题判断，单考点即可超出 `hf_slots`。
- **影响**：用户请求题数可能被超出（最多 +2/考点）；错题阶段严格限量不受影响。
- **用例**：`test_m3_sprint.py::test_count_limit`（xfail）。

## 16. 三里程碑质量门禁汇总

| 门禁 | M1（T6） | M2（T12） | M3（T18） |
|---|---|---|---|
| pytest 单元/集成 | ✅ 178 passed | ⚠️ 274 passed / 10 xfailed / 2 failed（D-12 预存） | ✅ **383 passed / 5 xfailed / 8 xpassed**（1 failed 为 test_config 预存环境性） |
| 前端构建烟测 | ✅ npm run build | ✅ npm run build:h5 | ✅ npm run build（DONE） |
| 三层质量门禁（pytest / OCR / RAG） | pytest ✅；OCR 待 M2；RAG mock 层 ✅ | 五件套 49 用例 + OCR mock 流程 ✅（真实 Pix2Text 样本集仍缺模型） | pytest ✅（M3 67 用例）；OCR/RAG 回归随全量通过（M2 已覆盖） |
| M2 P1/P2 阻断缺陷 | — | ❌ D-8/D-15/D-16 阻断 | ✅ 全部修复并 XPASS 验证 |
| M3 新阻断 | — | — | ⚠️ D-20（图谱多章 root 丢失）建议修复后放开图谱页面；D-21/D-22 为 P2/P3 可排期 |

**发布建议**：M2 三个 P1/P2 阻断（判分/出题/题目详情）已由 T15 修复并自动验证；M3 主链路（看板/排行/预警/突击/打卡连胜）验收通过。建议优先修复 D-20（多章科目图谱空白，影响真实使用），D-21/D-22 可随下个里程碑排期。缺陷用例均已 xfail 固化，修复后自动转 XPASS。

---

# AceExam 测试报告（M3.5 TTS/UGC/班级/分享卡验收）

> 文档归属：`docs/qa/`（ep-qa 测试工程师产出）
> 关联任务：T23 M3.5 验收测试（kanban t_7b665a57）
> 基线：`backend @ 2edfd57 + bc6a8cf`、`frontend @ dab2aec`（T20/T21/T22 交付后）
> 执行环境：Windows / backend/.venv (Python 3.11.15) / node v22.23.1
> 范围：TTS 语音 / UGC 投稿审核 / 班级 / 分享卡 四模块验收 + 全量回归

---

## 17. M3.5 测试范围与新增用例

| 模块 | 验收点（api.md §12） | 新增/扩展测试文件 | 用例数 |
|---|---|---|---|
| TTS 生成 | 会员鉴权、会话归属 404、无讲解 404、voice 白名单 422、mock edge-tts 合成 200、缓存幂等、上游失败 502 | `tests/test_m35_tts_api.py`（新建） | 16（2 xfail D-23/D-24） |
| 音频流 | 真实路由下载 200 audio/mpeg、缓存缺失 404、免费用户 403 | `tests/test_m35_tts_api.py` | 4（1 xfail D-24） |
| UGC 投稿 | 201+pending、<15 字 422、answer-type 校验、重复 409 | `tests/test_m35_api.py`（既有） | 3 |
| UGC 审核 | admin 鉴权 403、列表 status 过滤、approve→active、reject 需 reason 422、reject→rejected+reason、已审重审 409、非 UGC 422、404 | `tests/test_m35_api.py`（扩展 7 用例） | 10 |
| 班级 | 建班 6 位邀请码、邀请码加入、GET /me/class、二选一 422、无效码 404 | `tests/test_m35_api.py`（扩展 3 用例） | 7 |
| 分享卡 | totals/recent_7d/streak/mastery/weak_points/class/exam 聚合、全零边界 | `tests/test_m35_api.py`（扩展 5 用例） | 7（2 xfail D-26、1 xfail D-27） |
| 班级排行 | scope=class 未加入 422、同班过滤、subject 叠加过滤 | `tests/test_m35_api.py`（扩展 1 用例） | 3 |
| 合计（新增） | | | **34 用例（其中新增/扩展 16，M3.5 专项共 89 项 + 5 xfail）** |

实现说明：
- 上游 edge-tts 一律 mock（`monkeypatch edge_tts.Communicate.stream` 返回假音频字节），不真调网络；TTS 磁盘缓存目录用 `tmp_path` 隔离，不污染仓库。
- 技术选型沿用 M1~M3：pytest + pytest-asyncio（asyncio_mode=auto）+ httpx ASGITransport + 直接入库种子。
- 发现的 5 个新缺陷（D-23~D-27）按约定用非严格 xfail 固化契约，修复后自动转 XPASS 验证。

## 18. 执行结果（M3.5 实测）

### 18.1 M3.5 专项套件

```
89 passed, 5 xfailed in 80.07s
```

### 18.2 后端 pytest 全量回归

```
472 passed, 1 failed, 9 xfailed, 9 xpassed in 392.38s
```

- T23 开工前基线：`397 项（M3 全量）`；本次全量 491 项（+94 项为 M3.5 新增）。
- 唯一失败：`tests/test_config.py::test_default_database_url` —— **预存环境性失败**（本地开发配置 `DATABASE_URL=sqlite+aiosqlite:///./aceexam.db`，测试断言默认应为 asyncpg PG 串），与 T17/T18 交接记录一致，非本次引入。
- **9 个 XPASS** = M2 缺陷契约自动验证通过（D-8/D-9/D-11/D-15×4/D-16 等已修复用例转 XPASS 确认）。
- 5 个 M3.5 xfail = D-23/D-24/D-26×2/D-27（本批新增，见 §20）。
- 回归结论：**M1~M3 主链路测试全部保持通过**（唯一失败为环境性 test_config），M3.5 新增功能除 TTS 播放链路（D-24）与 share-card 考试/掌握度分支（D-26）外均通过。

### 18.3 前端烟测

```
cd frontend && npm run build
→ DONE  Build complete.   (仅 Dart Sass legacy-js-api 弃用警告)
```

### 18.4 运行方式（复现）

```bash
cd backend
PYTHONPATH= .venv/Scripts/python.exe -m pytest -q                                    # 全量
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_m35_*.py -q               # M3.5 专项
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_m35_tts_api.py -v        # TTS 专项
```

## 19. M3.5 验收点清单（对照 api.md §12）

| 验收点 | 状态 | 说明 |
|---|---|---|
| §12.1 TTS 生成：会员鉴权 | ✅ 通过 | 免费用户 403；未登录 401 |
| §12.1 TTS 生成：会话归属 | ✅ 通过 | 不存在/非本人 session → 404 |
| §12.1 TTS 生成：无讲解内容 | ✅ 通过 | 无 assistant 消息/空白内容 → 404 EXPLANATION_NOT_FOUND |
| §12.1 TTS 生成：voice 白名单 | ✅ 通过 | 非法 voice → 422；缺省默认 Xiaoxiao |
| §12.1 TTS 生成：mock edge-tts 合成 | ✅ 通过 | 200 + audio_url/voice/text_preview/cache_hit=false；LaTeX 清洗后中文保留 |
| §12.1 TTS 生成：缓存幂等 | ✅ 通过 | 同 session 同 voice 二次调用 cache_hit=true，不重复合成 |
| §12.1 TTS 生成：上游失败 | ✅ 通过 | edge-tts 异常 → 502 TTS_UNAVAILABLE |
| §12.1 TTS 生成：audio_url 可播放 | ❌ 阻断（D-24） | 返回 `/api/v1/tts/audio/...`，真实路由 `/api/v1/chat/tts/audio/...` → 前端按 audio_url 请求必 404 |
| §12.1 TTS 生成：display math 清洗 | ❌ 缺陷（D-23） | `$$...$$` 不被 `_clean_text_for_tts` 剥光，LaTeX 命令会进 TTS 语音 |
| §12.2 音频流下载 | ⚠️ 部分（D-24/D-25） | 真实路由 200 audio/mpeg + Range 支持通过；audio_url 与路由不一致（D-24）；鉴权实现为会员，契约写登录（D-25） |
| §12.3 UGC 投稿 | ✅ 通过 | 201+pending+source=ugc；<15 字 422；answer 与选项 key 匹配 422；内容重复 409 DUPLICATE |
| §12.4 审核列表 | ✅ 通过 | admin 鉴权（非 admin 403）；status=pending/active/rejected 过滤；total/items 正确 |
| §12.5 审核状态机 | ✅ 通过 | approve→active；reject 需 reason（422）；reject→rejected+reject_reason 落库；已审重审 409；非 UGC 422；不存在 404 |
| §12.6 建班/加入 | ✅ 通过 | 建班 201/200 + 6 位邀请码 + is_creator；邀请码加入（不返回 invite_code）；二选一 422；无效码 404 |
| §12.7 /me/class | ✅ 通过 | 已加入返回 class+my_rank（member_count 实时）；未加入 class=null+my_rank=null |
| §12.7 scope=class 排行 | ✅ 通过 | 未加入 422 CLASS_NOT_JOINED；只聚合同班成员（非同班用户排除）；subject_id 叠加过滤正确 |
| §12.8 share-card：totals/recent_7d | ✅ 通过 | 做题量/正确数/正确率聚合正确；recent_7d 只统计近 7 天（8 天前仅进 totals）；全零用户返回 0 值 |
| §12.8 share-card：streak | ✅ 通过 | 3 天连续打卡 → current=3/longest=3 |
| §12.8 share-card：mastery/weak_points | ❌ 阻断（D-26） | 有 UserKnowledgeState 数据 → best_subject 段 NameError → 500 |
| §12.8 share-card：exam 倒计时 | ❌ 阻断（D-26） | 有 active 计划（exam_date）→ exam 段 NameError → 500 |
| §12.8 share-card：class 区块 | ⚠️ 缺陷（D-27） | 实现字段名 `class_`，契约/前端消费 `class` → 海报班级区块永不显示 |

## 20. M3.5 缺陷记录（新增）

> 按工作约定只记录不修改业务代码；以下缺陷需 ep-backend / ep-ai 修复。

### D-23 [P3] TTS 文本清洗不处理 display math（$$...$$）
- **现象**：讲解文本含 `$$...$$` 展示公式时，`chat.py::_clean_text_for_tts` 仅用 `re.sub(r'\$[^$]*\$', '', content)` 剥 inline math，`$$...$$` 残留 LaTeX 命令（如 `\lim`、`\frac`）进入 TTS 语音。
- **根因**：`_clean_text_for_tts` 与 `tts_service.preprocess_text`（正确处理 display math）实现不一致，chat 端点未复用后者。
- **影响**：公式题讲解语音会朗读 LaTeX 命令，体验缺陷。
- **用例**：`test_m35_tts_api.py::TestTTSValidation::test_tts_display_math_not_stripped`（xfail）。

### D-24 [P1] TTS audio_url 与真实路由不一致 → 前端播放必 404
- **现象**：`POST /chat/explain/{id}/tts` 返回 `audio_url: "/api/v1/tts/audio/{hash}.mp3"`，但 GET 音频真实路由为 `/api/v1/chat/tts/audio/{hash}.mp3`（chat router prefix=`/chat`）。前端 `resolveAudioUrl` 直接 origin+audio_url 请求 → 404。
- **根因**：`chat.py generate_tts` 拼 audio_url 时漏掉 `/chat` 段。
- **影响**：TTS 生成成功但音频播放链路完全不可用。
- **用例**：`test_m35_tts_api.py::TestTTSAudioDownload::test_audio_url_from_tts_matches_route`（xfail）。

### D-25 [P3] 音频下载鉴权与契约不符
- **现象**：契约 §12.2 写"鉴权：登录"，实现 `get_tts_audio` 用 `get_current_member`（免费用户 403）。
- **影响**：免费用户即使拿到音频 URL 也无法播放（与 §12.1 会员语义一致，可能是有意设计，需契约对齐）。
- **用例**：`test_m35_tts_api.py::TestTTSAudioDownload::test_audio_download_free_user_forbidden`（按实现固化 403）。

### D-26 [P1] share-card 使用未定义的 Subject → 500
- **现象**：`GET /me/share-card` 在两类数据下 500：① 有 `user_knowledge_states` 数据（best_subject 分支）；② 有 active 计划且 `exam_date` 非空（exam 分支）。
- **根因**：`me.py` 模块顶部未导入 `Subject`；best_subject 段局部 `from app.db.models import Subject as _Subject` 但查询写的是 `select(Subject.name)`（line 236），exam 段直接 `select(Subject.name)`（line 274）→ NameError。
- **影响**：分享卡在真实用户（有掌握度/有备考计划）下必 500，仅全零用户可用。
- **用例**：`test_m35_api.py::TestShareCard::test_share_card_mastery_and_weak`、`test_share_card_exam_days_left`（均 xfail）。

### D-27 [P2] share-card 班级字段序列化为 class_ 而非 class
- **现象**：`ShareCardResponse.class_` 无 pydantic alias，响应 JSON 键为 `"class_"`；契约 §12.8 与前端 `SharePoster.vue`（`d.class`）均消费 `"class"` → 海报班级区块永不显示。
- **根因**：schema 字段名带下划线后缀且未配 `Field(alias="class")`。
- **影响**：班级区块静默缺失。
- **用例**：`test_m35_api.py::TestShareCard::test_share_card_class_field_contract`（xfail）。

## 21. 四里程碑质量门禁汇总

| 门禁 | M1（T6） | M2（T12） | M3（T18） | M3.5（T23） |
|---|---|---|---|---|
| pytest 单元/集成 | ✅ 178 passed | ⚠️ 274 passed / 10 xfailed / 2 failed（D-12 预存） | ✅ 383 passed / 5 xfailed / 8 xpassed | ✅ **472 passed / 9 xfailed / 9 xpassed**（1 failed 为 test_config 预存环境性） |
| 前端构建烟测 | ✅ npm run build | ✅ npm run build:h5 | ✅ npm run build | ✅ npm run build（DONE） |
| M3.5 新增功能 | — | — | — | TTS 生成/音频流、UGC 审核状态机、班级、scope=class 排行 ✅；分享卡 ⚠️ D-26 阻断 mastery/exam 分支 |
| 三层质量门禁（pytest / OCR / RAG） | pytest ✅；OCR 待 M2；RAG mock 层 ✅ | 五件套 49 用例 + OCR mock 流程 ✅ | pytest ✅；OCR/RAG 回归随全量通过 | pytest ✅（M3.5 34 用例）；OCR/RAG 随全量回归通过 |
| 新阻断缺陷 | — | D-8/D-15/D-16 | D-20（图谱多章 root 丢失，M3 遗留 xfail） | ⚠️ D-24（TTS 播放 404）、D-26（share-card 500）建议修复后放开对应页面 |

**发布建议**：M3.5 的 TTS 生成、UGC 投稿/审核状态机、班级、班级排行主链路验收通过；**D-24（TTS 播放 404）与 D-26（分享卡 mastery/exam 分支 500）为 P1 阻断，建议修复后放开 TTS 播放与分享卡页面**；D-25/D-27 为契约对齐（P3/P2），可随下个里程碑排期。缺陷用例均已 xfail 固化，修复后自动转 XPASS。

---

## 22. M4 测试范围与新增用例

> 关联任务：T27 选课验收测试（kanban t_a3a033a2）
> 依赖交付：T25 后端 49819c9（4 端点 + 0005 迁移）、T26 前端 9806d15
> 契约来源：docs/api.md §13（13.1~13.4）、docs/architecture.md §13.6、docs/ops/M4-taskgraph.md

| 文件 | 用例数 | 覆盖 |
|---|---|---|
| `tests/test_m4_subjects_plaza.py`（T25 交付） | 14 passed / 3 skipped | 基础路径：major 更新/清除/401、PUT/GET /me/subjects、422 SUBJECT_NOT_JOINABLE、plaza 游客/登录、schema 扩展（major/is_public） |
| `tests/test_m4_plaza_acceptance.py`（T27 新增） | 11 passed / 1 xfailed | 契约边界补充：major 空白 strip/超长/100 边界、**幂等覆盖语义（D-29 xfail）**、清空后重设、返回顺序=请求数组顺序、stats 数值口径（q/correct/accuracy/mastery/kp/streak）、零记录零值、plaza joined 真实状态（加入 true/未加入 false）、私有课不进广场、sort_order 排序、question_count 仅计 active |
| `tests/test_m4_migration.py`（T27 新增） | 3 passed | 迁移链 0001→0005 离线 SQL 可生成（alembic upgrade head --sql）、0005 关键 DDL 断言、迁移文件元数据链 |

**T27 新增 15 用例（14 passed + 1 xfailed）**；累计全量 500 passed / 3 skipped / 9 xfailed / 10 xpassed（1 failed 为 test_config 预存环境性，见 §21）。

## 23. 执行结果（M4 实测）

### 23.1 M4 专项套件

```bash
cd backend
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_m4_subjects_plaza.py -q                      # T25 交付
→ 14 passed, 3 skipped
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_m4_plaza_acceptance.py tests/test_m4_migration.py -q   # T27 新增
→ 14 passed, 1 xfailed in 21.86s
```

### 23.2 后端 pytest 全量回归

```bash
PYTHONPATH= .venv/Scripts/python.exe -m pytest -q
→ 500 passed, 3 skipped, 9 xfailed, 10 xpassed, 1 failed in 431.80s
```

- 唯一 failed：`tests/test_config.py::test_default_database_url` —— **预存环境性**（本地 `.env` 配置 `DATABASE_URL=sqlite+aiosqlite:///./aceexam.db`，该用例断言默认 PG asyncpg 串）；M3/M3.5 报告同项，与 M4 改动无关。
- 10 xpassed：既有 M2/M3 缺陷修复确认（D-8/D-9/D-11/D-15/D-16 等，随 T25 全量回归报告）。
- 主链路回归：subjects/questions/practice/auth/wrong-answers/chat 等 43 端点全部通过，**无破坏**。

### 23.3 前端烟测

```bash
cd frontend && npm run build
→ DONE  Build complete.（T26 交付 9806d15 代码，Dart Sass legacy-js-api 弃用警告非错误）
```

### 23.4 迁移可执行性（任务要求）

```bash
cd backend
PYTHONPATH= .venv/Scripts/python.exe -m alembic upgrade head --sql
→ exit 0；渲染 0001_initial → 0005_user_major_plaza 全链；输出含
  ALTER TABLE users ADD COLUMN major VARCHAR(100);
  ALTER TABLE subjects ADD COLUMN is_public BOOLEAN DEFAULT false NOT NULL;
  CREATE TABLE user_subjects (...);
```

## 24. M4 验收点清单（对照 api.md §13）

| 验收点 | 状态 | 说明 |
|---|---|---|
| 13.1 PUT /me/profile 更新 major | ✅ 通过 | 200 返回 UserPublic+major；首尾空白 strip；置空 `""`/None 清除（T25） |
| 13.1 未登录 401 | ✅ 通过 | T25 用例 |
| 13.1 超长 major → 400 VALIDATION_ERROR | ⚠️ 契约偏差 | **实际返回 422**（Pydantic 默认）；见缺陷 D-28 |
| 13.2 PUT /me/subjects 设置课程（幂等覆盖） | ❌ 缺陷 | **D-29：第二次 PUT 含重叠 id → UNIQUE 冲突 500**，违反"先删后插同事务"契约；用例已 xfail 固化 |
| 13.2 空数组清空 / 重复 id 去重 / 422 SUBJECT_NOT_JOINABLE | ✅ 通过 | T25 + T27 |
| 13.3 GET /me/subjects 返回自选课程+学习状态 | ✅ 通过 | 顺序=请求数组顺序；stats 数值口径正确（q=10/c=8/acc=0.8/mastery=0.5/kp/streak≥1）；零记录零值 |
| 13.4 GET /subjects/plaza 公共课 + 加入状态 | ✅ 通过 | joined 加入 true/未加入 false；仅 is_public+is_active；sort_order,name 排序 |
| 13.4 未登录可看列表 | ✅ 通过 | 游客 joined 恒 false（T25） |
| 13.4 question_count 仅计 active | ✅ 通过 | active×2 + rejected×1 → 2 |
| 0005 迁移可执行 | ✅ 通过 | alembic upgrade head --sql exit 0 + DDL 断言 |
| 回归：subjects/questions/practice 主链路 | ✅ 通过 | 全量 500 passed（唯一 failed 为预存环境性） |
| 前端冒烟 npm run build | ✅ 通过 | DONE Build complete. |

## 25. M4 缺陷记录（新增）

### D-28 [P3] PUT /me/profile major 超长返回 422 而非契约 400 VALIDATION_ERROR
- **现象**：`PUT /me/profile` 请求 `{"major": "x"*101}` 返回 **422**（FastAPI Pydantic RequestValidationError 形态），契约 api.md §13.1 错误表写 400 `VALIDATION_ERROR`。
- **根因**：`ProfileUpdate.major` 声明 `max_length=100`，Pydantic 校验失败由 FastAPI 默认 422 处理器接管；项目未注册自定义 `RequestValidationError` handler 映射为 400。
- **影响**：前端按 400 分支处理会漏掉超长提示（前端实际按 422 亦可，影响小）。
- **用例**：`test_m4_plaza_acceptance.py::TestProfileBoundary::test_major_too_long_returns_422`（固化现状，不 xfail，避免门禁误伤；契约对齐与否由 ep-backend 裁决）。

### D-29 [P1] PUT /me/subjects 幂等全量覆盖同事务 UNIQUE 冲突 → 500
- **现象**：先 `PUT /me/subjects {"subject_ids":[A,B]}` 成功；再 `PUT /me/subjects {"subject_ids":[B,C]}`（含重叠 B）→ `sqlite3.IntegrityError: UNIQUE constraint failed: user_subjects.user_id, user_subjects.subject_id` → 全局异常兜底 500。
- **根因**：`me.py::set_my_subjects` 先 `await db.delete(us)` 收集删除，随后在**同一事务**插入新 `UserSubject`；SQLite（及多数方言）在 flush 时 INSERT 先于 DELETE 落地，命中 `uq_us_user_subject` 唯一约束。缺 `await db.flush()`（或先执行 DELETE 语句再插入）保证先删后插。
- **影响**：**违反 api.md §13.2 幂等全量覆盖核心语义**；真实前端"重新勾选课程"（含保留已选课）必现 500。T25 交付的 `test_idempotent`/`test_dedup` 依赖 seed 数据在空测试库被 skip，**未覆盖到此路径**。
- **用例**：`test_m4_plaza_acceptance.py::TestIdempotentOverwrite::test_overwrite_replaces_not_merges`（**xfail 固化**；ep-backend 修复后自动 XPASS）。
- **建议修复**：`set_my_subjects` 删除后 `await db.flush()` 再插入，或在同一事务用 `delete(UserSubject).where(user_id==...)` 执行删除。

---

## 26. M5 测试范围与新增用例

> 关联任务：T33 M5 验收测试（kanban t_f8cb7781）
> 依赖交付：T29 db 51acca6、T30 backend a7e1976、T31 ai 6b94455、T32 frontend 1ec16b2
> 契约来源：docs/api.md §14（14.1~14.5）、docs/architecture.md §14（D19~D22）、docs/database.md §12

| 文件 | 用例数 | 覆盖 |
|---|---|---|
| `tests/test_m5_api.py`（T30 交付） | 24 passed | 基础路径：aliases 401/空库、match mock/未知/422、me/courses 手动建/重复/模板 404/列表、ugc upload 422/201/404/skip、ugc status 401/空/过滤 |
| `tests/test_ai_course_matcher.py`（T31 交付） | 23 passed | 归一化、别名命中、AI 语义匹配（mock LLM）、JSON 解析健壮性、降级回退 |
| `tests/test_ai_ugc_review.py`（T31 交付） | 35 passed | ugc_review 服务：verdict/confidence/reasons、规则抽检、mock LLM 边界 |
| `tests/test_m5_acceptance.py`（T33 新增） | **58 passed + 4 xfailed** | 表结构（alias UNIQUE/template FK/默认值/CHECK）、match 别名精确命中 + AI 阈值边界（0.85/0.60/0.59）+ 候选降序（D-33 xfail）、me/courses 模板映射 + school 实例 + 幂等 409、别名沉淀（D-34 xfail×2）、aliases 联想（q/is_verified/limit/template 过滤）、UGC 预检 + pass/flag 分流 + 自动放行 active + subject_id 模板解析、status 查询（本人/过滤/前缀反解/admin reject）、ai_review 透传（D-36 xfail） |

**T33 新增 62 用例（58 passed + 4 xfailed）**；M5 专项合计 **140 passed + 4 xfailed**（24+23+35+58）。

## 27. 执行结果（M5 实测）

### 27.1 M5 专项套件

```bash
cd backend
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_m5_api.py tests/test_m5_acceptance.py tests/test_ai_course_matcher.py tests/test_ai_ugc_review.py -q
→ 140 passed, 4 xfailed in 132.59s
```

### 27.2 后端 pytest 全量回归

```bash
PYTHONPATH= .venv/Scripts/python.exe -m pytest -q
→ 640 passed, 3 skipped, 13 xfailed, 10 xpassed, 1 failed in 614.68s
```

- 唯一 failed：`tests/test_config.py::test_default_database_url` —— **预存环境性**（本地 `.env` 配置 `DATABASE_URL` 覆盖默认 PG 串；M3/M3.5/M4 报告同项，与 M5 改动无关）。
- **D-29 XPASS 确认修复**：`test_m4_plaza_acceptance.py::TestIdempotentOverwrite::test_overwrite_replaces_not_merges` 由 xfail 转 XPASS —— T30（a7e1976）在 `set_my_subjects` 增加先删后插 `await db.flush()`，M4 遗留 P1 缺陷已修复。
- **测试基础设施硬化（T33）**：
  - `test_m35_api.py::test_share_card_streak_only` 与 `test_m4_plaza_acceptance.py::test_stats_aggregation_values` 的 `_d()` 播种由本地 `date.today()` 改为 UTC 口径（`datetime.now(timezone.utc).date()`），消除本地 00:00~08:00 时区窗口必败（D-35，见 §29）。
  - 沿用 run-44 遗留的 pytest 配置（`asyncio_default_fixture_loop_scope=session`）与 conftest Windows 文件清理重试，全量 640 passed 稳定通过。
- 主链路回归：subjects / user_subjects / questions / practice / auth / wrong-answers / chat 等全部通过，**无 M5 相关回归**。

### 27.3 运行方式（复现）

```bash
cd backend
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_m5_acceptance.py -q    # T33 新增
PYTHONPATH= .venv/Scripts/python.exe -m pytest -q                                 # 全量
```

## 28. M5 验收点清单（对照 api.md §14）

| 验收点 | 状态 | 说明 |
|---|---|---|
| 14.1 GET /courses/aliases 未登录 401 | ✅ 通过 | T33 |
| 14.1 无 q 返回 verified 别名、有 q 时 ILIKE 匹配 + is_verified 优先 | ✅ 通过 | T33：verified-only 2 条；q=高数 → verified 在前；`limit` ≤20（21 → 422）；`template_subject_id` 过滤 + 非法 uuid 400 |
| 14.2 POST /courses/match 别名精确命中 | ✅ 通过 | 归一化后命中 verified 别名 → `strategy=alias`、`confidence=1.0`、单候选、`source=alias`；unverified 别名不命中（走 AI） |
| 14.2 未命中走 AI（mock LLM） | ✅ 通过 | strategy=ai；高等数学A → 0.92、高等数学 → 0.88、概率论 → 0.80；未知课程 → matched=false |
| 14.2 阈值边界（D21） | ✅ 通过 | monkeypatch 注入：0.85 → matched=true；0.60 → matched=true；0.59 → matched=false |
| 14.2 候选按 confidence 降序 | ⚠️ 缺陷 | **D-33 xfail**：路由透传上游顺序不重排（契约要求降序；当前依赖 T31 服务排序） |
| 14.2 name 归一化（学期/年份/括号/空白） | ✅ 通过 | `2026春 高等数学A（上）` → 命中 `高等数学a` 别名；name 空/超长 → 422 |
| 14.3 POST /me/courses 映射模板 | ✅ 通过 | `template_subject_id` 写入 user_subjects；无同名 school 行 → 直接挂模板；已存在同名 school 行 → 复用（subject_id=校本行, template_subject_id=模板）；模板不存在/不活跃 404、非法 uuid 400 |
| 14.3 手动建 school 实例 | ✅ 通过 | template NULL → `subjects` 插入 level='school' 行（code `school_<hash>`、is_public=false）、user_subjects.template_subject_id=NULL、matched=false |
| 14.3 幂等 409 ALREADY_EXISTS | ✅ 通过 | 同用户同 subject_id 二次提交 → 409（模板路径 + school 路径）；不同用户同校名复用同一 school 行（仅新增各自关联） |
| 14.3 命中沉淀 alias（架构 §14.2 飞轮） | ❌ 缺陷 | **D-34 xfail×2**：AI 匹配/模板映射后不沉淀 `source='ai'` 别名（course_aliases 仅 seed 写入） |
| 14.4 POST /ugc/upload 规则预检 | ✅ 通过 | content<15 → 422；answer 不在 options → 422；content_hash 去重 → 409 DUPLICATE（带既有 question_id）；subject/kp 不存在 → 404 |
| 14.4 AI 初审 pass → pending | ✅ 通过 | mock pass（conf=0.9）+ 默认 subject 配置 → status=pending、ai_review.verdict=pass |
| 14.4 自动放行 active（D22） | ✅ 通过 | `subjects.config.ugc_ai_auto_approve=true` + pass + conf≥0.9 → 直接 active（DB 校验 status/reject_reason） |
| 14.4 AI flag → pending + 预填理由 | ✅ 通过（契约口径） | 无答案 → AI flag → status=pending + reject_reason `[AI:flag] 无答案`；**任务 body 所述「AI reject → rejected」与 D22 冲突**，实现按 D22「AI 只预筛不终审」：AI 不终审，人工 admin reject 才置 rejected（回归通过，见下） |
| 14.4 subject_id 解析（school → 模板） | ✅ 通过 | 投稿传 school 实例 id → 按 user_subjects.template_subject_id 解析为模板课程落库（question.subject_id=模板） |
| 14.5 GET /ugc/status 仅本人 | ✅ 通过 | 另一用户查不到 |
| 14.5 status 过滤 / 分页 / 内容截断 | ✅ 通过 | pending 过滤、admin reject 后 rejected 可查、content 50 字截断 |
| 14.5 ai_review 透传 | ⚠️ 缺陷 | **D-36 xfail**：pass→pending 投稿 ai_review=null（pass 结果未持久化，契约示例要求透传） |
| 回归：M1~M4 全量不破 | ✅ 通过 | 640 passed / 3 skipped / 13 xfailed / 10 xpassed / 1 failed（test_config 预存环境性）；**D-29 XPASS 确认修复** |

## 29. M5 缺陷记录（新增）

### D-33 [P3] POST /courses/match AI 候选未在 API 层按 confidence 降序
- **现象**：monkeypatch 注入乱序候选 `[0.6, 0.88]`，响应原样返回（未降序）。契约 api.md §14.2 要求「候选按 confidence 降序」。
- **根因**：`courses.py::match_course` 遍历 AI 结果不重排；排序仅在 T31 服务 `course_matcher.py`（line 289~290）内部做。当前路由用 mock（单候选），T31 真实接入后依赖上游排序才能满足契约。
- **建议**：路由层 `sorted(candidates, key=confidence, reverse=True)` 兜底，或在 T31 接入联调时验证服务契约。
- **用例**：`test_m5_acceptance.py::TestMatchAIStrategy::test_ai_candidates_sorted_desc`（**xfail 固化**）。

### D-34 [P2] M5「命中沉淀 alias」飞轮未实现
- **现象**：`POST /courses/match` AI 命中、`POST /me/courses` 模板映射后，`course_aliases` 均无新增行（仅 seed 有数据）。架构 §14.2 要求「用户录入时 AI 匹配命中 → 沉淀一条 `source='ai'`（幂等，命中即 upsert）」。
- **影响**：课程归一对齐飞轮闭环缺失——别名库不会随用户录入增长，长期依赖 AI 调用（成本与延迟不降）。
- **用例**：`test_m5_acceptance.py::TestAliasPrecipitation::test_ai_match_precipitates_alias`、`test_me_courses_map_precipitates_alias`（**xfail 固化×2**）。

### D-35 [P3] 预存测试时区窗口 flaky（已修复）
- **现象**：`test_share_card_streak_only`（M3.5）与 `test_stats_aggregation_values`（M4）在本地 00:00~08:00 必败：`StudySession.session_date` 用本地 `date.today()` 播种，而 `me.py` 按 `datetime.now(timezone.utc).date()` 计算 streak → UTC 落后本地一天时 latest 日期超前 → current_streak=0。
- **处理**：`_d()` 改 UTC 口径播种（两文件），与 API 一致；非 M5 引入，T33 顺手硬化。全量回归 640 passed 证实修复。

### D-36 [P2] /ugc/status 对 pass→pending 投稿 ai_review=null
- **现象**：AI 初审 pass 的 pending 投稿，`GET /ugc/status` 返回 `ai_review: null`。契约 api.md §14.5 示例要求 `ai_review: {verdict: pass, confidence, reasons}` 透传。
- **根因**：MVP 约定「AI 初审结果序列化进 `reject_reason` 前缀」，但 `_encode_ai_review_prefix` 仅对 flag 写 `[AI:flag]`，pass 不写 → 反解函数对 `reject_reason=None, status=pending` 返回 None。主动态（auto-approve）与 flag 态可反解，pass→pending 丢失。
- **建议**：pass 也写前缀（如 `[AI:pass] 题干完整; 答案自算一致`）或新增 `questions.ai_review` JSONB 列（T29 预留选项）。
- **用例**：`test_m5_acceptance.py::TestUgcStatusQuery::test_ai_review_passthrough_for_pending_pass`（**xfail 固化**）。

### 观察项（非阻断，契约待澄清）
- **school/textbook 字段未参与匹配**：`CourseMatchRequest.school`/`textbook` 被接收但 `courses.py` 未使用（mock 也不消费）；api.md §14.2 示例「清华 2026春 高等数学A」归一化后为「清华高等数学a」——学校名前缀未剥离，无法命中「高等数学a」别名。前端当前应传纯课程名（校名走 school 字段）或由 T31 服务做校名/教材识别。
- **升级路径无更新端点**：api.md §14.3「成功后可再调 POST /courses/match 或后续匹配流程回填 template_subject_id」——但 `POST /me/courses` 对已存在 `(user, subject_id)` 恒 409，无 PATCH/PUT 更新 template_subject_id 的端点，已建 school 实例无法通过 API 升级到模板。
- **Idempotency-Key 未实现**：api.md §14.4/§14.3 声明支持 `Idempotency-Key`，当前无中间件/读取逻辑；实际防重依赖 content_hash 去重（409 DUPLICATE，已测）。

## 30. M5 质量门禁结论

| 门禁 | 结果 |
|---|---|
| pytest 单元/集成（M5 专项） | ✅ **140 passed / 4 xfailed**（course_matcher 23 + ugc_review 35 + test_m5_api 24 + test_m5_acceptance 58） |
| 全量回归（M1~M5） | ✅ **640 passed / 3 skipped / 13 xfailed / 10 xpassed / 1 failed**（唯一 failed 为 test_config 预存环境性）；**D-29 XPASS 确认修复** |
| M5 新增功能验收 | 课程对齐：别名命中 / 阈值分流 / 模板映射 / school 实例 / 幂等 ✅；**别名沉淀飞轮 ❌ D-34**；UGC 审核流：预检 / pass→pending / 自动放行 / flag 预填 / status 查询 ✅；**ai_review 透传 ⚠️ D-36** |
| 前端烟测 | 由 T32（1ec16b2，vue-tsc + h5/mp-weixin build 通过）承担，本卡不重复 |
| 新阻断缺陷 | 无 P1；D-34（P2，飞轮核心目标缺失）与 D-36（P2，状态可查性）建议排期修复；D-33（P3）随 T31 真实接入联调 |

**发布建议**：M5 主链路（课程录入联想/匹配/映射、UGC 投稿 AI 初审/状态查询）验收通过，无 P1 阻断，可进入发布评审。**建议 ep-backend/ep-ai 在发布前或 M6 排期处理 D-34（别名沉淀飞轮）与 D-36（pass 结果透传）**——两者均属契约明示行为（架构 §14.2 / api.md §14.5），缺陷用例已 xfail 固化，修复后自动转 XPASS。


