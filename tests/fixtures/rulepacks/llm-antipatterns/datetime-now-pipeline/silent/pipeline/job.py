from datetime import datetime
from typing import Callable


def stamp(clock: Callable[[], datetime]):
    return clock()
