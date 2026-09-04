import csv
import json
import subprocess
import sys
from pathlib import Path

from scripts.build_matrix import build_matrix
from scripts.merge_results import merge_manifests


def test_company_file_builds_exactly_215_unique_matrix_entries():
    matrix = build_matrix(Path('companies.txt'))
    assert len(matrix['include']) == 215
    assert len({x['company'] for x in matrix['include']}) == 215
    assert matrix['include'][3]['company'] == 'Aavas Financiers Ltd.'


def test_merge_results_writes_expected_indexes(tmp_path):
    manifests = tmp_path / 'manifests'
    manifests.mkdir()
    (manifests / 'a.json').write_text(json.dumps({
        'company': 'Aavas Financiers Ltd.',
        'matched_name': 'Aavas Financiers Ltd.',
        'status': 'SUCCESS',
        'archive_asset': 'Aavas_Financiers_Ltd.zip',
        'reports': [{
            'financial_year': 'FY2024-25', 'end_year': 2025,
            'source_type': 'Official company', 'source_url': 'https://aavas.in/report.pdf',
            'status': 'DOWNLOADED', 'notes': ''
        }],
        'errors': [],
    }), encoding='utf-8')
    (manifests / 'b.json').write_text(json.dumps({
        'company': 'Acme Resources Ltd.', 'matched_name': '', 'status': 'TIMEOUT',
        'archive_asset': '', 'reports': [], 'errors': ['company budget exhausted'],
    }), encoding='utf-8')
    out = tmp_path / 'results'
    progress = merge_manifests(manifests, out, run_id='123')
    assert progress['companies_processed'] == 2
    assert progress['reports_downloaded'] == 1
    assert progress['companies_with_reports'] == 1
    rows = list(csv.DictReader((out / 'master_index.csv').open(encoding='utf-8-sig')))
    assert rows[0]['Company Name'] == 'Aavas Financiers Ltd.'
    missing = list(csv.DictReader((out / 'missing_reports.csv').open(encoding='utf-8-sig')))
    assert any(r['Company Name'] == 'Acme Resources Ltd.' for r in missing)


def test_workflow_contains_anti_stall_and_storage_guards():
    text = Path('.github/workflows/collect-annual-reports.yml').read_text(encoding='utf-8')
    assert 'max-parallel: 8' in text
    assert 'timeout-minutes: 8' in text
    assert 'timeout 180s' in text
    assert 'annual-reports-archive' in text
    assert 'gh release upload' in text
    assert 'actions/upload-artifact@v4' in text
    assert 'actions/download-artifact@v4' in text
    assert 'scripts/merge_results.py' in text


def test_build_matrix_cli_runs_from_repository_root():
    proc = subprocess.run([sys.executable, 'scripts/build_matrix.py', 'companies.txt'], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert len(payload['include']) == 215
