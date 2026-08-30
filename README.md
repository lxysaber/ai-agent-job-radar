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
npm install -g @loong243/boss-scripts
python3 scripts/collect_boss_agent_jobs.py
```

首次运行时请在工具启动的独立 Chrome 中自行登录 BOSS。脚本只复用该本机会话抓取列表和详情，不保存 Cookie、不绕过验证码。

## 牛客面经

```bash
opencli nowcoder search "AI Agent 面经 深圳" --type post --limit 20 -f json > data/inbox/interviews/nowcoder-ai-agent.json
python3 scripts/build_interview_notes.py --input data/inbox/interviews --out notes/interviews
```

可以把 `--out` 指向 Obsidian 的按日期收件箱目录。生成笔记只保留原帖来源、提取的考点、问题和复盘清单；请人工回看原帖确认。

## 飞书定时推送

将本目录推送至你自己的**私有 GitHub 仓库**，并设置：

- GitHub Actions Secret：`FEISHU_WEBHOOK_URL`
- 可选 GitHub Actions Variable：`WORKBENCH_URL`

`FEISHU_WEBHOOK_URL` 不要发到聊天、写入代码或提交 Git。工作流会在发送成功后更新 `data/notify_state.json`，以避免重复推送。

完整的部署、BOSS 本机定时、牛客收集和 Obsidian 输出说明见 [AI Agent 运行手册](docs/AI_AGENT_RUNBOOK.md)。

## 验证

```bash
python3 scripts/smoke_test.py
```

外部 JD 和讨论帖都被当作不可信文本处理。分析器不会执行帖子中的指令；模型分析应只在结构化、审核后的文本上进行。
