"""Deterministic P55 fixture: canonical state changes while a projection stays stale."""

from __future__ import annotations

import json
import sys
from pathlib import Path

STATE = Path(__file__).with_name("state.json")


def main() -> None:
    phase = sys.argv[1]
    if phase == "setup":
        STATE.write_text(json.dumps({"canonical": "old", "projection": "old"}))
        result = {"fettle-operation": "v1"}
    elif phase == "mutate":
        state = json.loads(STATE.read_text())
        state["canonical"] = "new"
        STATE.write_text(json.dumps(state))
        result = {"fettle-operation": "v1"}
    elif phase == "canonical":
        result = {"fettle-observation": "v1", "value": json.loads(STATE.read_text())["canonical"]}
    elif phase == "observer":
        result = {"fettle-observation": "v1", "value": json.loads(STATE.read_text())["projection"]}
    elif phase == "cleanup":
        STATE.unlink(missing_ok=True)
        result = {"fettle-operation": "v1"}
    else:
        raise SystemExit(2)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
