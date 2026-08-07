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
