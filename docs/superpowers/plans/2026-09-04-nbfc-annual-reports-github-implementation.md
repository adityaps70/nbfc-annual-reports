# NBFC Annual Reports GitHub Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a non-blocking GitHub Actions collector that processes the 215-company input list independently, stores annual-report archives on GitHub Releases, and commits durable result indexes back to the repository.

**Architecture:** One Python collector handles exactly one company per invocation and writes a manifest. GitHub Actions builds a company matrix, runs company jobs in parallel with hard shell/job timeouts, uploads deterministic per-company ZIPs to one release, then merges manifest artifacts into repository CSV/JSON indexes. Source discovery is bounded and uses official IR pages first, BSE/NSE and indexed/search fallbacks second.

**Tech Stack:** Python 3.12, requests, BeautifulSoup4, pytest, GitHub Actions, GitHub CLI (`gh`), actions/upload-artifact v4, actions/download-artifact v4.

**Spec:** `docs/superpowers/specs/2026-09-04-nbfc-annual-reports-github-design.md`

## Global Constraints

- Scope starts at FY2011-12 (`start_fy=2011`) and never fabricates unavailable pre-operation years.
- Connect timeout: 5 seconds; read timeout: 15 seconds; company wall-clock budget: 180 seconds; GitHub Actions company job timeout: 8 minutes.
- Initial matrix `max-parallel`: 8.
- A failed/timed-out company must still produce a manifest and must not fail the whole matrix.
- PDFs must be validated by `%PDF` signature and minimum size before acceptance.
- Durable Git history stores indexes/status only; report PDFs are stored as deterministic ZIP assets on release `annual-reports-archive`.
- No external API keys, browser cookies, or Screener credentials.

---

### Task 1: Core normalization, year parsing, HTTP/PDF validation

**Files:**
- Create: `collector/__init__.py`
- Create: `collector/utils.py`
- Create: `tests/test_utils.py`
- Create: `requirements.txt`

**Interfaces:**
- Produces: `normalize_company(name: str) -> str`, `company_score(a: str, b: str) -> float`, `extract_end_year(text: str) -> int | None`, `fy_label(end_year: int) -> str`, `safe_slug(text: str) -> str`, `is_valid_pdf(data: bytes, content_type: str = "") -> bool`, `Budget(seconds: float)`.

- [ ] Write tests asserting legal-suffix normalization, FY2011-12 → end year 2012 behavior, 2024-25 parsing, PDF signature/minimum-size validation, and budget expiration.
- [ ] Run `pytest tests/test_utils.py -v` and verify failure before implementation.
- [ ] Implement minimal utilities and constants `CONNECT_TIMEOUT=5`, `READ_TIMEOUT=15`, `MIN_PDF_BYTES=1024`.
- [ ] Run `pytest tests/test_utils.py -v` and verify PASS.
- [ ] Commit as `feat: add collector utilities and validation`.

### Task 2: Bounded source discovery

**Files:**
- Create: `collector/sources.py`
- Create: `tests/test_sources.py`

**Interfaces:**
- Consumes: utilities from Task 1.
- Produces: `ReportCandidate(end_year, url, source_type, context, priority)`, `resolve_screener(session, company, budget)`, `discover_official_archive(session, company, website_hint, budget)`, `discover_candidates(session, company, start_end_year, budget) -> DiscoveryResult`.

- [ ] Write fixture-based tests for parsing annual-report anchors, excluding AGM/annual-return links, normalized company matching, and stopping when `Budget` is expired.
- [ ] Run `pytest tests/test_sources.py -v` and verify failure.
- [ ] Implement bounded source discovery: Screener search variants; official website extraction; common IR paths; bounded Bing/DuckDuckGo HTML fallback; original BSE/NSE links; BSE historical-path candidate generation; dedupe by `(year,url)`.
- [ ] Run `pytest tests/test_sources.py -v` and verify PASS.
- [ ] Commit as `feat: add bounded annual report source discovery`.

### Task 3: Single-company collector and manifest

