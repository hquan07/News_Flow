from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import clickhouse_connect
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import pandas as pd
import uuid

# Define Default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def run_topic_modeling():
    # Connect to ClickHouse (using the docker network hostname 'clickhouse')
    # Default port for clickhouse_connect is 8123 (HTTP)
    client = clickhouse_connect.get_client(host='clickhouse', port=8123, user='default', password='')
    
    # Get recent data from raw_articles
    query = """
        SELECT title, content, publish_time 
        FROM newspulse.raw_articles 
        WHERE publish_time >= now() - INTERVAL 4 HOUR 
          AND content != ''
    """
    df = client.query_df(query)
    
    if len(df) < 50:
        print(f"Not enough data for clustering: {len(df)} rows. Skipping...")
        return
        
    print(f"Clustering {len(df)} articles...")
    
    # TF-IDF
    vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(df['content'])
    
    # LDA
    num_topics = max(3, min(20, len(df) // 100)) # Dynamic number of topics (3 to 20)
    lda = LatentDirichletAllocation(n_components=num_topics, random_state=42)
    lda.fit(tfidf_matrix)
    
    # Get Topic Keywords
    feature_names = vectorizer.get_feature_names_out()
    
    # Assign documents to topics to count them
    topic_assignments = lda.transform(tfidf_matrix).argmax(axis=1)
    df['topic'] = topic_assignments
    
    # Build Insert Data
    insert_data = []
    
    for topic_idx, topic in enumerate(lda.components_):
        top_indices = topic.argsort()[:-11:-1]
        top_keywords = [feature_names[i] for i in top_indices]
        
        topic_articles = df[df['topic'] == topic_idx]
        article_count = len(topic_articles)
        
        if article_count == 0:
            continue
            
        cluster_id = str(uuid.uuid4())
        cluster_name = f"Topic: {', '.join(top_keywords[:3])}"
        start_time = topic_articles['publish_time'].min()
        end_time = topic_articles['publish_time'].max()
        
        insert_data.append([
            cluster_id,
            cluster_name,
            top_keywords,
            article_count,
            0.0, # Default avg_sentiment since we are not joining with sentiment table yet
            start_time.to_pydatetime() if hasattr(start_time, 'to_pydatetime') else start_time,
            end_time.to_pydatetime() if hasattr(end_time, 'to_pydatetime') else end_time,
            datetime.now()
        ])
        
    if insert_data:
        client.insert('newspulse.event_clusters', insert_data, column_names=[
            'cluster_id', 'cluster_name', 'top_keywords', 'article_count', 
            'avg_sentiment', 'start_time', 'end_time', 'created_at'
        ])
        print(f"Inserted {len(insert_data)} clusters to ClickHouse.")

with DAG(
    'dynamic_topic_modeling',
    default_args=default_args,
    description='A simple DAG for Event Clustering using TF-IDF and LDA',
    schedule_interval=timedelta(hours=4),
    catchup=False,
) as dag:
    
    topic_modeling_task = PythonOperator(
        task_id='run_topic_modeling',
        python_callable=run_topic_modeling,
    )
    
    topic_modeling_task
