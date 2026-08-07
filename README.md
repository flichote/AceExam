# AceExam — 大学生的 AI 备考教练

> **定位一句话**：帮助在校大学生顺利通过每一科考试的 AI 备考教练 —— 不是又一个题库 App，而是"诊断薄弱点 → 制定通关计划 → 精准刷题 → AI 讲解 → 考前突击"的完整闭环。

## 与兄弟项目对比

| | CCN (Continuum-Care-Network) | RehabFlow | **AceExam（本项目）** |
|---|---|---|---|
| 核心场景 | 院外延续康护随访 | 院内康复调度台 | **大学生期末备考通关** |
| 核心动作 | 随访计划执行、健康数据采集 | 排课冲突检测、康复流程流转 | **刷题、AI 讲解、薄弱诊断、备考计划** |
| 关键角色 | 患者/医生/护士 | 治疗师/患者/主任 | **在校大学生** |
| 差异化能力 | 院外关怀闭环 | 冲突检测 + 状态机 | **RAG 教材答疑 + 自适应选题 + 拍照录题** |
| 主色 | teal 蓝绿 | indigo 靛蓝 | **amber 活力橙（橙=成功上岸）** |
| 仓库可见性 | public | public | **private（创业项目）** |

## 产品定位

- **目标用户**：在校大学生（期末备考场景，高挂科率科目痛点最深）
- **切入策略**：先公共科目（高数、英语），打磨"科目模板"后逐步扩展到线代、概率论、大物、专业课
- **核心闭环**：诊断 → 规划 → 练习 → 讲解 → 突击 → 复盘
- **商业模式**：Freemium —— 基础刷题免费（获客），AI 教练/深度解析/定制计划订阅（变现）

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | **uni-app**（Vue3 + Vite + TS） | 一套代码 → 微信小程序 / App / H5，小程序先行获客 |
| 后端 | **FastAPI** | 题库/计划/用户服务、OCR 集成 |
| 数据库 | **PostgreSQL 16 + pgvector** | 题库、知识点图谱、教材向量库一体 |
| AI 层 | **DeepSeek**（flash 快答 / pro 深度讲解）+ Embedding API | RAG 教材答疑，flash/pro 分级控成本 |
| OCR | **Pix2Text**（自部署 ONNX） | 拍照录题：文字+公式混合识别 → Markdown/LaTeX |
| 公式渲染 | KaTeX（uni-app 适配组件） | 题库/解析中 LaTeX 公式显示 |
| 部署 | Docker Compose | 复用 CCN/RehabFlow 部署经验 |

## 快速开始

```bash
# 克隆（私有仓库，需 GitHub 认证）
git clone https://github.com/flichote/AceExam.git
cd AceExam
# 文档先行 —— 当前阶段仅文档骨架，业务代码见里程碑规划
```

## 文档索引

- [产品需求 PRD](docs/PRD.md) — 需求的唯一事实来源
- [设计系统](docs/design/design-system.md) — 视觉 token 与设计规范
- [页面地图](docs/design/pages.md) — 站点地图与页面优先级
- [组件规范](docs/design/components.md) — 页面级组件
- [交互流程](docs/design/flows.md) — 核心流程与验收点
- [运维文档](docs/ops/README.md) — 部署/监控（规划中）

## 里程碑

- **M1 地基**：文档定稿、GitHub 私有仓库、数据库表结构（题库/图谱/向量）、AI 服务骨架（DeepSeek 接入 + Pix2Text 部署）、uni-app 脚手架
- **M2 核心闭环**：智能刷题 + AI 讲解（RAG）+ 拍照录题 + 薄弱诊断 + 备考计划（MVP 五件套）
- **M3 体验与增长**：知识点图谱可视化、考前突击模式、打卡连胜、数据看板、排行榜/UGC 共建、挂科预警

## 团队角色（规划中，待定）

6+1 角色：`ep-arch` 架构师 / `ep-ai` AI 工程师（灵魂角色，pro）/ `ep-backend` 后端（pro）/ `ep-frontend` 前端 / `ep-db` 数据库 / `ep-qa` 测试；运维复用 CCN devops。详见 PRD 附录。
