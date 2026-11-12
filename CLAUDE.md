# CLAUDE.md

## This repository is public

Everything committed here — code, comments, README / changelog, tests, commit
messages, PR titles and bodies — is publicly visible.

- Do not reference private or internal projects, repositories, services, tickets,
  PR / ADR numbers, or internal file paths. Describe such dependencies generically
  ("downstream billing", "downstream consumers", "the cost calculator that reads
  these keys").
- Do not include credentials, hostnames, account details, or measurements taken
  on private infrastructure.
- Check a diff for both before committing or opening a PR.

## Working rules

- Never hand-edit `filtered_models.json`. Change the rules in
  `model_sync_rules.py`, run `python filter_models.py`, and commit both together.
- Before merging, run the CI steps locally: `pytest -q`,
  `python capability_check.py --upstream <pinned snapshot>` and
  `python drift_report.py --pinned` (must report "No drift").
- Prices come from the vendor's own live pricing page. Upstream LiteLLM data is a
  starting point, not a source of truth.
