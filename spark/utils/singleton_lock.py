import fcntl
import os
from pathlib import Path
from typing import Dict, IO


class SingletonLockError(RuntimeError):
    """Raised when another streaming driver already owns the shared lock."""


def acquire_singleton_lock(path: str) -> IO[str]:
    """Hold an advisory lock for the lifetime of the returned file object."""
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+", encoding="utf-8")

    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise SingletonLockError(
            f"Another NewsPulse streaming driver is already running (lock: {path})"
        ) from exc

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def validate_unique_checkpoints(checkpoints: Dict[str, str]) -> None:
    normalized = [os.path.normpath(path) for path in checkpoints.values()]
    if len(normalized) != len(set(normalized)):
        duplicates = sorted({path for path in normalized if normalized.count(path) > 1})
        raise ValueError(f"Checkpoint paths must be unique: {', '.join(duplicates)}")
