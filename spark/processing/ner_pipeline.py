from typing import List, Dict
from underthesea import ner
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    StructType,
    StructField,
    StringType,
)

# Entity types we care about
ENTITY_TYPES = {
    "B-PER": "PER",
    "I-PER": "PER",
    "B-LOC": "LOC",
    "I-LOC": "LOC",
    "B-ORG": "ORG",
    "I-ORG": "ORG",
}

# Schema for NER output
ENTITY_SCHEMA = ArrayType(
    StructType([
        StructField("entity", StringType(), False),
        StructField("entity_type", StringType(), False),
        StructField("label", StringType(), False),
    ])
)


def extract_entities(text: str) -> List[Dict[str, str]]:
    if not text or len(text) < 10:
        return []

    try:
        ner_results = ner(text)
    except Exception:
        return []

    entities = []
    current_entity = []
    current_type = None

    for word, pos, chunk, ner_tag in ner_results:
        if ner_tag.startswith("B-") and ner_tag in ENTITY_TYPES:
            # Save previous entity if exists
            if current_entity and current_type:
                entity_text = " ".join(current_entity)
                entities.append({
                    "entity": entity_text,
                    "entity_type": current_type,
                    "label": ner_tag[2:],  # PER, LOC, ORG
                })

            # Start new entity
            current_entity = [word]
            current_type = ENTITY_TYPES[ner_tag]

        elif ner_tag.startswith("I-") and ner_tag in ENTITY_TYPES:
            expected_type = ENTITY_TYPES[ner_tag]
            if current_type == expected_type:
                current_entity.append(word)
            else:
                # Type mismatch, start fresh
                if current_entity and current_type:
                    entity_text = " ".join(current_entity)
                    entities.append({
                        "entity": entity_text,
                        "entity_type": current_type,
                        "label": current_type[:3].upper(),
                    })
                current_entity = [word]
                current_type = expected_type
        else:
            # Save any pending entity
            if current_entity and current_type:
                entity_text = " ".join(current_entity)
                entities.append({
                    "entity": entity_text,
                    "entity_type": current_type,
                    "label": current_type[:3].upper(),
                })
                current_entity = []
                current_type = None

    if current_entity and current_type:
        entity_text = " ".join(current_entity)
        entities.append({
            "entity": entity_text,
            "entity_type": current_type,
            "label": current_type[:3].upper(),
        })

    # Deduplicate entities (keep first occurrence)
    seen = set()
    unique_entities = []
    for ent in entities:
        key = (ent["entity"].lower(), ent["entity_type"])
        if key not in seen:
            seen.add(key)
            unique_entities.append(ent)

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