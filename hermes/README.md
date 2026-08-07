# AceExam — Hermes 角色团队（可移植配置）

AceExam 的 6 个 Hermes 开发角色配置，**随私有仓库分发**，可在任意电脑一键重建。
规划在办公电脑完成，实际开发在个人电脑执行 —— 本目录就是两边的"角色交接文件"。

## 角色清单

| Profile | 角色 | 模型 | 职责 |
|---|---|---|---|
| `ep-arch` | 架构师/技术负责人 | flash | 系统设计、里程碑拆解、方案评审、ADR |
| `ep-ai` | AI 工程师（灵魂角色） | **pro** | RAG 讲解引擎、LLM flash/pro 分级、Pix2Text OCR、自适应选题、薄弱诊断 |
| `ep-backend` | 后端工程师 | **pro** | FastAPI 题库/计划/用户/错题本服务、OCR 集成 |
| `ep-frontend` | 前端工程师 | flash | uni-app 小程序/App/H5、KaTeX 渲染、mock 先行 |
| `ep-db` | 数据库工程师 | flash | PG16+pgvector 表设计、Alembic 迁移、种子数据 |
| `ep-qa` | 测试工程师 | flash | pytest 三层质量门禁、烟测、缺陷报告 |

运维角色复用 CCN 团队的 `devops`（不重复创建）。

## 个人电脑（Win11）前置条件

> 脚本已在 Windows（git-bash）实测通过，Win10/Win11 行为一致。个人电脑首次需要：

1. **安装 Git for Windows**（自带 git-bash，脚本用它跑）：https://git-scm.com/download/win
2. **安装 Hermes**（安装器会自动装 Python 环境）：`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
3. **配置 GitHub 认证**（私有仓库克隆需要）：HTTPS PAT 写入 `~/.git-credentials`，或安装 gh CLI 登录
4. **首次运行 hermes setup** 配置主 profile（DeepSeek API key + context7 MCP）
5. 确认 `hermes` 命令在 git-bash 的 PATH 中（安装后重开终端生效）

## 在个人电脑上恢复（3 步）

```bash
# 1. 克隆私有仓库（个人电脑需已配置 GitHub 认证）
git clone https://github.com/flichote/AceExam.git
cd AceExam

# 2. 前置：确保有一个已配置的源 profile（含 DeepSeek key + context7 MCP）
#    - 如已有 user001 / default 等配置好的 profile，直接下一步
#    - 若都没有：hermes setup 先配好主 profile，再：
#      hermes profile create user001 --clone-from default --no-alias

# 3. 一键重建全部角色（幂等，可重复跑）
bash hermes/setup-roles.sh
#    如需指定其他源 profile：bash hermes/setup-roles.sh --src 其他profile
```

> 💡 若 Hermes 装在非默认路径，先 `export HERMES_HOME=<你的hermes目录>` 再跑脚本（脚本已支持）。

## 验证

```bash
hermes profile list          # 6 个 ep-* 角色出现，Gateway 均 stopped（正常）
hermes profile show ep-ai    # Model: deepseek-v4-pro / .env: exists / SOUL.md: exists
hermes -p ep-ai chat -q "用一句话说明你的角色定位"   # 冒烟测试
```

## 目录结构

```
hermes/
├── README.md          # 本文件（恢复指南）
├── setup-roles.sh     # 一键重建脚本（幂等）
└── roles/
    ├── ep-arch/SOUL.md
    ├── ep-ai/SOUL.md
    ├── ep-backend/SOUL.md
    ├── ep-frontend/SOUL.md
    ├── ep-db/SOUL.md
    └── ep-qa/SOUL.md
```

## 注意事项

- **密钥不入库**：脚本克隆自源 profile 继承 `.env`（DeepSeek key 等），仓库里没有明文密钥
- **Gateway 保持 stopped**：角色由 kanban 调度器按需拉起，不要手动常驻 gateway（避免微信 token 冲突）
- **改角色配置**：改 `roles/<name>/SOUL.md` 后重新跑 `setup-roles.sh` 即可同步
- **kanban 板**：开发时 `hermes kanban create aceexam` 建专用板，任务图见 PRD 附录 A
