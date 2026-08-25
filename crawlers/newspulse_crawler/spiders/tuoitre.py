import logging
from datetime import datetime

import scrapy
from scrapy.http import Response

from newspulse_crawler.items import ArticleItem
from .base import BaseNewsSpider

logger = logging.getLogger(__name__)


class TuoiTreSpider(BaseNewsSpider):
    name = "tuoitre"
    allowed_domains = ["tuoitre.vn"]
    source_name = "tuoitre"

    start_urls = [
        "https://tuoitre.vn/rss/tin-moi-nhat.rss",
        "https://tuoitre.vn/rss/the-thao.rss",
        "https://tuoitre.vn/rss/cong-nghe.rss",
        "https://tuoitre.vn/rss/kinh-doanh.rss",
        "https://tuoitre.vn/rss/thoi-su.rss",
        "https://tuoitre.vn/rss/giai-tri.rss",
        "https://tuoitre.vn/rss/suc-khoe.rss",
        "https://tuoitre.vn/rss/giao-duc.rss",
        "https://tuoitre.vn/rss/the-gioi.rss",
        "https://tuoitre.vn/rss/phap-luat.rss",
    ]

    category_map = {
        "the-thao": "thể thao",
        "cong-nghe": "công nghệ",
        "nhip-song-so": "công nghệ",
        "kinh-doanh": "kinh doanh",
        "tai-chinh": "kinh doanh",
        "thoi-su": "thời sự",
        "giai-tri": "giải trí",
        "van-hoa": "văn hóa",
        "suc-khoe": "sức khỏe",
        "giao-duc": "giáo dục",
        "the-gioi": "thế giới",
        "phap-luat": "pháp luật",
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
        title = (
            response.css("h1.detail-title::text").get()
            or response.css("h1.article-title::text").get()
            or response.xpath("//h1/text()").get("")
        )

        # Description / sapo
        description = (
            response.css("h2.detail-sapo::text").get()
            or response.css("div.detail-sapo::text").get()
            or response.meta.get("rss_description", "")
        )

        # Main content
        paragraphs = response.css("div#main-detail-body p::text").getall()
        if not paragraphs:
            paragraphs = response.css("div.detail-content p::text").getall()
        if not paragraphs:
            paragraphs = response.css("article p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip())

        # Author
        author = (
            response.css("div.detail-author a::text").get()
            or response.css("span.author-name::text").get("")
        )

        # Publish time
        publish_time = self._parse_time(response)

        # Tags
        tags_raw = response.css("div.detail-tag a::text").getall()
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
        # Try meta tag
        meta_time = (
            response.css("meta[property='article:published_time']::attr(content)").get()
            or response.css("meta[name='pubdate']::attr(content)").get()
        )
        if meta_time:
            return meta_time

        # Try date element
        time_text = response.css("div.detail-time span::text").get()
        if time_text:
            try:
                # Format: "15/01/2024 08:30 GMT+7"
                clean = time_text.strip().replace("GMT+7", "").strip()
                dt = datetime.strptime(clean, "%d/%m/%Y %H:%M")
                return dt.isoformat()
            except (ValueError, IndexError):
                pass

        return response.meta.get("rss_pub_date", "")