from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.utils import safe_slug


def build_matrix(path: Path, only: list[str] | None = None):
    companies = [x.strip() for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    seen = set()
    unique = []
    for c in companies:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    if only:
        wanted = {x.strip().lower() for x in only if x.strip()}
        unique = [c for c in unique if c.lower() in wanted]
    return {'include': [{'index': i, 'company': c, 'slug': safe_slug(c)} for i, c in enumerate(unique, 1)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path', type=Path)
    ap.add_argument('--only', default='')
    args = ap.parse_args()
    only = [x for x in args.only.split(';') if x.strip()] if args.only else None
    print(json.dumps(build_matrix(args.path, only=only), separators=(',', ':')))


if __name__ == '__main__':
    main()
