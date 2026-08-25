import os
import sys

from loguru import logger


def setup_logging(
    service_name: str = "newspulse",
    log_dir: str = "logs",
    log_level: str = "INFO",
    rotation: str = "50 MB",
    retention: str = "7 days",
    json_logs: bool = False,
) -> None:
    log_level = os.getenv("LOG_LEVEL", log_level).upper()
    os.makedirs(log_dir, exist_ok=True)

    # Remove default logger
    logger.remove()

    # Console format — human-readable
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[service]}</cyan> | "
        "<level>{message}</level>"
    )

    # JSON format cho file — machine-parseable
    json_format = (
        '{{"timestamp":"{time:YYYY-MM-DDTHH:mm:ss.SSSZ}",'
        '"level":"{level}",'
        '"service":"{extra[service]}",'
        '"module":"{module}",'
        '"function":"{function}",'
        '"line":{line},'
        '"message":"{message}"}}'
    )

    file_format = json_format if json_logs else (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{extra[service]} | {module}:{function}:{line} | {message}"
    )

    # Console handler
    logger.add(
        sys.stderr,
        format=console_format,
        level=log_level,
        colorize=True,
    )

    # Service-specific log file
    logger.add(
        os.path.join(log_dir, f"{service_name}.log"),
        format=file_format,
        level=log_level,
        rotation=rotation,
        retention=retention,
        compression="gz",
        enqueue=True,  # Thread-safe
    )

    # Error-only log file (tất cả services ghi chung)
    logger.add(
        os.path.join(log_dir, "errors.log"),
        format=file_format,
        level="ERROR",
        rotation=rotation,
        retention="30 days",
        compression="gz",
        enqueue=True,
    )

    # Bind service name cho context
    logger.configure(extra={"service": service_name})

    logger.info(f"Logging initialized for '{service_name}' at level {log_level}")


# Convenience
def get_crawler_logger():
    setup_logging(service_name="crawler")
    return logger


def get_spark_logger():
    setup_logging(service_name="spark")
    return logger


def get_api_logger():
    setup_logging(service_name="api")
    return logger


def get_pipeline_logger():
    setup_logging(service_name="pipeline")
    return logger