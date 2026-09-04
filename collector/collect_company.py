from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from .sources import DiscoveryResult, ReportCandidate, discover_candidates
from .utils import Budget, BudgetExpired, MIN_PDF_BYTES, fy_label, safe_slug

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _download(session, candidate: ReportCandidate, dest: Path, budget: Budget):
    budget.check()
    host = candidate.url.lower()
    referer = 'https://www.bseindia.com/' if 'bseindia.com' in host else 'https://www.nseindia.com/' if 'nseindia.com' in host else candidate.url
    response = session.get(candidate.url, timeout=budget.request_timeout(), headers={'User-Agent': UA, 'Accept': 'application/pdf,*/*;q=0.8', 'Referer': referer}, allow_redirects=True, stream=True)
    try:
        if response.status_code == 404:
            raise FileNotFoundError('HTTP 404')
        if response.status_code >= 400:
            raise RuntimeError(f'HTTP {response.status_code}')
        tmp = dest.with_suffix('.part')
        prefix = bytearray()
        total = 0
        with tmp.open('wb') as f:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                budget.check()
                if not chunk:
                    continue
                if len(prefix) < 16:
                    prefix.extend(chunk[:16 - len(prefix)])
                f.write(chunk)
                total += len(chunk)
        if total < MIN_PDF_BYTES or not bytes(prefix).startswith(b'%PDF'):
            tmp.unlink(missing_ok=True)
            raise RuntimeError('response is not a valid PDF')
        tmp.replace(dest)
        return total, getattr(response, 'url', candidate.url)
    finally:
        close = getattr(response, 'close', None)
        if callable(close):
            close()


def _write_manifest(path: Path | None, manifest: dict) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')


def collect_company(company: str, output_dir: Path, start_fy: int, budget_seconds: float, *, session=None, discovery: DiscoveryResult | None = None, manifest_path: Path | None = None) -> dict:
    started = now_iso()
    slug = safe_slug(company)
    company_dir = Path(output_dir) / slug
    company_dir.mkdir(parents=True, exist_ok=True)
    budget = Budget(budget_seconds)
    session = session or requests.Session()
    manifest = {
        'company': company, 'matched_name': '', 'status': 'UNRESOLVED',
        'started_at': started, 'finished_at': '', 'reports': [], 'errors': [],
        'archive_path': '', 'archive_asset': f'{slug}.zip',
    }
    downloaded_paths: list[Path] = []
    try:
        budget.check()
        disc = discovery or discover_candidates(session, company, start_fy + 1, budget)
        manifest['matched_name'] = disc.matched_name
        manifest['errors'].extend(disc.errors)
        grouped: dict[int, list[ReportCandidate]] = {}
        for c in disc.candidates:
            if c.end_year >= start_fy + 1:
                grouped.setdefault(c.end_year, []).append(c)
        if not grouped:
            budget.check()
            manifest['errors'].append('No annual-report candidates discovered')
        for year in sorted(grouped):
            budget.check()
            fy = fy_label(year)
            row = {
                'financial_year': fy, 'end_year': year, 'source_type': '', 'source_url': '',
                'status': 'UNRESOLVED', 'file_name': '', 'bytes': 0, 'notes': '', 'attempts': [],
            }
            for cand in sorted(grouped[year], key=lambda x: (x.priority, x.url))[:10]:
                budget.check()
                row['attempts'].append(cand.url)
                dest = company_dir / f'{slug}_{fy}_Annual_Report.pdf'
                try:
                    size, final_url = _download(session, cand, dest, budget)
                    row.update({'source_type': cand.source_type, 'source_url': final_url, 'status': 'DOWNLOADED', 'file_name': dest.name, 'bytes': size})
                    downloaded_paths.append(dest)
                    break
                except FileNotFoundError:
                    row['notes'] = 'HTTP 404 on candidate; tried alternate source'
                    continue
                except BudgetExpired:
                    raise
                except Exception as e:
                    row['notes'] = str(e)[:300]
                    continue
            manifest['reports'].append(row)
        if downloaded_paths:
            archive = Path(output_dir) / f'{slug}.zip'
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
                for p in downloaded_paths:
                    zf.write(p, arcname=p.name)
            manifest['archive_path'] = str(archive)
            manifest['status'] = 'SUCCESS'
        elif manifest['status'] != 'TIMEOUT':
            manifest['status'] = 'UNRESOLVED'
    except BudgetExpired as e:
        manifest['status'] = 'TIMEOUT'
        manifest['errors'].append(str(e))
    except Exception as e:
        manifest['status'] = 'ERROR'
        manifest['errors'].append(f'{type(e).__name__}: {e}')
    finally:
        manifest['finished_at'] = now_iso()
        _write_manifest(manifest_path, manifest)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--company', required=True)
    ap.add_argument('--output-dir', default='work')
    ap.add_argument('--start-fy', type=int, default=2011)
    ap.add_argument('--budget-seconds', type=float, default=165)
    ap.add_argument('--manifest', required=True)
    args = ap.parse_args()
    manifest = collect_company(args.company, Path(args.output_dir), args.start_fy, args.budget_seconds, manifest_path=Path(args.manifest))
    print(json.dumps({'company': args.company, 'status': manifest['status'], 'reports': len(manifest['reports']), 'archive': manifest['archive_path']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
