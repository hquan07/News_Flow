import psycopg2

from config.spark_config import (
    PG_HOST,
    PG_PORT,
    PG_DB,
    PG_USER,
    PG_PASSWORD,
)


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )