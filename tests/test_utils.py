import time
import pytest

from collector.utils import (
    Budget,
    BudgetExpired,
    company_score,
    extract_end_year,
    fy_label,
    is_valid_pdf,
    normalize_company,
    safe_slug,
)


def test_normalize_company_ignores_legal_suffix_and_punctuation():
    assert normalize_company('Aavas Financiers Ltd.') == 'aavas financiers'
    assert normalize_company('Apex Capital & Finance Limited') == 'apex capital and finance'


def test_company_score_accepts_legal_name_variation():
    assert company_score('Aavas Financiers Ltd.', 'AAVAS FINANCIERS LIMITED') > 0.95


def test_extract_end_year_from_financial_year_range():
    assert extract_end_year('Annual Report 2011-12') == 2012
    assert extract_end_year('FY 2024-25') == 2025
    assert extract_end_year('Annual Report 2025') == 2025


def test_fy_label_maps_end_year_to_financial_year():
    assert fy_label(2012) == 'FY2011-12'
    assert fy_label(2025) == 'FY2024-25'


def test_safe_slug_is_stable_and_filesystem_safe():
    assert safe_slug('AKME Fintrade (India) Ltd.') == 'AKME_Fintrade_India_Ltd'


def test_pdf_validation_requires_signature_and_minimum_size():
    assert is_valid_pdf(b'%PDF-' + b'x' * 2000, 'application/pdf')
    assert not is_valid_pdf(b'<html>' + b'x' * 3000, 'application/pdf')
    assert not is_valid_pdf(b'%PDF-small', 'application/pdf')


def test_budget_expires_and_raises():
    budget = Budget(0.01)
    time.sleep(0.02)
    assert budget.expired
    with pytest.raises(BudgetExpired):
        budget.check()
