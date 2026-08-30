# 深圳 AI Agent 求职雷达

面向以下目标岗位的个人情报工作流：

- AI Agent 开发工程师
- AI 应用开发工程师
- AI Agent 后端开发工程师

岗位地点严格偏向 **深圳**，飞书只推送未推过的高匹配新增职位。

## 已包含的三条链路

1. **JD → 技能与学习计划**：官网/ATS 职位和本机 BOSS 详情进入统一岗位库；`scripts/analyze_agent_jds.py` 会生成带 JD 证据句的技能雷达。
2. **讨论帖 → 面经笔记**：将 OpenCLI 或浏览器收集的牛客公开面经放入收集箱，`scripts/build_interview_notes.py` 会按公司、岗位、轮次生成 Markdown 笔记。
3. **新增 JD → 飞书**：GitHub Actions 每日北京时间 08:17 抓取稳定公开信源；本机 BOSS 登录态可在每天 19:17 通过 launchd 模板补抓并推送。

## 快速开始

```bash
python3 -m pip install -r requirements.txt
python3 scripts/sync_plan.py fast
python3 scripts/analyze_agent_jds.py
python3 scripts/notify_preview.py --min-focus 110 --min-match 65
```

上述命令依赖的 Playwright 仅用于牛客等 SPA 慢源；日常官网/ATS 快扫不需要它。

## BOSS 职位详情

```bash
# 暂用 GitHub 主分支：npm 已发布包曾遗漏 shared/ 目录，导致模块找不到。
npm install -g "git+https://github.com/lx419394005-cloud/boss-scripts.git#main"
python3 scripts/collect_boss_agent_jobs.py
```

首次运行时请在工具启动的独立 Chrome 中自行登录 BOSS。脚本只复用该本机会话抓取列表和详情，不保存 Cookie、不绕过验证码。

## 牛客面经

```bash
# 仅首次：在项目内隔离安装网页发现依赖。
python3 -m venv .venv
.venv/bin/pip install playwright
.venv/bin/playwright install chromium

# 发现公开的候选帖子链接；随后人工打开原帖核验并保存正文。
.venv/bin/python scripts/nowcoder_discover.py --include-discussion --limit-per-keyword 6 --pages 1 --replace
python3 scripts/build_interview_notes.py --input data/inbox/interviews --out notes/interviews
```

`nowcoder_discover.py` 只收集候选链接，不绕过登录或反爬。将核验后的公开帖子正文保存为 `.md`、`.txt` 或 JSON 放入 `data/inbox/interviews/`，再生成笔记。可以把 `--out` 指向 Obsidian 的按日期收件箱目录。生成笔记只保留原帖来源、提取的考点、问题和复盘清单；请人工回看原帖确认。

已配置的本机面经任务可在工作日运行以下命令，自动筛选公开可见、深圳且 AI Agent/应用相关的候选，写入当天的 Obsidian 收件箱，并以 URL 去重：

```bash
.venv/bin/python scripts/daily_nowcoder_interviews.py \
  --obsidian-root /path/to/Obsidian/00-收件箱 \
  --max-records 4
```

它不读取 Cookie、不绕过登录或验证码；原帖正文仅保存在本机的已忽略目录，自动生成的笔记仍须抽查原帖。

## 飞书定时推送

将本目录推送至你的 GitHub 仓库，并设置：

- GitHub Actions Secret：`FEISHU_WEBHOOK_URL`
- 可选 GitHub Actions Variable：`WORKBENCH_URL`

`FEISHU_WEBHOOK_URL` 不要发到聊天、写入代码或提交 Git。工作流会在发送成功后更新 `data/notify_state.json`，以避免重复推送。

完整的部署、BOSS 本机定时、牛客收集和 Obsidian 输出说明见 [AI Agent 运行手册](docs/AI_AGENT_RUNBOOK.md)。

## 验证

```bash
python3 scripts/smoke_test.py
```

外部 JD 和讨论帖都被当作不可信文本处理。分析器不会执行帖子中的指令；模型分析应只在结构化、审核后的文本上进行。
