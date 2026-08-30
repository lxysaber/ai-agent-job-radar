#!/usr/bin/env bash
# 本机每日同步：BOSS 登录态职位 + 公共稳定信源 + 技能报告 + 飞书新增推送。
# 飞书 Webhook 优先读环境变量；否则仅从本机钥匙串读取，绝不写入 Git。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
KEYCHAIN_ACCOUNT="ai-agent-job-radar"
KEYCHAIN_SERVICE="ai-agent-job-radar-feishu-webhook"

if [[ -z "${FEISHU_WEBHOOK_URL:-}" ]]; then
  if ! FEISHU_WEBHOOK_URL="$(/usr/bin/security find-generic-password -a "$KEYCHAIN_ACCOUNT" -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)"; then
    echo "未找到飞书 Webhook：请将其保存到 macOS 钥匙串服务 ${KEYCHAIN_SERVICE:-ai-agent-job-radar-feishu-webhook}。" >&2
    exit 1
  fi
  export FEISHU_WEBHOOK_URL
fi

# 本机和 GitHub Actions 共用 data/notify_state.json；每次执行前先取回云端状态。
SYNC_TO_ORIGIN=0
if git remote get-url origin >/dev/null 2>&1; then
  git pull --rebase
  SYNC_TO_ORIGIN=1
fi

python3 scripts/collect_boss_agent_jobs.py
python3 scripts/sync_plan.py fast
python3 scripts/analyze_agent_jds.py
python3 scripts/send_notify.py --min-focus 110 --min-match 65

# 原始 BOSS 导出可能含不适合公开的信息，只同步标准化岗位、报告和去重状态。
if [[ "$SYNC_TO_ORIGIN" -eq 1 ]]; then
  git add -- data/jobs.json data/jobs_archive.json data/jobs.html data/notify_preview.md data/notify_state.json reports/
  if ! git diff --cached --quiet; then
    git commit -m "chore(data): local BOSS sync $(date -u +%F)"
    git push
  fi
fi
