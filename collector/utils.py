from __future__ import annotations

import difflib
import re
import time
from dataclasses import dataclass

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15
MIN_PDF_BYTES = 1024


class BudgetExpired(RuntimeError):
    pass


@dataclass
class Budget:
    seconds: float

    def __post_init__(self) -> None:
        self.started = time.monotonic()
        self.deadline = self.started + max(0.0, float(self.seconds))

    @property
    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    @property
    def expired(self) -> bool:
        return self.remaining <= 0

    def check(self) -> None:
        if self.expired:
            raise BudgetExpired("company budget exhausted")

    def request_timeout(self) -> tuple[float, float]:
        self.check()
        remaining = max(0.1, self.remaining)
        return (min(CONNECT_TIMEOUT, remaining), min(READ_TIMEOUT, remaining))


def normalize_company(name: str) -> str:
    s = name.lower().replace('&', ' and ')
    s = re.sub(r'\b(private|pvt)\b\.?', ' ', s)
    s = re.sub(r'\b(limited|ltd)\b\.?', ' ', s)
    s = re.sub(r'\b(company|co)\b\.?', ' ', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def company_score(a: str, b: str) -> float:
    na, nb = normalize_company(a), normalize_company(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / max(1, len(ta | tb))
    contains = 1.0 if na in nb or nb in na else 0.0
    return min(1.0, 0.55 * seq + 0.35 * jac + 0.10 * contains)


def extract_end_year(text: str) -> int | None:
    if not text:
        return None
    s = text.replace('–', '-').replace('—', '-').replace('−', '-')
    m = re.search(r'\b((?:19|20)\d{2})\s*[-/]\s*(\d{2,4})\b', s)
    if m:
        y1 = int(m.group(1))
        raw = m.group(2)
        if len(raw) == 2:
            y2 = (y1 // 100) * 100 + int(raw)
            if y2 < y1:
                y2 += 100
        else:
            y2 = int(raw)
        if y1 <= y2 <= y1 + 1:
            return y2
    m = re.search(r'(?:annual\s+report|financial\s+year|\bfy\b)\D{0,16}((?:19|20)\d{2})\b', s, re.I)
    if m:
        return int(m.group(1))
    return None


def fy_label(end_year: int) -> str:
    return f"FY{end_year - 1}-{str(end_year)[-2:]}"


def safe_slug(text: str) -> str:
    s = re.sub(r'[^A-Za-z0-9]+', '_', text).strip('_')
    s = re.sub(r'_+', '_', s)
    return s[:120] or 'company'


def is_valid_pdf(data: bytes, content_type: str = '') -> bool:
    return len(data) >= MIN_PDF_BYTES and data.startswith(b'%PDF')
