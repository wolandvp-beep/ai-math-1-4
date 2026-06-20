#!/usr/bin/env python3
"""Math AI 1-4 release/audit automation helper.

V507.05 goal: remove repetitive manual GitHub Pages deployment while keeping the
quality gates strict. The script is intentionally conservative: it can prepare
and validate a release package, generate the self-hosted audit URL, and check a
final-report URL. It does not accept a batch unless all proof fields show real
API/token/DOM work.

Run from the project root that contains `backend/` and `frontend/`:

    python -B backend/release_pipeline.py --offset 400 --limit 100

To validate a final report:

    python -B backend/release_pipeline.py --final-report-url https://.../final-report/...
"""
from __future__ import annotations

import argparse
import json
import html as _html
import re
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

DEFAULT_BACKEND_BASE_URL = 'https://wolandvp-beep-ai-math-1-4-8e2f.twc1.net'
DEFAULT_RELEASE = 'v507_05_short_final_report_parking'
DEFAULT_AUDIT_KEY = 'v507-05-live-audit'
DEFAULT_SECTION = 'excel_numeric_regression'
DEFAULT_OFFSET = 400
DEFAULT_LIMIT = 100
MAX_BACKEND_FILES = 100
MAX_FRONTEND_FILES = 100
GARBAGE_NAMES = {'__pycache__', '.DS_Store', 'Thumbs.db'}
GARBAGE_SUFFIXES = {'.pyc', '.pyo', '.tmp', '.log'}


def _root() -> Path:
    here = Path(__file__).resolve()
    if here.parent.name == 'backend':
        return here.parent.parent
    cwd = Path.cwd().resolve()
    if (cwd / 'backend').is_dir() and (cwd / 'frontend').is_dir():
        return cwd
    raise SystemExit('Run from project root with backend/ and frontend/, or from backend/release_pipeline.py')


def _count_files(path: Path) -> int:
    return sum(1 for p in path.rglob('*') if p.is_file())


def _cleanup_garbage(root: Path) -> None:
    for p in sorted(root.rglob('*'), reverse=True):
        if p.name == '__pycache__' and p.is_dir():
            for child in sorted(p.rglob('*'), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            p.rmdir()
        elif p.is_file() and (p.name in GARBAGE_NAMES or p.suffix in GARBAGE_SUFFIXES):
            p.unlink()


def _garbage_files(root: Path) -> list[str]:
    bad: list[str] = []
    for p in root.rglob('*'):
        if p.name in GARBAGE_NAMES or p.suffix in GARBAGE_SUFFIXES:
            bad.append(str(p.relative_to(root)))
    return sorted(bad)


def _compile_backend(root: Path) -> None:
    py_files = [str(p) for p in sorted((root / 'backend').rglob('*.py'))]
    if py_files:
        subprocess.run([sys.executable, '-B', '-m', 'py_compile', *py_files], check=True)


def _node_check(root: Path) -> None:
    bundle = root / 'frontend' / 'app.bundle.js'
    if not bundle.is_file():
        raise SystemExit('frontend/app.bundle.js not found')
    subprocess.run(['node', '--check', str(bundle)], check=True)


def preflight(root: Path) -> dict[str, Any]:
    _cleanup_garbage(root)
    _compile_backend(root)
    _cleanup_garbage(root)
    _node_check(root)
    _cleanup_garbage(root)
    backend_files = _count_files(root / 'backend')
    frontend_files = _count_files(root / 'frontend')
    bad = _garbage_files(root)
    if backend_files > MAX_BACKEND_FILES:
        raise SystemExit(f'backend file limit exceeded: {backend_files} > {MAX_BACKEND_FILES}')
    if frontend_files > MAX_FRONTEND_FILES:
        raise SystemExit(f'frontend file limit exceeded: {frontend_files} > {MAX_FRONTEND_FILES}')
    if bad:
        raise SystemExit('garbage files found: ' + ', '.join(bad[:20]))
    return {
        'backendFiles': backend_files,
        'frontendFiles': frontend_files,
        'garbageFiles': 0,
        'pyCompile': True,
        'nodeCheck': True,
    }


def audit_url(backend_base_url: str, frontend_url: str, release: str, audit_key: str, section: str, offset: int, limit: int, cache_bust: str | None = None) -> str:
    frontend_url = frontend_url.rstrip('/') + '/'
    query = urlencode({
        'matematichkaUiAudit': 'frontend-operator',
        'backendBaseUrl': backend_base_url.rstrip('/'),
        'release': release,
        'auditKey': audit_key,
        'section': section,
        'offset': str(offset),
        'limit': str(limit),
        'autoStart': '1',
        'cacheBust': cache_bust or release.replace('_', '-'),
    })
    return frontend_url + '?' + query


def build_zip(root: Path, out_path: Path) -> None:
    if out_path.exists():
        out_path.unlink()
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for top in ('backend', 'frontend'):
            base = root / top
            for p in sorted(base.rglob('*')):
                if p.is_file():
                    zf.write(p, p.relative_to(root).as_posix())


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read()
    text = data.decode('utf-8')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'<h2>JSON</h2><pre>(.*?)</pre>', text, flags=re.S | re.I)
        if not match:
            raise
        return json.loads(_html.unescape(match.group(1)))


