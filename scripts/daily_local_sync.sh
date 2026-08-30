#!/usr/bin/env bash
# 本机每日同步：BOSS 登录态职位 + 公共稳定信源 + 技能报告 + 飞书新增推送。
# 使用前：安装 boss-scripts，并设置 FEISHU_WEBHOOK_URL。不要把该 URL 写入文件或提交 Git。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/collect_boss_agent_jobs.py
python3 scripts/sync_plan.py fast
python3 scripts/analyze_agent_jds.py
python3 scripts/send_notify.py --min-focus 110 --min-match 65
