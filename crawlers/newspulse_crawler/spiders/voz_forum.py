import scrapy
from datetime import datetime, timezone
from newspulse_crawler.items import SocialItem

class VozForumSpider(scrapy.Spider):
    name = "voz_forum"
    allowed_domains = ["voz.vn"]
    start_urls = ["https://voz.vn/f/diem-bao.33/"]

    def parse(self, response):
        # Lấy danh sách các thread (trừ các thread dính/sticky)
        threads = response.css("div.structItemContainer-group.js-threadList div.structItem--thread")
        
        for thread in threads:
            title_node = thread.css("div.structItem-title a[data-tp-primary='on']")
            if not title_node:
                continue
            
            title = title_node.css("::text").get()
            link = title_node.attrib.get("href")
            
            # Lấy số reply và view từ trang chủ đề
            stats_dl = thread.css("div.structItem-cell--meta dl")
            reply_count = 0
            view_count = 0
            if len(stats_dl) >= 2:
                # XenForo lưu reply ở dl thứ 1, view ở dl thứ 2
                reply_text = stats_dl[0].css("dd::text").get(default="0").replace(",", "").replace(".", "")
                view_text = stats_dl[1].css("dd::text").get(default="0").replace(",", "").replace(".", "")
                try:
                    if 'K' in reply_text: reply_count = int(float(reply_text.replace('K', '')) * 1000)
                    else: reply_count = int(reply_text)
                    
                    if 'K' in view_text: view_count = int(float(view_text.replace('K', '')) * 1000)
                    else: view_count = int(view_text)
                except ValueError:
                    pass

            yield response.follow(
                link, 
                callback=self.parse_thread, 
                meta={
                    "thread_title": title,
                    "reply_count": reply_count,
                    "view_count": view_count
                }
            )

    def parse_thread(self, response):
        meta = response.meta
        
        # Bài post đầu tiên (bài gốc điểm báo)
        first_post = response.css("article.message--post").first()
        if not first_post:
            return

        author = first_post.css("a.username::text").get(default="Unknown").strip()
        content_html = first_post.css("div.bbWrapper").get(default="")
        
        # Trích xuất nguồn (báo gốc) nếu có trong post đầu
        source_url = first_post.css("div.bbWrapper a::attr(href)").get(default="")
        
        # Lấy các comment tiếp theo làm top comments
        comments = []
        for post in response.css("article.message--post")[1:11]: # Lấy 10 comment đầu trang 1
            comment_text = post.css("div.bbWrapper ::text").getall()
            comment_text = " ".join([t.strip() for t in comment_text if t.strip()])
            if comment_text:
                comments.append(comment_text)

        item = SocialItem()
        item["post_id"] = response.url.split(".")[-1].strip("/")
        item["url"] = response.url
        item["title"] = meta.get("thread_title", "")
        item["content"] = content_html
        item["author"] = author
        item["source"] = "voz_forum"
        item["category"] = "social_news"
        item["like_count"] = meta.get("view_count", 0) # Dùng view_count tạm cho like_count của voz
        item["upvote_ratio"] = 1.0 # Voz không có upvote/downvote
        item["reply_count"] = meta.get("reply_count", 0)
        item["top_comments"] = comments
        item["publish_time"] = datetime.now(timezone.utc).isoformat() # Voz time cần parse phức tạp hơn, tạm dùng now
        item["crawl_time"] = datetime.now(timezone.utc).isoformat()
        
        yield item
