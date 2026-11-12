import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # repo root


@pytest.fixture(autouse=True)
def isolate_fettle_state(tmp_path_factory, monkeypatch):
    """Keep every test away from the user's process-global Fettle state."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("xdg-state")))
