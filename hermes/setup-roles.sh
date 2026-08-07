#!/usr/bin/env bash
# ============================================================
# AceExam — Hermes 角色团队一键重建脚本
# 用途：在任意电脑（个人电脑/新环境）恢复 AceExam 的 6 个
#       Hermes 开发角色（ep-arch / ep-ai / ep-backend /
#       ep-frontend / ep-db / ep-qa）
# 用法：bash hermes/setup-roles.sh
# 前置：hermes 已安装；存在一个已配置的源 profile
#       （默认 user001，含 DeepSeek key + context7 MCP），
#       可用 --src 覆盖：bash hermes/setup-roles.sh --src 其他profile
# 幂等：重复运行安全（已存在的角色跳过创建，仅刷新 SOUL/描述）
# ============================================================
set -euo pipefail

# ---- 参数 ----
SRC="user001"
if [[ "${1:-}" == "--src" ]]; then
  SRC="${2:-user001}"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROLES_DIR="$SCRIPT_DIR/roles"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/AppData/Local/hermes}"
PROFILES_DIR="$HERMES_HOME_DIR/profiles"

# 角色清单：name|模型|描述
ROLES=(
  "ep-arch|deepseek-v4-flash|AceExam 架构师/技术负责人：系统设计、里程碑拆解（M1地基→M2 MVP五件套→M3增长）、RAG管线与自适应算法方案评审、ADR决策、任务分解与跨角色协调"
  "ep-ai|deepseek-v4-pro|AceExam AI工程师（灵魂角色）：RAG讲解引擎（教材向量化+检索+溯源）、DeepSeek flash/pro分级路由、Pix2Text OCR服务、自适应选题算法、薄弱点诊断引擎"
  "ep-backend|deepseek-v4-pro|AceExam 后端工程师：FastAPI 题库/计划/用户/错题本服务、OCR集成、作答判定、pytest"
  "ep-frontend|deepseek-v4-flash|AceExam 前端工程师：uni-app（Vue3+TS）小程序/App/H5，四Tab+拍照录题+AI讲解页，KaTeX公式渲染，mock先行"
  "ep-db|deepseek-v4-flash|AceExam 数据库工程师：PostgreSQL16+pgvector 表设计（题库/知识点图谱/教材向量）、Alembic迁移、种子数据"
  "ep-qa|deepseek-v4-flash|AceExam 测试工程师：pytest三层质量门禁（单元+OCR精度+RAG质量评估）、状态机流转测试、全链路烟测、缺陷报告"
)

echo ">>> 源 profile: $SRC"
echo ">>> profiles 目录: $PROFILES_DIR"

# ---- 检查源 profile ----
if ! hermes profile show "$SRC" >/dev/null 2>&1; then
  echo "❌ 源 profile '$SRC' 不存在或不可用。请先创建/配置它（含 DeepSeek key + context7 MCP）。"
  exit 1
fi

# ---- 创建角色 ----
for entry in "${ROLES[@]}"; do
  IFS='|' read -r name model desc <<< "$entry"

  echo ""
  echo "=== $name ==="

  # 1. 创建（已存在则跳过）
  if hermes profile show "$name" >/dev/null 2>&1; then
    echo "  已存在，跳过创建"
  else
    hermes profile create "$name" --clone-from "$SRC" --no-alias
  fi

  # 2. 覆盖 SOUL.md
  SOUL_SRC="$ROLES_DIR/$name/SOUL.md"
  SOUL_DST="$PROFILES_DIR/$name/SOUL.md"
  if [[ -f "$SOUL_SRC" ]]; then
    cp "$SOUL_SRC" "$SOUL_DST"
    echo "  SOUL.md 已写入"
  else
    echo "  ⚠️ 未找到 $SOUL_SRC，跳过 SOUL.md"
  fi

  # 3. 模型
  hermes -p "$name" config set model.default "$model" >/dev/null
  echo "  模型: $model"

  # 4. 角色描述
  hermes profile describe "$name" --text "$desc" >/dev/null
  echo "  描述已设置"
done

echo ""
echo "✅ 全部角色就绪。验证：hermes profile list"
echo "（角色 Gateway 应为 stopped —— 正常状态，由 kanban 调度器按需拉起）"
