from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .utils import Budget, BudgetExpired, company_score, extract_end_year, normalize_company

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
SCREENER = 'https://www.screener.in'
EXCLUDES = ('agm notice', 'annual return', 'mgt-7', 'mgt 7', 'brsr', 'business responsibility', 'quarter', 'financial result', 'shareholding', 'notice')
COMMON_IR_PATHS = (
    '/investor-relations/annual-reports', '/investor-relations/annual-reports/',
    '/investors/annual-reports', '/investors/annual-reports/',
    '/investor/annual-reports', '/investor/annual-reports/',
    '/annual-reports', '/annual-reports/', '/annual-report', '/annual-report/',
    '/investor-relations', '/investors',
)
BAD_DOMAINS = {
    'moneycontrol.com', 'economictimes.indiatimes.com', 'marketscreener.com', 'screener.in',
    'goodreturns.in', 'business-standard.com', 'zaubacorp.com', 'tofler.in', 'trendlyne.com',
    'tickertape.in', 'investing.com', 'simplywall.st'
}


@dataclass(frozen=True)
class ReportCandidate:
    end_year: int
    url: str
    source_type: str
    context: str = ''
    priority: int = 50


@dataclass
class DiscoveryResult:
    matched_name: str = ''
    bse_code: str = ''
    website_hint: str = ''
    official_page: str = ''
    candidates: list[ReportCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _root_domain(url: str) -> str:
    host = urlparse(url).netloc.lower().split(':')[0]
    return host[4:] if host.startswith('www.') else host


def _get(session: requests.Session, url: str, budget: Budget, *, headers=None, stream=False):
    budget.check()
    return session.get(url, timeout=budget.request_timeout(), headers=headers, allow_redirects=True, stream=stream)


def parse_report_links(page_url: str, html: str, source_type: str, priority: int, budget: Budget | None = None) -> list[ReportCandidate]:
    if budget is not None and budget.expired:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    out: list[ReportCandidate] = []
    for a in soup.find_all('a', href=True):
        if budget is not None and budget.expired:
            break
        href = a.get('href', '').strip()
        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            continue
        anchor = ' '.join(a.stripped_strings)
        parent = ' '.join(a.parent.stripped_strings) if a.parent else ''
        context = f'{anchor} | {parent}'[:900]
        low = (context + ' ' + href).lower()
        if 'annual report' not in low and 'annual-report' not in low and 'annual_report' not in low:
            continue
        if any(x in low for x in EXCLUDES) and 'annual report' not in anchor.lower():
            continue
        if any(x in anchor.lower() for x in ('agm notice', 'annual return', 'mgt-7', 'mgt 7')):
            continue
        year = extract_end_year(context) or extract_end_year(href)
        if not year:
            continue
        out.append(ReportCandidate(year, urljoin(page_url, href), source_type, context, priority))
    return sorted(out, key=lambda x: (x.end_year, x.priority, x.url))


def _search_variants(company: str) -> list[str]:
    variants = [company]
    no_suffix = re.sub(r'\b(?:Private|Pvt\.?|Limited|Ltd\.?)\b', ' ', company, flags=re.I)
    no_suffix = re.sub(r'\s+', ' ', no_suffix).strip(' .,-')
    variants += [no_suffix, normalize_company(company)]
    out, seen = [], set()
    for v in variants:
        k = v.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(v)
    return out


def resolve_screener(session: requests.Session, company: str, budget: Budget):
    headers = {'User-Agent': UA, 'Accept': 'application/json,*/*;q=0.8', 'Referer': SCREENER + '/', 'X-Requested-With': 'XMLHttpRequest'}
    ranked = []
    for query in _search_variants(company):
        if budget.expired:
            break
        try:
            r = _get(session, f'{SCREENER}/api/company/search/?q={quote_plus(query)}', budget, headers=headers)
            if r.status_code != 200:
                continue
            for item in r.json() or []:
                if item.get('name') and item.get('url'):
                    ranked.append((company_score(company, item['name']), item))
        except Exception:
            continue
    if not ranked:
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1] if ranked[0][0] >= 0.48 else None


