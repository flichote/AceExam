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
| `QuestionCard` | 题目展示（题干/公式/选项） | KaTeX 渲染公式；选项点击选中 |
| `AnswerFeedback` | 作答结果反馈（对/错 + 解析入口） | 200ms 缩放动效；"AI 讲解"按钮 |
| `AiExplainCard` | AI 讲解 step-by-step 卡片 | 分步折叠；追问输入框 |
| `CitationBlock` | 教材引用块（RAG 溯源） | 显示教材名+章节+原文片段 |
| `PhotoCapture` | 拍照/相册 + 裁剪 | 调起相机；裁剪框 |
| `OcrResultEditor` | OCR 识别结果确认/编辑 | Markdown/LaTeX 预览；可编辑 |
| `DiagnoseReport` | 摸底诊断报告 | 薄弱 Top5 列表 + 建议 |
| `KnowledgeMap` | 薄弱知识点图谱 | 节点点击 → 对应题/讲解 |
| `DailyPlanCard` | 今日任务卡片 | 打卡按钮；完成态打勾 |

## 通用组件

| 组件 | 职责 |
|---|---|
| `SubjectPill` | 科目/知识点标签 |
| `ProgressRing` | 掌握度进度环（400ms ease-out） |
| `StreakBadge` | 连胜徽章 |
| `EmptyState` | 空状态占位（无错题/无任务） |
| `ErrorBoundary` | 错误/边界状态（加载失败重试） |
| `LoadingSkeleton` | 骨架屏（刷题页/诊断页） |

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
