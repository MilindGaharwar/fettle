import os
import tempfile
from pathlib import Path


def dump(path: Path, content: str):
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    os.write(fd, content.encode())
    os.close(fd)
    os.replace(tmp, path)
