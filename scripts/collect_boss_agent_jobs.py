#!/usr/bin/env python3
"""在本机、已登录的 Chrome 会话中采集深圳 AI Agent 岗位，再导入雷达。

此脚本只调用用户主动安装的 boss-scripts。不会导出 Cookie，也不会尝试绕过验证。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ("AI Agent开发", "AI应用开发", "AI Agent后端")


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")


def _rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("data", "jobs", "list", "items", "results"):
            if isinstance(data.get(key), list):
                return [row for row in data[key] if isinstance(row, dict)]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="本机抓取深圳 AI Agent 岗位并导入 Job Radar。")
    parser.add_argument("--city", default="深圳")
    parser.add_argument("--query", action="append", dest="queries", help="可重复；默认使用 3 个 AI Agent 关键词")
    parser.add_argument("--count", type=int, default=30, help="每个关键词的目标职位数")
    parser.add_argument("--delay", type=int, default=8000, help="每条详情的最小间隔（毫秒）")
    parser.add_argument("--output-dir", default=str(ROOT / "data" / "inbox" / "boss"))
    args = parser.parse_args()
    if not shutil.which("boss-scripts"):
        raise SystemExit("未找到 boss-scripts；请先按项目文档安装并在独立 Chrome 中登录 BOSS 直聘。")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    exports = []
    for query in args.queries or QUERIES:
        path = output_dir / f"boss_{_slug(query)}.json"
        subprocess.run([
            "boss-scripts", "list", "--query", query, "--city", args.city,
            "--count", str(args.count), "--slow", "--output", str(path),
        ], check=True)
        subprocess.run([
            "boss-scripts", "detail", "--input", str(path), "--output", str(path),
            "--delay", str(args.delay),
        ], check=True)
        exports.append(path)

    merged = []
    for export in exports:
        merged.extend(_rows(export))
    combined = output_dir / "boss_ai_agent_shenzhen.json"
    combined.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "import_boss_export.py"), "--input", str(combined)], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze_agent_jds.py")], check=True)
    print(f"本机 BOSS 同步完成：{combined}")


if __name__ == "__main__":
    main()
