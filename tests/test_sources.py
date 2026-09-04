from collector.sources import parse_report_links, bse_historical_candidates
from collector.utils import Budget


def test_parse_report_links_finds_annual_reports_and_excludes_notices():
    html = '''
    <html><body>
      <a href="/reports/ar-2024-25.pdf">Annual Report 2024-25</a>
      <a href="/reports/agm-2024-25.pdf">AGM Notice 2024-25</a>
      <a href="/reports/mgt7-2024-25.pdf">Annual Return MGT-7 2024-25</a>
      <a href="/reports/ar-2011-12.pdf">Annual Report 2011-12</a>
    </body></html>
    '''
    found = parse_report_links('https://example.com/investors/', html, 'Official company', 10)
    assert [(x.end_year, x.url) for x in found] == [
        (2012, 'https://example.com/reports/ar-2011-12.pdf'),
        (2025, 'https://example.com/reports/ar-2024-25.pdf'),
    ]


def test_bse_historical_candidate_uses_scrip_code_and_year():
    rows = bse_historical_candidates('Abhishek Finlease Ltd.', '538935', 2012)
    assert any('HIS_ANN_RPT/HISTANNR/2012/' in x.url for x in rows)
    assert any('538935' in x.url for x in rows)


def test_parse_report_links_respects_budget():
    budget = Budget(0)
    assert parse_report_links('https://example.com', '<a href="x.pdf">Annual Report 2024-25</a>', 'Official', 10, budget=budget) == []
