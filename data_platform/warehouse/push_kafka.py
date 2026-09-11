import json
import logging
import sys

sys.path.append("/opt/airflow")
from kafka_utils.producer import ArticleProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def push():
    producer = ArticleProducer(bootstrap_servers="kafka:9092")
    
    success_count = 0
    fail_count = 0
    
    with open("/opt/airflow/warehouse/articles_dump.json", "r", encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            success = producer.send_article(doc)
            if success:
                success_count += 1
            else:
                fail_count += 1
                
            if (success_count + fail_count) % 100 == 0:
                logger.info(f"Pushed {success_count + fail_count}...")
                
    producer.flush()
    logger.info(f"Push complete! Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    push()
