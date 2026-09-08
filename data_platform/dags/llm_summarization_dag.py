import os
import logging
from datetime import datetime, timedelta
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}

@dag(
    dag_id="llm_summarization_and_embedding",
    default_args=default_args,
    description="Batch Process: Tóm tắt bài báo bằng Groq Llama-3 và nhúng Vector",
    schedule="*/15 * * * *",  # Chạy mỗi 15 phút
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["ai", "llm", "rag"],
    max_active_runs=1,
)
def llm_pipeline():

    @task
    def fetch_unprocessed_articles():
        """Lấy các bài báo chưa được tóm tắt từ ClickHouse"""
        import clickhouse_connect
        import pandas as pd
        
        try:
            client = clickhouse_connect.get_client(host="clickhouse", port=8123, username="default", password="")
            
            # Lấy các bài báo chưa có trong bảng raw_article_summaries
            query = """
                SELECT a.url_hash, a.title, a.content 
                FROM newspulse.raw_articles a
                LEFT JOIN newspulse.raw_article_summaries s ON a.url_hash = s.url_hash
                WHERE s.url_hash = '' OR s.url_hash IS NULL
                ORDER BY a.loaded_at DESC
                LIMIT 50
            """
            df = client.query_df(query)
            if df.empty:
                logger.info("Không có bài báo mới nào cần xử lý.")
                return []
            
            return df.to_dict("records")
        except Exception as e:
            logger.error(f"Lỗi khi fetch dữ liệu từ ClickHouse: {e}")
            return []

    @task
    def generate_ai_metadata(articles: list):
        """Dùng Groq tóm tắt và SentenceTransformers tạo vector"""
        if not articles:
            return {"summaries": [], "embeddings": []}
            
        import os
        from groq import Groq
        from sentence_transformers import SentenceTransformer
        
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key or groq_api_key == "your_groq_api_key_here":
            logger.warning("GROQ_API_KEY chưa được cấu hình. Bỏ qua tóm tắt AI.")
            return {"summaries": [], "embeddings": []}

        # Khởi tạo clients
        groq_client = Groq(api_key=groq_api_key)
        # Tải mô hình embedding nhỏ gọn (chạy local trên CPU)
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        summaries_data = []
        embeddings_data = []
        
        for article in articles:
            url_hash = article["url_hash"]
            title = article["title"]
            content = str(article["content"])[:3000] # Giới hạn context để tránh quá token
            
            # 1. Tạo Tóm Tắt (Groq Llama-3)
            try:
                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": "Bạn là một biên tập viên tin tức xuất sắc. Hãy tóm tắt bài báo sau thành 2-3 câu ngắn gọn, súc tích và đúng trọng tâm nhất bằng tiếng Việt."
                        },
                        {
                            "role": "user",
                            "content": f"Tiêu đề: {title}\nNội dung: {content}"
                        }
                    ],
                    model="llama3-8b-8192",
                    temperature=0.3,
                    max_tokens=256,
                )
                summary_text = chat_completion.choices[0].message.content.strip()
                
                summaries_data.append({
                    "url_hash": url_hash,
                    "summary": summary_text,
                    "model_name": "llama3-8b-8192"
                })
            except Exception as e:
                logger.error(f"Lỗi khi gọi Groq API cho {url_hash}: {e}")
            
            # 2. Tạo Vector Embedding (Local)
            try:
                # Gộp tiêu đề và tóm tắt (hoặc đoạn đầu content) để làm context nhúng
                text_to_embed = f"{title}. {content[:500]}"
                vector = model.encode(text_to_embed).tolist()
                
                embeddings_data.append({
                    "url_hash": url_hash,
                    "embedding": vector,
                    "model_name": "all-MiniLM-L6-v2"
                })
            except Exception as e:
                logger.error(f"Lỗi khi tạo Embedding cho {url_hash}: {e}")
                
        return {
            "summaries": summaries_data,
            "embeddings": embeddings_data
        }

    @task
    def save_to_clickhouse(ai_data: dict):
        """Lưu kết quả AI ngược lại vào ClickHouse"""
        summaries = ai_data.get("summaries", [])
        embeddings = ai_data.get("embeddings", [])
        
        if not summaries and not embeddings:
            logger.info("Không có dữ liệu AI nào để lưu.")
            return
            
        import clickhouse_connect
        
        try:
            client = clickhouse_connect.get_client(host="clickhouse", port=8123, username="default", password="")
            
            # Lưu Summaries
            if summaries:
                client.insert("newspulse.raw_article_summaries", 
                              [[s["url_hash"], s["summary"], s["model_name"]] for s in summaries],
                              column_names=["url_hash", "summary", "model_name"])
                logger.info(f"Đã lưu {len(summaries)} bản tóm tắt vào ClickHouse.")
                
            # Lưu Embeddings
            if embeddings:
                client.insert("newspulse.raw_article_embeddings", 
                              [[e["url_hash"], e["embedding"], e["model_name"]] for e in embeddings],
                              column_names=["url_hash", "embedding", "model_name"])
                logger.info(f"Đã lưu {len(embeddings)} vectors vào ClickHouse.")
                
        except Exception as e:
            logger.error(f"Lỗi khi ghi dữ liệu AI vào ClickHouse: {e}")

    # Flow
    articles = fetch_unprocessed_articles()
    ai_data = generate_ai_metadata(articles)
    save_to_clickhouse(ai_data)

# Init DAG
dag = llm_pipeline()
