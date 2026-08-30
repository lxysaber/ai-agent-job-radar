"""将已获取的公开讨论/面经文本整理为可复习的 Markdown 笔记。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


TOPICS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("Agent 架构与工具调用", ("agent", "智能体", "mcp", "tool calling", "function calling", "多智能体"), "准备工具边界、状态管理、失败恢复与可观测性。"),
    ("RAG 与知识库", ("rag", "检索增强", "embedding", "向量", "召回", "重排", "rerank", "知识库"), "准备切分、召回、重排、引用与评测的完整链路。"),
    ("模型与 Prompt", ("大模型", "llm", "prompt", "幻觉", "上下文", "token", "微调"), "准备模型选择、结构化输出、上下文控制与安全边界。"),
    ("后端与系统设计", ("python", "fastapi", "接口", "微服务", "redis", "mysql", "postgres", "并发", "缓存", "队列"), "准备服务分层、并发、缓存、数据库和故障处理。"),
    ("部署、评测与安全", ("docker", "k8s", "部署", "评测", "eval", "监控", "可观测", "安全", "注入"), "准备发布、指标、离线集、成本控制和 prompt 注入防护。"),
    ("项目经历", ("项目", "难点", "负责", "优化", "指标", "效果", "复盘"), "用 STAR 结构准备项目目标、你的贡献、量化结果和复盘。"),
)


@dataclass
class InterviewRecord:
    title: str
    content: str
    url: str = ""
    company: str = "未知公司"
    role: str = "AI Agent/AI 应用开发"
    round_name: str = "未标注轮次"
    source: str = "牛客/公开讨论"
    material_type: str = "面经"


def _value(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _records_from_json(path: Path) -> list[InterviewRecord]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        for key in ("data", "items", "list", "records", "results"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
        else:
            raw = [raw]
    if not isinstance(raw, list):
        return []
    records = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        title = _value(row, "title", "name", "subject") or path.stem
        content = _value(row, "content", "text", "body", "summary", "description")
        if not content:
            continue
        records.append(InterviewRecord(
            title=title,
            content=content,
            url=_value(row, "url", "link", "canonical_url"),
            company=_value(row, "company", "company_name") or "未知公司",
            role=_value(row, "role", "position", "job_title") or "AI Agent/AI 应用开发",
            round_name=_value(row, "round", "stage") or _round_from_text(title + " " + content),
            source=_value(row, "source", "platform") or "牛客/公开讨论",
            material_type=_value(row, "material_type", "资料类型", "type") or "面经",
        ))
    return records


def _round_from_text(text: str) -> str:
    match = re.search(r"(hr面|一面|二面|三面|四面|终面|笔试|机考|群面)", text, re.I)
    return match.group(1) if match else "未标注轮次"


def _records_from_text(path: Path) -> list[InterviewRecord]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text or text.startswith("# 请将"):
        return []
    meta = {}
    for key, value in re.findall(r"(?m)^(公司|岗位|轮次|来源|类型|链接|URL)\s*[:：]\s*(.+)$", text):
        meta[key.lower()] = value.strip()
    url = meta.get("链接") or meta.get("url") or _first_url(text)
    title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.strip().startswith("#")), path.stem)
    return [InterviewRecord(
        title=title,
        content=text,
        url=url,
        company=meta.get("公司", "未知公司"),
        role=meta.get("岗位", "AI Agent/AI 应用开发"),
        round_name=meta.get("轮次") or _round_from_text(text),
        source=meta.get("来源", "牛客/公开讨论"),
        material_type=meta.get("类型", "面经"),
    )]


def _first_url(text: str) -> str:
    match = re.search(r"https?://[^\s)>]+", text)
    return match.group(0) if match else ""


def load_records(input_dir: Path) -> list[InterviewRecord]:
    records: list[InterviewRecord] = []
    for path in sorted(input_dir.glob("**/*")):
        if not path.is_file() or path.name.startswith(".") or path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() == ".json":
            records.extend(_records_from_json(path))
        elif path.suffix.lower() in {".md", ".txt"}:
            records.extend(_records_from_text(path))
    unique: dict[str, InterviewRecord] = {}
    for record in records:
        key = record.url or hashlib.sha1((record.title + record.content).encode("utf-8")).hexdigest()
        unique.setdefault(key, record)
    return list(unique.values())


def topics_for(record: InterviewRecord) -> list[tuple[str, str]]:
    text = f"{record.title} {record.content}".lower()
    return [(name, action) for name, keys, action in TOPICS if any(key.lower() in text for key in keys)]


def questions_for(record: InterviewRecord, limit: int = 12) -> list[str]:
    lines = [re.sub(r"\s+", " ", line).strip(" -•") for line in record.content.splitlines()]
    candidates = [
        line for line in lines
        if len(line) >= 8 and ("？" in line or "?" in line or re.match(r"^(q|问题|\d+[.、)])", line, re.I))
    ]
    if not candidates:
        sentences = re.split(r"[。！？!?\n]+", record.content)
        candidates = [s.strip() for s in sentences if re.search(r"问|如何|什么|为什么|怎么", s) and len(s.strip()) >= 8]
    return list(dict.fromkeys(candidates))[:limit]


def _slug(value: str, fallback: str) -> str:
    result = re.sub(r"[\\/:*?\"<>|\s]+", "-", value).strip("-.")
    return (result or fallback)[:48]


def note_markdown(record: InterviewRecord) -> str:
    topics = topics_for(record)
    questions = questions_for(record)
    tags = ["AI-Agent", record.material_type]
    if "深圳" in f"{record.title} {record.content}":
        tags.append("深圳")
    heading_parts = [record.company, record.role]
    if record.material_type == "面经":
        heading_parts.append(record.round_name)
    heading_parts.append(record.material_type)
    lines = [
        "---",
        f"company: {record.company}",
        f"role: {record.role}",
        f"round: {record.round_name}",
        f"source: {record.source}",
        f"url: {record.url}",
        f"material_type: {record.material_type}",
        f"tags: [{', '.join(tags)}]",
        "---",
        "",
        f"# {'｜'.join(heading_parts)}",
        "",
        "## 来源",
        "",
        f"- 原帖：{record.url or '未提供链接，请在原始收集箱补充'}",
        f"- 标题：{record.title}",
        "",
        "## 高频考点",
        "",
    ]
    if topics:
        lines.extend(f"- {name}：{action}" for name, action in topics)
    else:
        lines.append("- 未识别到 AI Agent 专项考点；建议人工标注后再复跑。")
    lines.extend(["", "## 记录到的问题", ""])
    if questions:
        lines.extend(f"- {question}" for question in questions)
    else:
        lines.append("- 原帖没有可自动提取的提问句，请回看来源补充。")
    lines.extend([
        "",
        "## 我的准备与复盘",
        "",
        "- [ ] 为每个问题写出 1 分钟概述、3 分钟展开与一个项目实例。",
        "- [ ] 标注不会的知识点，链接到学习笔记或代码示例。",
        "- [ ] 回到原帖核对上下文；自动整理不等同于完整、准确的面经复述。",
        "",
    ])
    return "\n".join(lines)


def write_notes(records: Iterable[InterviewRecord], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    existing_count = len(list(output_dir.glob("*.md")))
    for index, record in enumerate(records, existing_count + 1):
        filename = f"{index:02d}-{_slug(record.company, '未知公司')}-{_slug(record.role, 'AI-Agent')}-{_slug(record.material_type, '面经')}.md"
        path = output_dir / filename
        path.write_text(note_markdown(record), encoding="utf-8")
        written.append(path)
    return written
