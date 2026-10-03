"""Pure-Python PhoBERT sentiment inference shared by Spark and backfill jobs."""

import logging
import os

logger = logging.getLogger(__name__)

_sentiment_pipeline = None


class SentimentModelUnavailable(RuntimeError):
    """Raised when inference cannot run; callers must not persist fake neutral data."""


def _get_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        try:
            os.environ["HF_HOME"] = "/tmp/hf_cache"
            os.environ["TRANSFORMERS_CACHE"] = "/tmp/hf_cache"
            from transformers import pipeline

            model_id = "wonrax/phobert-base-vietnamese-sentiment"
            logger.info("Loading Sentiment model %s", model_id)
            _sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=model_id,
                tokenizer=model_id,
            )
        except Exception as exc:
            logger.exception("Failed to load the sentiment model")
            raise SentimentModelUnavailable("Sentiment model is unavailable") from exc

    return _sentiment_pipeline


def analyze_sentiment(text: str) -> dict:
    if not text or len(text.strip()) < 10:
        return {"sentiment_score": 0.0, "sentiment_label": "neutral"}

    try:
        nlp = _get_pipeline()
        result = nlp(text, truncation=True, max_length=256)[0]
    except Exception as exc:
        logger.error("Sentiment extraction error: %s", exc)
        raise

    label_map = {
        "POS": "positive",
        "NEG": "negative",
        "NEU": "neutral",
    }
    label = result.get("label", "NEU")
    score = result.get("score", 0.0)

    if label == "POS":
        mapped_score = score
    elif label == "NEG":
        mapped_score = -score
    else:
        mapped_score = 0.0

    return {
        "sentiment_score": float(mapped_score),
        "sentiment_label": label_map.get(label, "neutral"),
    }
