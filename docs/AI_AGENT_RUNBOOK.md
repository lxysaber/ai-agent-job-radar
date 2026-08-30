# 深圳 AI Agent 求职雷达：运行手册

本版本已固定画像为：`AI Agent开发`、`AI应用开发`、`AI Agent后端`；地点仅深圳；推送渠道为飞书。

## 1. BOSS：本机采集职位和 JD

安装 [boss-scripts](https://github.com/lx419394005-cloud/boss-scripts) 后，在它启动的独立 Chrome 中手动完成一次 BOSS 登录。该工具复用本机浏览器会话来抓职位列表和 JD 详情；本项目不保存 Cookie，也不绕过验证码。

```bash
npm install -g @loong243/boss-scripts
python3 scripts/collect_boss_agent_jobs.py
```

脚本按以下关键词、深圳城市运行：`AI Agent开发`、`AI应用开发`、`AI Agent后端`。它会将详情 JSON 增量导入 `data/jobs.json`，并生成 `reports/ai-agent-skills.md`。

## 2. 牛客：收集面经，再生成 Obsidian 笔记

OpenCLI 已有牛客职位、搜索和面经命令。示例：

```bash
opencli nowcoder search "AI Agent 面经 深圳" --type post --limit 20 -f json > data/inbox/interviews/nowcoder-ai-agent.json
python3 scripts/build_interview_notes.py --input data/inbox/interviews --out notes/interviews
```

也可以把公开帖子内容保存成 `.md` 或 `.txt` 放入 `data/inbox/interviews/`。建议前置写出“公司、岗位、轮次、链接”四项元数据。笔记只保留来源、考点、问题与复盘清单，生成后必须回看原帖核对。

若要直接写入 Obsidian 收件箱，可以把 `--out` 改为你的按日期目录，例如：

```bash
python3 scripts/build_interview_notes.py \
  --out /Users/shitou/WWWLLL/obsidian-workspace/obsidian-workspace/00-收件箱/2026-08-30
```

## 3. 飞书：每日新增岗位推送

为你的 GitHub 私有仓库添加 Action Secret：`FEISHU_WEBHOOK_URL`。日常工作流会在北京时间每天 **08:17** 执行稳定官网/ATS 信源、生成技能报告，并且只推送未推过的高匹配新增岗位。GitHub 的 schedule 支持 IANA 时区，仍可能在高负载时延迟数分钟。

本机 BOSS 登录态不应该放入 GitHub Actions。若希望 BOSS 同样每天更新，可将 `launchd/ai-agent-job-radar.plist.example` 复制为用户 LaunchAgent，替换项目绝对路径和 webhook，然后由你手动加载。它的默认时间是每天 19:17。

两条推送共同使用 `data/notify_state.json` 去重；如果云端和本机都运行，请将本机生成的数据同步到你的私有仓库，或只保留其中一条推送，避免两个状态文件分叉。

## 4. 日常产物

- `data/jobs.json`：标准化岗位库。
- `reports/ai-agent-skills.md`：JD 技能频次、证据句和学习顺序。
- `notes/interviews/` 或 Obsidian 收件箱：按公司、岗位、轮次整理的面经笔记。
- `data/notify_preview.md`：飞书实际会发送的新增预览。

外部 JD、帖子均为不可信文本；分析器不会执行其中的指令。不要把登录 Cookie、飞书 webhook、个人联系方式或简历原文提交到 Git。
