#!/usr/bin/env python3
"""从已入库 JD 生成深圳 AI Agent 开发岗位的技能与学习报告。"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from job_radar.agent_analysis import report_markdown  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 AI Agent / AI 应用开发 JD 技能报告。")
    parser.add_argument("--input", default=os.path.join(ROOT, "data", "jobs.json"))
    parser.add_argument("--out", default=os.path.join(ROOT, "reports", "ai-agent-skills.md"))
    parser.add_argument("--city", default="深圳")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        jobs = json.load(f)
    if not isinstance(jobs, list):
        raise SystemExit("输入必须是岗位对象数组。")
    report = report_markdown(jobs, args.city)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"已分析 {len(jobs)} 条岗位 → {args.out}")


if __name__ == "__main__":
    main()
