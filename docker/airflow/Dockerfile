FROM apache/airflow:2.8.1-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*
USER airflow

# Step 1: Install Airflow providers with constraints (ensures compatibility with 2.8.1)
ARG CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-2.8.1/constraints-3.11.txt"
RUN pip install --no-cache-dir -c "${CONSTRAINT_URL}" \
    apache-airflow-providers-openlineage \
    apache-airflow-providers-postgres \
    apache-airflow-providers-mongo \
    apache-airflow-providers-http

# Step 2: Install DAG dependencies (NOT the full requirements.txt — avoid SQLAlchemy conflict)
RUN pip install --no-cache-dir \
    psycopg2-binary==2.9.10 \
    pymongo==4.9.2 \
    kafka-python==2.0.2 \
    loguru==0.7.3 \
    underthesea==6.8.4 \
    regex==2024.11.6 \
    python-dotenv==1.0.1 \
    beautifulsoup4==4.12.3 \
    lxml==5.3.0 \
    scrapy==2.11.2 \
    fake-useragent==1.5.1 \
    feedparser==6.0.11 \
    itemadapter>=0.8.0