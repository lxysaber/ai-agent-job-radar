#!/usr/bin/env python3
"""把本机 boss-scripts 的职位详情导出增量并入 Job Radar。"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from job_radar import sync  # noqa: E402
from job_radar.boss_export import load  # noqa: E402
from job_radar.dedup import dedup  # noqa: E402
from job_radar.quality_rules import quality_tags  # noqa: E402
from job_radar.score import score_job  # noqa: E402
from scripts import export_html  # noqa: E402

SOURCE = {
    "source_id": "boss-local",
    "company_name": "BOSS直聘",
    "org_type": "aggregator",
    "source_type": "aggregator",
}


def score(jobs, profiles) -> None:
    for job in jobs:
        best = max((score_job(job, profile) for profile in profiles.values()), key=lambda result: result.score)
        qtags, qrisks = quality_tags(job)
        job.match_score = best.score
        job.tags = list(dict.fromkeys(([f"行业:{job.industry}"] if job.industry else []) + best.tags + qtags))
        job.risk_flags = list(dict.fromkeys(job.risk_flags + best.risk_flags + qrisks))


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 boss-scripts 的 JSON，并保留其它信源数据。")
    parser.add_argument("--input", required=True, help="已执行 detail 的 JSON 文件")
    parser.add_argument("--data-dir", default=os.path.join(ROOT, "data"))
    args = parser.parse_args()

    raw_jobs = load(args.input)
    if not raw_jobs:
        raise SystemExit("未从 JSON 识别到职位。请确认先完成 boss-scripts detail，并检查导出格式。")
    jobs = dedup(sync._to_jobs(SOURCE, raw_jobs))
    with open(sync.PROFILES_JSON, encoding="utf-8") as f:
        profiles = json.load(f)
    jobs, excluded = sync.filter_jobs(jobs, profiles)
    score(jobs, profiles)
    now = sync._now()
    data_dir = os.path.abspath(args.data_dir)
    jobs_path = os.path.join(data_dir, "jobs.json")
    archive_path = os.path.join(data_dir, "jobs_archive.json")
    merged = sync._merge_incremental([job.to_dict() for job in jobs], jobs_path, now, {"boss-local"})
    sync._save_json(jobs_path, merged["jobs"])
    sync._archive_gone(archive_path, merged.get("gone_jobs", []), now)
    export_html.main()
    print(f"已导入 {len(jobs)} 条符合画像的 BOSS 职位（过滤 {len(excluded)} 条，新增 {merged['new']}）→ {jobs_path}")


if __name__ == "__main__":
    main()
