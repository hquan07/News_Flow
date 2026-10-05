import importlib.util
from types import SimpleNamespace
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "progress_metrics", Path(__file__).resolve().parents[1] / "spark/streaming/progress_metrics.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ProgressRegistry = module.ProgressRegistry


def test_progress_registry_exposes_batch_rates_and_failure_counter():
    registry = ProgressRegistry()
    registry.record(SimpleNamespace(
        name="news_raw", id="q1", numInputRows=25,
        inputRowsPerSecond=5, processedRowsPerSecond=4,
        durationMs={"triggerExecution": 1200}, batchId=7,
    ))
    registry.terminated("news_raw", failed=True)
    output = registry.render().decode()
    assert 'newspulse_spark_input_rows{query="news_raw"} 25.0' in output
    assert 'newspulse_spark_batch_duration_ms{query="news_raw"} 1200.0' in output
    assert 'newspulse_spark_query_failures_total{query="news_raw"} 1' in output
