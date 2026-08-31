"""牛客网社招广场。

优先解析公开页面里的 SSR 职位卡片，不需要登录，也不依赖浏览器渲染；当页面
改为纯前端渲染、无法取得卡片时，才回退到既有 Playwright 方式。

公开入口：https://www.nowcoder.com/jobs/fulltime/center
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import register
from .http import get_text
from ..models import RawJob


def _with_page(url: str, n: int) -> str:
    parts = urlsplit(url)
    # 牛客首页直接输出 SSR 卡片；显式附上 ?page=1 会返回精简的 SPA 壳。
    if n == 1 and not parts.query:
        return url
    q = dict(parse_qsl(parts.query))
    q["page"] = str(n)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))

_CITY = re.compile(r"(北京|上海|深圳|广州|杭州|成都|武汉|南京|苏州|西安|天津|重庆|长沙|"
                   r"合肥|厦门|珠海|东莞|无锡|宁波|济南|青岛|郑州|福州|大连|远程)")
_SAL = re.compile(r"(\d[\d.]*\s*[-~]\s*\d[\d.]*\s*(?:元/天|元/月|K|k)[^ \n，]*|\d+-\d+K·\d+薪)")
_CO = re.compile(r"[一-龥A-Za-z0-9（）()·]{2,24}?(公司|科技|集团|股份|有限|银行|"
                 r"研究院|研究所|网络|信息|技术|数据|智能|半导体|医药|生物|汽车|电子)")
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
PAGES = 8   # 公开 SSR 列表翻页深度（无新增职位时会提前停止）


class _NowcoderCardParser(HTMLParser):
    """只提取牛客公开 SSR 卡片中稳定的语义 class，不依赖页面样式。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict[str, Any]] = []
        self._card: dict[str, Any] | None = None
        self._depth = 0
        self._fields: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if self._card is None:
            if tag == "div" and "job-card-item" in classes:
                self._card = {"title": [], "salary": [], "company": [], "info": [], "text": [], "url": ""}
                self._depth = 1
            return

        if tag not in _VOID_TAGS:
            self._depth += 1
        if tag == "a" and "job-message-boxs" in classes:
            self._card["url"] = attr.get("href") or self._card["url"]

        field = ""
        if "job-name" in classes:
            field = "title"
        elif "job-salary" in classes:
            field = "salary"
        elif "company-name" in classes:
            field = "company"
        elif "job-info-item" in classes:
            field = "info"
        if field:
            self._fields.append((tag, field))

    def handle_data(self, data: str) -> None:
        if self._card is None:
            return
        text = " ".join(data.split())
        if not text:
            return
        self._card["text"].append(text)
        if self._fields:
            self._card[self._fields[-1][1]].append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._card is None:
            return
        if self._fields and self._fields[-1][0] == tag:
            self._fields.pop()
        if tag not in _VOID_TAGS:
            self._depth -= 1
        if self._depth != 0:
            return

        card = self._card
        self._card = None
        self._fields.clear()
        title, url = " ".join(card["title"]), str(card["url"])
        if title and url:
            self.cards.append({
                "title": title,
                "salary": " ".join(card["salary"]),
                "company": " ".join(card["company"]),
                "info": list(card["info"]),
                "text": " ".join(card["text"]),
                "url": url,
            })


def _parse_ssr_cards(html: str) -> list[dict[str, Any]]:
    parser = _NowcoderCardParser()
    parser.feed(html)
    parser.close()
    return parser.cards


def _fetch_ssr(endpoint: str) -> list[dict[str, Any]]:
    """读取牛客社招广场公开 HTML；失败时返回空，供浏览器回退。"""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for n in range(1, PAGES + 1):
        try:
            cards = _parse_ssr_cards(get_text(_with_page(endpoint, n), headers={"Referer": "https://www.nowcoder.com/"}))
        except Exception:
            break
        fresh = [card for card in cards if str(card["url"]) not in seen]
        if not fresh:
            break
        rows.extend(fresh)
        seen.update(str(card["url"]) for card in fresh)
    return rows


def _fetch_browser(endpoint: str) -> list[dict[str, Any]]:
    """页面不再输出 SSR 卡片时的兼容回退。"""
    from . import _pw

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for n in range(1, PAGES + 1):
        page = _pw.new_page()
        try:
            page.set_default_timeout(30_000)
            try:
                page.goto(_with_page(endpoint, n), wait_until="networkidle", timeout=45_000)
            except Exception:
                # 牛客可能持续轮询；超时后页面通常已渲染，仍尝试读取职位卡片。
                pass
            page.wait_for_timeout(1_500)
            batch = page.eval_on_selector_all(
                "a.job-message-boxs[href*='/jobs/detail/']",
                "els => els.map(a => ({t: a.innerText, h: a.href}))",
            )
        except Exception:
            batch = []
        finally:
            page.close()
        fresh = [row for row in batch if row.get("h") and row["h"] not in seen]
        if not fresh:
            break
        rows.extend(fresh)
        seen.update(row["h"] for row in fresh)
    return rows


@register("nowcoder")
def fetch(endpoint: str) -> list[RawJob]:
    rows = _fetch_ssr(endpoint) or _fetch_browser(endpoint)
    jobs: list[RawJob] = []
    seen: set[tuple[str, str]] = set()
    _NOISE = ("求职首页", "发布职位", "全部职位", "求职", "首页", "登录", "注册")
    for r in rows:
        text = str(r.get("text") or r.get("t") or "")
        url = str(r.get("url") or r.get("h") or "")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = str(r.get("title") or (lines[0] if lines else ""))
        if not title or not url:
            continue
        key = (title, url)
        if key in seen or len(title) < 3 or title in _NOISE:
            continue
        seen.add(key)
        sal = str(r.get("salary") or "")
        if not sal:
            m = _SAL.search(text)
            sal = re.sub(r"\s+", "", m.group(0)) if m else ""
        mc = _CITY.search(" ".join(str(x) for x in r.get("info", [])) or text)
        loc = mc.group(0) if mc else ""
        comp = str(r.get("company") or "")
        if not comp:
            for line in lines[1:]:
                mm = _CO.search(line)
                if mm and len(line) <= 24:
                    comp = mm.group(0)
                    break
        job_id = re.search(r"/jobs/detail/(\d+)", url)
        jobs.append(RawJob(
            company_name=comp, title=title, location=loc,
            official_url=url, jd_text=text[:800],
            raw={"platform": "nowcoder", "id": job_id.group(1) if job_id else "",
                 "salary": sal, "employmentType": "FULL_TIME", "crawl_mode": "ssr"}))
    return jobs
