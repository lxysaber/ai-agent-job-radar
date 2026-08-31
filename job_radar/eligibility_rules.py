"""按画像筛选招聘阶段与工作经验。

岗位来源对“社招/校招/经验”字段并不统一：本模块统一从标题、JD 和 source_id
做可解释判断，并由同步、导入、工作台和推送共同调用，避免只在某个入口漏筛。
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping


_INTERN_KW = ("实习", "intern", "见习", "見習")
_CAMPUS_KW = (
    "校招", "校园招聘", "应届", "应届生", "应届毕业生", "校招生", "毕业生",
    "管培", "管理培训生", "培训生", "储备干部", "储备生", "校园", "在校",
    "2025届", "2026届", "2027届", "2028届", "graduate", "campus",
)
_CAMPUS_SOURCES = {"cn-tencent-campus", "cn-huawei-campus", "cn-meituan-campus", "nk-campus", "nk-intern", "sxs-intern", "gov-ncss", "gov-qyzp"}
_UNLIMITED_EXPERIENCE_KW = ("经验不限", "不限经验", "无需经验", "无经验要求", "零经验", "0经验")
_NUMBERS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_NUMBER = r"(?:10|[0-9零一二三四五六七八九十])"
_RANGE_RE = re.compile(rf"(?<!\d)({_NUMBER})\s*(?:-|—|~|～|至|到)\s*({_NUMBER})\s*年")
_AT_LEAST_RE = re.compile(rf"(?<!\d)({_NUMBER})\s*年\s*(?:及|或)?\s*以上")
_EXACT_RE = re.compile(
    rf"(?<![0-9零一二三四五六七八九十-])(?:经验\s*(?:为|：)?\s*|(?:具备|有|要求)?\s*)"
    rf"({_NUMBER})\s*年(?:相关)?(?:工作|开发|项目)?经验"
)
_CAMPUS_ONE_YEAR_RE = re.compile(
    r"(?:工作)?经验\s*(?:不超过|未满|不足|≤)?\s*(?:1|一)\s*年(?:左右|以内|内)?|"
    r"(?:1|一)\s*年(?:左右|以内|内)?(?:的)?(?:工作)?经验|"
    r"毕业(?:后)?\s*(?:未满|不超过|不多于|不足|≤)?\s*(?:1|一)\s*年"
)


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    recruitment_kind: str
    experience_label: str
    reason: str


def _value(job: Any, name: str) -> str:
    if isinstance(job, Mapping):
        return str(job.get(name) or "")
    return str(getattr(job, name, "") or "")


def _text(job: Any) -> str:
    return " ".join((_value(job, "title"), _value(job, "jd_text"))).lower()


def _number(value: str) -> int | None:
    return int(value) if value.isdigit() else _NUMBERS.get(value)


def recruitment_kind(job: Any) -> str:
    """分类为社招、校招或实习；优先相信正文，避免只依赖信源。"""
    text = _text(job)
    sid = _value(job, "source_id")
    if any(keyword in text for keyword in _INTERN_KW) or sid in {"nk-intern", "sxs-intern"}:
        return "实习"
    if sid in _CAMPUS_SOURCES or sid.endswith("-campus") or sid.startswith("edu-"):
        return "校招"
    if any(keyword in text for keyword in _CAMPUS_KW):
        return "校招"
    return "社招"


def _experience_limit(profile: Mapping[str, Any]) -> tuple[int, int, bool, int]:
    rules = profile.get("employment_filter", {})
    if not isinstance(rules, Mapping):
        rules = {}
    try:
        minimum = max(0, int(rules.get("min_experience_years", 0)))
        maximum = max(minimum, int(rules.get("max_experience_years", 5)))
        campus_maximum = max(0, int(rules.get("allow_campus_with_up_to_years", 1)))
    except (TypeError, ValueError):
        minimum, maximum, campus_maximum = 0, 5, 1
    return minimum, maximum, bool(rules.get("allow_unspecified_social_experience", False)), campus_maximum


def evaluate(job: Any, profile: Mapping[str, Any]) -> EligibilityResult:
    """判断岗位是否符合画像的社招与经验范围要求。"""
    minimum, maximum, allow_unspecified, campus_maximum = _experience_limit(profile)
    text = _text(job)
    kind = recruitment_kind(job)
    if kind == "实习":
        return EligibilityResult(False, kind, "不适用", "实习岗位不属于社招范围")
    if kind == "校招":
        if campus_maximum >= 1 and _CAMPUS_ONE_YEAR_RE.search(text):
            return EligibilityResult(True, kind, "≤1年", "校招明确接受约 1 年工作经验")
        return EligibilityResult(False, kind, "不适用", "校招未明确接受约 1 年工作经验")

    if any(keyword in text for keyword in _UNLIMITED_EXPERIENCE_KW):
        return EligibilityResult(True, kind, "经验不限", "社招且经验不限")

    # “5 年以上”并不等于“最多 5 年”：没有上限，不能按 0–5 年放行。
    at_least = _AT_LEAST_RE.search(text)
    if at_least:
        years = _number(at_least.group(1))
        return EligibilityResult(False, kind, f"{years or '?'}年以上", "经验要求没有 5 年以内的明确上限")

    ranges = []
    for match in _RANGE_RE.finditer(text):
        low, high = _number(match.group(1)), _number(match.group(2))
        if low is not None and high is not None:
            ranges.append((low, high))
    if ranges:
        low, high = ranges[0]
        if minimum <= low <= high <= maximum:
            return EligibilityResult(True, kind, f"{low}-{high}年", "社招经验范围符合画像")
        return EligibilityResult(False, kind, f"{low}-{high}年", f"经验范围不在 {minimum}-{maximum} 年内")

    exact = _EXACT_RE.search(text)
    if exact:
        years = _number(exact.group(1))
        if years is not None and minimum <= years <= maximum:
            return EligibilityResult(True, kind, f"{years}年", "社招经验要求符合画像")
        return EligibilityResult(False, kind, f"{years or '?'}年", f"经验要求不在 {minimum}-{maximum} 年内")

    if allow_unspecified:
        return EligibilityResult(True, kind, "未标注", "社招未标注经验，按画像配置保留")
    return EligibilityResult(False, kind, "未标注", "社招未明确标注 0-5 年经验范围")


def eligible_for_any_profile(job: Any, profiles: Mapping[str, Mapping[str, Any]]) -> bool:
    """多画像并行时，只要一个画像接受就保留岗位。"""
    return any(evaluate(job, profile).eligible for profile in profiles.values())


def filter_jobs(jobs: Iterable[Any], profiles: Mapping[str, Mapping[str, Any]]) -> tuple[list[Any], list[Any]]:
    """返回（符合岗位，过滤岗位），供同步和各类增量导入共享。"""
    kept, excluded = [], []
    for job in jobs:
        (kept if eligible_for_any_profile(job, profiles) else excluded).append(job)
    return kept, excluded
