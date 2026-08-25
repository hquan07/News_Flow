import logging
from datetime import datetime

import scrapy
from scrapy.http import Response

from newspulse_crawler.items import ArticleItem
from .base import BaseNewsSpider

logger = logging.getLogger(__name__)


class ThanhNienSpider(BaseNewsSpider):
    name = "thanhnien"
    allowed_domains = ["thanhnien.vn"]
    source_name = "thanhnien"

    start_urls = [
        "https://thanhnien.vn/rss/home.rss",
        "https://thanhnien.vn/rss/the-thao.rss",
        "https://thanhnien.vn/rss/cong-nghe.rss",
        "https://thanhnien.vn/rss/tai-chinh-kinh-doanh.rss",
        "https://thanhnien.vn/rss/thoi-su.rss",
        "https://thanhnien.vn/rss/giai-tri.rss",
        "https://thanhnien.vn/rss/suc-khoe.rss",
        "https://thanhnien.vn/rss/giao-duc.rss",
        "https://thanhnien.vn/rss/the-gioi.rss",
    ]

    category_map = {
        "the-thao": "thể thao",
        "cong-nghe": "công nghệ",
        "game": "công nghệ",
        "tai-chinh": "kinh doanh",
        "kinh-doanh": "kinh doanh",
        "thoi-su": "thời sự",
        "chinh-tri": "thời sự",
        "giai-tri": "giải trí",
        "van-hoa": "văn hóa",
        "suc-khoe": "sức khỏe",
        "doi-song": "sức khỏe",
        "giao-duc": "giáo dục",
        "the-gioi": "thế giới",
    }

    def parse(self, response: Response):
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
        title_nodes = (
            response.css("h1.detail-title *::text").getall()
            or response.css("h1.detail-title::text").getall()
            or response.css("h1.details__headline *::text").getall()
            or response.css("h1.details__headline::text").getall()
            or response.xpath("//h1//text()").getall()
        )
        title = "".join(t.strip() for t in title_nodes if t.strip())

        # Description / sapo
        description = (
            response.css("h2.detail-sapo::text").get()
            or response.css("div.detail-sapo::text").get()
            or response.css("div.details__summary::text").get()
            or response.meta.get("rss_description", "")
        )

        # Main content
        paragraphs = response.css("div#content-detail p::text").getall()
        if not paragraphs:
            paragraphs = response.css("div.details__content p::text").getall()
        if not paragraphs:
            paragraphs = response.css("div.detail-content p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip())

        # Author
        author = (
            response.css("div.detail-author a::text").get()
            or response.css("a.details__author::text").get()
            or response.css("span.author::text").get("")
        )

        # Publish time
        publish_time = self._parse_time(response)

        # Tags
        tags_raw = response.css("div.detail-tag a::text, div.tags a::text").getall()
        tag_list = [t.strip() for t in tags_raw if t.strip()]

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
        meta_time = (
            response.css("meta[property='article:published_time']::attr(content)").get()
            or response.css("meta[name='pubdate']::attr(content)").get()
        )
        if meta_time:
            return meta_time

        time_text = response.css("div.detail-time::text, time.details__time::text").get()
        if time_text:
            try:
                clean = time_text.strip()
                # Format: "08:30 - 15/01/2024" or "15/01/2024 - 08:30"
                if " - " in clean:
                    parts = clean.split(" - ")
                    if "/" in parts[0]:
                        dt = datetime.strptime(f"{parts[0].strip()} {parts[1].strip()}", "%d/%m/%Y %H:%M")
                    else:
                        dt = datetime.strptime(f"{parts[1].strip()} {parts[0].strip()}", "%d/%m/%Y %H:%M")
                    return dt.isoformat()
            except (ValueError, IndexError):
                pass

        return response.meta.get("rss_pub_date", "")