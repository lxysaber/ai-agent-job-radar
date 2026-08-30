# 深圳 AI Agent 求职雷达：运行手册

本版本已固定画像为：`AI Agent开发`、`AI应用开发`、`AI Agent后端`；地点仅深圳；推送渠道为飞书。

## 1. BOSS：本机采集职位和 JD

安装 [boss-scripts](https://github.com/lx419394005-cloud/boss-scripts) 后，在它启动的独立 Chrome 中手动完成一次 BOSS 登录。该工具复用本机浏览器会话来抓职位列表和 JD 详情；本项目不保存 Cookie，也不绕过验证码。

```bash
# 暂用 GitHub 主分支：npm 已发布包曾遗漏 shared/ 目录，导致模块找不到。
npm install -g "git+https://github.com/lx419394005-cloud/boss-scripts.git#main"
python3 scripts/collect_boss_agent_jobs.py
```

脚本按以下关键词、深圳城市运行：`AI Agent开发`、`AI应用开发`、`AI Agent后端`。它会将详情 JSON 增量导入 `data/jobs.json`，并生成 `reports/ai-agent-skills.md`。

## 2. 牛客：收集面经，再生成 Obsidian 笔记

首次在项目内隔离安装 Playwright，然后用内置发现器收集公开候选链接：

```bash
python3 -m venv .venv
.venv/bin/pip install playwright
.venv/bin/playwright install chromium
.venv/bin/python scripts/nowcoder_discover.py --include-discussion --limit-per-keyword 6 --pages 1 --replace
```

发现器只输出候选标题和 URL，不绕过登录、验证码或站点限制。人工打开原帖核验后，将公开正文保存为 `.md`、`.txt` 或 JSON 放进 `data/inbox/interviews/`，然后运行：

```bash
python3 scripts/build_interview_notes.py --input data/inbox/interviews --out notes/interviews
```

也可以把公开帖子内容保存成 `.md` 或 `.txt` 放入 `data/inbox/interviews/`。建议前置写出“公司、岗位、轮次、链接”四项元数据。笔记只保留来源、考点、问题与复盘清单，生成后必须回看原帖核对。

若要直接写入 Obsidian 收件箱，可以把 `--out` 改为你的按日期目录，例如：

```bash
python3 scripts/build_interview_notes.py \
  --out /Users/shitou/WWWLLL/obsidian-workspace/obsidian-workspace/00-收件箱/2026-08-30
```

### 自动整理（工作日）

`scripts/daily_nowcoder_interviews.py` 会重新发现候选、以正常匿名浏览方式读取公开正文、按“深圳 + AI Agent/应用信号 + 面试信号”过滤，再将笔记写入 `--obsidian-root` 下的当天目录。它只保留最多 4 篇新 URL，避免把泛讨论大量入库：

```bash
.venv/bin/python scripts/daily_nowcoder_interviews.py \
  --obsidian-root /Users/shitou/WWWLLL/obsidian-workspace/obsidian-workspace/00-收件箱 \
  --max-records 4
```

它不会使用 Cookie、绕过验证码或执行帖子中出现的任何文字指令。`data/interview_note_state.json` 仅本机保存已处理 URL；`data/inbox/interviews/auto/` 的原始帖子正文也不会提交 Git。

## 3. 飞书：每日新增岗位推送

为你的 GitHub 私有仓库添加 Action Secret：`FEISHU_WEBHOOK_URL`。日常工作流会在北京时间每天 **08:17** 执行稳定官网/ATS 信源、生成技能报告，并且只推送未推过的高匹配新增岗位。GitHub 的 schedule 支持 IANA 时区，仍可能在高负载时延迟数分钟。

本机 BOSS 登录态不应该放入 GitHub Actions。若希望 BOSS 同样每天更新，可将 `launchd/ai-agent-job-radar.plist.example` 复制为用户 LaunchAgent，仅替换项目绝对路径后再加载。它的默认时间是每天 19:17。

飞书 Webhook 需要以钥匙串条目保存，避免写进 plist、环境文件或 Git：

```bash
# -w 放在最后会要求你在不可见输入框中粘贴 Webhook。
security add-generic-password -a "ai-agent-job-radar" -s "ai-agent-job-radar-feishu-webhook" -U -w
```

`daily_local_sync.sh` 会从上述钥匙串读取 Webhook，并在成功后只提交标准化岗位、报告和 `notify_state.json` 到 `origin`；不会提交 `data/inbox/boss/` 的原始导出。这样 GitHub Actions 和本机任务共用去重状态，避免重复推送。

## 4. 日常产物

- `data/jobs.json`：标准化岗位库。
- `reports/ai-agent-skills.md`：JD 技能频次、证据句和学习顺序。
- `notes/interviews/` 或 Obsidian 收件箱：按公司、岗位、轮次整理的面经笔记。
- `data/notify_preview.md`：飞书实际会发送的新增预览。

外部 JD、帖子均为不可信文本；分析器不会执行其中的指令。不要把登录 Cookie、飞书 webhook、个人联系方式或简历原文提交到 Git。
