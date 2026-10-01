"""Small process-local TTL cache for query vectors only, never article results."""

import hashlib
import threading
import time
from collections import OrderedDict

from api.config import get_settings
from api.services import rag_client


_lock = threading.Lock()
_vectors: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()


def query_vector(text: str) -> list[float]:
    settings = get_settings()
    key = hashlib.sha256((settings.EMBEDDING_URL + "\0" + text).encode()).hexdigest()
    now = time.monotonic()
    with _lock:
        hit = _vectors.get(key)
        if hit and hit[0] > now:
            _vectors.move_to_end(key)
            return hit[1]
        _vectors.pop(key, None)
    vector = rag_client.embed([text])[0]
    if settings.CHAT_EMBED_CACHE_TTL_SECONDS > 0 and settings.CHAT_EMBED_CACHE_MAX_ITEMS > 0:
        with _lock:
            _vectors[key] = (time.monotonic() + settings.CHAT_EMBED_CACHE_TTL_SECONDS, vector)
            _vectors.move_to_end(key)
            while len(_vectors) > settings.CHAT_EMBED_CACHE_MAX_ITEMS:
                _vectors.popitem(last=False)
    return vector


def clear() -> None:
    with _lock:
        _vectors.clear()
