import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "insert_tokens", Path(__file__).resolve().parents[1] / "spark/streaming/insert_tokens.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_insert_token_is_stable_and_scoped_to_each_chunk():
    token = module.insert_token("news_raw", "raw_articles", 42, 2, 0)
    assert token == module.insert_token("news_raw", "raw_articles", 42, 2, 0)
    assert token != module.insert_token("news_raw", "raw_articles", 42, 2, 1)
    assert token != module.insert_token("news_raw", "raw_articles", 43, 2, 0)
