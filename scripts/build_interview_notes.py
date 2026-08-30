#!/usr/bin/env python3
"""把已收集的牛客/公开讨论帖整理为可复习的面经笔记。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from job_radar.interview_notes import load_records, write_notes  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 AI Agent 岗位面经 Markdown 笔记。")
    parser.add_argument("--input", default=os.path.join(ROOT, "data", "inbox", "interviews"))
    parser.add_argument("--out", default=os.path.join(ROOT, "notes", "interviews"))
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        raise SystemExit(f"收集箱不存在：{input_dir}")
    records = load_records(input_dir)
    written = write_notes(records, Path(args.out))
    print(f"已整理 {len(written)} 篇面经笔记 → {args.out}")


if __name__ == "__main__":
    main()
