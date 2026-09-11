import sys
sys.path.append('/opt/spark-apps')
import time
import multiprocessing
import clickhouse_connect
import re

from spark.processing.sentiment_pipeline import analyze_sentiment
from spark.processing.ner_pipeline import extract_entities
from spark.processing.keyword_extractor import extract_keywords_tfidf

def get_client():
    return clickhouse_connect.get_client(host="clickhouse", port=8123, username="admin", password="admin123", database="newspulse")

def clean_text(text: str) -> str:
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def process_batch(batch):
    sentiment_rows = []
    entities_rows = []
    keywords_rows = []
    for url_hash, title, content in batch:
        try:
            content_clean = clean_text(content)
            combined_text = f"{title} {content_clean}"
            
            # 1. Sentiment
            sentiment = analyze_sentiment(combined_text)
            sentiment_rows.append([url_hash, sentiment.get("sentiment_score", 0.0), sentiment.get("sentiment_label", "neutral")])
            
            # 2. Entities
            entities = extract_entities(content_clean)
            for e in entities:
                entities_rows.append([url_hash, e["entity"], e["entity_type"], e["label"]])
                
            # 3. Keywords
            keywords = extract_keywords_tfidf(content_clean)
            for k_str, k_score in keywords:
                keywords_rows.append([url_hash, k_str, float(k_score)])
                
        except Exception as e:
            print(f"Error processing {url_hash}: {e}", file=sys.stderr)
            
    return sentiment_rows, entities_rows, keywords_rows

def main():
    print("Connecting to ClickHouse...")
    client = get_client()
    
    print("Fetching all url_hashes from raw_articles...")
    all_articles = client.query("SELECT url_hash, title, content FROM newspulse.raw_articles").result_rows
    
    print("Fetching processed url_hashes from raw_article_sentiment...")
    processed = client.query("SELECT DISTINCT url_hash FROM newspulse.raw_article_sentiment").result_rows
    processed_set = set(row[0] for row in processed)
    
    to_process = [row for row in all_articles if row[0] not in processed_set]
    print(f"Total articles: {len(all_articles)}")
    print(f"Already processed: {len(processed_set)}")
    print(f"To process: {len(to_process)}")
    
    if not to_process:
        print("All articles are processed!")
        return
        
    # We use small batches to commit frequently
    BATCH_SIZE = 100
    batches = [to_process[i:i + BATCH_SIZE] for i in range(0, len(to_process), BATCH_SIZE)]
    print(f"Split into {len(batches)} batches of {BATCH_SIZE} articles.")
    
    pool_size = min(4, multiprocessing.cpu_count())
    print(f"Starting multiprocessing pool with {pool_size} workers...")
    
    processed_count = 0
    start_time = time.time()
    
    # We close the client before entering multiprocessing because we don't want to share socket state
    client.close()
    
    # Re-initialize client for inserting results
    write_client = get_client()
    
    with multiprocessing.Pool(pool_size) as pool:
        for idx, (s_rows, e_rows, k_rows) in enumerate(pool.imap_unordered(process_batch, batches)):
            try:
                if s_rows:
                    write_client.insert('newspulse.raw_article_sentiment', s_rows, column_names=['url_hash', 'sentiment_score', 'sentiment_label'])
                if e_rows:
                    write_client.insert('newspulse.raw_article_entities', e_rows, column_names=['url_hash', 'entity', 'entity_type', 'label'])
                if k_rows:
                    write_client.insert('newspulse.raw_article_keywords', k_rows, column_names=['url_hash', 'keyword', 'score'])
                    
                processed_count += len(s_rows)
                elapsed = time.time() - start_time
                rate = processed_count / elapsed if elapsed > 0 else 0
                
                print(f"Inserted batch {idx+1}/{len(batches)}. Total processed: {processed_count}/{len(to_process)}. Rate: {rate:.2f} articles/s")
            except Exception as e:
                print(f"Error inserting batch {idx+1}: {e}", file=sys.stderr)

    write_client.close()
    print("Backfill complete!")

if __name__ == "__main__":
    # Disable transformers warnings
    import os
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"
    main()
