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
