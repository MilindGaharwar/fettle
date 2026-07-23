---
name: threat-model
description: Generate a STRIDE-based threat model with auto-populated entry points and data stores
argument-hint: "[service-name]"
user-invocable: true
allowed-tools: Bash, Read, Write
---

Generate a threat model for the target service.

## Procedure

1. **Determine service name.** Use `$ARGUMENTS` if provided, otherwise derive from the workspace directory name.

2. **Run the generator:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/threat_model.py --name SERVICE --root . --output docs/threat-model-SERVICE.md
   ```

3. **Present the auto-detected data** (entry points, data stores, auth mechanisms) and ask the user to confirm or add missing items.

4. **Help fill STRIDE tables** by analyzing the detected components and suggesting threats for each category.

5. **Save the completed model** to `docs/threat-model-{name}.md`.

## Notes

- Auto-detection is best-effort (grep-based), NOT comprehensive
- The STRIDE tables require human judgment to fill
- This is a guided template, not a replacement for a security architect
