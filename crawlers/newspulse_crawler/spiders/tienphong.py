import logging
from datetime import datetime

import scrapy
from scrapy.http import Response

from newspulse_crawler.items import ArticleItem
from .base import BaseNewsSpider

logger = logging.getLogger(__name__)


class TienPhongSpider(BaseNewsSpider):
    name = "tienphong"
    allowed_domains = ["tienphong.vn"]
    source_name = "tienphong"

    # RSS feeds by category
    start_urls = [
        "https://tienphong.vn/rss/home.rss",
        "https://tienphong.vn/rss/the-thao.rss",
        "https://tienphong.vn/rss/suc-khoe.rss",
        "https://tienphong.vn/rss/giao-duc.rss",
        "https://tienphong.vn/rss/kinh-te.rss",
        "https://tienphong.vn/rss/the-gioi.rss",
        "https://tienphong.vn/rss/phap-luat.rss",
        "https://tienphong.vn/rss/giai-tri.rss",
    ]

    category_map = {
        "the-thao": "thể thao",
        "suc-khoe": "sức khỏe",
        "giao-duc": "giáo dục",
        "kinh-te": "kinh doanh",
        "the-gioi": "thế giới",
        "phap-luat": "pháp luật",
        "giai-tri": "giải trí",
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
        title = response.css("h1.article__title::text").get("")
        description = response.css("div.article__sapo::text").get("") or response.meta.get("rss_description", "")
        
        paragraphs = response.css("div.article__body p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip())

        author = response.css("div.article__author span::text").get("")
        
        publish_time = self._parse_time(response)
        
        tags = response.css("meta[name='keywords']::attr(content)").get("")
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        
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
        meta_time = response.css("meta[property='article:published_time']::attr(content)").get()
        if meta_time:
            return meta_time
        return response.meta.get("rss_pub_date", "")
