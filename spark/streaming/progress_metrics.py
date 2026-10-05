"""Small Prometheus endpoint for Spark Structured Streaming query progress."""

import logging
import os
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


logger = logging.getLogger(__name__)


def kafka_lag_from_sources(sources):
    """Return Spark's observed Kafka backlog, or None if offsets are unavailable."""
    total = 0
    observed = False
    for source in sources or []:
        latest = getattr(source, "latestOffset", None)
        end = getattr(source, "endOffset", None)
        if not latest or not end:
            continue
        try:
            latest = json.loads(latest) if isinstance(latest, str) else latest
            end = json.loads(end) if isinstance(end, str) else end
            for topic, partitions in latest.items():
                for partition, offset in partitions.items():
                    if topic in end and partition in end[topic]:
                        total += max(0, int(offset) - int(end[topic][partition]))
                        observed = True
        except (TypeError, ValueError, AttributeError):
            logger.warning("Cannot parse Spark Kafka source offsets", exc_info=True)
    return total if observed else None


class ProgressRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._queries = {}
        self._failed = {}
        self._active = {}
        self._total_rows = {}

    def started(self, name):
        with self._lock:
            self._active[name] = 1

    def record(self, progress):
        name = progress.name or str(progress.id)
        values = {
            "input_rows": float(progress.numInputRows),
            "input_rows_per_second": float(progress.inputRowsPerSecond),
            "processed_rows_per_second": float(progress.processedRowsPerSecond),
            "batch_duration_ms": float((progress.durationMs or {}).get("triggerExecution", 0)),
            "batch_id": float(progress.batchId),
            "last_progress_timestamp_seconds": time.time(),
        }
        lag = kafka_lag_from_sources(getattr(progress, "sources", []))
        if lag is not None:
            values["kafka_lag"] = float(lag)
        with self._lock:
            self._queries[name] = values
            self._active[name] = 1
            self._total_rows[name] = self._total_rows.get(name, 0) + progress.numInputRows
        logger.info("Spark progress query=%s batch=%s rows=%s duration_ms=%s",
                    name, progress.batchId, progress.numInputRows,
                    values["batch_duration_ms"])

    def terminated(self, name, failed):
        with self._lock:
            self._active[name] = 0
            if failed:
                self._failed[name] = self._failed.get(name, 0) + 1

    def render(self):
        with self._lock:
            queries = {name: values.copy() for name, values in self._queries.items()}
            failed = self._failed.copy()
            active = self._active.copy()
            total_rows = self._total_rows.copy()
        lines = []
        metrics = {
            "input_rows": "newspulse_spark_input_rows",
            "input_rows_per_second": "newspulse_spark_input_rows_per_second",
            "processed_rows_per_second": "newspulse_spark_processed_rows_per_second",
            "batch_duration_ms": "newspulse_spark_batch_duration_ms",
            "batch_id": "newspulse_spark_batch_id",
            "last_progress_timestamp_seconds": "newspulse_spark_last_progress_timestamp_seconds",
            "kafka_lag": "newspulse_spark_kafka_lag",
        }
        for field, metric in metrics.items():
            lines.append(f"# TYPE {metric} gauge")
            for name, values in sorted(queries.items()):
                if field not in values:
                    continue
                safe_name = name.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{metric}{{query="{safe_name}"}} {values[field]}')
        for metric, values, metric_type in (
            ("newspulse_spark_query_active", active, "gauge"),
            ("newspulse_spark_total_input_rows", total_rows, "counter"),
        ):
            lines.append(f"# TYPE {metric} {metric_type}")
            for name, value in sorted(values.items()):
                safe_name = name.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{metric}{{query="{safe_name}"}} {value}')
        lines.append("# TYPE newspulse_spark_query_failures_total counter")
        for name, count in sorted(failed.items()):
            safe_name = name.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'newspulse_spark_query_failures_total{{query="{safe_name}"}} {count}')
        return ("\n".join(lines) + "\n").encode()


def start_progress_monitor(spark, host="0.0.0.0", port=None):
    from pyspark.sql.streaming import StreamingQueryListener

    registry = ProgressRegistry()
    port = port or int(os.getenv("SPARK_PROGRESS_PORT", "9189"))

    class Listener(StreamingQueryListener):
        def __init__(self):
            super().__init__()
            self.names = {}

        def onQueryStarted(self, event):
            self.names[str(event.id)] = event.name or str(event.id)
            registry.started(self.names[str(event.id)])
            logger.info("Spark query started: %s", event.name)

        def onQueryProgress(self, event):
            registry.record(event.progress)

        def onQueryIdle(self, event):
            pass

        def onQueryTerminated(self, event):
            query_id = str(event.id)
            registry.terminated(self.names.pop(query_id, query_id), event.exception is not None)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/metrics":
                self.send_error(404)
                return
            body = registry.render()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    spark.streams.addListener(Listener())
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
