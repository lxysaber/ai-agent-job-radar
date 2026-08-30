#!/usr/bin/env python3
"""每日发现并整理公开牛客 AI Agent 面经。

只访问无需登录即可查看的页面；不读取 Cookie、不绕过验证码或反爬机制。
外部页面文本仅作为待分析数据，绝不执行其中任何指令。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from job_radar.interview_notes import InterviewRecord, write_notes  # noqa: E402
from scripts.nowcoder_discover import discover  # noqa: E402


INTERVIEW_KEYWORDS = (
    "深圳 AI Agent 面经",
    "深圳 AI应用开发 面经",
    "深圳 大模型应用开发 面经",
    "深圳 RAG 面经",
    "深圳 MCP 面经",
)
STATE_PATH = ROOT / "data" / "interview_note_state.json"
RAW_ROOT = ROOT / "data" / "inbox" / "interviews" / "auto"

AGENT_SIGNAL = re.compile(r"ai.?agent|\bagent\b|智能体|ai.?应用|大模型应用|llm|rag|检索增强|mcp|tool calling|function calling", re.I)
INTERVIEW_SIGNAL = re.compile(r"面经|一面|二面|三面|终面|笔试|机考|技术面", re.I)
SHENZHEN_SIGNAL = re.compile(r"深圳|base\s*深圳", re.I)
NOISE_SIGNAL = re.compile(r"求问|求助|求拷打|简历求|offer比较|offer帮选|去哪个|怎么选|投递记录", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {value for value in raw.get("processed_urls", []) if isinstance(value, str)}


def save_state(path: Path, urls: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "processed_urls": sorted(urls),
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rank_candidate(row: dict[str, Any]) -> tuple[int, str]:
    title = re.sub(r"\s+", " ", str(row.get("title") or "")).strip()
    score = int(row.get("quality") or 0)
    if AGENT_SIGNAL.search(title):
        score += 8
    if INTERVIEW_SIGNAL.search(title):
        score += 6
    if SHENZHEN_SIGNAL.search(title):
        score += 4
    if NOISE_SIGNAL.search(title):
        score -= 12
    return score, title


def trim_post(title: str, body: str) -> str:
    text = re.sub(r"\r", "", body)
    start = text.find(title) if title else -1
    if start >= 0:
        text = text[start:]
    end_positions = [text.find(marker) for marker in ("全部评论", "相关推荐", "提到的真题", "全站热榜")]
    ends = [position for position in end_positions if position > 0]
    if ends:
        text = text[:min(ends)]
    text = PHONE.sub("[手机号已脱敏]", text)
    text = EMAIL.sub("[邮箱已脱敏]", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:12000]


def fetch_public_records(rows: list[dict[str, Any]], delay_ms: int, verbose: bool = False) -> list[InterviewRecord]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("缺少 Playwright。请使用 .venv/bin/pip install playwright 并安装 Chromium。") from exc

    records: list[InterviewRecord] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(15000)
        for row in rows:
            url = str(row.get("url") or "").strip()
            if not url:
                continue
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(delay_ms)
                headings = page.locator("h1").all_inner_texts()
                title = next((value.strip() for value in headings if value.strip()), str(row.get("title") or "未命名面经"))
                content = trim_post(title, page.locator("body").inner_text())
            except Exception as exc:
                print(f"跳过无法读取的页面：{url} ({type(exc).__name__})")
                continue

            # 严格保留深圳 + AI Agent 方向 + 面试问题三种信号，防止普通讨论帖入库。
            evidence = f"{title}\n{content}"
            signals = {
                "agent": bool(AGENT_SIGNAL.search(evidence)),
                "interview": bool(INTERVIEW_SIGNAL.search(evidence)),
                "shenzhen": bool(SHENZHEN_SIGNAL.search(evidence)),
            }
            if verbose:
                print(f"候选诊断：len={len(content)} signals={signals} title={title}")
            if len(content) < 300 or not all(signals.values()):
                print(f"跳过低相关候选：{title}")
                continue
            records.append(InterviewRecord(
                title=title,
                content=content,
                url=url,
                company="未知公司",
                role="AI Agent / AI 应用开发",
                source="牛客公开面经（自动收集，待复核）",
            ))
        browser.close()
    return records


def write_raw(records: list[InterviewRecord], date: str) -> Path:
    output_dir = RAW_ROOT / date
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "nowcoder-auto.json"
    payload = [
        {
            "title": record.title,
            "content": record.content,
            "url": record.url,
            "company": record.company,
            "role": record.role,
            "source": record.source,
        }
        for record in records
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def explicit_rows(urls: list[str]) -> list[dict[str, Any]]:
    return [{"url": url, "title": "", "quality": 99} for url in urls]


def main() -> None:
    parser = argparse.ArgumentParser(description="自动发现公开牛客 AI Agent 面经，并输出当天 Obsidian 笔记。")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--obsidian-root", default=str(ROOT / "notes" / "interviews"),
                        help="Obsidian 收件箱根目录；当天日期目录会自动创建。")
    parser.add_argument("--limit-per-keyword", type=int, default=4)
    parser.add_argument("--max-records", type=int, default=4)
    parser.add_argument("--delay-ms", type=int, default=2200)
    parser.add_argument("--url", action="append", default=[], help="跳过发现，直接处理一个公开候选链接；可重复。")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    processed = load_state(STATE_PATH)
    if args.url:
        candidates = explicit_rows(args.url)
    else:
        candidates = discover(list(INTERVIEW_KEYWORDS), args.limit_per_keyword, include_discussion=True, pages=1)
    candidates = [row for row in candidates if str(row.get("url") or "") not in processed]
    candidates.sort(key=rank_candidate, reverse=True)
    candidates = candidates[:max(0, args.max_records)]
    if not candidates:
        print("没有新的候选面经。")
        return

    records = fetch_public_records(candidates, args.delay_ms, args.verbose)
    if not records:
        print("没有通过深圳 AI Agent 面经相关性校验的公开帖子。")
        return
    if args.dry_run:
        for record in records:
            print(f"待整理：{record.title} | {record.url}")
        return

    raw_path = write_raw(records, args.date)
    notes_dir = Path(args.obsidian_root) / args.date
    written = write_notes(records, notes_dir)
    save_state(STATE_PATH, processed | {record.url for record in records})
    print(f"已收集 {len(records)} 篇公开面经 → {raw_path}")
    print(f"已生成 {len(written)} 篇待复核笔记 → {notes_dir}")


if __name__ == "__main__":
    main()
