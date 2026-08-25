# 1. KHỞI ĐỘNG INFRASTRUCTURE

cd ~/News_Flow

# Cách 1: Dùng start.sh (khởi động tất cả 4 phases tự động)
./start.sh

# Cách 2: Khởi động thủ công từng service
docker compose up -d zookeeper
sleep 10
docker compose up -d kafka
sleep 20
docker compose up -d mongo postgres
sleep 10
docker compose up -d kafka-init           # Tạo 10 Kafka topics
sleep 15
docker compose up -d airflow-db
sleep 10
docker compose up -d airflow-init         # Migration + tạo admin user
sleep 10
docker compose up -d airflow-webserver airflow-scheduler
sleep 30


# 2. CRAWL DATA

# Crawl VnExpress
docker compose exec -T airflow-scheduler bash -c "
    cd /opt/airflow/crawlers && scrapy crawl vnexpress
"

# Crawl Tuổi Trẻ
docker compose exec -T airflow-scheduler bash -c "
    cd /opt/airflow/crawlers && scrapy crawl tuoitre
"

# Crawl Thanh Niên
docker compose exec -T airflow-scheduler bash -c "
    cd /opt/airflow/crawlers && scrapy crawl thanhnien
"

# Verify MongoDB có data
docker compose exec -T mongo mongosh --quiet --eval \
    "db.getSiblingDB('newspulse').articles_raw.countDocuments()"


# 3. ELT PIPELINE (MongoDB → raw → staging → warehouse → mart)

# Bước 3a: Load MongoDB → PostgreSQL raw.articles
docker compose exec -T airflow-scheduler bash -c "
    cd /opt/airflow
    python -c 'from warehouse.mongo_to_raw import run; run()'
"

# Bước 3b: Chạy full ELT pipeline (raw → staging → warehouse → mart)
docker compose exec -T airflow-scheduler bash -c "
    cd /opt/airflow
    python -c 'from warehouse.etl.run_pipeline import run_full_pipeline; run_full_pipeline()'
"

# Verify data qua từng layer
docker exec $(docker compose ps -q postgres) \
    psql -U newspulse -d newspulse -t -A -c "
    SELECT 'raw.articles' AS tbl, COUNT(*) FROM raw.articles
    UNION ALL SELECT 'staging.articles', COUNT(*) FROM staging.articles
    UNION ALL SELECT 'warehouse.fact_article', COUNT(*) FROM warehouse.fact_article
    UNION ALL SELECT 'mart.daily_overview', COUNT(*) FROM mart.daily_overview
    UNION ALL SELECT 'mart.hourly_distribution', COUNT(*) FROM mart.hourly_distribution;
"


# 4. KHỞI ĐỘNG SERVING LAYER

# FastAPI
docker compose up -d api

# Metabase
docker compose up -d metabase
# Chờ 90 giây cho Metabase khởi động (JVM)
sleep 90

# Superset
docker compose up -d superset
sleep 30

# Superset: tạo admin user (chỉ lần đầu)
docker compose exec -T superset superset fab create-admin \
    --username admin --firstname Admin --lastname NP \
    --email admin@local --password admin
docker compose exec -T superset superset db upgrade
docker compose exec -T superset superset init


# 5. TRUY CẬP SERVICES

# Airflow UI:   http://localhost:8081  (admin/admin)
# FastAPI Docs: http://localhost:8000/docs
# Metabase:     http://localhost:3000
# Superset:     http://localhost:8088  (admin/admin)
# Spark UI:     http://localhost:8082



# 8. DASHBOARD QUERIES (dùng trong Metabase/Superset)

# Overview — Bài viết theo nguồn & category
# SELECT source, category, SUM(article_count) AS total
# FROM mart.daily_overview
# GROUP BY source, category ORDER BY total DESC;

# Hourly Distribution — Phân bổ theo giờ
# SELECT hour, source, SUM(article_count) AS total
# FROM mart.hourly_distribution
# GROUP BY hour, source ORDER BY hour;

# Source Comparison — So sánh giữa các báo
# SELECT source, SUM(total_articles) AS articles,
#        ROUND(AVG(avg_word_count)) AS avg_words
# FROM mart.source_comparison
# GROUP BY source;

# Daily Trend — Xu hướng theo ngày
# SELECT date, source, SUM(article_count) AS total
# FROM mart.daily_overview
# GROUP BY date, source ORDER BY date;

# Category Distribution
# SELECT dc.name AS category, COUNT(*) AS cnt
# FROM warehouse.fact_article fa
# JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
# GROUP BY dc.name ORDER BY cnt DESC;


# 9. CẬP NHẬT DATA (chạy lại khi cần)

# Crawl mới → load → ELT (3 lệnh)
docker compose exec -T airflow-scheduler bash -c "
    cd /opt/airflow/crawlers && scrapy crawl vnexpress && scrapy crawl tuoitre
"
docker compose exec -T airflow-scheduler bash -c "
    cd /opt/airflow && python -c 'from warehouse.mongo_to_raw import run; run()'
"
docker compose exec -T airflow-scheduler bash -c "
    cd /opt/airflow && python -c 'from warehouse.elt.run_pipeline import run_full_pipeline; run_full_pipeline()'
"


# 10. QUẢN LÝ & MONITORING

# Xem trạng thái tất cả containers
docker compose ps

# Xem logs của service cụ thể
docker compose logs -f <service>    # service: kafka, postgres, airflow-scheduler, api, metabase, superset

# Restart một service
docker compose restart <service>

# Dừng tất cả (giữ data)
docker compose down

# Dừng tất cả + xóa data (reset hoàn toàn)
docker compose down -v

# Apply performance indexes (sau khi có data)
docker exec $(docker compose ps -q postgres) \
    psql -U newspulse -d newspulse -f /opt/airflow/warehouse/7_performance_indexes.sql

# Quick health check
docker exec $(docker compose ps -q postgres) \
    psql -U newspulse -d newspulse -c "
    SELECT 'fact_article' AS tbl, COUNT(*) FROM warehouse.fact_article
    UNION ALL SELECT 'dim_source', COUNT(*) FROM warehouse.dim_source
    UNION ALL SELECT 'dim_category', COUNT(*) FROM warehouse.dim_category;
"


# 11. TROUBLESHOOTING

# Kafka crash (InconsistentClusterIdException):
docker compose rm -f kafka
docker volume rm news_flow_kafka-data news_flow_zookeeper-data
docker compose up -d zookeeper && sleep 10 && docker compose up -d kafka

# Metabase migration lock:
docker compose rm -f metabase
docker volume rm news_flow_metabase-data
docker compose up -d metabase

# PostgreSQL connection refused:
docker compose restart postgres && sleep 10

# Airflow DAG not showing:
docker compose restart airflow-scheduler

# Spark không kết nối Kafka/PostgreSQL:
# → Spark compose dùng network riêng, cần fix theo FIX_SPARK_NETWORK.md