def _extract_screener_metadata(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    m = re.search(r'\bBSE\s*:\s*(\d{6})\b', text, re.I)
    bse = m.group(1) if m else ''
    website = ''
    for a in (soup.find(id='top') or soup).find_all('a', href=True):
        href = urljoin(SCREENER, a['href'])
        txt = a.get_text(' ', strip=True).lower()
        d = _root_domain(href)
        if d and d not in BAD_DOMAINS and not d.endswith('screener.in') and href.startswith('http'):
            if 'website' in txt:
                website = href
                break
            if not website:
                website = href
    return bse, website


def _decode_ddg(href: str) -> str:
    try:
        q = parse_qs(urlparse(href).query)
        if q.get('uddg'):
            return unquote(q['uddg'][0])
    except Exception:
        pass
    return href


def _search_web(session: requests.Session, query: str, budget: Budget, limit: int = 8) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    engines = [
        ('ddg', 'https://html.duckduckgo.com/html/?q=' + quote_plus(query)),
        ('bing', 'https://www.bing.com/search?q=' + quote_plus(query)),
    ]
    for engine, url in engines:
        if budget.expired:
            break
        try:
            r = _get(session, url, budget, headers={'User-Agent': UA})
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            nodes = soup.select('a.result__a[href]') if engine == 'ddg' else soup.select('li.b_algo h2 a[href]')
            for a in nodes:
                href = _decode_ddg(a['href']) if engine == 'ddg' else a['href']
                if href.startswith('http'):
                    results.append((href, ' '.join(a.stripped_strings)))
                    if len(results) >= limit:
                        return results
            if results:
                return results
        except Exception:
            continue
    return results


def discover_official_archive(session: requests.Session, company: str, website_hint: str, budget: Budget):
    candidates: list[str] = []
    if website_hint:
        p = urlparse(website_hint)
        root = f'{p.scheme or "https"}://{p.netloc}'
        candidates.append(website_hint)
        candidates.extend(urljoin(root + '/', x.lstrip('/')) for x in COMMON_IR_PATHS)
    if not budget.expired:
        for u, _ in _search_web(session, f'"{company}" "annual reports" investor relations', budget, 6):
            if _root_domain(u) not in BAD_DOMAINS:
                candidates.append(u)
    seen = set()
    for url in candidates[:16]:
        if budget.expired:
            break
        if url in seen:
            continue
        seen.add(url)
        try:
            r = _get(session, url, budget, headers={'User-Agent': UA})
            if r.status_code != 200:
                continue
            ctype = (r.headers.get('Content-Type') or '').lower()
            if 'pdf' in ctype or getattr(r, 'content', b'')[:4] == b'%PDF':
                continue
            found = parse_report_links(r.url, r.text, 'Official company', 10, budget)
            if found:
                return r.url, r.text, found
        except Exception:
            continue
    return '', '', []


def _bse_slugs(company: str) -> list[str]:
    s = company.upper().replace('&', ' AND ')
    s = re.sub(r'\bLIMITED\b', 'LTD', s)
    s = re.sub(r'[^A-Z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    variants = [s]
    if s.endswith('_LTD'):
        variants += [s[:-4], s[:-4] + '_LIMITED']
    return list(dict.fromkeys(variants))


def bse_historical_candidates(company: str, bse_code: str, end_year: int) -> list[ReportCandidate]:
    if not re.fullmatch(r'\d{6}', bse_code or ''):
        return []
    return [ReportCandidate(end_year, f'https://www.bseindia.com/HIS_ANN_RPT/HISTANNR/{end_year}/{slug}-{bse_code}-MARCH-{end_year}.PDF', 'BSE historical fallback', 'generated historical path', 40) for slug in _bse_slugs(company)]


def _dedupe(candidates: list[ReportCandidate]) -> list[ReportCandidate]:
    best = {}
    for c in candidates:
        key = (c.end_year, c.url.lower())
        if key not in best or c.priority < best[key].priority:
            best[key] = c
    return sorted(best.values(), key=lambda x: (x.end_year, x.priority, x.url))


def discover_candidates(session: requests.Session, company: str, start_end_year: int, budget: Budget) -> DiscoveryResult:
    result = DiscoveryResult()
    try:
        item = resolve_screener(session, company, budget)
        if item and not budget.expired:
            result.matched_name = item.get('name', '')
            r = _get(session, urljoin(SCREENER, item['url']), budget, headers={'User-Agent': UA})
            if r.status_code == 200:
                result.bse_code, result.website_hint = _extract_screener_metadata(r.text)
                result.candidates.extend(parse_report_links(r.url, r.text, 'Screener/BSE index', 30, budget))
    except BudgetExpired:
        raise
    except Exception as e:
        result.errors.append(f'Screener: {e}')

    try:
        if not budget.expired:
            page, _, found = discover_official_archive(session, company, result.website_hint, budget)
            result.official_page = page
            result.candidates.extend(found)
    except BudgetExpired:
        raise
    except Exception as e:
        result.errors.append(f'Official discovery: {e}')

    if not budget.expired:
        try:
            for url, title in _search_web(session, f'"{company}" "annual report" pdf', budget, 10):
                year = extract_end_year(title) or extract_end_year(url)
                if not year or year < start_end_year:
                    continue
                d = _root_domain(url)
                source = 'BSE search fallback' if d.endswith('bseindia.com') else 'NSE search fallback' if d.endswith('nseindia.com') else 'Search fallback'
                result.candidates.append(ReportCandidate(year, url, source, title, 35))
        except Exception as e:
            result.errors.append(f'Search fallback: {e}')

    result.candidates = [c for c in _dedupe(result.candidates) if c.end_year >= start_end_year]
    if result.bse_code:
        indexed_years = sorted({c.end_year for c in result.candidates if 'bse' in c.url.lower() or 'BSE' in c.source_type})
        for year in indexed_years:
            result.candidates.extend(bse_historical_candidates(result.matched_name or company, result.bse_code, year))
        result.candidates = _dedupe(result.candidates)
    return result
