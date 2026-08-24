# Demo Corpus

A maintained polyglot sample application that anchors Fettle's measured
claims. Consumers:

| Consumer | Uses |
|---|---|
| Graph build budgets (P46) | Full-build timing on a real, spec-linked tree |
| Seeded-defect benchmark (P77) | Spec scenarios + trace-marked tests as mutation seeds |
| Documentation screenshots | Stable, realistic output for `graph`, `links`, `spec` |
| UAT fixtures (P72–P77) | CLI surface with active specs and manual fallbacks |

Layout: Python ledger service (`src/fettle_demo/`), web surface
(`web/`), Go CLI (`go-service/`), living specification
(`specs/ledger-core.md`), trace-marked tests (`tests/`). The corpus is
fixture data — do not add real secrets, dependencies, or production code
here.

Rebuild the graph over it:

```bash
fettle graph status --root examples/corpus
```
