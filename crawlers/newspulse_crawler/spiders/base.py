import logging
from abc import abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterator
from zoneinfo import ZoneInfo

import scrapy
from scrapy.http import Response

from newspulse_crawler.items import ArticleItem

logger = logging.getLogger(__name__)

class BaseNewsSpider(scrapy.Spider):
    source_name: str = ""
    category_map: dict[str, str] = {}

    # entry point
    def parse(self, response: Response) -> Iterator[scrapy.Request]:
        # Follow article links
        for link in self._extract_article_links(response):
            yield scrapy.Request(
                url=response.urljoin(link),
                callback=self.parse_article,
                meta={"category": self._detect_category(link)},
            )

        # Follow pagination if present
        for next_page in self._extract_pagination(response):
            yield scrapy.Request(
                url=response.urljoin(next_page),
                callback=self.parse,
            )

    @abstractmethod
    def parse_article(self, response: Response) -> ArticleItem:
        ...

    # helpers
    def _extract_article_links(self, response: Response) -> list[str]:
        links = response.css("article a::attr(href), h2 a::attr(href), h3 a::attr(href)").getall()
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for link in links:
            if link not in seen and self._is_article_url(link):
                seen.add(link)
                unique.append(link)
        return unique

    def _extract_pagination(self, response: Response) -> list[str]:
        return []

    def _detect_category(self, url: str) -> str:
        for segment, category in self.category_map.items():
            if segment in url:
                return category
        return "general"

    def _is_article_url(self, url: str) -> bool:
        if not url:
            return False
        return url.endswith(".html") or url.endswith(".htm") or "-" in url.split("/")[-1]

    def _is_fresh_rss_item(self, published_at: str | None) -> bool:
        """Skip stale RSS entries while retaining entries with unknown dates."""
        if not published_at:
            return True

        try:
            published = parsedate_to_datetime(published_at)
        except (TypeError, ValueError, OverflowError):
            try:
                published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                logger.warning("Could not parse RSS publish time %r; keeping item", published_at)
                return True

        if published.tzinfo is None:
            published = published.replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))

        max_age_hours = self.crawler.settings.getfloat("RSS_MAX_AGE_HOURS", 6.0)
        age_seconds = (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds()
        is_fresh = age_seconds <= max_age_hours * 3600
        if not is_fresh:
            self.crawler.stats.inc_value("rss_items/stale_skipped")
        return is_fresh

    def _build_item(
            self,
            response: Response,
            title: str,
            content: str,
            author: str = "",
            publish_time: str = "",
            description: str = "",
            tags: list[str] | None = None,
            thumbnail_url: str = "",
    ) -> ArticleItem:
        category = response.meta.get("category", self._detect_category(response.url))

        return ArticleItem(
            url=response.url,
            title=title.strip() if title else "",
            content=content.strip() if content else "",
            raw_html=response.text,
            category=category,
            source=self.source_name,
            author=author.strip() if author else "",
            publish_time=publish_time or datetime.now(timezone.utc).isoformat(),
            crawl_time=datetime.now(timezone.utc).isoformat(),
            description=description.strip() if description else "",
            tags=tags or [],
            thumbnail_url=thumbnail_url or "",
        )
