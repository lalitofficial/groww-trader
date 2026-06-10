from __future__ import annotations

from datetime import datetime
import html
import re
from typing import Any
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import requests

from .storage import Storage


class CatalystService:
    def __init__(self, storage: Storage, public_data: Any | None = None) -> None:
        self.storage = storage
        self.public_data = public_data

    def catalysts_for(
        self,
        symbol: str,
        company_name: str | None = None,
        refresh: bool = False,
        allow_remote: bool = True,
        include_static_links: bool = True,
    ) -> list[dict[str, Any]]:
        symbol = symbol.upper()
        cached = self.storage.list_catalysts(symbol)
        if cached and not refresh:
            return cached
        if not allow_remote:
            return cached or (self._exchange_links(symbol, company_name) if include_static_links else [])
        catalysts: list[dict[str, Any]] = []
        catalysts.extend(self._nse_announcements(symbol))
        catalysts.extend(self._google_news(symbol, company_name))
        catalysts.extend(self._moneycontrol_results(symbol, company_name))
        catalysts.extend(self._exchange_links(symbol, company_name))
        self.storage.upsert_catalysts(symbol, catalysts)
        return self.storage.list_catalysts(symbol)

    def _nse_announcements(self, symbol: str) -> list[dict[str, Any]]:
        if self.public_data is None:
            return []
        try:
            items = self.public_data.corporate_announcements(symbol=symbol) or []
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        for item in items[:15]:
            title = (item.get("subject") or item.get("details") or "NSE corporate announcement").strip()
            url = item.get("file_url") or f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={symbol}"
            rows.append(
                {
                    "source_type": "filing",
                    "title": f"NSE: {title}"[:200],
                    "url": url,
                    "published_at": item.get("broadcast_at"),
                    "summary": (item.get("details") or "")[:240],
                    "relevance_score": 0.9,
                }
            )
        return rows

    def _google_news(self, symbol: str, company_name: str | None) -> list[dict[str, Any]]:
        query = quote_plus(f"{company_name or symbol} stock NSE results order win earnings")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        items = self._fetch_rss(url, source_type="news", symbol=symbol, company_name=company_name)
        return items[:10]

    def _moneycontrol_results(self, symbol: str, company_name: str | None) -> list[dict[str, Any]]:
        # Moneycontrol's "Latest Earnings News" RSS works as a general earnings/results feed;
        # we score by symbol/company name presence for relevance ranking.
        url = "https://www.moneycontrol.com/rss/results.xml"
        try:
            items = self._fetch_rss(url, source_type="filing", symbol=symbol, company_name=company_name)
        except Exception:
            return []
        return [item for item in items if (item.get("relevance_score") or 0) >= 0.55][:5]

    def _exchange_links(self, symbol: str, company_name: str | None) -> list[dict[str, Any]]:
        return [
            {
                "source_type": "filing",
                "title": f"NSE corporate announcements: {company_name or symbol}",
                "url": f"https://www.nseindia.com/get-quotes/equity?symbol={quote_plus(symbol)}",
                "published_at": datetime.now().isoformat(timespec="seconds"),
                "summary": "Exchange page for announcements, corporate actions, and filings.",
                "relevance_score": 0.75,
            },
            {
                "source_type": "filing",
                "title": f"BSE corporate filings: {company_name or symbol}",
                "url": f"https://www.bseindia.com/stock-share-price/{quote_plus((company_name or symbol).lower().replace(' ', '-'))}/{quote_plus(symbol)}/-/corp_information/",
                "published_at": datetime.now().isoformat(timespec="seconds"),
                "summary": "BSE filings, shareholding, and corporate actions.",
                "relevance_score": 0.7,
            },
            {
                "source_type": "calendar",
                "title": f"NSE results calendar (search {symbol})",
                "url": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
                "published_at": datetime.now().isoformat(timespec="seconds"),
                "summary": "Browse quarterly results calendar to verify upcoming earnings.",
                "relevance_score": 0.5,
            },
        ]

    def _fetch_rss(self, url: str, source_type: str, symbol: str, company_name: str | None) -> list[dict[str, Any]]:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            return []
        items: list[dict[str, Any]] = []
        for item in root.findall(".//item")[:25]:
            title = html.unescape(item.findtext("title", "")).strip()
            link = item.findtext("link", "").strip()
            published = item.findtext("pubDate", "").strip()
            if not title or not link:
                continue
            items.append(
                {
                    "source_type": source_type,
                    "title": title,
                    "url": link,
                    "published_at": published,
                    "summary": _summarize_title(title),
                    "relevance_score": _relevance(title, symbol, company_name),
                }
            )
        return items


def _summarize_title(title: str) -> str:
    clean = re.sub(r"\s+", " ", title)
    return clean[:180]


def _relevance(title: str, symbol: str, company_name: str | None) -> float:
    text = title.upper()
    score = 0.35
    if symbol.upper() in text:
        score += 0.35
    if company_name and any(part.upper() in text for part in company_name.split()[:2] if len(part) > 2):
        score += 0.2
    if any(word in text for word in ("RESULT", "ORDER", "MERGER", "DIVIDEND", "EARNINGS", "STAKE", "RATING", "BUYBACK", "BLOCK DEAL", "BULK DEAL")):
        score += 0.1
    return round(min(score, 1.0), 2)
