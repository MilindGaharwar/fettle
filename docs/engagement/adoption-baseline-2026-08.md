# Adoption Baseline: 2026-08-15

Status: captured before public discovery and packaging changes

Review date: 2026-09-14

## Public Surface

Collected from the GitHub API on 2026-08-15:

| Measure | Baseline |
|---|---:|
| Repository views, trailing 14 days | 818 |
| Unique repository visitors, trailing 14 days | 26 |
| Repository clones, trailing 14 days | 20,149 |
| Unique cloners, trailing 14 days | 203 |
| Stars | 2 |
| Forks | 0 |
| Watchers | 0 |
| Open issues | 0 |
| Open pull requests | 0 |
| Topics | None |
| Homepage | None |
| Discussions | Disabled |

Raw clones are excluded from primary acquisition evidence. Their scale relative
to unique visitors is consistent with substantial automation and cannot be
interpreted as human adoption.

The v1.10.0 release body contained only a full-changelog comparison link. Its
three assets were the wheel, source distribution, and CycloneDX SBOM.

PyPI reported v1.10.0 as current. The JSON API does not provide useful download
counts (`-1`), so downloads require a separate public aggregate source if they
are used in the 30-day review.

## Reproducible Baseline Commands

```bash
gh api repos/MilindGaharwar/fettle/traffic/views
gh api repos/MilindGaharwar/fettle/traffic/clones
gh repo view MilindGaharwar/fettle --json \
  description,homepageUrl,repositoryTopics,stargazerCount,forkCount,watchers,issues,pullRequests,hasDiscussionsEnabled,latestRelease
gh release view v1.10.0 --repo MilindGaharwar/fettle \
  --json name,body,publishedAt,url,assets
```

## Claim Inventory

Before this initiative, the public docs explicitly separated package and source
checkout behavior:

- `README.md:60-73` advertised wheel-based local scans and policy inspection.
- `README.md:75-94` required a Git checkout for live agent governance.
- `README.md:327-330` stated that agent transports require a checkout while CLI
  workflows, rules, and templates ship in the wheel.
- `docs/README.md:11-20` routed evaluators through package commands but did not
  claim wheel-installed host transports.
- `docs/OPENCODE.md` described checkout-relative OpenCode plugin setup.

The baseline wheel correctly ran `fettle --version`. A source-tree
`fettle check --changed` completed in 2.07 seconds with the repository's tools
available. A clean wheel does not include Ruff or Semgrep because Fettle's core
runtime has zero dependencies; therefore a clean evaluator must explicitly
install Ruff before relying on `fettle check` success.

## Thirty-Day Review

Repeat the GitHub commands above on 2026-09-14 and record:

- unique visitors and views as separate values;
- PyPI aggregate downloads if a reliable public source is available;
- successful proof replays and reported setup failures;
- external issue authors, comments, pull requests, and accepted contributions;
- support questions that would be better served by Discussions;
- bridge initialization or upgrade defects by host.

Do not backfill missing measurements or infer completion from stars, clones, or
overall implementation status.
