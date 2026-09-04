# NBFC Annual Reports Archive

This repository collects annual reports for the 215 NBFC/finance-company names in `companies.txt`, starting at FY2011-12 or the first available public annual report if later.

## How it runs

GitHub Actions processes companies independently with a 180-second hard company limit and eight jobs in parallel. A failure or timeout for one company is recorded and does not block other companies.

### Durable storage

- Report PDFs are bundled per company and stored on the GitHub Release tagged **`annual-reports-archive`**.
- `results/master_index.csv` lists successfully downloaded reports and their source URLs.
- `results/missing_reports.csv` records unresolved years/companies and failure reasons.
- `results/progress.json` contains run totals and the workflow run id.

## Running it

Open **Actions → Collect annual reports → Run workflow**.

- Leave `company` blank and set `full_run=true` for all 215 companies.
- Enter an exact company name to rerun only that company.
- `start_fy=2011` means FY2011-12 onward.

Pushes to an implementation branch run only the smoke set: Aavas Financiers, Abhishek Finlease and Acme Resources. A push to `main` runs the full company matrix.

## Anti-stall behavior

HTTP requests use short connect/read timeouts; 404s are skipped immediately; source discovery is bounded; the collector has a 165-second internal budget; and GNU `timeout 180s` is an outer kill switch. The GitHub job has an 8-minute safety limit.
