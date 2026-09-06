import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

logger = logging.getLogger(__name__)

SPIDER_NAMES = ["vnexpress", "tuoitre", "thanhnien", "dantri", "laodong", "tienphong"]


def run_all():
    settings = get_project_settings()
    process = CrawlerProcess(settings)

    for spider_name in SPIDER_NAMES:
        logger.info("Starting spider: %s", spider_name)
        process.crawl(spider_name)

    process.start()


def run_spider(name: str):
    if name not in SPIDER_NAMES:
        raise ValueError(f"Unknown spider: {name}. Available: {SPIDER_NAMES}")

    settings = get_project_settings()
    process = CrawlerProcess(settings)
    process.crawl(name)
    process.start()


if __name__ == "__main__":
    run_all()