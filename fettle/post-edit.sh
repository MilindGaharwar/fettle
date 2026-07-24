#!/usr/bin/env bash
# Back-compat wrapper — canonical entry is run.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run.sh" post_edit.py "$@"
