import json
import logging
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def dump():
    MONGO_URI = "mongodb://admin:Huyquan1607@localhost:27017/"
    MONGO_DB = "newspulse"
    MONGO_COLLECTION = "articles_raw_vi"

    logger.info(f"Connecting to MongoDB at {MONGO_URI}")
    
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return

    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]
    
    total = collection.count_documents({})
    logger.info(f"Found {total} documents.")
    
    with open("articles_dump.json", "w", encoding="utf-8") as f:
        count = 0
        for doc in collection.find({}):
            if "_id" in doc:
                del doc["_id"]
            if "raw_html" in doc:
                del doc["raw_html"]
            # datetime to string
            for k, v in doc.items():
                if hasattr(v, "isoformat"):
                    doc[k] = v.isoformat()
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            count += 1
            if count % 1000 == 0:
                logger.info(f"Dumped {count}/{total}")
    logger.info("Dump complete!")

if __name__ == "__main__":
    dump()
