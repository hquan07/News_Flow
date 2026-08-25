import logging
from datetime import datetime

import scrapy
from scrapy.http import Response

from newspulse_crawler.items import ArticleItem
from .base import BaseNewsSpider

logger = logging.getLogger(__name__)


class VnExpressSpider(BaseNewsSpider):
    name = "vnexpress"
    allowed_domains = ["vnexpress.net"]
    source_name = "vnexpress"

    # RSS feeds by category
    start_urls = [
        "https://vnexpress.net/rss/tin-moi-nhat.rss",       # latest
        "https://vnexpress.net/rss/the-thao.rss",           # sports
        "https://vnexpress.net/rss/khoa-hoc.rss",           # science/tech
        "https://vnexpress.net/rss/so-hoa.rss",             # digital
        "https://vnexpress.net/rss/kinh-doanh.rss",         # business
        "https://vnexpress.net/rss/thoi-su.rss",            # politics
        "https://vnexpress.net/rss/giai-tri.rss",           # entertainment
        "https://vnexpress.net/rss/suc-khoe.rss",           # health
        "https://vnexpress.net/rss/giao-duc.rss",           # education
        "https://vnexpress.net/rss/the-gioi.rss",           # world
        "https://vnexpress.net/rss/phap-luat.rss",          # law
    ]

    category_map = {
        "the-thao": "thể thao",
        "khoa-hoc": "khoa học",
        "so-hoa": "số hóa",
        "kinh-doanh": "kinh doanh",
        "thoi-su": "thời sự",
        "giai-tri": "giải trí",
        "suc-khoe": "sức khỏe",
        "giao-duc": "giáo dục",
        "the-gioi": "thế giới",
        "phap-luat": "pháp luật",
    }

    def parse(self, response: Response):
        # RSS feeds return XML
        response.selector.remove_namespaces()
        items = response.xpath("//item")

        for item in items:
            link = item.xpath("link/text()").get()
            pub_date = item.xpath("pubDate/text()").get()
            description = item.xpath("description/text()").get("")

            if link and self._is_article_url(link):
                yield scrapy.Request(
                    url=link,
                    callback=self.parse_article,
                    meta={
                        "category": self._detect_category(link),
                        "rss_pub_date": pub_date,
                        "rss_description": description,
                    },
                )

    def parse_article(self, response: Response) -> ArticleItem:
        # Title
        title = (
            response.css("h1.title-detail::text").get()
            or response.css("h1.title_news_detail::text").get()
            or response.xpath("//h1/text()").get("")
        )

        # Description / sapo
        description = (
            response.css("p.description::text").get()
            or response.meta.get("rss_description", "")
        )

        # Main content
        paragraphs = response.css("article.fck_detail p.Normal::text").getall()
        if not paragraphs:
            paragraphs = response.css("article p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip())

        # Author
        author = (
            response.css("p.author_mail strong::text").get()
            or response.css("p.Normal[style*='right'] strong::text").get("")
        )

        # Publish time
        publish_time = self._parse_time(response)

        # Tags
        tags = response.css("meta[name='keywords']::attr(content)").get("")
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        # Thumbnail
        thumbnail = response.css("meta[property='og:image']::attr(content)").get("")

        return self._build_item(
            response=response,
            title=title,
            content=content,
            author=author,
            publish_time=publish_time,
            description=description,
            tags=tag_list,
            thumbnail_url=thumbnail,
        )

    def _parse_time(self, response: Response) -> str:
        # Try meta tag first
        meta_time = response.css("meta[name='pubdate']::attr(content)").get()
        if meta_time:
            return meta_time

        # Try from span
        time_text = response.css("span.date::text").get()
        if time_text:
            try:
                # VnExpress format: "Thứ hai, 15/1/2024, 08:30 (GMT+7)"
                parts = time_text.split(",")
                if len(parts) >= 3:
                    date_str = parts[1].strip()
                    time_str = parts[2].strip().split("(")[0].strip()
                    dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
                    return dt.isoformat()
            except (ValueError, IndexError):
                pass

        # Fallback to RSS pub date
        return response.meta.get("rss_pub_date", "")