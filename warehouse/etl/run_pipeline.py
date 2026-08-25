from loguru import logger

from warehouse.etl import raw_to_staging
from warehouse.etl import staging_to_warehouse
from warehouse.etl import warehouse_to_mart


def run_full_pipeline():
    logger.info("=" * 60)
    logger.info("NewsPulse ELT Pipeline — Starting")
    logger.info("=" * 60)

    # Step 1
    staged_count = raw_to_staging.run()

    # Step 2
    fact_count = staging_to_warehouse.run()

    # Step 3
    warehouse_to_mart.run()

    logger.info("=" * 60)
    logger.info(
        f"ELT Pipeline Complete — "
        f"staged: {staged_count}, facts: {fact_count}"
    )
    logger.info("=" * 60)

    return {"staged": staged_count, "facts": fact_count}


if __name__ == "__main__":
    run_full_pipeline()