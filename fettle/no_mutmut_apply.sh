#!/usr/bin/env bash
# Hazard guard: mutmut apply corrupts the working tree (see improvement plan).
if git diff --cached | grep -q "mutmut apply"; then
  echo "BLOCKED: mutmut apply found in staged changes — use a scratch checkout"
  echo "(see docs/improvement-plan.md hazard notes)"
  exit 1
fi
