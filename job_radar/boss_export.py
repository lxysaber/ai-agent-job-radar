"""读取 boss-scripts 导出的 JSON，将其转换为本项目的 RawJob。

仅处理用户本机已经导出的职位文件，不处理 Cookie、验证码或浏览器控制。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import RawJob


def _first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        for key in ("data", "jobs", "list", "items", "results"):
            if isinstance(raw.get(key), list):
                return [row for row in raw[key] if isinstance(row, dict)]
        return [raw]
    return []


def load(path: str | Path) -> list[RawJob]:
    """尽量兼容 list/detail 导出的常见字段命名；缺少职位名的行被丢弃。"""
    source_path = Path(path)
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    jobs: list[RawJob] = []
    for row in _rows(raw):
        title = _first(row, "title", "jobName", "jobTitle", "positionName", "name", "job_name")
        if not title:
            continue
        company_raw = row.get("company")
        company = _first(row, "companyName", "brandName", "company_name", "bossCompany")
        if isinstance(company_raw, dict):
            company = company or _first(company_raw, "name", "companyName", "brandName")
        elif company_raw:
            company = company or str(company_raw)
        location = _first(row, "location", "workLocation", "work_location", "city", "area")
        jd_text = _first(row, "jobDescription", "job_description", "description", "jobDetail", "detail", "jd")
        url = _first(row, "url", "jobUrl", "job_url", "detailUrl", "detail_url")
        publish_time = _first(row, "publishTime", "publish_time", "createTime", "createdAt")
        salary = _first(row, "salary", "salaryDesc", "pay", "money")
        jobs.append(RawJob(
            company_name=company or "BOSS 直聘职位",
            title=title,
            location=location,
            publish_time=publish_time,
            official_url=url,
            jd_text=jd_text,
            raw={"salary": salary, "platform": "boss-zhipin", "source_file": source_path.name, **row},
        ))
    return jobs
