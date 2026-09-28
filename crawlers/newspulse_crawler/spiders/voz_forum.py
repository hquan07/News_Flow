import scrapy
from datetime import datetime, timezone, timedelta
import random
from newspulse_crawler.items import SocialItem

class VozForumSpider(scrapy.Spider):
    name = "voz_forum"
    allowed_domains = ["voz.vn", "httpbin.org"]

    def start_requests(self):
        yield scrapy.Request("https://httpbin.org/get", callback=self.parse, dont_filter=True)

    def parse(self, response):
        titles = [
            "[Dịch] Giá vàng thế giới lập đỉnh mới",
            "Có thím nào làm IT lương chuẩn 350 củ không?",
            "Tình hình kinh tế năm nay khó khăn quá các bác ạ",
            "[Góc nhờ vả] Tư vấn mua laptop tài chính 20 củ",
            "Tâm sự tuổi 30 chưa có gì trong tay",
            "[Dịch] Trung Quốc phóng vệ tinh mới",
            "Review đi phỏng vấn tại công ty X",
            "Vinfast IPO thành công trên sàn Nasdaq",
            "[Thảo luận] Tương lai của AI sẽ đi về đâu?",
            "Làm sao để thoát kiếp FA ở tuổi 25?"
        ]
        
        comments_pool = [
            "Đức. Tí đọc.",
            "Lương VOZer chuẩn 350 củ/tháng rồi, lo gì.",
            "Năm nay kinh tế buồn thật, công ty mình vừa layoff 30%.",
            "Thớt tư vấn như b**, vote ban.",
            "Tầm này có tiền mặt là vua, đừng ôm đất nữa.",
            "Chăm chỉ cày cuốc thôi các thím, than vãn cũng không giàu lên được.",
            "Lại bài văn mẫu à?",
            "Mình bằng tuổi thớt đã có nhà xe đầy đủ, chúc thớt cố gắng.",
            "AI sắp thay thế hết dev rồi, bỏ nghề dần đi là vừa.",
            "Đi làm chỉ mong tháng nhận lương, chán chả buồn nói."
        ]
        
        authors = ["TuanKhoi", "Con_Chim_Nho", "Vozer_Chuan", "BachTuoc", "Coder_Dao", "OngGiao", "Chi_Pheo"]

        for i in range(50):
            item = SocialItem()
            item["post_id"] = f"mock_voz_{i}"
            item["url"] = f"https://voz.vn/t/mock-thread-{i}/"
            item["title"] = random.choice(titles) + f" (Part {random.randint(1, 10)})"
            item["content"] = "Nội dung bài viết giả lập từ VOZ. " * 5
            item["author"] = random.choice(authors)
            item["source"] = "voz_forum"
            item["category"] = "social_news"
            item["like_count"] = random.randint(100, 10000)
            item["upvote_ratio"] = 1.0
            item["reply_count"] = random.randint(10, 500)
            
            # Chọn random 3-7 comments
            item["top_comments"] = random.sample(comments_pool, random.randint(3, 7))
            
            # Thời gian random trong 24h qua
            random_minutes = random.randint(0, 1440)
            publish_time = datetime.now(timezone.utc) - timedelta(minutes=random_minutes)
            
            item["publish_time"] = publish_time.isoformat()
            item["crawl_time"] = datetime.now(timezone.utc).isoformat()
            
            yield item
