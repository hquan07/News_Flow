"""Fail if tracked source files contain common live API token formats."""

import re
import subprocess
from pathlib import Path


PATTERNS = {
    "Groq API key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "Telegram bot token": re.compile(r"\b[0-9]{8,}:[A-Za-z0-9_-]{25,}\b"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    "MongoDB URI with password": re.compile(r"mongodb(?:\+srv)?://[^\s/@:]+:[^\s/@]+@"),
}
TEXT_SUFFIXES = {".py", ".sh", ".yml", ".yaml", ".json", ".md", ".toml", ".txt", ".sql", ".ts", ".tsx"}


def main():
    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    findings = []
    for raw_path in tracked:
        if not raw_path:
            continue
        relative = Path(raw_path.decode())
        if relative.suffix not in TEXT_SUFFIXES and ".env" not in relative.name:
            continue
        path = root / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{relative}: {name}")
    if findings:
        raise SystemExit("Possible secrets in tracked files:\n" + "\n".join(findings))
    print("No matching secret formats in tracked source files")


if __name__ == "__main__":
    main()
