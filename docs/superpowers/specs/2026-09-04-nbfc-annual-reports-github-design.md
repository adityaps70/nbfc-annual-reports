# NBFC Annual Reports GitHub Collector — Design

Date: 2026-09-04

## Goal

Collect annual reports for the 215 companies in the supplied NBFC/finance-company list, covering FY2011-12 onward or the first available operating/reporting year if later. The system must not stall on any single company and must keep all durable results on GitHub.

## Architecture

### Repository content

- `companies.txt` — canonical input list, one company per line.
- `collector/collect_company.py` — resolves one company, discovers report sources, downloads/validates PDFs, and writes a machine-readable result manifest.
- `collector/sources.py` — source adapters for official investor-relations pages, BSE, NSE and fallback indexed sources.
- `collector/utils.py` — normalization, year parsing, URL validation, PDF validation and timeout helpers.
- `scripts/build_matrix.py` — converts `companies.txt` into a GitHub Actions matrix.
- `scripts/merge_results.py` — merges per-company manifests into `results/master_index.csv`, `results/missing_reports.csv` and `results/progress.json`.
- `.github/workflows/collect-annual-reports.yml` — parallel GitHub Actions workflow.
- `results/` — durable indexes/status only, committed to Git.

### PDF storage

PDFs will not be committed directly into Git history because thousands of annual reports could make the repository many gigabytes and exceed normal GitHub repository/file-size limits. Each company job will create a ZIP containing its successfully downloaded reports and upload that ZIP as an asset to a GitHub Release named `annual-reports-archive`. This keeps the report files on GitHub while keeping the repository usable.

The release asset name will be deterministic, e.g. `Aavas_Financiers_Ltd.zip`, so reruns can replace/update a company archive rather than creating uncontrolled duplicates.

## Execution model

1. A prepare job reads all 215 companies and emits a JSON matrix.
2. GitHub Actions runs companies independently in parallel with `max-parallel` capped to avoid source-site rate limiting.
3. Each company job has a hard overall timeout.
4. Each HTTP request has a short connect/read timeout.
5. HTTP 404 is treated as permanent for that URL and skipped immediately.
6. Source failures are recorded and the job moves to the next source.
7. A company-level failure never fails the entire matrix; it produces an unresolved manifest instead.
8. Each company job uploads its manifest as a temporary workflow artifact and its PDFs as a GitHub Release ZIP asset.
9. A final merge job downloads all manifests, rebuilds the indexes, and commits only the index/status files back to the repository.

## Source priority

For each company and financial year:

1. Official company Investor Relations / Annual Reports pages.
2. BSE corporate filing / historical annual-report sources.
3. NSE corporate filing / annual-report sources.
4. Screener/indexed links only as discovery hints, never as the sole authority.
5. Search-engine discovery only as a bounded fallback, with strict timeouts.

No report is accepted merely because a URL looks plausible. Downloaded content must start with a valid PDF signature or have a PDF content type and pass a minimum-size check.

## Company matching

Company matching will normalize:

- `Ltd`, `Limited`, `Pvt`, punctuation and repeated whitespace.
- `&` versus `and`.
- Parentheses and common legal-suffix variations.

Resolved candidates are scored against the canonical company name. Ambiguous low-confidence matches are logged rather than downloaded under the wrong company.

## Year rules

- `--start-fy 2011` means FY2011-12 onward.
- A report labelled `2024-25` maps to FY2024-25.
- A single report year such as `Annual Report 2025` maps to the financial year ending in 2025.
- The collector never fabricates reports for years before the company existed or before public reports are available.

## Timeouts and anti-stall behavior

Target defaults:

- Connect timeout: 5 seconds.
- Read timeout: 15 seconds.
- Search/discovery page timeout: 15 seconds.
- Maximum source candidates per company: bounded.
- Maximum company wall-clock time: 180 seconds.
- GitHub Actions job timeout: 8 minutes as an outer safety limit.

If the company budget is exhausted, the collector stops discovery immediately, writes `TIMEOUT` to the manifest and exits successfully so the matrix proceeds.

## GitHub Actions concurrency

Initial `max-parallel`: 8. This can be increased later if BSE/NSE/company websites tolerate the load. A lower parallelism is preferred over triggering exchange anti-bot protections.

## Results

`results/master_index.csv` fields:

- Company Name
- Matched Name
- Financial Year
- Report End Year
- Source Type
- Source URL
- Download Status
- GitHub Release Asset
- Notes

`results/missing_reports.csv` records unresolved company/year combinations and every failure reason available.

`results/progress.json` summarizes:

- companies total
- companies processed
- companies with at least one report
- reports downloaded
- reports unresolved
- last workflow run / timestamp

## Reruns

Reruns are idempotent. Existing release assets can be reused/replaced, and committed indexes are rebuilt from current manifests rather than appended blindly. A failed or timed-out company can be rerun individually through `workflow_dispatch` inputs.

## Security and permissions

The workflow uses only the repository-scoped `GITHUB_TOKEN` with `contents: write` for release assets and index commits. No external API keys are required by default. No personal browser cookies or Screener session credentials are stored.

## Verification

Before the full 215-company run:

1. Unit tests validate year parsing, company normalization, PDF detection and timeout handling.
2. A smoke run processes Aavas Financiers Ltd. and several smaller names.
3. The workflow verifies that a deliberate unreachable URL times out and moves on.
4. Release upload and final index commit are verified.

The full run is started only after these checks pass.
