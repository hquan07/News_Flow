import os

BOT_NAME = "newspulse_crawler"
SPIDER_MODULES = ["newspulse_crawler.spiders"]
NEWSPIDER_MODULE = "newspulse_crawler.spiders"

# Respectful crawling
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = int(os.getenv("CRAWL_RATE_LIMIT", 2))
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = 30

# User Agent
USER_AGENT = os.getenv("USER_AGENT", "NewsPulse/1.0 (+https://github.com/newspulse)")

# Pipelines (order matters)
ITEM_PIPELINES = {
    "newspulse_crawler.pipelines.DedupPipeline": 100,
    "newspulse_crawler.pipelines.CleanTextPipeline": 200,
    "newspulse_crawler.pipelines.MongoPipeline": 300,
    "newspulse_crawler.pipelines.KafkaPipeline": 400,
}

# Middlewares
DOWNLOADER_MIDDLEWARES = {
    "newspulse_crawler.middlewares.RotateUserAgentMiddleware": 400,
}

# Auto-throttle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

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