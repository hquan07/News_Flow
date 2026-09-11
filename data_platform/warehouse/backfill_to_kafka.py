import os
import sys
import time
import socket
import struct
import logging
from pymongo import MongoClient

# Add /opt/airflow to path so we can import kafka_utils
sys.path.append("/opt/airflow")
from kafka_utils.producer import ArticleProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_host_ip():
    try:
        # Try host.docker.internal first
        return socket.gethostbyname('host.docker.internal')
    except Exception:
        # Fallback to docker bridge default gateway
        try:
            with open("/proc/net/route") as fh:
                for line in fh:
                    fields = line.strip().split()
                    if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                        continue
                    return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
        except Exception:
            pass
        return "172.17.0.1"

def run_backfill():
    MONGO_URI = os.getenv("MONGO_BACKFILL_URI", "mongodb://admin:Huyquan1607@localhost:27017/")
    MONGO_DB = os.getenv("MONGO_BACKFILL_DB", "newspulse")
    MONGO_COLLECTION = os.getenv("MONGO_BACKFILL_COL", "articles_raw_vi")

    logger.info(f"Connecting to MongoDB at {MONGO_URI}, DB: {MONGO_DB}, Col: {MONGO_COLLECTION}")
    
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.server_info() # trigger connection
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return

    db = mongo_client[MONGO_DB]
    collection = db[MONGO_COLLECTION]
    
    total_docs = collection.count_documents({})
    logger.info(f"Found {total_docs} documents in {MONGO_COLLECTION} to backfill.")
    
    if total_docs == 0:
        logger.info("Nothing to backfill.")
        return

    # Use localhost:29092 for Kafka which is exposed to host
    producer = ArticleProducer(bootstrap_servers="localhost:29092", schema_registry_url="http://localhost:8081")
    
    
    success_count = 0
    fail_count = 0

    cursor = collection.find({})
    for doc in cursor:
        if "_id" in doc:
            del doc["_id"]
        if "raw_html" in doc:
            del doc["raw_html"]
            
        success = producer.send_article(doc)
        if success:
            success_count += 1
        else:
            fail_count += 1
            
        if (success_count + fail_count) % 100 == 0:
            logger.info(f"Processed {success_count + fail_count}/{total_docs}...")

    producer.flush()
    logger.info(f"Backfill complete! Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    run_backfill()