def gate_report(report: dict[str, Any], planned: int | None = None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    expected = int(planned or report.get('planned') or DEFAULT_LIMIT)
    checks = {
        'finalAcceptance': report.get('finalAcceptance') is True,
        'status_done': report.get('status') == 'done',
        'completed_equals_planned': int(report.get('completed') or 0) == int(report.get('planned') or expected),
        'failed_zero': int(report.get('failed') or 0) == 0,
        'numeric_failed_zero': int(report.get('numericFailedCount') or 0) == 0,
        'suspicious_zero': int(report.get('suspiciousPassedCount') or 0) == 0,
        'external_calls': int(report.get('externalApiCalls') or 0) >= expected,
        'external_completed': int(report.get('externalApiCompleted') or 0) >= expected,
        'usage_proofs': int(report.get('deepseekUsageProofs') or 0) >= expected,
        'tokens_positive': int(report.get('apiTotalTokens') or 0) > 0,
        'cached_zero': int(report.get('cachedResults') or 0) == 0,
        'browser_fetch': int(report.get('browserClientFetchCompleted') or 0) >= expected,
        'evidence_rows': int(report.get('evidenceResultsCount') or 0) >= expected,
        'generalization': report.get('v500GeneralizationAcceptance') is True,
        'case_specific_zero': int(report.get('v500CaseSpecificRepairCount') or 0) == 0,
        'learning_coverage': float(report.get('v501LearningCoverageRatio') or report.get('v500TemplateCoverageRatio') or 0.0) >= 0.80,
        'trusted_api_number_violations_zero': int(report.get('v50503TrustedApiNumberViolationCount') or 0) == 0,
    }
    # If this field is present, strict mode requires no unapproved numeric changes.
    changed = int(report.get('v501PostprocessChangedAnswerNumberCount') or 0)
    if changed:
        allowed = sum(1 for item in report.get('evidenceResults') or [] if isinstance(item, dict) and item.get('v502ExplicitMultiAnswerTemplate'))
        checks['postprocess_answer_number_guard'] = changed <= allowed
    for name, ok in checks.items():
        if not ok:
            reasons.append(name)
    return not reasons, reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Math AI 1-4 V507 release/audit pipeline helper')
    parser.add_argument('--release', default=DEFAULT_RELEASE)
    parser.add_argument('--audit-key', default=DEFAULT_AUDIT_KEY)
    parser.add_argument('--section', default=DEFAULT_SECTION)
    parser.add_argument('--offset', type=int, default=DEFAULT_OFFSET)
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT)
    parser.add_argument('--backend-base-url', default=os.environ.get('PUBLIC_BACKEND_BASE_URL') or os.environ.get('PUBLIC_BACKEND_URL') or DEFAULT_BACKEND_BASE_URL)
    parser.add_argument('--frontend-url', default=os.environ.get('PUBLIC_FRONTEND_URL') or (DEFAULT_BACKEND_BASE_URL + '/app/'))
    parser.add_argument('--zip-out', default='')
    parser.add_argument('--final-report-url', default='')
    args = parser.parse_args(argv)

    root = _root()
    report = {'root': str(root)}
    report['preflight'] = preflight(root)
    report['auditUrl'] = audit_url(args.backend_base_url, args.frontend_url, args.release, args.audit_key, args.section, args.offset, args.limit)
    if args.zip_out:
        out = Path(args.zip_out).resolve()
        build_zip(root, out)
        report['zipOut'] = str(out)
    if args.final_report_url:
        final = fetch_json(args.final_report_url)
        accepted, reasons = gate_report(final, planned=args.limit)
        report['finalReportGate'] = {'accepted': accepted, 'reasons': reasons}
        report['finalReportSummary'] = {
            'release': final.get('release'),
            'planned': final.get('planned'),
            'completed': final.get('completed'),
            'passed': final.get('passed'),
            'failed': final.get('failed'),
            'numericFailedCount': final.get('numericFailedCount'),
            'externalApiCompleted': final.get('externalApiCompleted'),
            'deepseekUsageProofs': final.get('deepseekUsageProofs'),
            'apiTotalTokens': final.get('apiTotalTokens'),
            'cachedResults': final.get('cachedResults'),
            'v500GeneralizationAcceptance': final.get('v500GeneralizationAcceptance'),
            'v500CaseSpecificRepairCount': final.get('v500CaseSpecificRepairCount'),
            'v501LearningCoverageRatio': final.get('v501LearningCoverageRatio'),
            'v50503TrustedApiAuthoritativeCount': final.get('v50503TrustedApiAuthoritativeCount'),
            'v50503TrustedApiNumberPreservedCount': final.get('v50503TrustedApiNumberPreservedCount'),
            'v50503TrustedApiNumberViolationCount': final.get('v50503TrustedApiNumberViolationCount'),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
