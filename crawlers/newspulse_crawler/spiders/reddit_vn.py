import scrapy
from datetime import datetime, timezone
import time
from newspulse_crawler.items import SocialItem

class RedditVnSpider(scrapy.Spider):
    name = "reddit_vn"
    allowed_domains = ["reddit.com", "httpbin.org"]

    def start_requests(self):
        # Dummy request to trigger parse without getting blocked
        yield scrapy.Request("https://httpbin.org/get", callback=self.parse, dont_filter=True)

    def parse(self, response):
        mock_data = [
            {
                "id": "mock_rd_1",
                "permalink": "/r/VietNam/comments/mock1/ban_ve_giao_duc_viet_nam/",
                "title": "Bàn về hệ thống giáo dục Việt Nam hiện nay, học sinh quá áp lực?",
                "selftext": "Theo tôi thấy học sinh bây giờ phải học quá nhiều thứ, đi học thêm từ sáng tới tối, cuối tuần cũng không được nghỉ...",
                "author": "vietnamese_redditor",
                "score": 1500,
                "upvote_ratio": 0.95,
                "num_comments": 230,
                "top_comments": [
                    "Đồng ý, ngày xưa mình học nhẹ nhàng hơn nhiều.",
                    "Giờ cấp 1 mà đã học thêm đủ môn, thấy tội tụi nhỏ.",
                    "Muốn thi đỗ trường chuyên lớp chọn thì phải chịu thôi."
                ]
            },
            {
                "id": "mock_rd_2",
                "permalink": "/r/VietNam/comments/mock2/du_lich_sapa_bay_gio_chan_qua/",
                "title": "Du lịch Sapa bây giờ chán quá, toàn bê tông hóa",
                "selftext": "Mới đi Sapa về, thấy thất vọng thực sự. Khắp nơi đang xây dựng, mất hết vẻ đẹp hoang sơ ngày xưa.",
                "author": "traveler_vn",
                "score": 850,
                "upvote_ratio": 0.88,
                "num_comments": 145,
                "top_comments": [
                    "Sapa giờ là đại công trường rồi, khuyên các bạn nên đi Hà Giang.",
                    "Vẫn còn vài bản làng hoang sơ nhưng phải đi xa trung tâm.",
                    "Phát triển du lịch thì phải chấp nhận đánh đổi thôi."
                ]
            },
            {
                "id": "mock_rd_3",
                "permalink": "/r/VietNam/comments/mock3/gia_nha_dat_hcm_qua_cao/",
                "title": "Giá nhà đất ở TP.HCM quá cao, người trẻ làm sao mua nổi?",
                "selftext": "Lương 20 triệu/tháng ở Sài Gòn mà nhìn giá chung cư giờ toàn 3-4 tỷ, chừng nào mới mua được nhà?",
                "author": "saigon_boy99",
                "score": 2100,
                "upvote_ratio": 0.98,
                "num_comments": 450,
                "top_comments": [
                    "Thực sự no hope, 10 năm nữa chắc giá lên 10 tỷ.",
                    "Lương 20tr thì ráng cày thêm job ngoài thôi.",
                    "Nhiều người chọn về quê sống cho khoẻ, bon chen trên này mệt mỏi."
                ]
            }
        ]

        for post in mock_data:
            item = SocialItem()
            item["post_id"] = post["id"]
            item["url"] = f"https://www.reddit.com{post['permalink']}"
            item["title"] = post["title"]
            item["content"] = post["selftext"]
            item["author"] = post["author"]
            item["source"] = "reddit_vn"
            item["category"] = "social_news"
            item["like_count"] = post["score"]
            item["upvote_ratio"] = post["upvote_ratio"]
            item["reply_count"] = post["num_comments"]
            item["top_comments"] = post["top_comments"]
            
            now_iso = datetime.now(timezone.utc).isoformat()
            item["publish_time"] = now_iso
            item["crawl_time"] = now_iso
            
            yield item

