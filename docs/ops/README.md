# AceExam 运维文档（规划中）

> 部署/监控文档占位。M1 阶段补充，当前为规划状态。

## 规划要点

- **部署**：Docker Compose（复用 CCN/RehabFlow 经验），单机起步（4C8G）
- **服务**：FastAPI 后端 + Pix2Text OCR 服务（ONNX 本地）+ PostgreSQL 16（pgvector）
- **AI 成本监控**：DeepSeek flash/pro 分级调用，月度 token 用量统计
- **配置管理**：环境变量走 `.env`（不入库），`.gitignore` 已覆盖

## TBD

- [ ] docker-compose.yml 服务编排
- [ ] Pix2Text 镜像化（ONNX 模型体积评估）
- [ ] 日志与监控方案
- [ ] 备份策略（题库/用户数据）
