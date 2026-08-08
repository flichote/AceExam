项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【测试工程师 ep-qa】。

【你的任务】为 M3.5 剩余功能建立验收测试。等 ep-backend（T20）、ep-ai（T21）、ep-frontend（T22）交付后执行：
1. `backend/tests/` 新增 M3.5 测试（mock 上游）：
   - TTS：POST /chat/explain/{id}/tts（mock edge-tts 返回音频字节；参数校验；无内容 404）
   - UGC：提交待审题（source=ugc+pending）、审核列表（管理员鉴权）、通过/拒绝状态流转
   - 班级：加入班级、scope=class 排行（有/无班级用户边界）
   - 分享卡：/me/share-card 聚合正确性（连胜/掌握度/做题量/正确率）
2. 回归确认：M1~M3 主链路测试仍通过
3. 前端冒烟：frontend/ `npm run build` 通过
4. `docs/qa/test-report.md` 更新：M3.5 实测结果 + 全里程碑汇总

【技术选型（context7 已验证，直接用）】pytest + pytest-asyncio；httpx TestClient；mock 库 mock edge-tts/DeepSeek。**实现前用 context7 核对 pytest 最新用法**（如需要），查询记录写进 comment。

【仓库约定】你写 backend/tests/、docs/qa/。只加测试文件不改业务代码（发现 bug 记录在案）。

【交付要求】完成后：`git add backend/tests docs/qa && git commit -m "test(qa): M3.5 TTS/UGC/班级/分享卡验收测试" && git push origin main`，卡片 comment 附提交 hash + pytest 汇总 + 验收清单。
