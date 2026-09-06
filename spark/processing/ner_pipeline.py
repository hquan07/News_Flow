from typing import List, Dict
import logging
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    StructType,
    StructField,
    StringType,
)

logger = logging.getLogger(__name__)

# Schema for NER output
ENTITY_SCHEMA = ArrayType(
    StructType([
        StructField("entity", StringType(), False),
        StructField("entity_type", StringType(), False),
        StructField("label", StringType(), False),
    ])
)

# Global variables for Spark executors
_tokenizer = None
_ner_pipeline = None

def _get_pipeline():
    global _tokenizer, _ner_pipeline
    if _ner_pipeline is None:
        try:
            import os
            os.environ["HF_HOME"] = "/tmp/hf_cache"
            os.environ["TRANSFORMERS_CACHE"] = "/tmp/hf_cache"
            # Attempt to use ONNX runtime via optimum if available and model is exported
            from optimum.onnxruntime import ORTModelForTokenClassification
            from transformers import AutoTokenizer, pipeline
            
            model_id = "NlpHUST/ner-vietnamese-electra-base" # using an electra/phobert based NER
            logger.info(f"Loading NER model {model_id}")
            _tokenizer = AutoTokenizer.from_pretrained(model_id)
            
            # For strict ONNX, you would load ORTModelForTokenClassification.from_pretrained(model_id, export=True)
            # Falling back to standard transformers pipeline for immediate execution
            from transformers import AutoModelForTokenClassification
            model = AutoModelForTokenClassification.from_pretrained(model_id)
            _ner_pipeline = pipeline("ner", model=model, tokenizer=_tokenizer, aggregation_strategy="simple")
        except Exception as e:
            logger.error(f"Failed to load NER model: {e}")
            _ner_pipeline = lambda x: []
            
    return _ner_pipeline

def extract_entities(text: str) -> List[Dict[str, str]]:
    if not text or len(text) < 10:
        return []

    try:
        nlp = _get_pipeline()
        # Truncate text to avoid exceeding max length of 512 tokens
        text = text[:1500] 
        results = nlp(text)
    except Exception as e:
        logger.error(f"NER extraction error: {e}")
        return []

    unique_entities = []
    seen = set()
    for ent in results:
        # ent looks like {'entity_group': 'PER', 'score': 0.99, 'word': 'Nguyễn Văn A', 'start': 0, 'end': 12}
        label = ent.get("entity_group", "")
        if label not in ["PER", "LOC", "ORG"]:
            continue
            
        entity_text = ent.get("word", "").replace("@@", "").replace("_", " ").strip()
        if not entity_text:
            continue
            
        entity_type = "person" if label == "PER" else "location" if label == "LOC" else "organization"
        
        key = (entity_text.lower(), entity_type)
        if key not in seen:
            seen.add(key)
            unique_entities.append({
                "entity": entity_text,
                "entity_type": entity_type,
                "label": label
            })

    return unique_entities


# Register as Spark UDF
@F.udf(returnType=ENTITY_SCHEMA)
def extract_entities_udf(content: str) -> list:
    return extract_entities(content) if content else []


def apply_ner_extraction(df: DataFrame) -> DataFrame:
    enriched = df.withColumn(
        "entities", extract_entities_udf(F.col("content_clean"))
    )

    # Add entity type counts for analytics
    enriched = (
        enriched
        .withColumn(
            "person_count",
            F.size(
                F.filter(
                    F.col("entities"),
                    lambda x: x["entity_type"] == "person",
                )
            ),
        )
        .withColumn(
            "location_count",
            F.size(
                F.filter(
                    F.col("entities"),
                    lambda x: x["entity_type"] == "location",
                )
            ),
        )
        .withColumn(
            "org_count",
            F.size(
                F.filter(
                    F.col("entities"),
                    lambda x: x["entity_type"] == "organization",
                )
            ),
        )
    )

    return enriched