"""AI Agent / AI 应用 JD 的可解释技能分析。

本模块刻意不执行网页抓取，也不调用模型：它只处理已入库的 JD 文本，
输出可追溯的技能频次和证据句。这样可以先稳定日常工作流，后续再把同一
结构化结果交给 LLM 做个性化学习建议。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable


@dataclass(frozen=True)
class Skill:
    name: str
    keywords: tuple[str, ...]
    learning_action: str
    priority: str


SKILLS: tuple[Skill, ...] = (
    Skill("LLM API 与结构化输出", ("大模型", "llm", "openai", "通义", "qwen", "结构化输出", "json schema"),
          "用 Python 完成一个支持流式响应、函数调用和 JSON Schema 校验的模型服务。", "P0"),
    Skill("Agent 编排与工具调用", ("agent", "智能体", "tool calling", "function calling", "工具调用", "mcp", "多智能体", "multi-agent"),
          "实现一个可审计的 Agent：工具白名单、参数校验、超时、重试与调用日志缺一不可。", "P0"),
    Skill("RAG 与检索", ("rag", "检索增强", "embedding", "向量数据库", "向量检索", "rerank", "重排序", "milvus", "qdrant", "chromadb", "知识库"),
          "完成“文档切分→向量检索→重排→带来源回答”的闭环，并为每一步记录离线评测。", "P0"),
    Skill("Agent 框架与工作流", ("langchain", "langgraph", "llamaindex", "workflow", "工作流", "状态机", "prompt flow"),
          "先用状态机定义可恢复流程，再比较 LangGraph/LangChain/LlamaIndex 的抽象取舍。", "P1"),
    Skill("Python 后端工程", ("python", "fastapi", "flask", "django", "asyncio", "异步", "微服务", "api", "后端"),
          "用 FastAPI 编写生产化服务：鉴权、异步任务、限流、日志、单元测试和 OpenAPI 文档。", "P0"),
    Skill("数据与缓存", ("postgresql", "mysql", "redis", "elasticsearch", "kafka", "消息队列", "orm"),
          "把会话、任务、知识库元数据与缓存分层设计，写清一致性和失效策略。", "P1"),
    Skill("模型服务与部署", ("vllm", "sglang", "模型服务", "推理服务", "docker", "kubernetes", "k8s", "云原生", "gpu"),
          "容器化部署模型/应用服务，掌握并发、显存、延迟、吞吐和回滚的基本指标。", "P1"),
    Skill("评测、可观测与安全", ("评测", "eval", "ragas", "可观测", "tracing", "guardrail", "安全", "幻觉", "prompt 注入", "权限"),
          "建立 20 条以上带标准答案的测试集，追踪命中率、忠实性、工具失败率与单次成本。", "P1"),
    Skill("前端与产品化", ("react", "vue", "typescript", "javascript", "用户体验", "产品化", "前端"),
          "做一个可用的 Agent 工作台，覆盖流式展示、失败重试、引用展开与用户反馈。", "P2"),
)

AGENT_MARKERS = (
    "agent", "智能体", "ai应用", "ai 应用", "大模型应用", "llm应用", "llm 应用",
    "rag", "检索增强", "langchain", "langgraph", "llamaindex", "mcp",
)


@dataclass
class SkillFinding:
    skill: Skill
    job_count: int = 0
    examples: list[tuple[str, str, str]] = field(default_factory=list)


def _text(job: dict) -> str:
    return " ".join(str(job.get(k) or "") for k in ("title", "jd_text", "tags"))


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"[。！？!?.；;\n]+", text)
    return [re.sub(r"\s+", " ", chunk).strip() for chunk in chunks if len(chunk.strip()) >= 8]


def is_agent_job(job: dict, city: str = "") -> bool:
    text = _text(job).lower()
    if not any(marker in text for marker in AGENT_MARKERS):
        return False
    location = str(job.get("location") or "")
    return not city or not location or city.lower() in location.lower()


def analyze_jobs(jobs: Iterable[dict], city: str = "深圳", evidence_limit: int = 3) -> tuple[list[SkillFinding], list[dict]]:
    """返回技能聚合与纳入分析的岗位。每条证据均包含公司、职位与原句。"""
    selected = [job for job in jobs if is_agent_job(job, city)]
    findings = [SkillFinding(skill=skill) for skill in SKILLS]
    for job in selected:
        text = _text(job).lower()
        sentences = _sentences(_text(job))
        for finding in findings:
            matched = [key for key in finding.skill.keywords if key.lower() in text]
            if not matched:
                continue
            finding.job_count += 1
            if len(finding.examples) >= evidence_limit:
                continue
            sentence = next(
                (s for s in sentences if any(key.lower() in s.lower() for key in matched)),
                str(job.get("title") or ""),
            )
            finding.examples.append((
                str(job.get("company_name") or "未知公司"),
                str(job.get("title") or "未命名职位"),
                sentence[:180],
            ))
    findings.sort(key=lambda item: (item.skill.priority, -item.job_count, item.skill.name))
    return findings, selected


def report_markdown(jobs: Iterable[dict], city: str = "深圳") -> str:
    findings, selected = analyze_jobs(jobs, city)
    lines = [
        f"# {city} AI Agent / AI 应用开发技能雷达",
        "",
        f"分析岗位：{len(selected)} 条。此报告仅统计包含 AI Agent、智能体、RAG、MCP 或 Agent 框架信号的已采集 JD。",
        "结论基于原始 JD 的关键词和证据句；它是学习优先级建议，不替代职位原文。",
        "",
        "## 技能优先级",
        "",
        "| 优先级 | 技能 | 命中 JD 数 | 建议 |",
        "| --- | --- | ---: | --- |",
    ]
    for finding in findings:
        if finding.job_count:
            lines.append(
                f"| {finding.skill.priority} | {finding.skill.name} | {finding.job_count} | {finding.skill.learning_action} |"
            )
    if not any(f.job_count for f in findings):
        lines.append("| - | 暂无可分析 JD | 0 | 先导入 BOSS 或官网职位详情后再运行。 |")

    lines.extend(["", "## JD 证据", ""])
    for finding in findings:
        if not finding.examples:
            continue
        lines.append(f"### {finding.skill.name}")
        for company, title, sentence in finding.examples:
            lines.append(f"- {company}｜{title}：{sentence}")
        lines.append("")

    lines.extend([
        "## 推荐学习顺序",
        "",
        "1. Python/FastAPI + LLM API/结构化输出：先搭好可运行、可测试的后端基础。",
        "2. Tool Calling/MCP + 单 Agent：建立工具白名单、权限边界和错误恢复。",
        "3. RAG：补齐检索、重排、引用和离线评测，而不只做聊天演示。",
        "4. LangGraph 等工作流：把多步任务建模为可观察、可恢复的状态机。",
        "5. 部署与评测：把延迟、成本、命中率、工具失败率纳入项目验收。",
    ])
    return "\n".join(lines) + "\n"
