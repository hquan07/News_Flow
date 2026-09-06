FROM apache/spark:3.5.3-python3

USER root

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch (CPU version to keep image size small) and other NLP/Kafka dependencies
RUN pip3 install --no-cache-dir \
    networkx==3.1 \
    torch==2.1.2+cpu \
    -f https://download.pytorch.org/whl/torch_stable.html \
    transformers==4.36.2 \
    onnxruntime==1.16.3 \
    optimum==1.16.2 \
    loguru==0.7.3 \
    kafka-python==2.0.2 \
    clickhouse-connect==0.6.8 \
    underthesea

# Create directory for Hugging Face cache and set permissions so spark user can write to it
RUN mkdir -p /tmp/hf_cache && \
    chown -R spark:spark /tmp/hf_cache && \
    chmod -R 777 /tmp/hf_cache

USER spark

ENV HF_HOME="/tmp/hf_cache"
ENV TRANSFORMERS_CACHE="/tmp/hf_cache"