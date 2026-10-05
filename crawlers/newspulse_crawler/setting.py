import os

BOT_NAME = "newspulse_crawler"
SPIDER_MODULES = ["newspulse_crawler.spiders"]
NEWSPIDER_MODULE = "newspulse_crawler.spiders"

# Respectful crawling
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = int(os.getenv("CRAWL_CONCURRENT_REQUESTS", 32))
CONCURRENT_REQUESTS_PER_DOMAIN = int(os.getenv("CRAWL_CONCURRENT_REQUESTS_PER_DOMAIN", 4))
DOWNLOAD_DELAY = float(os.getenv("CRAWL_RATE_LIMIT", 0.5))
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = 30
CONCURRENT_ITEMS = int(os.getenv("CRAWL_CONCURRENT_ITEMS", 100))
RSS_MAX_AGE_HOURS = float(os.getenv("RSS_MAX_AGE_HOURS", 1))
PERSISTENT_DEDUP_ENABLED = os.getenv("PERSISTENT_DEDUP_ENABLED", "true").lower() == "true"

# User Agent
USER_AGENT = os.getenv("USER_AGENT", "NewsPulse/1.0 (+https://github.com/newspulse)")

# Pipelines (order matters)
ITEM_PIPELINES = {
    "newspulse_crawler.pipelines.DedupPipeline": 100,
    "newspulse_crawler.pipelines.CleanTextPipeline": 200,
    "newspulse_crawler.pipelines.FreshnessPipeline": 225,
    "newspulse_crawler.pipelines.MinIOPipeline": 250,
    "newspulse_crawler.pipelines.KafkaPipeline": 300,
    # Mongo is the completion marker used by persistent URL deduplication.
    "newspulse_crawler.pipelines.MongoPipeline": 400,
}

# Middlewares
DOWNLOADER_MIDDLEWARES = {
    "newspulse_crawler.middlewares.RotateUserAgentMiddleware": 400,
    # 'newspulse_crawler.middlewares.MockProxyMiddleware': 410,
}

SPIDER_MIDDLEWARES = {
    "newspulse_crawler.middlewares.ExistingUrlFilterMiddleware": 100,
}

# Auto-throttle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 8
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# Respect ETag/Last-Modified on feeds and avoid repeatedly downloading unchanged pages.
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 300
HTTPCACHE_POLICY = "scrapy.extensions.httpcache.RFC2616Policy"
HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"
HTTPCACHE_DIR = os.getenv("HTTPCACHE_DIR", "/tmp/newspulse-httpcache")

# Retry
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Logging
LOG_LEVEL = os.getenv("SCRAPY_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# Kafka / Mongo config (read from env)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB = os.getenv("MONGO_DB", "newspulse")

# Feed exports (disabled - we use custom pipelines)
FEEDS = {}

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
