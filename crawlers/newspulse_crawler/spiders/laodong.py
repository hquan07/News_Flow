import logging
from datetime import datetime

import scrapy
from scrapy.http import Response

from newspulse_crawler.items import ArticleItem
from .base import BaseNewsSpider

logger = logging.getLogger(__name__)


class LaoDongSpider(BaseNewsSpider):
    name = "laodong"
    allowed_domains = ["laodong.vn"]
    source_name = "laodong"

    # RSS feeds by category
    start_urls = [
        "https://laodong.vn/rss/home.rss",
        "https://laodong.vn/rss/thoi-su.rss",
        "https://laodong.vn/rss/the-thao.rss",
        "https://laodong.vn/rss/suc-khoe.rss",
        "https://laodong.vn/rss/kinh-doanh.rss",
        "https://laodong.vn/rss/the-gioi.rss",
        "https://laodong.vn/rss/phap-luat.rss",
    ]

    category_map = {
        "the-thao": "thể thao",
        "suc-khoe": "sức khỏe",
        "kinh-doanh": "kinh doanh",
        "the-gioi": "thế giới",
        "phap-luat": "pháp luật",
        "thoi-su": "thời sự",
    }

    def parse(self, response: Response):
        if "document.cookie=\"D1N=" in response.text:
            import re
            match = re.search(r'D1N=([^"]+)', response.text)
            if match:
                cookie_val = match.group(1)
                request = response.request.copy()
                request.cookies["D1N"] = cookie_val
                request.dont_filter = True
                yield request
            return

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
        if "document.cookie=\"D1N=" in response.text:
            import re
            match = re.search(r'D1N=([^"]+)', response.text)
            if match:
                cookie_val = match.group(1)
                request = response.request.copy()
                request.cookies["D1N"] = cookie_val
                request.dont_filter = True
                yield request
            return

        title = response.css("h1.title::text").get("") or response.css("title::text").get("")
        description = response.css("p.abs::text").get("") or response.meta.get("rss_description", "")
        
        paragraphs = response.css("div.article-content p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip())

        author = response.css("p.author a::text").get("") or response.css("p.author::text").get("")
        
        publish_time = self._parse_time(response)
        
        tags = response.css("meta[name='keywords']::attr(content)").get("")
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        
        thumbnail = response.css("meta[property='og:image']::attr(content)").get("")

        yield self._build_item(
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
