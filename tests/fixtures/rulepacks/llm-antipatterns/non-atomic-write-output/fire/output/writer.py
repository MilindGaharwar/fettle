from pathlib import Path


def dump(path: Path, content: str):
    path.write_text(content)
