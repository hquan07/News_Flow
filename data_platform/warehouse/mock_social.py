import json
import time
import random
from datetime import datetime, timedelta
from kafka import KafkaProducer

KAFKA_BROKER = "kafka:9092"
TOPIC = "social_posts"

def generate_mock_social():
    sources = ["facebook", "youtube", "tiktok", "twitter"]
    sentiments = ["positive", "negative", "neutral"]
    
    events = []
    now = datetime.utcnow()
    
    for i in range(150):
        # Generate data for the past 24 hours
        pub_time = now - timedelta(minutes=random.randint(0, 24 * 60))
        source = random.choice(sources)
        like_count = random.randint(10, 10000)
        reply_count = int(like_count * random.uniform(0.01, 0.5))
        
        event = {
            "post_id": f"mock_post_{i}",
            "source": source,
            "title": f"Discussing the latest news on {source} #{i}",
            "content": "This is a simulated social media comment or post reacting to recent events.",
            "like_count": like_count,
            "upvote_ratio": random.uniform(0.5, 1.0),
            "reply_count": reply_count,
            "sentiment_score": random.uniform(-1.0, 1.0),
            "sentiment_label": random.choice(sentiments),
            "publish_time": pub_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "crawl_time": now.strftime("%Y-%m-%dT%H:%M:%S")
        }
        events.append(event)
    return events

if __name__ == "__main__":
    print(f"Connecting to Kafka at {KAFKA_BROKER}")
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    events = generate_mock_social()
    for e in events:
        producer.send(TOPIC, e)
    
    producer.flush()
    print(f"Successfully pushed {len(events)} mock social events to {TOPIC}")
