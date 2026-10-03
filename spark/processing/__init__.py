__all__ = [
    "apply_text_cleaning",
    "apply_keyword_extraction",
    "apply_ner_extraction",
]


def __getattr__(name):
    """Keep the package importable without loading PySpark for one-shot tools."""
    if name == "apply_text_cleaning":
        from spark.processing.text_processor import apply_text_cleaning

        return apply_text_cleaning
    if name == "apply_keyword_extraction":
        from spark.processing.keyword_extractor import apply_keyword_extraction

        return apply_keyword_extraction
    if name == "apply_ner_extraction":
        from spark.processing.ner_pipeline import apply_ner_extraction

        return apply_ner_extraction
    raise AttributeError(name)
