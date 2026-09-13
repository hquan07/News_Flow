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

class SocialItem(scrapy.Item):
    post_id = scrapy.Field()
    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    author = scrapy.Field()
    source = scrapy.Field()
    category = scrapy.Field()
    like_count = scrapy.Field()
    upvote_ratio = scrapy.Field()
    reply_count = scrapy.Field()
    top_comments = scrapy.Field() # Array of comment strings or dicts
    publish_time = scrapy.Field()
    crawl_time = scrapy.Field()