**Files:**
- Create: `collector/collect_company.py`
- Create: `tests/test_collect_company.py`

**Interfaces:**
- Consumes: `discover_candidates` and utility functions.
- Produces CLI: `python -m collector.collect_company --company NAME --output-dir work --start-fy 2011 --budget-seconds 180 --manifest manifest.json`.
- Manifest keys: `company`, `matched_name`, `status`, `started_at`, `finished_at`, `reports[]`, `errors[]`, `archive_path`.

- [ ] Write tests with fake HTTP/session candidates showing: valid PDF accepted; first 404 immediately falls through to second candidate; non-PDF rejected; budget exhaustion writes `TIMEOUT` status without raising.
- [ ] Run `pytest tests/test_collect_company.py -v` and verify failure.
- [ ] Implement downloader, per-year candidate fallback, deterministic filenames, ZIP creation, and always-write-manifest behavior.
- [ ] Run `pytest tests/test_collect_company.py -v` and verify PASS.
- [ ] Commit as `feat: add single-company annual report collector`.

### Task 4: Matrix and result merger

**Files:**
- Create: `scripts/build_matrix.py`
- Create: `scripts/merge_results.py`
- Create: `tests/test_scripts.py`
- Create: `companies.txt`
- Create: `results/.gitkeep`

**Interfaces:**
- `build_matrix.py companies.txt` prints compact JSON `{"include":[{"index":1,"company":"...","slug":"..."},...]}`.
- `merge_results.py --manifests PATH --results results --run-id ID` writes `master_index.csv`, `missing_reports.csv`, `progress.json`.

- [ ] Write tests verifying exactly 215 unique matrix entries, stable slugs, CSV columns from the spec, timeout/unresolved rows, and progress totals.
- [ ] Run `pytest tests/test_scripts.py -v` and verify failure.
- [ ] Implement both scripts and copy the canonical 215-company list from the supplied source document into `companies.txt`.
- [ ] Run `pytest tests/test_scripts.py -v` and verify PASS.
- [ ] Commit as `feat: add matrix builder and result merger`.

### Task 5: GitHub Actions workflow and documentation

**Files:**
- Create: `.github/workflows/collect-annual-reports.yml`
- Create: `README.md`

**Interfaces:**
- Workflow inputs: `company` (optional exact/substring single-company filter), `start_fy` (default `2011`), `full_run` boolean.
- Release tag/name: `annual-reports-archive`.

- [ ] Add a workflow validation test/assertion that YAML contains `max-parallel: 8`, job timeout `8`, shell `timeout 180s`, `continue-on-error`/fallback-manifest behavior, release upload, manifest artifact upload, merge job, and results commit.
- [ ] Run full test suite and verify failure until workflow exists.
- [ ] Implement workflow: prepare matrix; matrix collect jobs; `timeout 180s` wrapper with fallback manifest; deterministic release ZIP upload via `gh release upload --clobber`; artifact upload; final manifest download/merge; commit changed indexes.
- [ ] Add README with Actions usage and result locations.
- [ ] Run `pytest -q` and verify PASS.
- [ ] Commit as `ci: run annual report collector in parallel on GitHub Actions`.

### Task 6: Smoke verification, PR and full-run trigger

**Files:**
- No code required unless verification finds a defect.

**Interfaces:**
- Smoke set: `Aavas Financiers Ltd.`, `Abhishek Finlease Ltd.`, `Acme Resources Ltd.` plus one deliberately bounded failure path covered by tests.

- [ ] Push feature branch and open PR.
- [ ] Verify push/PR GitHub Actions reaches matrix execution and no company job can block beyond outer timeout.
- [ ] Inspect smoke job logs and artifacts; verify at least the manifests/index flow completes even when some reports are unresolved.
- [ ] Run `pytest -q` again against the final branch and inspect combined CI status.
- [ ] Merge the verified PR.
- [ ] Trigger/allow the main-branch workflow to process the complete company list and verify the run starts.
- [ ] Confirm release `annual-reports-archive` and repository `results/` are the durable storage locations.
