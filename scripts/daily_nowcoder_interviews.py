#!/usr/bin/env python3
"""每日发现并整理多源公开 AI Agent 面经。

只访问无需登录即可查看的页面；不读取 Cookie、不绕过验证码或反爬机制。
外部页面文本仅作为待分析数据，绝不执行其中任何指令。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from job_radar.interview_notes import InterviewRecord, write_notes  # noqa: E402
from scripts.nowcoder_discover import discover  # noqa: E402


STATE_PATH = ROOT / "data" / "interview_note_state.json"
RAW_ROOT = ROOT / "data" / "inbox" / "interviews" / "auto"
SOURCES_PATH = ROOT / "config" / "interview_sources.json"
MANUAL_URLS_PATH = ROOT / "data" / "inbox" / "interviews" / "external_urls.txt"

AGENT_SIGNAL = re.compile(r"ai.?agent|\bagent\b|智能体|ai.?应用|大模型应用|llm|rag|检索增强|mcp|tool calling|function calling", re.I)
INTERVIEW_SIGNAL = re.compile(r"面经|一面|二面|三面|终面|笔试|机考|技术面", re.I)
SHENZHEN_SIGNAL = re.compile(r"深圳|base\s*深圳", re.I)
NOISE_SIGNAL = re.compile(r"求问|求助|求拷打|简历求|offer比较|offer帮选|去哪个|怎么选|投递记录", re.I)
# 这些是复习资料而非个人面经；保留在公开索引中供人查阅，但不自动写成“面经笔记”。
REFERENCE_SIGNAL = re.compile(r"面试题|题库|高频题|汇总|宝典|参考解答|知识图谱|真题整理", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PLATFORM_NAMES = {
    "www.nowcoder.com": "牛客",
    "blog.csdn.net": "CSDN",
    "gitcode.csdn.net": "GitCode",
    "devpress.csdn.net": "DevPress",
    "www.cnblogs.com": "博客园",
    "juejin.cn": "掘金",
    "www.zhihu.com": "知乎",
    "www.blanked.work": "个人博客",
}


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


def load_sources(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取面经来源配置：{path} ({exc})") from exc
    sources = raw.get("auto_sources", [])
    return [source for source in sources if isinstance(source, dict) and source.get("enabled", True)]


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
    if row.get("city_required"):
        score += 2
    return score, title


def discover_github_index(source: dict[str, Any]) -> list[dict[str, Any]]:
    """从公开 Markdown 索引中只提取白名单域名的候选链接。

    索引文字和外部页面都是不可信数据：这里只做 URL、标题和来源字段提取，
    不解释或执行其中出现的任何文字指令。
    """
    url = str(source.get("url") or "")
    allowed_hosts = {str(host).lower() for host in source.get("allowed_hosts", [])}
    if not url or not allowed_hosts:
        return []
    request = urllib.request.Request(url, headers={"User-Agent": "ai-agent-job-radar/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"跳过来源索引 {source.get('name', source.get('id'))}：{type(exc).__name__}")
        return []

    rows = []
    for title, target in re.findall(r"\[([^\]]{2,160})\]\((https?://[^)\s]+)\)", text):
        parsed = urllib.parse.urlparse(target)
        host = (parsed.hostname or "").lower()
        if host not in allowed_hosts:
            continue
        clean_title = re.sub(r"\s+", " ", title).strip()
        if not (AGENT_SIGNAL.search(clean_title) or INTERVIEW_SIGNAL.search(clean_title)):
            continue
        if REFERENCE_SIGNAL.search(clean_title):
            continue
        rows.append({
            "url": target,
            "title": clean_title,
            "quality": 8,
            "source_id": str(source.get("id") or "公开索引"),
            "source_name": f"{source.get('name', source.get('id', '公开索引'))} → {PLATFORM_NAMES.get(host, host)}",
            "city_required": bool(source.get("city_required")),
            "max_from_source": int(source.get("max_records", 2)),
        })
    return rows


def manual_url_rows(path: Path) -> list[dict[str, Any]]:
    """读取人工补充的公开 URL。

    每行可写 ``来源名称 | https://...``，也可只写 URL。文件内容只被当作候选
    元数据，不会执行其中的文字；受登录限制的平台可在浏览器可公开访问时再处理。
    """
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        label, separator, candidate_url = line.partition("|")
        url = candidate_url.strip() if separator else label
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            print(f"跳过无效公开链接：{line[:100]}")
            continue
        source_name = label.strip() if separator and label.strip() else "手动公开链接"
        rows.append({
            "url": url,
            "title": "",
            "quality": 99,
            "source_id": "manual-urls",
            "source_name": source_name,
            "city_required": False,
            "max_from_source": 99,
        })
    return rows


def discover_all_sources(sources: list[dict[str, Any]], limit_per_keyword: int,
                         manual_urls_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources:
        kind = source.get("kind")
        if kind == "nowcoder_search":
            discovered = discover(
                list(source.get("keywords", [])),
                limit_per_keyword,
                include_discussion=True,
                pages=1,
            )
            for row in discovered:
                row["source_id"] = str(source.get("id") or "nowcoder")
                row["source_name"] = source.get("name", "牛客公开面经")
                row["city_required"] = bool(source.get("city_required"))
                row["max_from_source"] = int(source.get("max_records", 2))
            rows.extend(discovered)
        elif kind == "github_markdown_index":
            rows.extend(discover_github_index(source))
        else:
            print(f"忽略未知面经来源类型：{kind}")
    rows.extend(manual_url_rows(manual_urls_path))
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = str(row.get("url") or "")
        if url:
            unique.setdefault(url, row)
    return list(unique.values())


def choose_candidates(rows: list[dict[str, Any]], max_records: int) -> list[dict[str, Any]]:
    """按相关性排序，同时限制每个自动来源的入选数，保证来源多样性。"""
    counts: dict[str, int] = {}
    chosen: list[dict[str, Any]] = []
    for row in sorted(rows, key=rank_candidate, reverse=True):
        source_id = str(row.get("source_id") or row.get("source_name") or "未知来源")
        try:
            cap = max(1, int(row.get("max_from_source", max_records)))
        except (TypeError, ValueError):
            cap = max_records
        if counts.get(source_id, 0) >= cap:
            continue
        chosen.append(row)
        counts[source_id] = counts.get(source_id, 0) + 1
        if len(chosen) >= max(0, max_records):
            break
    return chosen


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

            # 牛客搜索源严格要求深圳；跨站公开索引允许补充通用技术面经，来源会明确标注。
            evidence = f"{title}\n{content}"
            signals = {
                "agent": bool(AGENT_SIGNAL.search(evidence)),
                "interview": bool(INTERVIEW_SIGNAL.search(evidence)),
                "shenzhen": bool(SHENZHEN_SIGNAL.search(evidence)),
            }
            if verbose:
                print(f"候选诊断：len={len(content)} signals={signals} title={title}")
            city_ok = signals["shenzhen"] or not bool(row.get("city_required"))
            if len(content) < 300 or not (signals["agent"] and signals["interview"] and city_ok):
                print(f"跳过低相关候选：{title}")
                continue
            records.append(InterviewRecord(
                title=title,
                content=content,
                url=url,
                company="未知公司",
                role="AI Agent / AI 应用开发",
                source=f"{row.get('source_name', '公开页面')}（自动收集，待复核）",
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
    return [{
        "url": url,
        "title": "",
        "quality": 99,
        "source_id": "manual-urls",
        "source_name": "手动公开链接",
        "city_required": False,
        "max_from_source": 99,
    } for url in urls]


def main() -> None:
    parser = argparse.ArgumentParser(description="自动发现多源公开 AI Agent 面经，并输出当天 Obsidian 笔记。")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--obsidian-root", default=str(ROOT / "notes" / "interviews"),
                        help="Obsidian 收件箱根目录；当天日期目录会自动创建。")
    parser.add_argument("--limit-per-keyword", type=int, default=4)
    parser.add_argument("--max-records", type=int, default=4)
    parser.add_argument("--delay-ms", type=int, default=2200)
    parser.add_argument("--url", action="append", default=[], help="跳过发现，直接处理一个公开候选链接；可重复。")
    parser.add_argument("--sources-file", default=str(SOURCES_PATH), help="来源清单 JSON。")
    parser.add_argument("--manual-urls-file", default=str(MANUAL_URLS_PATH),
                        help="手工补充公开链接的文本文件；每行可写“来源 | URL”。")
    parser.add_argument("--source", action="append", default=[],
                        help="仅运行指定来源 ID（可重复，例如 nowcoder 或 agent-interview-hub）。")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    processed = load_state(STATE_PATH)
    if args.url:
        candidates = explicit_rows(args.url)
    else:
        sources = load_sources(Path(args.sources_file))
        if args.source:
            requested = set(args.source)
            sources = [source for source in sources if str(source.get("id")) in requested]
            unknown = requested - {str(source.get("id")) for source in sources} - {"manual-urls"}
            if unknown:
                raise SystemExit(f"未配置的来源 ID：{', '.join(sorted(unknown))}")
        candidates = discover_all_sources(sources, args.limit_per_keyword, Path(args.manual_urls_file))
        if args.source and "manual-urls" not in args.source:
            candidates = [row for row in candidates if row.get("source_id") != "manual-urls"]
    candidates = [row for row in candidates if str(row.get("url") or "") not in processed]
    candidates = choose_candidates(candidates, args.max_records)
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
