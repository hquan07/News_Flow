import json
import logging
import os

from pymongo import MongoClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def dump():
    mongo_uri = os.getenv("MONGO_BACKFILL_URI", "mongodb://localhost:27017/")
    mongo_db = os.getenv("MONGO_BACKFILL_DB", "newspulse")
    mongo_collection = os.getenv("MONGO_BACKFILL_COL", "articles_raw_vi")

    logger.info("Connecting to MongoDB, DB: %s, Col: %s", mongo_db, mongo_collection)
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.server_info()
    except Exception as exc:
        logger.error("Failed to connect: %s", type(exc).__name__)
        return

    db = client[mongo_db]
    collection = db[mongo_collection]
    total = collection.count_documents({})
    logger.info("Found %d documents", total)

    with open("articles_dump.json", "w", encoding="utf-8") as output:
        for count, doc in enumerate(collection.find({}), start=1):
            doc.pop("_id", None)
            for key, value in doc.items():
                if hasattr(value, "isoformat"):
                    doc[key] = value.isoformat()
            output.write(json.dumps(doc, ensure_ascii=False) + "\n")
            if count % 1000 == 0:
                logger.info("Dumped %d/%d", count, total)
    client.close()
    logger.info("Dump complete")


if __name__ == "__main__":
    dump()
