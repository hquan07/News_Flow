import json
import os
from pymongo import MongoClient
from datetime import datetime

def push_to_mongo():
    dump_file = "/home/hquan07/News_Flow/data_platform/warehouse/articles_dump.json"
    
    if not os.path.exists(dump_file):
        print(f"Dump file not found: {dump_file}")
        return

    # Connect to MongoDB on localhost mapped port
    uri = "mongodb://localhost:27018/"
    client = MongoClient(uri)
    
    db = client["newspulse"]
    collection = db["articles_raw"]

    print("Loading JSON data...")
    data = []
    with open(dump_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
        
    print(f"Loaded {len(data)} articles. Inserting into MongoDB 'newspulse.articles_raw'...")
    
    if not data:
        print("No data to insert.")
        return
        
    # Insert in batches to avoid payload too large
    batch_size = 5000
    total_inserted = 0
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        
        # We need to remove _id if it's there so MongoDB creates a new one or keeps it if it doesn't conflict
        for doc in batch:
            if '_id' in doc:
                del doc['_id']
            # Reconstruct datetime objects for fields that end with _time or _at or _date if needed
            if 'publish_time' in doc and isinstance(doc['publish_time'], str):
                try:
                    # Remove Z if it's there to support fromisoformat in older pythons
                    clean_str = doc['publish_time'].replace('Z', '+00:00')
                    doc['publish_time'] = datetime.fromisoformat(clean_str)
                except Exception as e:
                    pass
            if 'crawl_time' in doc and isinstance(doc['crawl_time'], str):
                try:
                    clean_str = doc['crawl_time'].replace('Z', '+00:00')
                    doc['crawl_time'] = datetime.fromisoformat(clean_str)
                except:
                    pass
        
        collection.insert_many(batch)
        total_inserted += len(batch)
        print(f"Inserted {total_inserted}/{len(data)}...")
        
    print("Done inserting to MongoDB!")

if __name__ == "__main__":
    push_to_mongo()
