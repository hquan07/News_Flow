import os
import hashlib
from pathlib import Path
from threading import Lock
from pyspark.sql import DataFrame
from pyspark.sql.functions import udf
from pyspark.sql.types import FloatType
from loguru import logger
from groq import Groq

# Initialize Groq client only once per executor
_groq_client = None
_groq_client_key_fingerprint = None
_circuit_lock = Lock()
_disabled_logged = False


def _key_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def _circuit_breaker_path() -> Path:
    return Path(
        os.getenv(
            "GROQ_CIRCUIT_BREAKER_FILE",
            "/tmp/spark-checkpoints/runtime/groq-disabled",
        )
    )


def _is_unauthorized(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code is None:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
    return status_code == 401 or "401" in str(error)


def _is_circuit_open(api_key: str) -> bool:
    marker = _circuit_breaker_path()
    if not marker.exists():
        return False

    try:
        disabled_fingerprint = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return False

    current_fingerprint = _key_fingerprint(api_key)
    if disabled_fingerprint == current_fingerprint:
        return True

    # A changed key automatically closes the previous key's circuit.
    try:
        marker.unlink(missing_ok=True)
    except OSError:
        pass
    return False


def _open_circuit(api_key: str) -> None:
    marker = _circuit_breaker_path()
    with _circuit_lock:
        marker.parent.mkdir(parents=True, exist_ok=True)
        temporary = marker.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(_key_fingerprint(api_key), encoding="utf-8")
        os.replace(temporary, marker)


def get_groq_client():
    global _groq_client, _groq_client_key_fingerprint
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or _is_circuit_open(api_key):
        return None

    fingerprint = _key_fingerprint(api_key)
    if _groq_client is None or _groq_client_key_fingerprint != fingerprint:
        _groq_client = Groq(
            api_key=api_key,
            timeout=float(os.getenv("GROQ_TIMEOUT_SECONDS", "10")),
            max_retries=0,
        )
        _groq_client_key_fingerprint = fingerprint
    return _groq_client


def detect_clickbait(title: str) -> float:
    global _disabled_logged
    if not title or len(title.strip()) < 10:
        return 0.0

    api_key = os.getenv("GROQ_API_KEY")
    client = get_groq_client()
    if not client:
        if api_key and not _disabled_logged:
            logger.warning("Groq clickbait detection is disabled by the authentication circuit breaker")
            _disabled_logged = True
        return 0.0

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a highly accurate clickbait detector for Vietnamese news. "
                               "Return ONLY a float number from 0.0 to 1.0 representing the probability that the title is clickbait, sensational, or misleading. "
                               "0.0 means completely objective and factual, 1.0 means extremely sensational clickbait."
                },
                {
                    "role": "user",
                    "content": f"Title: {title}"
                }
            ],
            model="llama3-8b-8192",
            temperature=0.0,
            max_tokens=10,
        )
        
        response_text = chat_completion.choices[0].message.content.strip()
        score = float(response_text)
        return min(max(score, 0.0), 1.0)
    except Exception as e:
        if api_key and _is_unauthorized(e):
            _open_circuit(api_key)
            logger.error("Groq returned HTTP 401; clickbait detection disabled for this API key")
        else:
            logger.error(f"Groq API error for clickbait detection: {e}")
        return 0.0

# Register as UDF
clickbait_udf = udf(detect_clickbait, FloatType())


def apply_clickbait_detection(df: DataFrame) -> DataFrame:
    """
    Applies Llama 3 clickbait detection to the 'title_clean' column.
    """
    if os.getenv("GROQ_API_KEY"):
        logger.info("Applying Clickbait Detection with Groq API (Llama 3)")
        return df.withColumn("clickbait_score", clickbait_udf("title_clean"))
    else:
        logger.warning("GROQ_API_KEY not found. Skipping clickbait detection.")
        from pyspark.sql.functions import lit
        return df.withColumn("clickbait_score", lit(0.0).cast(FloatType()))
