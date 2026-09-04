from pathlib import Path

from collector.collect_company import collect_company
from collector.sources import DiscoveryResult, ReportCandidate


class FakeResponse:
    def __init__(self, status_code=200, body=b'', content_type='application/pdf', url='https://example.com/a.pdf'):
        self.status_code = status_code
        self.headers = {'Content-Type': content_type}
        self.url = url
        self._body = body

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i+chunk_size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, *args, **kwargs):
        response = self.responses.pop(0)
        response.url = args[0]
        return response


def discovery(candidates):
    return DiscoveryResult(
        matched_name='Test Finance Ltd.',
        bse_code='123456',
        website_hint='https://example.com',
        official_page='https://example.com/investors',
        candidates=candidates,
        errors=[],
    )


def test_valid_pdf_is_downloaded_and_archived(tmp_path):
    pdf = b'%PDF-' + b'a' * 5000
    cands = [ReportCandidate(2025, 'https://example.com/a.pdf', 'Official company', '', 10)]
    manifest = collect_company(
        'Test Finance Ltd.', tmp_path, 2011, 30,
        session=FakeSession([FakeResponse(body=pdf)]),
        discovery=discovery(cands),
    )
    assert manifest['status'] == 'SUCCESS'
    assert manifest['reports'][0]['status'] == 'DOWNLOADED'
    assert Path(manifest['archive_path']).exists()


def test_404_falls_through_to_next_candidate(tmp_path):
    pdf = b'%PDF-' + b'b' * 5000
    cands = [
        ReportCandidate(2025, 'https://example.com/missing.pdf', 'Official company', '', 10),
        ReportCandidate(2025, 'https://example.com/good.pdf', 'BSE', '', 20),
    ]
    manifest = collect_company(
        'Test Finance Ltd.', tmp_path, 2011, 30,
        session=FakeSession([FakeResponse(status_code=404), FakeResponse(body=pdf)]),
        discovery=discovery(cands),
    )
    assert manifest['reports'][0]['status'] == 'DOWNLOADED'
    assert manifest['reports'][0]['source_url'].endswith('good.pdf')


def test_non_pdf_is_rejected(tmp_path):
    cands = [ReportCandidate(2025, 'https://example.com/not.pdf', 'Official company', '', 10)]
    manifest = collect_company(
        'Test Finance Ltd.', tmp_path, 2011, 30,
        session=FakeSession([FakeResponse(body=b'<html>' + b'x' * 5000)]),
        discovery=discovery(cands),
    )
    assert manifest['status'] == 'UNRESOLVED'
    assert manifest['reports'][0]['status'] == 'UNRESOLVED'


def test_zero_budget_returns_timeout_manifest_without_raising(tmp_path):
    manifest = collect_company(
        'Test Finance Ltd.', tmp_path, 2011, 0,
        session=FakeSession([]),
        discovery=discovery([]),
    )
    assert manifest['status'] == 'TIMEOUT'
    assert manifest['errors']
