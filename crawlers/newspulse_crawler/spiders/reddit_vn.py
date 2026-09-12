import scrapy
from datetime import datetime, timezone
from newspulse_crawler.items import SocialItem

class RedditVnSpider(scrapy.Spider):
    name = "reddit_vn"
    allowed_domains = ["reddit.com"]
    start_urls = ["https://www.reddit.com/r/VietNam/hot.json?limit=20"]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 NewsPulse/1.0',
        'ROBOTSTXT_OBEY': False
    }

    def parse(self, response):
        data = response.json()
        posts = data.get('data', {}).get('children', [])
        
        for post in posts:
            post_data = post.get('data', {})
            
            # Bỏ qua bài ghim (stickied)
            if post_data.get('stickied'):
                continue
                
            permalink = post_data.get('permalink')
            
            # Trỏ request vào file json của bài viết để lấy comment
            comments_url = f"https://www.reddit.com{permalink}.json"
            
            yield scrapy.Request(
                url=comments_url,
                callback=self.parse_comments,
                meta={'post_data': post_data}
            )

    def parse_comments(self, response):
        post_data = response.meta['post_data']
        
        try:
            # API trả về list 2 phần tử: [0] là bài gốc, [1] là comments
            data = response.json()
            comments_tree = data[1].get('data', {}).get('children', [])
        except Exception:
            comments_tree = []
            
        top_comments = []
        for i, comment in enumerate(comments_tree):
            if i >= 10: # Chỉ lấy 10 comment đầu tiên
                break
            body = comment.get('data', {}).get('body')
            if body:
                top_comments.append(body)

        item = SocialItem()
        item["post_id"] = post_data.get('id')
        item["url"] = f"https://www.reddit.com{post_data.get('permalink')}"
        item["title"] = post_data.get('title', '')
        item["content"] = post_data.get('selftext', '')
        item["author"] = post_data.get('author', 'Unknown')
        item["source"] = "reddit_vn"
        item["category"] = "social_news"
        item["like_count"] = int(post_data.get('score', 0))
        item["upvote_ratio"] = float(post_data.get('upvote_ratio', 1.0))
        item["reply_count"] = int(post_data.get('num_comments', 0))
        item["top_comments"] = top_comments
        
        created_utc = post_data.get('created_utc')
        if created_utc:
            item["publish_time"] = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
        else:
            item["publish_time"] = datetime.now(timezone.utc).isoformat()
            
        item["crawl_time"] = datetime.now(timezone.utc).isoformat()
        
        yield item
