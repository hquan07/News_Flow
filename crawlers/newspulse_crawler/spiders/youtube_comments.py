import scrapy
import os
import logging
from datetime import datetime, timezone
from newspulse_crawler.items import SocialItem
from dotenv import load_dotenv

try:
    from googleapiclient.discovery import build
except ImportError:
    build = None

load_dotenv()
logger = logging.getLogger(__name__)

class YoutubeCommentsSpider(scrapy.Spider):
    name = "youtube_comments"
    allowed_domains = ["youtube.com"]
    # Bắt đầu bằng 1 video ID hoặc danh sách các video ID thời sự
    start_urls = ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"] # Placeholder, can be dynamically fed
    
    def __init__(self, *args, **kwargs):
        super(YoutubeCommentsSpider, self).__init__(*args, **kwargs)
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        
        if build and self.api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            except Exception as e:
                self.youtube = None
                logger.error(f"Failed to initialize YouTube API: {e}")
        else:
            self.youtube = None

    def parse(self, response):
        if not self.youtube:
            logger.error("YouTube API configuration is missing (YOUTUBE_API_KEY) or google-api-python-client not installed.")
            return

        # Extract video_id from URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID)
        video_id = response.url.split("v=")[-1].split("&")[0]
        
        try:
            # 1. Lấy thông tin video (Title, View count)
            video_response = self.youtube.videos().list(
                part="snippet,statistics",
                id=video_id
            ).execute()
            
            if not video_response.get("items"):
                return
                
            video_info = video_response["items"][0]
            video_title = video_info["snippet"]["title"]
            video_desc = video_info["snippet"]["description"]
            channel_name = video_info["snippet"]["channelTitle"]
            
            # 2. Lấy top comments
            comment_response = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                order="relevance",
                maxResults=20
            ).execute()
            
            top_comments = []
            for item in comment_response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                text = snippet["textDisplay"]
                like_count = snippet["likeCount"]
                # Ưu tiên những comment có like cao làm Social Sentiment
                if text:
                    top_comments.append(f"[{like_count} likes] {text}")

            social_item = SocialItem()
            social_item["post_id"] = video_id
            social_item["url"] = response.url
            social_item["title"] = video_title
            social_item["content"] = video_desc
            social_item["author"] = channel_name
            social_item["source"] = "youtube_comments"
            social_item["category"] = "social_news"
            social_item["like_count"] = int(video_info["statistics"].get("likeCount", 0))
            social_item["upvote_ratio"] = 1.0 # YouTube đã bỏ đếm dislike public
            social_item["reply_count"] = int(video_info["statistics"].get("commentCount", 0))
            social_item["top_comments"] = top_comments
            social_item["publish_time"] = video_info["snippet"]["publishedAt"]
            social_item["crawl_time"] = datetime.now(timezone.utc).isoformat()
            
            yield social_item
            
        except Exception as e:
            logger.error(f"Error fetching YouTube data for {video_id}: {e}")
