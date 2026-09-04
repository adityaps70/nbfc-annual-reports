from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

MASTER_FIELDS = ['Company Name','Matched Name','Financial Year','Report End Year','Source Type','Source URL','Download Status','GitHub Release Asset','Notes']
MISSING_FIELDS = ['Company Name','Matched Name','Financial Year','Report End Year','Company Status','Failure Reason','Attempted URLs']


def _load_manifests(root: Path):
    rows = []
    if not root.exists():
        return rows
    for p in sorted(root.rglob('*.json')):
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data.get('company'):
                rows.append(data)
        except Exception:
            pass
    return rows


def merge_manifests(manifests_dir: Path, results_dir: Path, run_id: str = ''):
    manifests = _load_manifests(manifests_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    master_rows, missing_rows = [], []
    reports_downloaded = reports_unresolved = companies_with_reports = 0
    for m in manifests:
        downloaded_here = 0
        reports = m.get('reports') or []
        for r in reports:
            if r.get('status') == 'DOWNLOADED':
                downloaded_here += 1
                reports_downloaded += 1
                master_rows.append({
                    'Company Name': m.get('company',''), 'Matched Name': m.get('matched_name',''),
                    'Financial Year': r.get('financial_year',''), 'Report End Year': r.get('end_year',''),
                    'Source Type': r.get('source_type',''), 'Source URL': r.get('source_url',''),
                    'Download Status': r.get('status',''), 'GitHub Release Asset': m.get('archive_asset',''),
                    'Notes': r.get('notes',''),
                })
            else:
                reports_unresolved += 1
                missing_rows.append({
                    'Company Name': m.get('company',''), 'Matched Name': m.get('matched_name',''),
                    'Financial Year': r.get('financial_year',''), 'Report End Year': r.get('end_year',''),
                    'Company Status': m.get('status',''), 'Failure Reason': r.get('notes','') or '; '.join(m.get('errors') or []),
                    'Attempted URLs': ' | '.join(r.get('attempts') or []),
                })
        if downloaded_here:
            companies_with_reports += 1
        if not reports or m.get('status') in ('TIMEOUT','ERROR'):
            if not downloaded_here:
                missing_rows.append({
                    'Company Name': m.get('company',''), 'Matched Name': m.get('matched_name',''),
                    'Financial Year': '', 'Report End Year': '', 'Company Status': m.get('status',''),
                    'Failure Reason': '; '.join(m.get('errors') or ['No report candidates']), 'Attempted URLs': '',
                })
    with (results_dir / 'master_index.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=MASTER_FIELDS)
        w.writeheader()
        w.writerows(master_rows)
    with (results_dir / 'missing_reports.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=MISSING_FIELDS)
        w.writeheader()
        w.writerows(missing_rows)
    progress = {
        'companies_total': 215,
        'companies_processed': len(manifests),
        'companies_with_reports': companies_with_reports,
        'reports_downloaded': reports_downloaded,
        'reports_unresolved': reports_unresolved + sum(1 for m in manifests if not m.get('reports') and m.get('status') != 'SUCCESS'),
        'workflow_run_id': str(run_id),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    (results_dir / 'progress.json').write_text(json.dumps(progress, indent=2), encoding='utf-8')
    return progress


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifests', type=Path, required=True)
    ap.add_argument('--results', type=Path, default=Path('results'))
    ap.add_argument('--run-id', default='')
    args = ap.parse_args()
    print(json.dumps(merge_manifests(args.manifests, args.results, args.run_id), indent=2))


if __name__ == '__main__':
    main()
