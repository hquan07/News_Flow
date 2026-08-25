import scrapy

class ArticleItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    raw_html = scrapy.Field()
    category = scrapy.Field()
    source = scrapy.Field()
    author = scrapy.Field()
    publish_time = scrapy.Field()
    crawl_time = scrapy.Field()
    thumbnail_url = scrapy.Field()
    description = scrapy.Field()
    tags = scrapy.Field()