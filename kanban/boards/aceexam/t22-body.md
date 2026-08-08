项目：AceExam（大学生的 AI 备考教练，期末通关闭环）。公开仓库，主干 main。你被分派为【前端工程师 ep-frontend】。

【你的任务】实现 M3.5 剩余功能页面。参照 ep-arch 的 docs/api.md 契约（若已存在）：
1. **TTS 语音播放**（AI 讲解页集成）：
   - 讲解完成后显示"🔊 听讲解"按钮 → 请求 TTS 音频 → 音频组件播放
   - 加载/错误状态处理（生成失败提示重试）
2. **UGC 题目提交入口**（拍照录题页扩展）：
   - 手动录入模式已有 → 增加"提交为共享题"选项（或独立入口）
   - 提交后状态提示（待审核）
3. **班级排行榜**（排行榜页扩展）：
   - 维度切换增加"班级"（scope=class）
   - 加入班级入口（输入班级名，POST /me/class）
4. **成绩单海报分享**（我的页新增）：
   - 分享卡数据（GET /me/share-card）→ canvas 生成海报（连胜/掌握度/做题量/本周正确率 + 品牌视觉 amber 橙）
   - 保存/分享：H5 下载图片 / 小程序保存相册（平台判断）
5. mock 降级保留：API 未就绪时 mock 数据顶上

【技术选型（context7 已验证，直接用）】uni-app Vue3+Vite+TS；canvas 海报生成（uni-app 支持，注意小程序 canvas 2d 接口差异）；音频组件 `<audio>` 或 uni.createInnerAudioContext。**实现前用 context7 核对 uni-app 最新 API**（`context7 query docs uni-app`），查询记录写进 comment。

【仓库约定】你写 frontend/。ep-backend/ep-ai 在 backend/，不要动。mock 数据放 frontend/src/mock/ 作降级。

【交付要求】完成后：`git add frontend/ && git commit -m "feat(frontend): M3.5 TTS播放/UGC提交/班级排行/海报分享" && git push origin main`，卡片 comment 附提交 hash + 构建输出 + context7 查询记录。
