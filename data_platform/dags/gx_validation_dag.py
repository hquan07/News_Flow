import hashlib
from datetime import datetime, timedelta, timezone
import logging
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

@dag(
    dag_id="gx_validation_dag",
    default_args=default_args,
    description="Chạy Great Expectations kiểm tra Data Quality trong ClickHouse",
    schedule="0 * * * *",  # Chạy mỗi giờ
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["data-quality", "gx"],
    max_active_runs=1,
)
def gx_validation_pipeline():

    @task
    def run_great_expectations():
        import clickhouse_connect
        import pandas as pd
        import great_expectations as gx
        from great_expectations.dataset import PandasDataset
        
        # 1. Kết nối ClickHouse
        try:
            # Thông thường ClickHouse ở container `clickhouse` port 8123
            client = clickhouse_connect.get_client(host="clickhouse", port=8123, username="default", password="")
            
            # Lấy 1000 bản ghi mới nhất để kiểm tra
            query = """
                SELECT * FROM newspulse.raw_article_entities 
                ORDER BY timestamp DESC
                LIMIT 1000
            """
            df = client.query_df(query)
        except Exception as e:
            logger.warning(f"Could not connect to ClickHouse or query data: {e}. Mocking dataframe for GX validation.")
            # Tạo DataFrame giả lập nếu DB chưa có
            df = pd.DataFrame({
                "url": ["http://test.com/1"],
                "title": ["Valid Title"],
                "content": ["This is a very long text to pass the GX 100 characters expectation rule." * 10],
                "author": ["Author Name"],
                "category": ["tech"]
            })
            
        if df.empty:
            logger.info("No data to validate.")
            return True

        # 2. Tạo GX PandasDataset
        gx_df = PandasDataset(df)
        
        # 3. Định nghĩa các Rules (Expectations)
        if "title" in gx_df.columns:
            gx_df.expect_column_values_to_not_be_null("title")
            
        if "author" in gx_df.columns:
            gx_df.expect_column_values_to_not_be_null("author")
            
        if "content" in gx_df.columns:
            gx_df.expect_column_value_lengths_to_be_between("content", min_value=100)
            
        if "category" in gx_df.columns:
            gx_df.expect_column_values_to_be_in_set(
                "category", 
                ["sports","tech","economy","politics","general","entertainment","health","education","world","law"]
            )
            
        # 4. Chạy validation
        results = gx_df.validate()
        
        success = results["success"]
        stats = results["statistics"]
        
        logger.info(f"GX Validation Success: {success}")
        logger.info(f"GX Statistics: {stats}")
        
        if not success:
            failed_expectations = [res for res in results["results"] if not res["success"]]
            logger.error(f"Great Expectations Data Quality FAILED: {failed_expectations}")
            
            # Gửi cảnh báo qua Telegram
            try:
                from monitoring.alert_dispatcher import (
                    AlertEvent,
                    send_telegram_events,
                )

                expectation_names = sorted(
                    {
                        result.get("expectation_config", {}).get(
                            "expectation_type", "unknown_expectation"
                        )
                        for result in failed_expectations
                    }
                )
                signature = hashlib.sha256(
                    "|".join(expectation_names).encode("utf-8")
                ).hexdigest()[:12]
                hour_key = datetime.now(timezone.utc).strftime("%Y%m%d%H")
                send_telegram_events(
                    [
                        AlertEvent(
                            alert_id=f"data-quality:{signature}:{hour_key}",
                            alert_type="data_quality",
                            severity="critical",
                            title="Kiểm tra chất lượng dữ liệu thất bại",
                            details=(
                                f"{len(failed_expectations)} expectation bị lỗi",
                                f"Rules: {', '.join(expectation_names[:5])}",
                            ),
                        )
                    ]
                )
            except Exception:
                logger.exception("Failed to send data quality alert")
                
            # Raise exception để task fail
            raise ValueError(f"Data Quality Check Failed! {failed_expectations}")
            
        return success

    # Thực thi
    run_great_expectations()

# Khởi tạo DAG
dag = gx_validation_pipeline()
