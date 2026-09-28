import scrapy
from datetime import datetime, timezone, timedelta
import random
from newspulse_crawler.items import SocialItem

class YoutubeCommentsSpider(scrapy.Spider):
    name = "youtube_comments"
    allowed_domains = ["youtube.com", "httpbin.org"]
    
    def start_requests(self):
        yield scrapy.Request("https://httpbin.org/get", callback=self.parse, dont_filter=True)

    def parse(self, response):
        titles = [
            "Toàn cảnh bão siêu cấp Yagi đổ bộ",
            "Review iPhone 16 Pro Max sau 1 tháng sử dụng",
            "Làng Trong Phố Tập Cuối - Phim Truyền Hình VTV",
            "MẸO: 5 cách học Tiếng Anh cho người mất gốc",
            "Ca khúc mới nhất của Sơn Tùng M-TP [Official Video]",
            "Trực tiếp Bóng đá Việt Nam - Thái Lan Chung kết",
            "Vlog 1 ngày làm việc của Data Engineer tại VNG",
            "Sự thật về các khoá học làm giàu trên mạng",
            "Hướng dẫn nấu Phở Bò chuẩn vị Hà Nội",
            "Phân tích thị trường chứng khoán VN-Index tuần này"
        ]
        
        comments_pool = [
            "Video rất hay và ý nghĩa, cảm ơn tác giả.",
            "Tôi thấy chưa đồng tình với quan điểm ở phút 3:45.",
            "Tuyệt vời quá Việt Nam ơi!!!",
            "Xem xong thấy cuộc đời thật tươi đẹp hơn.",
            "Cho mình hỏi nhạc nền đoạn 2:10 là bài gì vậy ạ?",
            "Thực sự thất vọng về nội dung video này.",
            "Chúc kênh ngày càng phát triển nhé.",
            "Nội dung này rất bổ ích cho những người mới.",
            "Đừng clickbait nữa bạn ơi, nội dung không đúng tiêu đề.",
            "Hay quá, hóng phần 2 ạ."
        ]
        
        channels = ["VTV24", "Vật Vờ Studio", "Sơn Tùng M-TP Official", "Web5Ngay", "FAP TV", "PewPew", "MixiGaming"]

        for i in range(50):
            item = SocialItem()
            item["post_id"] = f"mock_yt_{i}"
            item["url"] = f"https://www.youtube.com/watch?v=mock{i}"
            item["title"] = random.choice(titles)
            item["content"] = "Mô tả video YouTube giả lập. " * 3
            item["author"] = random.choice(channels)
            item["source"] = "youtube_comments"
            item["category"] = "social_news"
            item["like_count"] = random.randint(1000, 1000000)
            item["upvote_ratio"] = 1.0
            item["reply_count"] = random.randint(100, 50000)
            
            top_comments = []
            for _ in range(random.randint(3, 8)):
                likes = random.randint(0, 5000)
                text = random.choice(comments_pool)
                top_comments.append(f"[{likes} likes] {text}")
                
            item["top_comments"] = top_comments
            
            random_hours = random.randint(0, 72)
            publish_time = datetime.now(timezone.utc) - timedelta(hours=random_hours)
            
            item["publish_time"] = publish_time.isoformat()
            item["crawl_time"] = datetime.now(timezone.utc).isoformat()
            
            yield item
