# AceExam 组件规范

> 页面级组件规范，先登记再实现。命名遵循 uni-app Vue3 单文件组件约定。

## 全局布局组件

| 组件 | 职责 | 关键交互 |
|---|---|---|
| `AppTabBar` | 4+1 TabBar（中央拍照按钮凸起） | 切换 Tab；中央按钮开 modal |
| `AppNavBar` | 页面导航栏（返回/标题/右操作） | 返回堆栈；支持自定义 slot |
| `ExamStatusBar` | 小程序状态栏适配容器 | 主色系背景 |

## 核心页组件（P0，MVP 必做）

| 组件 | 职责 | 关键交互 |
|---|---|---|
| `QuestionCard` | 题目展示（题干/公式/选项/填空/简答） | KaTeX 渲染公式；选项点击选中；填空/简答输入 |
| `AnswerFeedback` | 作答结果反馈（对/错 + 解析入口） | 200ms 缩放动效；"AI 讲解"按钮 |
| `AiExplainCard` | AI 讲解 step-by-step 卡片 | 分步折叠；流式打字指示 |
| `CitationBlock` | 教材引用块（RAG 溯源） | 显示教材名+章节+原文片段 |
| `PhotoCapture` | 拍照/相册（并入 pages/ocr/index，M3 再拆裁剪组件） | 调起相机 |
| `OcrResultEditor` | OCR 识别结果确认/编辑 | Markdown/LaTeX 原文可编辑 + 结构化表单（题型/题干/选项/答案/解析） |
| `DiagnoseReport` | 摸底诊断报告 | 薄弱 Top5 列表 + 建议 + 优势/未开始 + 下一步 |
| `KnowledgeMap` | 薄弱知识点地图（P1 简化：列表） | 状态分组排序；点击 → 对应练习 |
| `DailyPlanCard` | 今日任务卡片 | 倒计时 + 每日任务进度 + 打卡按钮（幂等）；无计划引导创建 |

## 通用组件

| 组件 | 职责 |
|---|---|
| `SubjectPill` | 科目/知识点标签 |
| `ProgressRing` | 掌握度进度环（400ms ease-out） |
| `StreakBadge` | 连胜徽章（🔥 N 天，M3） |
| `EmptyState` | 空状态占位（无错题/无任务） |
| `ErrorBoundary` | 错误/边界状态（加载失败重试） |
| `LoadingSkeleton` | 骨架屏（刷题页/诊断页） |

## M3 新增组件（2026-08-08 登记）

| 组件 | 职责 | 关键交互 |
|---|---|---|
| `KnowledgeGraphTree` | 知识点图谱自绘 canvas 树（三级：章→节→知识点） | 节点状态着色；父节点展开/收起；点击节点 emit select → 题单/讲解入口 |
| `TrendLineChart` | 近 N 天做题量 + 正确率趋势图（自绘 canvas） | 柱状 = 做题量、折线 = 正确率（null 桶跳过） |
| `WarningList` | 挂科预警风险列表 | 整体风险条（高/中/低）+ 条目理由/建议/元信息；点击条目 emit select |
| `StreakBadge` | 连胜徽章 | 🔥 N 天；variant: primary（深色底）/ light（浅色底） |

## M3.5 新增组件（2026-08-08 登记，T22）

| 组件 | 职责 | 关键交互 |
|---|---|---|
| `TtsPlayer` | AI 讲解语音播放（docs/api.md §12.1/§12.2） | 「🔊 听讲解」→ 请求 TTS → 下载音频（带 Authorization）→ createInnerAudioContext 播放；状态机 idle/loading/playing/paused/error（生成失败提示重试） |
| `SharePoster` | 成绩单海报 canvas 生成（§12.8，D12） | 343×609 画布绘制（amber 品牌视觉），导出 uni.canvasToTempFilePath（destWidth 750）；无数据边界展示「开始第一题」引导；暴露 exportImage() |

## 组件规范约定

1. **props 用 TypeScript 接口定义**，default 值必填
2. **公式一律走 KaTeX 适配组件**，禁止图片代替公式
3. **状态色只用设计系统 token**，禁止硬编码色值
4. 组件先在本文件登记，再实现；新增组件回填本表

## 错误/边界状态

| 场景 | 表现 |
|---|---|
| 网络失败 | `ErrorBoundary` 重试按钮 |
| OCR 识别为空 | 引导重拍 / 手动录入 |
| RAG 无引用命中 | 兜底：纯模型讲解 + "教材未覆盖"提示 |
| 题目加载中 | `LoadingSkeleton` |
