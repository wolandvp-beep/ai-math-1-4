from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from html import escape

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from backend.platform.modules.core.public.services.access.config import build_public_product_config
from backend.platform.modules.core.public.services.access.service import (
    AccessService,
    AccessServiceError,
    LimitExceededError,
)
from backend.platform.modules.core.public.services.access.store import JsonAccessStateStore, resolve_state_file_path
from backend.service import APP_RELEASE, SOLVER_VERSION, attach_release, deepseek_api_key_configured, generate_explanation_response, prevalidate_explanation_request, resolve_solver_mode
from backend.diagnostic_audit import DEFAULT_AUDIT_CASES, _check_payload, _normalize_case, run_math_audit


app = FastAPI()
_ACCESS_SERVICE: AccessService | None = None
_ACCESS_SERVICE_STATE_PATH: str | None = None

NO_CACHE_HEADERS = {
    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    'Pragma': 'no-cache',
    'Expires': '0',
    'X-Matematichka-Release': APP_RELEASE,
}


def _json_ok(payload: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers=NO_CACHE_HEADERS)


def _html_ok(body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(body, status_code=status_code, headers=NO_CACHE_HEADERS)


CARD_DATA_BLOCK_MESSAGE = (
    'Данные банковской карты нельзя отправлять в приложение. '
    'Оплата подписки проходит только на стороне Robokassa.'
)


FRONTEND_EXPECTED_BACKEND_RELEASE = APP_RELEASE


def _public_base_url(request: Request | None = None) -> str:
    env_base = (
        os.environ.get('PUBLIC_BACKEND_URL')
        or os.environ.get('BACKEND_PUBLIC_URL')
        or os.environ.get('APP_PUBLIC_URL')
        or ''
    ).strip().rstrip('/')
    if env_base:
        return env_base
    if request is None:
        return 'https://wolandvp-beep-ai-math-1-4-8e2f.twc1.net'
    forwarded_host = (request.headers.get('x-forwarded-host') or '').split(',')[0].strip()
    host = forwarded_host or (request.headers.get('host') or '').split(',')[0].strip()
    forwarded_proto = (request.headers.get('x-forwarded-proto') or '').split(',')[0].strip()
    scheme = forwarded_proto or request.url.scheme or 'https'
    if host and host.endswith('.twc1.net') and scheme == 'http':
        scheme = 'https'
    if host:
        return f'{scheme}://{host}'.rstrip('/')
    raw = str(request.base_url).rstrip('/')
    if raw.startswith('http://') and 'twc1.net' in raw:
        raw = 'https://' + raw[len('http://'):]
    return raw


def _next_live_audit_links(request: Request | None = None, key: str | None = None) -> dict:
    audit_key = key or os.environ.get('LIVE_AUDIT_PUBLIC_HINT_KEY') or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY
    base_url = _public_base_url(request)
    release_token = APP_RELEASE
    start_path = f'/api/diagnostics/live-audit/start-next/{release_token}/{audit_key}'
    control_path = f'/api/diagnostics/live-audit/control/{release_token}/{audit_key}'
    status_template = f'/api/diagnostics/live-audit/status-run/{release_token}/{audit_key}/{{runId}}'
    summary_template = f'/api/diagnostics/live-audit/summary-run/{release_token}/{audit_key}/{{runId}}'
    failures_template = f'/api/diagnostics/live-audit/failures-run/{release_token}/{audit_key}/{{runId}}'
    results_template = f'/api/diagnostics/live-audit/results-run/{release_token}/{audit_key}/{{runId}}'
    results_full_template = f'/api/diagnostics/live-audit/results-full-run/{release_token}/{audit_key}/{{runId}}'
    evidence_template = f'/api/diagnostics/live-audit/evidence-run/{release_token}/{audit_key}/{{runId}}'
    suspicious_template = f'/api/diagnostics/live-audit/suspicious-run/{release_token}/{audit_key}/{{runId}}'
    acceptance_template = f'/api/diagnostics/live-audit/acceptance-run/{release_token}/{audit_key}/{{runId}}'
    report_template = f'/api/diagnostics/live-audit/report-run/{release_token}/{audit_key}/{{runId}}'
    legacy_start_query = urlencode([
        ('section', 'g1_arithmetic_actions'),
        ('key', audit_key),
        ('limit', '100'),
        ('offset', '0'),
        ('allowExternal', '1'),
        ('maxExternalCalls', '150'),
        ('release', APP_RELEASE),
        ('cacheBust', APP_RELEASE),
    ])
    legacy_start_path = f'/api/diagnostics/live-audit/start?{legacy_start_query}'
    return {
        'nextAuditPlannedMapStep': 'V296.03 — 1 класс, раздел 2 — Арифметические действия, proof audit + stable operator run',
        'nextAuditSection': 'g1_arithmetic_actions',
        'nextAuditLimit': 100,
        'nextAuditRelease': APP_RELEASE,
        'nextAuditCacheBust': APP_RELEASE,
        'nextAuditControlPath': control_path,
        'nextAuditControlUrl': base_url + control_path,
        'nextAuditStartPath': start_path,
        'nextAuditStartUrl': base_url + start_path,
        'nextAuditStartUrlPathBased': True,
        'nextAuditRootIsClickableDashboard': True,
        'nextAuditStatusUrlTemplate': base_url + status_template,
        'nextAuditSummaryUrlTemplate': base_url + summary_template,
        'nextAuditFailuresUrlTemplate': base_url + failures_template,
        'nextAuditResultsUrlTemplate': base_url + results_template,
        'nextAuditResultsFullUrlTemplate': base_url + results_full_template,
        'nextAuditEvidenceUrlTemplate': base_url + evidence_template,
        'nextAuditSuspiciousUrlTemplate': base_url + suspicious_template,
        'nextAuditAcceptanceUrlTemplate': base_url + acceptance_template,
        'nextAuditReportUrlTemplate': base_url + report_template,
        'nextAuditEvidenceRequired': True,
        'nextAuditAcceptanceRule': 'Раздел принимать только если acceptancePassed=true: status=done, completed=planned, failed=0, failures=0, suspicious=0, evidence rows=planned, external API evidence present.',
        'nextAuditUserRunWorkflow': [
            '1) Откройте nextAuditStartUrl в браузере со своего компьютера.',
            '2) Периодически открывайте statusFreshUrl/summaryFreshUrl до status=done.',
            '3) Пришлите ChatGPT acceptanceFreshUrl или reportFreshUrl; одного aggregate summary недостаточно.',
        ],
        'nextAuditLocalOperatorWorkflow': 'Лучший вариант: запускать audit в своём браузере/на своём компьютере, а ChatGPT присылать готовую ссылку acceptanceFreshUrl или reportFreshUrl для анализа.',
        'nextAuditLegacyStartPath': legacy_start_path,
        'nextAuditLegacyStartUrl': base_url + legacy_start_path,
        'nextAuditQueryOrderSafe': True,
        'nextAuditNoSectionEntityRisk': True,
        'nextAuditNoQueryParamReorderRisk': True,
        'nextAuditNote': 'Повторные status/summary/failures/results/evidence/suspicious/acceptance/report не вызывают DeepSeek; повторный start без force=1 переиспользует run/cache текущего release.',
    }

def _version_payload(request: Request | None = None) -> dict:
    return {
        'release': APP_RELEASE,
        'backendBuild': APP_RELEASE,
        'solverVersion': SOLVER_VERSION,
        'frontendExpectedBackend': FRONTEND_EXPECTED_BACKEND_RELEASE,
        'solverMode': resolve_solver_mode(),
        'deepseekApiKeyConfigured': deepseek_api_key_configured(),
        'status': 'ok',
        **_next_live_audit_links(request),
    }


LIVE_PRODUCTION_AUDIT_DEFAULT_KEY = 'v296.03-live-audit'
LIVE_PRODUCTION_AUDIT_MAX_LIMIT = 50
LIVE_PRODUCTION_AUDIT_REPRESENTATIVE_NAMES = (
    'v280_route_multi_task_newline_warning',
    'v280_g1_place_value_write_47',
    'write_5',
    'read_14',
    'read_18',
    'cmp_12_18',
    'after_17',
    'between_14_16',
    'inc_12_3',
    'dec_18_6',
    'more_diff_12_7',
    'order_14_11_18',
    'series_by_2',
    'series_by_5',
    'dm_cm_to_cm_15',
    'compare_len',
    'count_fruits',
    'v287_add_7_5',
    'v287_sub_15_8',
    'v287_missing_add_6_to_13',
    'v287_compare_expr_equal_8_5_14_1',
    'v281_g3_place_value_write_384',
    'v281_g4_expr_parentheses_420',
    'v281_g3_library_boxes',
    'v281_g4_two_cars_towards',
    'v281_g4_square_area_from_perimeter',
    'v281_g3_table_total_visitors',
)


def _live_audit_key_matches(key: str | None) -> bool:
    expected = (
        os.environ.get('LIVE_AUDIT_KEY')
        or os.environ.get('MATH_AUDIT_KEY')
        or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY
    ).strip()
    return bool(expected) and str(key or '').strip() == expected


def _case_matches_v285_numbers_values(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v285_') or name.startswith('v285_')




def _case_matches_v289_numbers_values(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v289_') or name.startswith('v289_')

def _case_matches_current_programmatic_section(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v296_') or name.startswith('v296_')


def _select_live_production_cases(section: str) -> list[dict[str, Any]]:
    section_key = str(section or 'representative').strip().lower().replace('-', '_')
    cases = list(DEFAULT_AUDIT_CASES)
    if section_key in {'v285', 'g1_numbers_values_v285'}:
        return [case for case in cases if _case_matches_v285_numbers_values(case)]
    if section_key in {'g1_numbers_values', 'g1_section1', 'g1_numbers_values_v289', 'current_section', 'v289'}:
        return [case for case in cases if _case_matches_v289_numbers_values(case)]
    if section_key in {'g1_arithmetic_actions', 'g1_section2', 'v296'}:
        return [case for case in cases if _case_matches_current_programmatic_section(case)]
    if section_key in {'llm_fallback_smoke', 'deepseek_primary_smoke', 'deepseek_smoke'}:
        preferred = {
            'v287_add_7_5',
            'v287_sub_15_8',
            'v287_missing_add_6_to_13',
            'v287_compare_expr_equal_8_5_14_1',
            'v281_g3_library_boxes',
            'v281_g4_two_cars_towards',
            'v281_g4_square_area_from_perimeter',
            'v281_g3_table_total_visitors',
            'v280_g1_place_value_write_47',
            'count_fruits',
            'v289_write_digit_5',
            'v289_compare_12_15',
            'v289_dm_cm_1_5',
        }
        selected = [case for case in cases if str(case.get('name') or case.get('id') or '') in preferred]
        return selected or [case for case in cases if not str(case.get('expectedSource') or '').startswith('guard')][:10]
    if section_key in {'all', 'full'}:
        return cases
    if section_key in {'representative', 'smoke', 'sample'}:
        by_name: dict[str, dict[str, Any]] = {
            str(case.get('name') or case.get('id') or ''): case for case in cases
        }
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for name in LIVE_PRODUCTION_AUDIT_REPRESENTATIVE_NAMES:
            case = by_name.get(name)
            if case is not None:
                selected.append(case)
                seen.add(str(case.get('name') or case.get('id') or ''))
        # Fill the sample with one case from each category so the default audit
        # touches many solver families without running the whole accumulated suite.
        seen_categories: set[str] = {str(case.get('category') or '') for case in selected}
        for case in cases:
            category = str(case.get('category') or '')
            name = str(case.get('name') or case.get('id') or '')
            if name in seen or category in seen_categories:
                continue
            selected.append(case)
            seen.add(name)
            seen_categories.add(category)
            if len(selected) >= 50:
                break
        return selected
    if section_key.startswith('category:'):
        category = section_key.split(':', 1)[1]
        return [case for case in cases if str(case.get('category') or '').lower() == category]
    return cases


def _source_looks_external(source: str, payload: dict[str, Any]) -> bool:
    source_l = str(source or '').lower()
    fallback_path_l = str(payload.get('fallback_path') or '').lower()
    return bool(
        source_l.startswith(('legacy-ai', 'legacy-fallback', 'fallback'))
        or fallback_path_l.startswith(('legacy-ai', 'legacy-fallback', 'fallback'))
        or 'deepseek' in source_l
        or 'deepseek' in fallback_path_l
    )


async def _generate_with_external_call_counter(text: str, *, allow_external: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    import backend.legacy_core as legacy_core

    original_call = getattr(legacy_core, 'call_deepseek', None)
    counter = {
        'externalApiAttempts': 0,
        'externalApiCompleted': 0,
        'externalApiBlocked': 0,
        'externalApiErrors': 0,
    }

    if not callable(original_call):
        payload = await generate_explanation_response(text, solver_mode='deepseek_primary', allow_external=allow_external)
        return payload, counter

    async def counted_call_deepseek(*args, **kwargs):
        counter['externalApiAttempts'] += 1
        if not allow_external:
            counter['externalApiBlocked'] += 1
            raise RuntimeError('External API call blocked by live-production-audit allowExternal=false')
        try:
            result = await original_call(*args, **kwargs)
            counter['externalApiCompleted'] += 1
            return result
        except Exception:
            counter['externalApiErrors'] += 1
            raise

    setattr(legacy_core, 'call_deepseek', counted_call_deepseek)
    try:
        payload = await generate_explanation_response(text, solver_mode='deepseek_primary', allow_external=allow_external)
    finally:
        setattr(legacy_core, 'call_deepseek', original_call)
    return payload, counter


# --- v290 live audit runner with persistent cache and short summary endpoints ---
LIVE_AUDIT_RUNNER_PROMPT_VERSION = 'v296.03-g1-arithmetic-actions-proof-audit-v1'
LIVE_AUDIT_RUNNER_MAX_LIMIT = 200
LIVE_AUDIT_RUNNER_DEFAULT_MAX_EXTERNAL_CALLS = 100
LIVE_AUDIT_RUNNER_STATE_ENV = 'LIVE_AUDIT_STATE_FILE'


def _live_audit_env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name) or default)
    except Exception:
        return float(default)


LIVE_AUDIT_RUNNER_CASE_TIMEOUT_SECONDS = _live_audit_env_float('LIVE_AUDIT_CASE_TIMEOUT_SECONDS', 55.0)
LIVE_AUDIT_RUNNER_STALE_SECONDS = _live_audit_env_float('LIVE_AUDIT_STALE_SECONDS', 90.0)
_LIVE_AUDIT_STATE_LOCK = threading.Lock()
_LIVE_AUDIT_TASKS: dict[str, asyncio.Task] = {}


def _live_audit_state_path() -> Path:
    raw = (
        os.environ.get(LIVE_AUDIT_RUNNER_STATE_ENV)
        or os.environ.get('LIVE_AUDIT_CACHE_FILE')
        or os.environ.get('MATH_AUDIT_STATE_FILE')
        or '/tmp/matematichka_live_audit_runner_cache.json'
    )
    return Path(raw)


def _empty_live_audit_state() -> dict[str, Any]:
    return {'schema': 1, 'runs': {}, 'plans': {}, 'caseCache': {}}


def _read_live_audit_state_unlocked() -> dict[str, Any]:
    path = _live_audit_state_path()
    if not path.is_file():
        return _empty_live_audit_state()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return _empty_live_audit_state()
    if not isinstance(data, dict):
        return _empty_live_audit_state()
    data.setdefault('schema', 1)
    data.setdefault('runs', {})
    data.setdefault('plans', {})
    data.setdefault('caseCache', {})
    if not isinstance(data.get('runs'), dict):
        data['runs'] = {}
    if not isinstance(data.get('plans'), dict):
        data['plans'] = {}
    if not isinstance(data.get('caseCache'), dict):
        data['caseCache'] = {}
    return data


def _write_live_audit_state_unlocked(state: dict[str, Any]) -> None:
    path = _live_audit_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp_path.replace(path)


def _load_live_audit_state() -> dict[str, Any]:
    with _LIVE_AUDIT_STATE_LOCK:
        return _read_live_audit_state_unlocked()


def _save_live_audit_state(state: dict[str, Any]) -> None:
    with _LIVE_AUDIT_STATE_LOCK:
        _write_live_audit_state_unlocked(state)


def _mutate_live_audit_state(mutator) -> Any:
    with _LIVE_AUDIT_STATE_LOCK:
        state = _read_live_audit_state_unlocked()
        result = mutator(state)
        _write_live_audit_state_unlocked(state)
        return result


def _now_ts() -> float:
    return time.time()


def _short_hash(value: Any, length: int = 16) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:length]


def _live_audit_fresh_nonce() -> str:
    # Web automation may cache exact URLs. A nonce in the path makes every
    # status/summary/failures/results/evidence/acceptance/report click a fresh URL while preserving no-token-spend
    # semantics on the backend.
    now = _now_ts()
    return f"{int(now * 1000)}-{_short_hash({'t': now, 'pid': os.getpid(), 'thread': threading.get_ident()}, 8)}"


def _live_audit_fresh_paths(run_id: str, key: str | None = None) -> dict[str, str]:
    audit_key = str(key or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY).strip()
    nonce = _live_audit_fresh_nonce()
    status_path = f'/api/diagnostics/live-audit/status-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    summary_path = f'/api/diagnostics/live-audit/summary-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    failures_path = f'/api/diagnostics/live-audit/failures-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    results_path = f'/api/diagnostics/live-audit/results-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    results_full_path = f'/api/diagnostics/live-audit/results-full-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    evidence_path = f'/api/diagnostics/live-audit/evidence-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    suspicious_path = f'/api/diagnostics/live-audit/suspicious-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    acceptance_path = f'/api/diagnostics/live-audit/acceptance-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    report_path = f'/api/diagnostics/live-audit/report-fresh/{APP_RELEASE}/{audit_key}/{run_id}/{nonce}'
    base_url = _public_base_url(None)
    return {
        'freshNonce': nonce,
        'statusFreshPath': status_path,
        'summaryFreshPath': summary_path,
        'failuresFreshPath': failures_path,
        'resultsFreshPath': results_path,
        'resultsFullFreshPath': results_full_path,
        'evidenceFreshPath': evidence_path,
        'suspiciousFreshPath': suspicious_path,
        'acceptanceFreshPath': acceptance_path,
        'reportFreshPath': report_path,
        'statusFreshUrl': base_url + status_path,
        'summaryFreshUrl': base_url + summary_path,
        'failuresFreshUrl': base_url + failures_path,
        'resultsFreshUrl': base_url + results_path,
        'resultsFullFreshUrl': base_url + results_full_path,
        'evidenceFreshUrl': base_url + evidence_path,
        'suspiciousFreshUrl': base_url + suspicious_path,
        'acceptanceFreshUrl': base_url + acceptance_path,
        'reportFreshUrl': base_url + report_path,
        'freshPollingCacheBypass': True,
        'freshPollingNote': 'Use FRESH links for repeated polling and evidence export; every click has a new path nonce and does not force/re-spend completed cases. V296.03 acceptance requires evidence/results/suspicious/acceptance/report proof, not only aggregate summary.',
    }


def _live_audit_plan_key(section: str, offset: int, limit: int, allow_external: bool, max_external_calls: int) -> str:
    return _short_hash({
        'release': APP_RELEASE,
        'solverVersion': SOLVER_VERSION,
        'runnerPromptVersion': LIVE_AUDIT_RUNNER_PROMPT_VERSION,
        'section': str(section or '').strip().lower(),
        'offset': offset,
        'limit': limit,
        'allowExternal': bool(allow_external),
        'maxExternalCalls': int(max_external_calls),
    })


def _live_audit_case_cache_key(case: dict[str, Any], allow_external: bool) -> str:
    return _short_hash({
        'release': APP_RELEASE,
        'solverVersion': SOLVER_VERSION,
        'runnerPromptVersion': LIVE_AUDIT_RUNNER_PROMPT_VERSION,
        'solverMode': resolve_solver_mode(),
        'allowExternal': bool(allow_external),
        'id': case.get('id') or case.get('name'),
        'text': case.get('text'),
        'expected': case.get('expected'),
        'expectedFinalAnswer': case.get('expectedFinalAnswer'),
        'expectedUnit': case.get('expectedUnit'),
    }, length=24)


def _live_audit_text(value: Any, limit: int = 8000) -> str:
    text = str(value or '')
    if len(text) > limit:
        return text[:limit] + f'… [truncated {len(text) - limit} chars]'
    return text


def _live_audit_extract_answer_line(result: str) -> str:
    match = re.search(r'Ответ\s*:\s*(.+)', str(result or ''), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ''
    return match.group(1).splitlines()[0].strip().rstrip('.')


def _live_audit_expected_answer_text(row: dict[str, Any]) -> str:
    final = str(row.get('expectedFinalAnswer') or '').strip()
    if final:
        return final
    expected = row.get('expected')
    if isinstance(expected, list):
        return '; '.join(str(item) for item in expected)
    return str(expected or '').strip()


def _live_audit_row_is_guard(row: dict[str, Any]) -> bool:
    expected_source = str(row.get('expectedSource') or '')
    category = str(row.get('category') or '').lower()
    source = str(row.get('source') or '').lower()
    return bool(expected_source.startswith('guard') or 'guard' in category or source.startswith('guard'))


def _live_audit_forbidden_markers() -> tuple[str, ...]:
    return (
        'Применяем правило:',
        'Zad3',
        'deterministic regression',
        'lookup',
        'answer map',
        'generic fallback',
        '<html',
        '<body',
        '<script',
        '```',
        '###',
    )


def _live_audit_strict_format_issues(case: dict[str, Any], result_text: str, *, is_guard_case: bool) -> list[str]:
    if is_guard_case:
        return []
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    if not (category.startswith('v296_') or name.startswith('v296_')):
        return []
    text = str(result_text or '')
    low = text.lower().replace('ё', 'е')
    issues: list[str] = []
    if not re.search(r'задача\s*[\.:]', low):
        issues.append('strict proof: missing Задача. header')
    if not re.search(r'решение\s*[\.:]', low):
        issues.append('strict proof: missing Решение. header')
    if 'ответ:' not in low:
        issues.append('strict proof: missing Ответ: line')
    if not re.search(r'(?m)^\s*1\)\s*\S+', text):
        issues.append('strict proof: missing numbered solution step 1)')
    answer = _live_audit_extract_answer_line(text).lower().replace('ё', 'е')
    if not answer:
        issues.append('strict proof: empty answer after Ответ:')
    if any(bad in answer for bad in ('не уверен', 'нужно уточнить', 'уточните', 'не могу', 'не удалось')):
        issues.append('strict proof: low-confidence/clarification text used as final answer')
    for marker in _live_audit_forbidden_markers():
        if marker.lower() in low:
            issues.append(f'strict proof: forbidden marker in result: {marker}')
    return issues


def _live_audit_suspicion_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    result_text = str(row.get('resultText') or row.get('resultPreview') or '')
    low = result_text.lower().replace('ё', 'е')
    is_guard = _live_audit_row_is_guard(row)
    if bool(row.get('ok')):
        if not is_guard and not bool(row.get('externalApiUsed')):
            reasons.append('passed normal case without external API evidence')
        if not is_guard and int(row.get('externalApiCompleted') or 0) <= 0 and not bool(row.get('fromCache')):
            reasons.append('passed normal case has no completed external API call and is not a cache replay')
        if not is_guard and 'ответ:' not in low:
            reasons.append('passed but result has no Ответ: line')
        if not is_guard and not re.search(r'(?m)^\s*1\)\s*\S+', result_text):
            reasons.append('passed but result has no numbered step 1)')
        for marker in _live_audit_forbidden_markers():
            if marker.lower() in low:
                reasons.append(f'passed despite forbidden marker: {marker}')
    if int(row.get('externalApiErrors') or 0) > 0:
        reasons.append('external API error recorded')
    if row.get('deepseekPrimaryFallback'):
        reasons.append(f"deepseekPrimaryFallback={row.get('deepseekPrimaryFallback')}")
    if str(row.get('source') or '').startswith(('fallback', 'legacy-ai')):
        reasons.append(f"source looks like fallback: {row.get('source')}")
    return reasons


def _compact_live_audit_result(row: dict[str, Any]) -> dict[str, Any]:
    result_text = str(row.get('resultText') or row.get('resultPreview') or '')
    compact = {
        'caseIndex': row.get('caseIndex'),
        'id': row.get('id'),
        'grade': row.get('grade'),
        'category': row.get('category'),
        'name': row.get('name'),
        'ok': bool(row.get('ok')),
        'issues': row.get('issues') or [],
        'source': row.get('source'),
        'inputPreview': str(row.get('inputText') or '')[:220],
        'expectedFinalAnswer': row.get('expectedFinalAnswer'),
        'expectedUnit': row.get('expectedUnit'),
        'actualAnswerLine': row.get('actualAnswerLine') or _live_audit_extract_answer_line(result_text),
        'externalApiAttempts': int(row.get('externalApiAttempts') or 0),
        'externalApiCompleted': int(row.get('externalApiCompleted') or 0),
        'externalApiBlocked': int(row.get('externalApiBlocked') or 0),
        'externalApiErrors': int(row.get('externalApiErrors') or 0),
        'externalApiUsed': bool(row.get('externalApiUsed')),
        'fromCache': bool(row.get('fromCache')),
        'cacheKey': row.get('cacheKey'),
        'resultPreview': result_text[:520],
    }
    compact['suspiciousReasons'] = _live_audit_suspicion_reasons({**row, 'resultText': result_text})
    compact['proofHash'] = _short_hash({
        'input': compact['inputPreview'],
        'expected': compact['expectedFinalAnswer'],
        'actual': compact['actualAnswerLine'],
        'resultPreview': compact['resultPreview'],
        'ok': compact['ok'],
    }, 16)
    return compact


def _live_audit_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    result_text = _live_audit_text(row.get('resultText') or row.get('resultPreview') or '', 8000)
    evidence = {
        'caseIndex': row.get('caseIndex'),
        'id': row.get('id'),
        'grade': row.get('grade'),
        'category': row.get('category'),
        'name': row.get('name'),
        'ok': bool(row.get('ok')),
        'issues': row.get('issues') or [],
        'suspiciousReasons': [],
        'inputText': _live_audit_text(row.get('inputText') or '', 3000),
        'expected': row.get('expected'),
        'expectedNumericAnswer': row.get('expectedNumericAnswer'),
        'expectedUnit': row.get('expectedUnit'),
        'expectedFinalAnswer': row.get('expectedFinalAnswer'),
        'expectedAnswerText': _live_audit_expected_answer_text(row),
        'actualAnswerLine': row.get('actualAnswerLine') or _live_audit_extract_answer_line(result_text),
        'resultText': result_text,
        'source': row.get('source'),
        'expectedSource': row.get('expectedSource'),
        'expectedSourceFamily': row.get('expectedSourceFamily'),
        'externalApiAttempts': int(row.get('externalApiAttempts') or 0),
        'externalApiCompleted': int(row.get('externalApiCompleted') or 0),
        'externalApiBlocked': int(row.get('externalApiBlocked') or 0),
        'externalApiErrors': int(row.get('externalApiErrors') or 0),
        'externalApiUsed': bool(row.get('externalApiUsed')),
        'fromCache': bool(row.get('fromCache')),
        'solverMode': row.get('solverMode'),
        'deepseekPrimaryFallback': row.get('deepseekPrimaryFallback'),
        'verifier': row.get('verifier'),
        'structuredSolution': row.get('structuredSolution'),
        'payloadError': row.get('payloadError'),
        'cacheKey': row.get('cacheKey'),
    }
    evidence['suspiciousReasons'] = _live_audit_suspicion_reasons({**row, 'resultText': result_text})
    proof_material = {
        'inputText': evidence['inputText'],
        'expected': evidence['expected'],
        'expectedFinalAnswer': evidence['expectedFinalAnswer'],
        'actualAnswerLine': evidence['actualAnswerLine'],
        'resultText': evidence['resultText'],
        'source': evidence['source'],
        'externalApiUsed': evidence['externalApiUsed'],
        'ok': evidence['ok'],
        'issues': evidence['issues'],
    }
    evidence['proofHash'] = _short_hash(proof_material, 24)
    return evidence


def _live_audit_evidence_list(run: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = [item for item in (run.get('evidenceResults') or []) if isinstance(item, dict)]
    if evidence:
        return evidence
    return [_live_audit_evidence_row(item) for item in (run.get('results') or []) if isinstance(item, dict)]


def _live_audit_acceptance_blockers(run: dict[str, Any]) -> list[str]:
    evidence = _live_audit_evidence_list(run)
    planned = int(run.get('planned') or 0)
    completed = int(run.get('completed') or 0)
    failed = int(run.get('failed') or 0)
    normal_cases = [item for item in evidence if not _live_audit_row_is_guard(item)]
    suspicious_passed = [item for item in evidence if item.get('ok') and item.get('suspiciousReasons')]
    external_total = int(run.get('externalApiCalls') or 0) + int(run.get('cachedExternalApiCalls') or 0)
    blockers: list[str] = []
    if run.get('status') != 'done':
        blockers.append('run status is not done')
    if planned <= 0:
        blockers.append('planned is zero')
    if str(run.get('section') or '') == 'g1_arithmetic_actions' and planned != 100:
        blockers.append('planned must be 100 for V296.03 g1_arithmetic_actions acceptance')
    if completed != planned:
        blockers.append('completed != planned')
    if failed != 0:
        blockers.append('failed != 0')
    if len(evidence) != planned:
        blockers.append('evidenceResultsCount != planned')
    if normal_cases and external_total < len(normal_cases):
        blockers.append('externalApiCallsTotalIncludingCache < normal case count')
    if any(not item.get('externalApiUsed') for item in normal_cases):
        blockers.append('at least one normal case has externalApiUsed=false')
    if suspicious_passed:
        blockers.append('suspicious passed cases are present')
    if int(run.get('externalApiErrors') or 0) != 0:
        blockers.append('externalApiErrors != 0')
    return blockers



def _live_audit_build_case_limit_error(case: dict[str, Any], cache_key: str, message: str) -> dict[str, Any]:
    return {
        'id': case.get('id'),
        'grade': case.get('grade'),
        'category': case.get('category'),
        'name': case.get('name'),
        'ok': False,
        'issues': [message],
        'source': 'live-audit-runner-budget-guard',
        'expectedSource': case.get('expectedSource'),
        'expectedSourceFamily': case.get('expectedSourceFamily'),
        'expectedNumericAnswer': case.get('expectedNumericAnswer'),
        'expectedUnit': case.get('expectedUnit'),
        'expectedFinalAnswer': case.get('expectedFinalAnswer'),
        'expected': case.get('expected'),
        'inputText': case.get('text'),
        'actualAnswerLine': '',
        'resultText': '',
        'structuredSolution': None,
        'payloadError': message,
        'externalApiAttempts': 0,
        'externalApiCompleted': 0,
        'externalApiBlocked': 0,
        'externalApiErrors': 0,
        'externalApiUsed': False,
        'solverMode': resolve_solver_mode(),
        'deepseekPrimaryFallback': None,
        'verifier': None,
        'cacheKey': cache_key,
        'fromCache': False,
        'resultPreview': '',
    }


def _live_audit_build_case_timeout_error(case: dict[str, Any], cache_key: str, message: str, *, allow_external: bool) -> tuple[dict[str, Any], dict[str, int]]:
    row = _live_audit_build_case_limit_error(case, cache_key, message)
    row['source'] = 'live-audit-runner-timeout'
    row['externalApiAttempts'] = 1 if allow_external else 0
    row['externalApiCompleted'] = 0
    row['externalApiBlocked'] = 0
    row['externalApiErrors'] = 1
    row['externalApiUsed'] = bool(allow_external)
    row['resultPreview'] = ''
    return row, {
        'externalApiAttempts': row['externalApiAttempts'],
        'externalApiCompleted': 0,
        'externalApiBlocked': 0,
        'externalApiErrors': 1,
        'cachedExternalApiAttempts': 0,
    }


async def _evaluate_live_audit_case(case: dict[str, Any], *, allow_external: bool, cache_key: str) -> tuple[dict[str, Any], dict[str, int]]:
    try:
        payload, external = await _generate_with_external_call_counter(case['text'], allow_external=allow_external)
    except Exception as exc:
        payload = {
            'result': '',
            'source': 'live-audit-runner-exception',
            'error': str(exc),
        }
        external = {
            'externalApiAttempts': 0,
            'externalApiCompleted': 0,
            'externalApiBlocked': 0,
            'externalApiErrors': 1,
        }
    case_for_check = dict(case)
    expected_source = str(case_for_check.get('expectedSource') or '')
    is_guard_case = expected_source.startswith('guard') or str(case_for_check.get('category') or '').endswith('guard') or 'guard' in str(case_for_check.get('category') or '')
    if not expected_source.startswith('guard'):
        case_for_check.pop('expectedSource', None)
        case_for_check.pop('expectedSourceFamily', None)
    checked = _check_payload(case_for_check, payload)
    result_text = str(payload.get('result') or '')
    source = str(payload.get('source') or '')
    external_by_source = _source_looks_external(source, payload)
    row_external_attempts = int(external.get('externalApiAttempts') or 0)
    if allow_external and resolve_solver_mode() == 'deepseek_primary' and not is_guard_case and not (row_external_attempts or external_by_source):
        checked['issues'].append('DeepSeek-primary did not call external API for a normal audit case')
        checked['ok'] = False
    if allow_external and resolve_solver_mode() == 'deepseek_primary' and not is_guard_case and payload.get('deepseekPrimaryFallback'):
        checked['issues'].append(f"DeepSeek-primary fell back locally: {payload.get('deepseekPrimaryFallback')}")
        checked['ok'] = False
    if not allow_external and (row_external_attempts or external_by_source):
        checked['issues'].append('external API/fallback used while allowExternal=false')
        checked['ok'] = False
    if not allow_external and int(external.get('externalApiBlocked') or 0):
        checked['issues'].append('external API call was blocked')
        checked['ok'] = False
    strict_format_issues = _live_audit_strict_format_issues(case, result_text, is_guard_case=is_guard_case)
    if strict_format_issues:
        checked['issues'].extend(strict_format_issues)
        checked['ok'] = False
    structured_solution = payload.get('structured_solution') if isinstance(payload.get('structured_solution'), dict) else None
    row = {
        'id': case.get('id'),
        'grade': case.get('grade'),
        'category': case.get('category'),
        'name': case.get('name'),
        'ok': checked['ok'],
        'issues': checked['issues'],
        'source': source,
        'expectedSource': case.get('expectedSource'),
        'expectedSourceFamily': case.get('expectedSourceFamily'),
        'expectedNumericAnswer': case.get('expectedNumericAnswer'),
        'expectedUnit': case.get('expectedUnit'),
        'expectedFinalAnswer': case.get('expectedFinalAnswer'),
        'expected': case.get('expected'),
        'inputText': case.get('text'),
        'actualAnswerLine': _live_audit_extract_answer_line(result_text),
        'resultText': _live_audit_text(result_text, 8000),
        'structuredSolution': structured_solution,
        'payloadError': payload.get('error'),
        'payloadValidated': payload.get('validated'),
        'externalApiAttempts': row_external_attempts,
        'externalApiCompleted': int(external.get('externalApiCompleted') or 0),
        'externalApiBlocked': int(external.get('externalApiBlocked') or 0),
        'externalApiErrors': int(external.get('externalApiErrors') or 0),
        'externalApiUsed': bool(row_external_attempts or external_by_source),
        'solverMode': payload.get('solverMode'),
        'deepseekPrimaryFallback': payload.get('deepseekPrimaryFallback'),
        'verifier': payload.get('verifier'),
        'cacheKey': cache_key,
        'fromCache': False,
        'resultPreview': result_text[:520],
    }
    return row, {
        'externalApiAttempts': row['externalApiAttempts'],
        'externalApiCompleted': row['externalApiCompleted'],
        'externalApiBlocked': row['externalApiBlocked'],
        'externalApiErrors': row['externalApiErrors'],
    }


def _live_audit_public_run_summary(run: dict[str, Any], *, include_failures_preview: bool = True) -> dict[str, Any]:
    failures = run.get('failures') or []
    now = _now_ts()
    heartbeat = float(run.get('heartbeatAt') or run.get('updatedAt') or run.get('startedAt') or 0.0)
    stale_age = max(0.0, now - heartbeat) if heartbeat > 0 else None
    run_id = str(run.get('runId') or '')
    audit_key = str(run.get('auditKey') or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY)
    fresh_links = _live_audit_fresh_paths(run_id, audit_key) if run_id else {}
    out = {
        **_version_payload(),
        'diagnostic': 'live-audit-runner',
        'runnerMode': 'BACKGROUND_TIMEWEB_DEEPSEEK_AUDIT_WITH_CACHE',
        'runId': run.get('runId'),
        'status': run.get('status'),
        'section': run.get('section'),
        'offset': run.get('offset'),
        'limit': run.get('limit'),
        'planned': run.get('planned'),
        'completed': run.get('completed'),
        'remaining': max(0, int(run.get('planned') or 0) - int(run.get('completed') or 0)),
        'passed': run.get('passed'),
        'failed': run.get('failed'),
        'total': run.get('completed'),
        'allPassed': bool(run.get('completed') == run.get('planned') and int(run.get('failed') or 0) == 0),
        'allowExternal': run.get('allowExternal'),
        'force': run.get('force'),
        'maxExternalCalls': run.get('maxExternalCalls'),
        'externalApiCalls': run.get('externalApiCalls'),
        'externalApiCompleted': run.get('externalApiCompleted'),
        'externalApiBlocked': run.get('externalApiBlocked'),
        'externalApiErrors': run.get('externalApiErrors'),
        'externalApiUsed': bool(int(run.get('externalApiCalls') or 0) > 0 or int(run.get('cachedExternalApiCalls') or 0) > 0),
        'cachedResults': run.get('cachedResults'),
        'cachedExternalApiCalls': run.get('cachedExternalApiCalls'),
        'externalApiCallsTotalIncludingCache': int(run.get('externalApiCalls') or 0) + int(run.get('cachedExternalApiCalls') or 0),
        'failuresCount': len(failures),
        'resultsCount': len(run.get('results') or []),
        'evidenceResultsCount': len(_live_audit_evidence_list(run)),
        'suspiciousPassedCount': len([item for item in _live_audit_evidence_list(run) if isinstance(item, dict) and item.get('ok') and item.get('suspiciousReasons')]),
        'suspiciousCount': len([item for item in _live_audit_evidence_list(run) if isinstance(item, dict) and item.get('suspiciousReasons')]),
        'acceptanceReady': len(_live_audit_acceptance_blockers(run)) == 0,
        'acceptanceIssues': _live_audit_acceptance_blockers(run),
        'acceptanceRequires': ['status == done', 'completed == planned', 'failed == 0', 'externalApiUsed == true', 'caseProofsTotal == planned', 'suspiciousPassedCount == 0'],
        'startedAt': run.get('startedAt'),
        'updatedAt': run.get('updatedAt'),
        'finishedAt': run.get('finishedAt'),
        'planKey': run.get('planKey'),
        'stateFile': str(_live_audit_state_path()),
        'serverNow': now,
        'heartbeatAt': run.get('heartbeatAt'),
        'staleAgeSeconds': stale_age,
        'activeCaseIndex': run.get('activeCaseIndex'),
        'activeCaseId': run.get('activeCaseId'),
        'recoveries': run.get('recoveries', 0),
        'lastRecoveryAt': run.get('lastRecoveryAt'),
        'error': run.get('error'),
        'runnerCaseTimeoutSeconds': LIVE_AUDIT_RUNNER_CASE_TIMEOUT_SECONDS,
        'runnerStaleSeconds': LIVE_AUDIT_RUNNER_STALE_SECONDS,
        'nextPlannedMapStep': 'after V296.03 pass: V297 — 1 класс, раздел 3 — Текстовые задачи',
        **fresh_links,
    }
    if include_failures_preview:
        out['failuresPreview'] = [_compact_live_audit_result(item) for item in failures[:10]]
    return out


async def _run_live_audit_background(run_id: str) -> None:
    def _mark_running(state):
        run = state['runs'].get(run_id)
        if not isinstance(run, dict):
            return None
        if run.get('status') == 'done':
            return run
        run['status'] = 'running'
        run.setdefault('startedAt', _now_ts())
        run['heartbeatAt'] = _now_ts()
        run['updatedAt'] = _now_ts()
        return run

    run = _mutate_live_audit_state(_mark_running)
    if not isinstance(run, dict) or run.get('status') == 'done':
        return
    try:
        case_items = list(run.get('cases') or [])
        allow_external = bool(run.get('allowExternal'))
        force = bool(run.get('force'))
        max_external_calls = int(run.get('maxExternalCalls') or LIVE_AUDIT_RUNNER_DEFAULT_MAX_EXTERNAL_CALLS)
        case_timeout = max(10.0, float(LIVE_AUDIT_RUNNER_CASE_TIMEOUT_SECONDS))
        for idx, item in enumerate(case_items):
            case = dict(item.get('case') or {})
            cache_key = str(item.get('cacheKey') or _live_audit_case_cache_key(case, allow_external))
            state = _load_live_audit_state()
            current = state['runs'].get(run_id, {})
            if current.get('status') in {'cancelled', 'done', 'error'}:
                return
            existing_keys = {
                str(result.get('cacheKey') or '')
                for result in (current.get('results') or [])
                if isinstance(result, dict)
            }
            if cache_key in existing_keys:
                continue

            def _heartbeat(state):
                live_run = state['runs'].get(run_id)
                if not isinstance(live_run, dict):
                    return
                live_run['status'] = 'running'
                live_run['activeCaseIndex'] = idx
                live_run['activeCaseId'] = case.get('id') or case.get('name')
                live_run['heartbeatAt'] = _now_ts()
                live_run['updatedAt'] = _now_ts()
            _mutate_live_audit_state(_heartbeat)

            cached_entry = None if force else state.get('caseCache', {}).get(cache_key)
            if isinstance(cached_entry, dict) and isinstance(cached_entry.get('row'), dict):
                row = dict(cached_entry['row'])
                row['fromCache'] = True
                row['cacheKey'] = cache_key
                external_counts = {
                    'externalApiAttempts': 0,
                    'externalApiCompleted': 0,
                    'externalApiBlocked': 0,
                    'externalApiErrors': 0,
                    'cachedExternalApiAttempts': int(row.get('externalApiAttempts') or 0),
                }
            else:
                state = _load_live_audit_state()
                current = state['runs'].get(run_id, {})
                if allow_external and int(current.get('externalApiCalls') or 0) >= max_external_calls:
                    row = _live_audit_build_case_limit_error(case, cache_key, 'live-audit external API budget reached before this case')
                    external_counts = {'externalApiAttempts': 0, 'externalApiCompleted': 0, 'externalApiBlocked': 0, 'externalApiErrors': 0, 'cachedExternalApiAttempts': 0}
                else:
                    try:
                        row, external_counts = await asyncio.wait_for(
                            _evaluate_live_audit_case(case, allow_external=allow_external, cache_key=cache_key),
                            timeout=case_timeout,
                        )
                    except asyncio.TimeoutError:
                        row, external_counts = _live_audit_build_case_timeout_error(
                            case,
                            cache_key,
                            f'live-audit case timed out after {case_timeout:g}s',
                            allow_external=allow_external,
                        )
                    def _save_cache(state):
                        state.setdefault('caseCache', {})[cache_key] = {
                            'release': APP_RELEASE,
                            'solverVersion': SOLVER_VERSION,
                            'runnerPromptVersion': LIVE_AUDIT_RUNNER_PROMPT_VERSION,
                            'section': run.get('section'),
                            'caseId': case.get('id') or case.get('name'),
                            'createdAt': _now_ts(),
                            'row': row,
                        }
                    _mutate_live_audit_state(_save_cache)
            row['caseIndex'] = idx
            row.setdefault('inputText', case.get('text'))
            if not row.get('resultText'):
                row['resultText'] = _live_audit_text(row.get('resultPreview') or '', 8000)
            if not row.get('actualAnswerLine'):
                row['actualAnswerLine'] = _live_audit_extract_answer_line(str(row.get('resultText') or row.get('resultPreview') or ''))
            compact = _compact_live_audit_result(row)
            evidence_row = _live_audit_evidence_row(row)
            def _append_result(state):
                live_run = state['runs'].get(run_id)
                if not isinstance(live_run, dict):
                    return
                known = {str(result.get('cacheKey') or '') for result in (live_run.get('results') or []) if isinstance(result, dict)}
                if cache_key in known:
                    return
                live_run.setdefault('results', []).append(compact)
                live_run.setdefault('evidenceResults', []).append(evidence_row)
                if evidence_row.get('suspiciousReasons'):
                    live_run.setdefault('suspiciousResults', []).append(evidence_row)
                live_run['completed'] = int(live_run.get('completed') or 0) + 1
                if bool(row.get('ok')):
                    live_run['passed'] = int(live_run.get('passed') or 0) + 1
                else:
                    live_run['failed'] = int(live_run.get('failed') or 0) + 1
                    live_run.setdefault('failures', []).append(row)
                live_run['externalApiCalls'] = int(live_run.get('externalApiCalls') or 0) + int(external_counts.get('externalApiAttempts') or 0)
                live_run['externalApiCompleted'] = int(live_run.get('externalApiCompleted') or 0) + int(external_counts.get('externalApiCompleted') or 0)
                live_run['externalApiBlocked'] = int(live_run.get('externalApiBlocked') or 0) + int(external_counts.get('externalApiBlocked') or 0)
                live_run['externalApiErrors'] = int(live_run.get('externalApiErrors') or 0) + int(external_counts.get('externalApiErrors') or 0)
                if bool(row.get('fromCache')):
                    live_run['cachedResults'] = int(live_run.get('cachedResults') or 0) + 1
                    live_run['cachedExternalApiCalls'] = int(live_run.get('cachedExternalApiCalls') or 0) + int(external_counts.get('cachedExternalApiAttempts') or 0)
                live_run.pop('activeCaseIndex', None)
                live_run.pop('activeCaseId', None)
                live_run['heartbeatAt'] = _now_ts()
                live_run['updatedAt'] = _now_ts()
            _mutate_live_audit_state(_append_result)
        def _mark_done(state):
            live_run = state['runs'].get(run_id)
            if not isinstance(live_run, dict):
                return
            live_run['status'] = 'done'
            live_run.pop('activeCaseIndex', None)
            live_run.pop('activeCaseId', None)
            live_run['finishedAt'] = _now_ts()
            live_run['heartbeatAt'] = live_run['finishedAt']
            live_run['updatedAt'] = live_run['finishedAt']
        _mutate_live_audit_state(_mark_done)
    except asyncio.CancelledError:
        def _mark_cancelled_for_recovery(state):
            live_run = state['runs'].get(run_id)
            if not isinstance(live_run, dict):
                return
            if live_run.get('status') not in {'done', 'error', 'cancelled'}:
                live_run['status'] = 'running'
                live_run['lastCancellationForRecoveryAt'] = _now_ts()
                live_run['updatedAt'] = _now_ts()
        _mutate_live_audit_state(_mark_cancelled_for_recovery)
        raise
    except Exception as exc:
        def _mark_error(state):
            live_run = state['runs'].get(run_id)
            if not isinstance(live_run, dict):
                return
            live_run['status'] = 'error'
            live_run['error'] = str(exc)[:500]
            live_run['updatedAt'] = _now_ts()
        _mutate_live_audit_state(_mark_error)



def _live_audit_run_is_stale(run: dict[str, Any] | None) -> bool:
    if not isinstance(run, dict) or run.get('status') not in {'queued', 'running'}:
        return False
    last = float(run.get('heartbeatAt') or run.get('updatedAt') or run.get('startedAt') or 0.0)
    if last <= 0:
        return True
    return (_now_ts() - last) > float(LIVE_AUDIT_RUNNER_STALE_SECONDS)


def _ensure_live_audit_task(run_id: str) -> None:
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(run_id)
    stale = _live_audit_run_is_stale(run)
    task = _LIVE_AUDIT_TASKS.get(run_id)
    if task is not None and not task.done() and not stale:
        return
    if task is not None and not task.done() and stale:
        task.cancel()
        def _mark_recovery(state):
            live_run = state.get('runs', {}).get(run_id)
            if not isinstance(live_run, dict):
                return
            live_run['status'] = 'running'
            live_run['recoveries'] = int(live_run.get('recoveries') or 0) + 1
            live_run['lastRecoveryAt'] = _now_ts()
            live_run['updatedAt'] = _now_ts()
        _mutate_live_audit_state(_mark_recovery)
    _LIVE_AUDIT_TASKS[run_id] = asyncio.create_task(_run_live_audit_background(run_id))


def _json_error(status_code: int, content: dict) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=attach_release(content))


def _luhn_check(digits: str) -> bool:
    value = re.sub(r'\D+', '', str(digits or ''))
    if len(value) < 13 or len(value) > 19:
        return False
    if re.fullmatch(r'(\d)\1+', value):
        return False
    total = 0
    double_digit = False
    for char in reversed(value):
        n = int(char)
        if double_digit:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        double_digit = not double_digit
    return total % 10 == 0


def _contains_bank_card_details(text: str) -> bool:
    source = str(text or '')
    candidates = re.findall(r'(?:\d[\s-]?){13,19}', source)
    return any(_luhn_check(candidate) for candidate in candidates)


def get_access_service() -> AccessService:
    global _ACCESS_SERVICE, _ACCESS_SERVICE_STATE_PATH
    current_path = str(resolve_state_file_path())
    if _ACCESS_SERVICE is None or _ACCESS_SERVICE_STATE_PATH != current_path:
        _ACCESS_SERVICE = AccessService(JsonAccessStateStore(current_path))
        _ACCESS_SERVICE_STATE_PATH = current_path
    return _ACCESS_SERVICE

app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://wolandvp-beep.github.io', 'http://localhost', 'http://127.0.0.1'],
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'PATCH', 'OPTIONS'],
    allow_headers=['*'],
)


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get('Authorization', '').strip()
    if not auth_header.lower().startswith('bearer '):
        return None
    token = auth_header[7:].strip()
    return token or None


def _extract_install_id(request: Request, payload: dict | None = None) -> str | None:
    payload = payload or {}
    for key in ('X-Install-Id', 'X-Client-Id'):
        value = request.headers.get(key, '').strip()
        if value:
            return value
    for key in ('installId', 'clientId'):
        value = str(payload.get(key) or '').strip()
        if value:
            return value
    return None


def _error_payload(exc: AccessServiceError, *, access: dict | None = None) -> JSONResponse:
    content = {'error': str(exc), 'code': getattr(exc, 'code', 'access_error')}
    if access is not None:
        content['access'] = access
    return _json_error(getattr(exc, 'status_code', 400), content)


def _safe_access_status(*, token: str | None, install_id: str | None) -> dict | None:
    try:
        return get_access_service().get_access_status(token=token, install_id=install_id)
    except Exception:
        return None


async def _solve_text(*, text: str, token: str | None, install_id: str | None) -> JSONResponse | dict:
    if _contains_bank_card_details(text):
        access = _safe_access_status(token=token, install_id=install_id)
        content = attach_release({'error': CARD_DATA_BLOCK_MESSAGE, 'code': 'card_data_not_allowed'})
        if access is not None:
            content['access'] = access
        return _json_error(400, content)

    result: dict | None = None
    prevalidated = prevalidate_explanation_request(text)
    if prevalidated is not None:
        access = _safe_access_status(token=token, install_id=install_id)
        if 'error' in prevalidated:
            content = dict(prevalidated)
            if access is not None:
                content['access'] = access
            return _json_error(400, content)
        if access is not None:
            return attach_release({**prevalidated, 'access': access})
        return attach_release(prevalidated)
    try:
        access = get_access_service().record_final_submission(token=token, install_id=install_id)
    except LimitExceededError as exc:
        status = get_access_service().get_access_status(token=token, install_id=install_id)
        return _error_payload(exc, access=status)
    except AccessServiceError as exc:
        return _error_payload(exc)

    try:
        result = await generate_explanation_response(text)
        if 'error' in result:
            return _json_error(400, {**result, 'access': access})
        return attach_release({**result, 'access': access})
    except httpx.ReadTimeout:
        return _json_error(504, {'error': 'DeepSeek timeout: сервер не дождался ответа от API'})
    except httpx.ConnectTimeout:
        return _json_error(504, {'error': 'DeepSeek connect timeout: сервер не смог подключиться к API'})
    except httpx.ConnectError as exc:
        return _json_error(502, {'error': f'DeepSeek connect error: {str(exc)}'})
    except Exception as exc:  # pragma: no cover - runtime safety
        return _json_error(500, {'error': f'Server exception: {str(exc)}'})


@app.options('/')
@app.options('/api')
@app.options('/api/{path:path}')
async def options(path: str | None = None):
    return {'message': 'OK'}


def _root_payload(request: Request) -> dict:
    product = build_public_product_config()
    return {
        **_version_payload(request),
        'message': 'Математичка backend работает.',
        'provider': product['provider'],
        'platforms': product['distributionPlatforms'],
        'checkoutMode': product['checkoutMode'],
        'hint': 'POST / with action=explain or POST /api/explanations with {text}',
    }


def _audit_dashboard_html(title: str, payload: dict, extra_links: list[tuple[str, str]] | None = None) -> str:
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    links: list[str] = []
    for label, url in (extra_links or []):
        if url:
            links.append(f'<p><a href="{escape(str(url), quote=True)}">{escape(label)}</a></p>')
    start = payload.get('nextAuditStartUrl') or payload.get('startUrl') or payload.get('startPath') or ''
    control = payload.get('nextAuditControlUrl') or payload.get('controlUrl') or ''
    status = payload.get('statusUrl') or payload.get('statusPath') or ''
    summary = payload.get('summaryUrl') or payload.get('summaryPath') or ''
    failures = payload.get('failuresUrl') or payload.get('failuresPath') or ''
    status_fresh = payload.get('statusFreshUrl') or payload.get('statusFreshPath') or ''
    summary_fresh = payload.get('summaryFreshUrl') or payload.get('summaryFreshPath') or ''
    failures_fresh = payload.get('failuresFreshUrl') or payload.get('failuresFreshPath') or ''
    results = payload.get('resultsUrl') or payload.get('resultsPath') or ''
    results_full = payload.get('resultsFullUrl') or payload.get('resultsFullPath') or ''
    evidence = payload.get('evidenceUrl') or payload.get('evidencePath') or ''
    suspicious = payload.get('suspiciousUrl') or payload.get('suspiciousPath') or ''
    acceptance = payload.get('acceptanceUrl') or payload.get('acceptancePath') or ''
    report = payload.get('reportUrl') or payload.get('reportPath') or ''
    results_fresh = payload.get('resultsFreshUrl') or payload.get('resultsFreshPath') or ''
    results_full_fresh = payload.get('resultsFullFreshUrl') or payload.get('resultsFullFreshPath') or ''
    evidence_fresh = payload.get('evidenceFreshUrl') or payload.get('evidenceFreshPath') or ''
    suspicious_fresh = payload.get('suspiciousFreshUrl') or payload.get('suspiciousFreshPath') or ''
    acceptance_fresh = payload.get('acceptanceFreshUrl') or payload.get('acceptanceFreshPath') or ''
    report_fresh = payload.get('reportFreshUrl') or payload.get('reportFreshPath') or ''
    for label, url in [
        ('Open audit control dashboard', control),
        ('START next live DeepSeek audit', start),
        ('Check audit status FRESH', status_fresh),
        ('Open audit summary FRESH', summary_fresh),
        ('Open audit failures FRESH', failures_fresh),
        ('Open audit results proof FRESH', results_fresh),
        ('Open audit full results proof FRESH', results_full_fresh),
        ('Open audit evidence FRESH', evidence_fresh),
        ('Open suspicious-but-passed FRESH', suspicious_fresh),
        ('Open acceptance proof FRESH', acceptance_fresh),
        ('Open audit report FRESH', report_fresh),
        ('Check audit status', status),
        ('Open audit summary', summary),
        ('Open audit failures', failures),
        ('Open audit results proof', results),
        ('Open audit full results proof', results_full),
        ('Open audit evidence', evidence),
        ('Open suspicious-but-passed', suspicious),
        ('Open acceptance proof', acceptance),
        ('Open audit report', report),
        ('Open JSON /api/version', '/api/version'),
    ]:
        if url:
            links.append(f'<p><a href="{escape(str(url), quote=True)}">{escape(label)}</a></p>')
    return (
        '<!doctype html>\n'
        '<html lang="ru"><head><meta charset="utf-8"><meta name="robots" content="noindex">\n'
        '<meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">\n'
        f'<title>{escape(title)}</title>\n'
        '<style>body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:980px;margin:32px auto;padding:0 16px;line-height:1.45}pre{white-space:pre-wrap;background:#f6f6f6;padding:16px;border-radius:12px;overflow:auto}a{font-weight:700}</style></head>\n'
        f'<body><h1>{escape(title)}</h1>\n'
        '<p>Это HTML-dashboard для автоматизации: веб-инструмент может нажимать ссылки, а JSON остаётся ниже для проверки.</p>\n'
        + ''.join(links) +
        f'<h2>JSON</h2><pre>{escape(data)}</pre>\n</body></html>'
    )


@app.get('/')
def read_root(request: Request):
    return _html_ok(_audit_dashboard_html('Математичка backend live audit dashboard', _root_payload(request)))


@app.get('/api')
def read_api(request: Request):
    return _json_ok(_root_payload(request))


@app.get('/version')
@app.get('/api/version')
def read_version(request: Request):
    return _json_ok(_version_payload(request))


_DIAGNOSTIC_CASES = [
    ('multiline_guard', '2+2\n32-8', 'guard-multi-task', 'Ответ: Разделите задания'),
    ('joint_work_tractor', 'Один трактор может вспахать поле площадью 240 аров за 3 часа, а другой трактор — за 6 часов. За сколько часов вспашут поле оба трактора, работая вместе?', 'local:live-joint-work', '120 аров в час'),
    ('joint_work_tractor_acres', 'Один трактор может вспахать поле площадью 240 акров за 3 часа, а другой трактор — за 6 часов. За сколько часов вспашут поле оба трактора, работая вместе?', 'local:live-joint-work', '120 акров в час'),
    ('joint_work_combine', 'Один комбайн убрал с поля 168 т пшеницы за 6 дней, а другой — столько же за 12 дней. За сколько дней уберут поле оба комбайна, работая вместе?', 'local:live-joint-work', 'за 4 дня'),
    ('system_comma', 'x + y = 10, y - x = 2', 'local:live-system-solver', 'x = 4, y = 6'),
    ('system_newline', 'x + y = 10\ny - x = 2', 'local:live-system-solver', 'y-x=2'),
    ('system_cyrillic_newline', 'х + у = 10\nу - х = 2', 'local:live-system-solver', 'x = 4, y = 6'),
    ('system_collapsed', 'x + y = 10 y - x = 2', 'local:live-system-solver', 'x = 4, y = 6'),
    ('motion_remaining', 'Велосипедист ехал 2 ч со скоростью 10 км/ч. После этого ему осталось проехать в 2 раза больше того, что он проехал. Сколько всего километров он должен проехать?', 'local:live-v281-motion-remaining', '60 километров'),
    ('equal_groups_remaining', 'На 3 ветках по 9 шишек. Белка утащила 3 шишки. Сколько шишек осталось?', 'local:live-v279-equal-groups-remaining', '24 шишки'),
    ('division_container', 'В коробки кладут по 6 яблок. Сколько коробок понадобится для 25 яблок?', 'local:live-division-containers', '5 коробок'),
    ('money_mixed', 'Сколько копеек в 3 рублях 50 копейках?', 'local:live-money-conversion', '350 копеек'),
]


@app.get('/api/diagnostics/live-smoke')
async def live_smoke_diagnostics():
    results = []
    bad_markers = ('Применяем правило:', 'Zad3', 'deterministic regression', 'lookup', 'answer map', 'generic fallback')
    for name, text, expected_source, expected_fragment in _DIAGNOSTIC_CASES:
        payload = await generate_explanation_response(text, solver_mode='local_primary')
        result_text = str(payload.get('result') or '')
        source = str(payload.get('source') or '')
        issues = []
        if source != expected_source:
            issues.append(f'expected source {expected_source!r}, got {source!r}')
        if expected_fragment not in result_text:
            issues.append(f'missing result fragment {expected_fragment!r}')
        for marker in bad_markers:
            if marker.lower() in result_text.lower():
                issues.append(f'forbidden marker {marker!r}')
        results.append({
            'name': name,
            'ok': not issues,
            'issues': issues,
            'source': source,
            'expectedSource': expected_source,
            'resultPreview': result_text[:240],
        })
    passed = sum(1 for item in results if item['ok'])
    return {
        **_version_payload(),
        'diagnostic': 'live-smoke',
        'passed': passed,
        'total': len(results),
        'allPassed': passed == len(results),
        'results': results,
    }


@app.get('/api/diagnostics/live-production-audit')
async def live_production_audit_diagnostics(
    key: str = '',
    limit: int = 20,
    offset: int = 0,
    section: str = 'representative',
    allowExternal: int = 1,
):
    if not _live_audit_key_matches(key):
        return _json_error(403, {
            'error': 'Нужен live-audit key. Передайте ?key=... или задайте LIVE_AUDIT_KEY на сервере.',
            'diagnostic': 'live-production-audit',
            'hint': 'Default test key in this build: v296.03-live-audit. For production, set LIVE_AUDIT_KEY in Timeweb.',
        })
    try:
        limit_value = int(limit)
        offset_value = int(offset)
    except Exception:
        return _json_error(400, {'error': 'limit и offset должны быть числами', 'diagnostic': 'live-production-audit'})
    if limit_value < 1:
        return _json_error(400, {'error': 'limit должен быть >= 1', 'diagnostic': 'live-production-audit'})
    if limit_value > LIVE_PRODUCTION_AUDIT_MAX_LIMIT:
        return _json_error(400, {
            'error': f'limit слишком большой. Максимум {LIVE_PRODUCTION_AUDIT_MAX_LIMIT} за один live-запуск.',
            'diagnostic': 'live-production-audit',
            'maxLimit': LIVE_PRODUCTION_AUDIT_MAX_LIMIT,
        })
    if offset_value < 0:
        return _json_error(400, {'error': 'offset должен быть >= 0', 'diagnostic': 'live-production-audit'})

    pool = _select_live_production_cases(section)
    selected_raw = pool[offset_value:offset_value + limit_value]
    normalized = [_normalize_case(case, offset_value + idx) for idx, case in enumerate(selected_raw)]
    allow_external = str(allowExternal).lower() not in {'0', 'false', 'no', 'off'}

    results: list[dict[str, Any]] = []
    total_external_attempts = 0
    total_external_completed = 0
    total_external_blocked = 0
    total_external_errors = 0
    for case in normalized:
        try:
            payload, external = await _generate_with_external_call_counter(case['text'], allow_external=allow_external)
        except Exception as exc:
            payload = {
                'result': '',
                'source': 'live-production-audit-exception',
                'error': str(exc),
            }
            external = {
                'externalApiAttempts': 0,
                'externalApiCompleted': 0,
                'externalApiBlocked': 0,
                'externalApiErrors': 1,
            }
        total_external_attempts += int(external.get('externalApiAttempts') or 0)
        total_external_completed += int(external.get('externalApiCompleted') or 0)
        total_external_blocked += int(external.get('externalApiBlocked') or 0)
        total_external_errors += int(external.get('externalApiErrors') or 0)
        case_for_check = dict(case)
        expected_source = str(case_for_check.get('expectedSource') or '')
        is_guard_case = expected_source.startswith('guard') or str(case_for_check.get('category') or '').endswith('guard') or 'guard' in str(case_for_check.get('category') or '')
        if not expected_source.startswith('guard'):
            # In v288 live production audit the expected source is the live route;
            # DeepSeek-primary may be used for normal tasks, so historical local
            # source equality is no longer a correctness condition. Guard cases
            # still must stay local and keep their exact source.
            case_for_check.pop('expectedSource', None)
            case_for_check.pop('expectedSourceFamily', None)
        checked = _check_payload(case_for_check, payload)
        result_text = str(payload.get('result') or '')
        source = str(payload.get('source') or '')
        external_by_source = _source_looks_external(source, payload)
        row_external_attempts = int(external.get('externalApiAttempts') or 0)
        if allow_external and resolve_solver_mode() == 'deepseek_primary' and not is_guard_case and not (row_external_attempts or external_by_source):
            checked['issues'].append('DeepSeek-primary did not call external API for a normal audit case')
            checked['ok'] = False
        if allow_external and resolve_solver_mode() == 'deepseek_primary' and not is_guard_case and payload.get('deepseekPrimaryFallback'):
            checked['issues'].append(f"DeepSeek-primary fell back locally: {payload.get('deepseekPrimaryFallback')}")
            checked['ok'] = False
        if not allow_external and (row_external_attempts or external_by_source):
            checked['issues'].append('external API/fallback used while allowExternal=false')
            checked['ok'] = False
        if not allow_external and int(external.get('externalApiBlocked') or 0):
            checked['issues'].append('external API call was blocked')
            checked['ok'] = False
        results.append({
            'id': case.get('id'),
            'grade': case.get('grade'),
            'category': case.get('category'),
            'name': case.get('name'),
            'ok': checked['ok'],
            'issues': checked['issues'],
            'source': source,
            'expectedSource': case.get('expectedSource'),
            'expectedSourceFamily': case.get('expectedSourceFamily'),
            'expectedNumericAnswer': case.get('expectedNumericAnswer'),
            'expectedUnit': case.get('expectedUnit'),
            'expectedFinalAnswer': case.get('expectedFinalAnswer'),
            'expected': case.get('expected'),
            'externalApiAttempts': row_external_attempts,
            'externalApiCompleted': int(external.get('externalApiCompleted') or 0),
            'externalApiBlocked': int(external.get('externalApiBlocked') or 0),
            'externalApiErrors': int(external.get('externalApiErrors') or 0),
            'externalApiUsed': bool(row_external_attempts or external_by_source),
            'solverMode': payload.get('solverMode'),
            'deepseekPrimaryFallback': payload.get('deepseekPrimaryFallback'),
            'verifier': payload.get('verifier'),
            'resultPreview': result_text[:320],
        })

    passed = sum(1 for item in results if item['ok'])
    failed = len(results) - passed
    next_offset = offset_value + len(selected_raw)
    return {
        **_version_payload(),
        'diagnostic': 'live-production-audit',
        'auditMode': 'LIVE_PRODUCTION_ON_TIMEWEB_GET_ENDPOINT',
        'routeUnderAudit': 'generate_explanation_response via live backend process',
        'solverModeUnderAudit': resolve_solver_mode(),
        'deepseekApiKeyConfigured': deepseek_api_key_configured(),
        'section': section,
        'sectionTotal': len(pool),
        'offset': offset_value,
        'limit': limit_value,
        'returned': len(results),
        'nextOffset': next_offset if next_offset < len(pool) else None,
        'remaining': max(0, len(pool) - next_offset),
        'passed': passed,
        'failed': failed,
        'total': len(results),
        'allPassed': failed == 0,
        'allowExternal': allow_external,
        'externalApiCalls': total_external_attempts,
        'externalApiCompleted': total_external_completed,
        'externalApiBlocked': total_external_blocked,
        'externalApiErrors': total_external_errors,
        'externalApiUsed': total_external_attempts > 0,
        'failures': [item for item in results if not item['ok']],
        'results': results,
        'nextPlannedMapStep': 'after V296.03 pass: V297 — 1 класс, раздел 3 — Текстовые задачи',
    }



@app.get('/api/diagnostics/live-audit/control/{release_token}/{key_value}')
async def live_audit_control_dashboard(request: Request, release_token: str, key_value: str):
    payload = {
        **_version_payload(request),
        'diagnostic': 'live-audit-control-dashboard',
        'requestedRelease': release_token,
        'currentRelease': APP_RELEASE,
        'releaseMatches': release_token == APP_RELEASE,
    }
    return _html_ok(_audit_dashboard_html('Live audit control dashboard', payload))


@app.get('/api/diagnostics/live-audit/start-next/{release_token}/{key_value}')
async def live_audit_runner_start_next(request: Request, release_token: str, key_value: str):
    """Path-based automation endpoint for the next planned audit.

    Returns HTML with clickable status/summary/failures links so web-tool
    automation can continue without the user pasting long URLs.
    """
    result = await live_audit_runner_start(
        request=request,
        key=key_value,
        section='g1_arithmetic_actions',
        limit=100,
        offset=0,
        allowExternal=1,
        force=0,
        maxExternalCalls=150,
        release=release_token,
        cacheBust=release_token,
    )
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit started', result))


@app.get('/api/diagnostics/live-audit/status-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_status_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_status(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit status', result))


@app.get('/api/diagnostics/live-audit/summary-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_summary_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_summary(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit summary', result))


@app.get('/api/diagnostics/live-audit/failures-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_failures_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_failures(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit failures', result))



@app.get('/api/diagnostics/live-audit/results-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_results_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_results(key=key_value, runId=run_id_value, release=release_token, includeFull=0)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit results proof', result))


@app.get('/api/diagnostics/live-audit/results-full-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_results_full_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_results(key=key_value, runId=run_id_value, release=release_token, includeFull=1)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit FULL results proof', result))


@app.get('/api/diagnostics/live-audit/evidence-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_evidence_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_evidence(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit evidence proof', result))


@app.get('/api/diagnostics/live-audit/suspicious-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_suspicious_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_suspicious(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit suspicious passed results', result))


@app.get('/api/diagnostics/live-audit/acceptance-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_acceptance_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_acceptance(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit acceptance proof', result))


@app.get('/api/diagnostics/live-audit/report-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_report_path(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_report(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    return _html_ok(_audit_dashboard_html('Live audit report', result))


@app.get('/api/diagnostics/live-audit/status-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_status_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_status(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-status-fresh'
    return _html_ok(_audit_dashboard_html('Live audit status FRESH', result))


@app.get('/api/diagnostics/live-audit/summary-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_summary_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_summary(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-summary-fresh'
    return _html_ok(_audit_dashboard_html('Live audit summary FRESH', result))


@app.get('/api/diagnostics/live-audit/failures-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_failures_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_failures(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-failures-fresh'
    return _html_ok(_audit_dashboard_html('Live audit failures FRESH', result))



@app.get('/api/diagnostics/live-audit/results-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_results_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_results(key=key_value, runId=run_id_value, release=release_token, includeFull=0)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-results-fresh'
    return _html_ok(_audit_dashboard_html('Live audit results proof FRESH', result))


@app.get('/api/diagnostics/live-audit/results-full-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_results_full_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_results(key=key_value, runId=run_id_value, release=release_token, includeFull=1)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-results-full-fresh'
    return _html_ok(_audit_dashboard_html('Live audit FULL results proof FRESH', result))


@app.get('/api/diagnostics/live-audit/evidence-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_evidence_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_evidence(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-evidence-fresh'
    return _html_ok(_audit_dashboard_html('Live audit evidence proof FRESH', result))


@app.get('/api/diagnostics/live-audit/suspicious-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_suspicious_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_suspicious(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-suspicious-fresh'
    return _html_ok(_audit_dashboard_html('Live audit suspicious passed FRESH', result))


@app.get('/api/diagnostics/live-audit/acceptance-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_acceptance_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_acceptance(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-acceptance-fresh'
    return _html_ok(_audit_dashboard_html('Live audit acceptance proof FRESH', result))


@app.get('/api/diagnostics/live-audit/report-fresh/{release_token}/{key_value}/{run_id_value}/{nonce}')
async def live_audit_runner_report_fresh_path(release_token: str, key_value: str, run_id_value: str, nonce: str):
    result = await live_audit_runner_report(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['freshRequestNonce'] = nonce
    result['diagnostic'] = 'live-audit-runner-report-fresh'
    return _html_ok(_audit_dashboard_html('Live audit report FRESH', result))


@app.get('/api/diagnostics/live-audit/start')
async def live_audit_runner_start(
    request: Request,
    key: str = '',
    section: str = 'g1_numbers_values',
    limit: int = 100,
    offset: int = 0,
    allowExternal: int = 1,
    force: int = 0,
    maxExternalCalls: int = LIVE_AUDIT_RUNNER_DEFAULT_MAX_EXTERNAL_CALLS,
    release: str = '',
    cacheBust: str = '',
):
    if not _live_audit_key_matches(key):
        return _json_error(403, {
            'error': 'Нужен live-audit key. Передайте ?key=... или задайте LIVE_AUDIT_KEY на сервере.',
            'diagnostic': 'live-audit-runner-start',
            'hint': 'Default test key in this build: v296.03-live-audit. For production, set LIVE_AUDIT_KEY in Timeweb.',
        })
    requested_release = str(release or cacheBust or '').strip()
    if requested_release and requested_release != APP_RELEASE:
        return _json_error(409, {
            'error': 'Live audit link release mismatch. Open fresh /api/version and use nextAuditStartUrl from the current backend.',
            'diagnostic': 'live-audit-runner-start',
            'requestedRelease': requested_release,
            'currentRelease': APP_RELEASE,
        })
    try:
        limit_value = int(limit)
        offset_value = int(offset)
        max_external_calls_value = int(maxExternalCalls)
    except Exception:
        return _json_error(400, {'error': 'limit, offset и maxExternalCalls должны быть числами', 'diagnostic': 'live-audit-runner-start'})
    if limit_value < 1:
        return _json_error(400, {'error': 'limit должен быть >= 1', 'diagnostic': 'live-audit-runner-start'})
    if limit_value > LIVE_AUDIT_RUNNER_MAX_LIMIT:
        return _json_error(400, {
            'error': f'limit слишком большой. Максимум {LIVE_AUDIT_RUNNER_MAX_LIMIT} для одного runner-запуска.',
            'diagnostic': 'live-audit-runner-start',
            'maxLimit': LIVE_AUDIT_RUNNER_MAX_LIMIT,
        })
    if offset_value < 0:
        return _json_error(400, {'error': 'offset должен быть >= 0', 'diagnostic': 'live-audit-runner-start'})
    if max_external_calls_value < 0:
        return _json_error(400, {'error': 'maxExternalCalls должен быть >= 0', 'diagnostic': 'live-audit-runner-start'})

    allow_external = str(allowExternal).lower() not in {'0', 'false', 'no', 'off'}
    force_value = str(force).lower() in {'1', 'true', 'yes', 'on'}
    pool = _select_live_production_cases(section)
    selected_raw = pool[offset_value:offset_value + limit_value]
    normalized = [_normalize_case(case, offset_value + idx) for idx, case in enumerate(selected_raw)]
    cases_for_run = [
        {'cacheKey': _live_audit_case_cache_key(case, allow_external), 'case': case}
        for case in normalized
    ]
    plan_key = _live_audit_plan_key(section, offset_value, limit_value, allow_external, max_external_calls_value)
    force_suffix = ('-' + str(int(_now_ts()))) if force_value else ''
    run_id = f"{APP_RELEASE}-{str(section or 'section').strip().lower().replace(':','_')}-{offset_value}-{limit_value}-{plan_key[:10]}{force_suffix}"

    def _create_or_reuse(state):
        runs = state.setdefault('runs', {})
        plans = state.setdefault('plans', {})
        if not force_value:
            existing_id = plans.get(plan_key)
            existing_run = runs.get(existing_id) if existing_id else None
            if isinstance(existing_run, dict):
                reuse_ok = (
                    existing_run.get('release') == APP_RELEASE
                    and existing_run.get('backendBuild') == APP_RELEASE
                    and existing_run.get('solverVersion') == SOLVER_VERSION
                    and existing_run.get('runnerPromptVersion') == LIVE_AUDIT_RUNNER_PROMPT_VERSION
                    and str(existing_run.get('section')) == str(section)
                    and int(existing_run.get('offset') or 0) == offset_value
                    and int(existing_run.get('limit') or 0) == limit_value
                    and bool(existing_run.get('allowExternal')) == bool(allow_external)
                    and int(existing_run.get('maxExternalCalls') or 0) == max_external_calls_value
                )
                if reuse_ok:
                    return existing_id, existing_run, True
                # Do not reuse a stale run from a previous release even if a bad old
                # state file accidentally maps the same plan. Drop the mapping and create fresh.
                if existing_id in runs:
                    existing_run.setdefault('staleForRelease', APP_RELEASE)
                plans.pop(plan_key, None)
        run = {
            'runId': run_id,
            'planKey': plan_key,
            'release': APP_RELEASE,
            'backendBuild': APP_RELEASE,
            'solverVersion': SOLVER_VERSION,
            'runnerPromptVersion': LIVE_AUDIT_RUNNER_PROMPT_VERSION,
            'status': 'queued',
            'section': section,
            'sectionTotal': len(pool),
            'offset': offset_value,
            'limit': limit_value,
            'planned': len(cases_for_run),
            'completed': 0,
            'passed': 0,
            'failed': 0,
            'allowExternal': allow_external,
            'auditKey': key,
            'force': force_value,
            'maxExternalCalls': max_external_calls_value,
            'externalApiCalls': 0,
            'externalApiCompleted': 0,
            'externalApiBlocked': 0,
            'externalApiErrors': 0,
            'cachedResults': 0,
            'cachedExternalApiCalls': 0,
            'results': [],
            'evidenceResults': [],
            'suspiciousResults': [],
            'failures': [],
            'cases': cases_for_run,
            'createdAt': _now_ts(),
            'updatedAt': _now_ts(),
            'nextOffset': offset_value + len(cases_for_run) if (offset_value + len(cases_for_run)) < len(pool) else None,
            'remainingAfterRun': max(0, len(pool) - (offset_value + len(cases_for_run))),
        }
        runs[run_id] = run
        plans[plan_key] = run_id
        return run_id, run, False

    run_id_value, run, reused = _mutate_live_audit_state(_create_or_reuse)
    if run.get('status') in {'queued', 'running'}:
        _ensure_live_audit_task(run_id_value)
    summary = _live_audit_public_run_summary(run, include_failures_preview=False)
    status_path = '/api/diagnostics/live-audit/status?' + urlencode([('key', key), ('release', APP_RELEASE), ('runId', run_id_value)])
    summary_path = '/api/diagnostics/live-audit/summary?' + urlencode([('key', key), ('release', APP_RELEASE), ('runId', run_id_value)])
    failures_path = '/api/diagnostics/live-audit/failures?' + urlencode([('key', key), ('release', APP_RELEASE), ('runId', run_id_value)])
    status_path_based = f'/api/diagnostics/live-audit/status-run/{APP_RELEASE}/{key}/{run_id_value}'
    summary_path_based = f'/api/diagnostics/live-audit/summary-run/{APP_RELEASE}/{key}/{run_id_value}'
    failures_path_based = f'/api/diagnostics/live-audit/failures-run/{APP_RELEASE}/{key}/{run_id_value}'
    results_path_based = f'/api/diagnostics/live-audit/results-run/{APP_RELEASE}/{key}/{run_id_value}'
    results_full_path_based = f'/api/diagnostics/live-audit/results-full-run/{APP_RELEASE}/{key}/{run_id_value}'
    evidence_path_based = f'/api/diagnostics/live-audit/evidence-run/{APP_RELEASE}/{key}/{run_id_value}'
    suspicious_path_based = f'/api/diagnostics/live-audit/suspicious-run/{APP_RELEASE}/{key}/{run_id_value}'
    acceptance_path_based = f'/api/diagnostics/live-audit/acceptance-run/{APP_RELEASE}/{key}/{run_id_value}'
    report_path_based = f'/api/diagnostics/live-audit/report-run/{APP_RELEASE}/{key}/{run_id_value}'
    base_url = _public_base_url(request)
    return {
        **summary,
        'diagnostic': 'live-audit-runner-start',
        'reusedExistingRun': bool(reused),
        'runId': run_id_value,
        'statusPath': status_path_based,
        'summaryPath': summary_path_based,
        'failuresPath': failures_path_based,
        'resultsPath': results_path_based,
        'resultsFullPath': results_full_path_based,
        'evidencePath': evidence_path_based,
        'suspiciousPath': suspicious_path_based,
        'acceptancePath': acceptance_path_based,
        'reportPath': report_path_based,
        **_live_audit_fresh_paths(run_id_value, key),
        'statusUrl': base_url + status_path_based,
        'summaryUrl': base_url + summary_path_based,
        'failuresUrl': base_url + failures_path_based,
        'resultsUrl': base_url + results_path_based,
        'resultsFullUrl': base_url + results_full_path_based,
        'evidenceUrl': base_url + evidence_path_based,
        'suspiciousUrl': base_url + suspicious_path_based,
        'acceptanceUrl': base_url + acceptance_path_based,
        'reportUrl': base_url + report_path_based,
        'legacyStatusUrl': base_url + status_path,
        'legacySummaryUrl': base_url + summary_path,
        'legacyFailuresUrl': base_url + failures_path,
        'pathBasedUrls': True,
        'note': 'Повторные status/summary/failures/results/evidence/acceptance/report не вызывают DeepSeek. Повторный start без force=1 переиспользует этот run/cache; для принятия используйте acceptanceUrl/reportUrl/evidenceUrl/suspiciousUrl. Автоматизация должна использовать path-based URL без query-параметров.',
    }


@app.get('/api/diagnostics/live-audit/status')
async def live_audit_runner_status(key: str = '', runId: str = '', release: str = ''):
    if not _live_audit_key_matches(key):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'live-audit-runner-status'})
    if release and str(release).strip() != APP_RELEASE:
        return _json_error(409, {'error': 'release mismatch', 'diagnostic': 'live-audit-runner-status', 'requestedRelease': release, 'currentRelease': APP_RELEASE})
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(str(runId or '').strip())
    if not isinstance(run, dict):
        return _json_error(404, {'error': 'runId не найден', 'diagnostic': 'live-audit-runner-status', 'runId': runId})
    if run.get('status') in {'queued', 'running'}:
        _ensure_live_audit_task(str(run.get('runId') or runId))
        state = _load_live_audit_state()
        run = state.get('runs', {}).get(str(runId or '').strip()) or run
    return _live_audit_public_run_summary(run, include_failures_preview=True)


@app.get('/api/diagnostics/live-audit/summary')
async def live_audit_runner_summary(key: str = '', runId: str = '', release: str = ''):
    if not _live_audit_key_matches(key):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'live-audit-runner-summary'})
    if release and str(release).strip() != APP_RELEASE:
        return _json_error(409, {'error': 'release mismatch', 'diagnostic': 'live-audit-runner-summary', 'requestedRelease': release, 'currentRelease': APP_RELEASE})
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(str(runId or '').strip())
    if not isinstance(run, dict):
        return _json_error(404, {'error': 'runId не найден', 'diagnostic': 'live-audit-runner-summary', 'runId': runId})
    if run.get('status') in {'queued', 'running'}:
        _ensure_live_audit_task(str(run.get('runId') or runId))
        state = _load_live_audit_state()
        run = state.get('runs', {}).get(str(runId or '').strip()) or run
    return _live_audit_public_run_summary(run, include_failures_preview=True)


@app.get('/api/diagnostics/live-audit/failures')
async def live_audit_runner_failures(key: str = '', runId: str = '', release: str = '', limit: int = 50):
    if not _live_audit_key_matches(key):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'live-audit-runner-failures'})
    if release and str(release).strip() != APP_RELEASE:
        return _json_error(409, {'error': 'release mismatch', 'diagnostic': 'live-audit-runner-failures', 'requestedRelease': release, 'currentRelease': APP_RELEASE})
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(str(runId or '').strip())
    if not isinstance(run, dict):
        return _json_error(404, {'error': 'runId не найден', 'diagnostic': 'live-audit-runner-failures', 'runId': runId})
    if run.get('status') in {'queued', 'running'}:
        _ensure_live_audit_task(str(run.get('runId') or runId))
        state = _load_live_audit_state()
        run = state.get('runs', {}).get(str(runId or '').strip()) or run
    try:
        limit_value = max(1, min(200, int(limit)))
    except Exception:
        limit_value = 50
    failures = list(run.get('failures') or [])[:limit_value]
    return {
        **_live_audit_public_run_summary(run, include_failures_preview=False),
        'diagnostic': 'live-audit-runner-failures',
        'failuresReturned': len(failures),
        'failures': failures,
    }




def _live_audit_load_run_for_read(key: str, runId: str, release: str, diagnostic: str) -> dict[str, Any] | JSONResponse:
    if not _live_audit_key_matches(key):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': diagnostic})
    if release and str(release).strip() != APP_RELEASE:
        return _json_error(409, {'error': 'release mismatch', 'diagnostic': diagnostic, 'requestedRelease': release, 'currentRelease': APP_RELEASE})
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(str(runId or '').strip())
    if not isinstance(run, dict):
        return _json_error(404, {'error': 'runId не найден', 'diagnostic': diagnostic, 'runId': runId})
    if run.get('status') in {'queued', 'running'}:
        _ensure_live_audit_task(str(run.get('runId') or runId))
        state = _load_live_audit_state()
        run = state.get('runs', {}).get(str(runId or '').strip()) or run
    return run


def _live_audit_results_for_payload(run: dict[str, Any], *, include_full: bool, only_suspicious: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # Prefer evidenceResults because it preserves the full result text and proof fields.
    # The compact `results` list is kept for small summaries/backward compatibility.
    for raw in _live_audit_evidence_list(run):
        if not isinstance(raw, dict):
            continue
        evidence = dict(raw)
        if not evidence.get('proofHash'):
            evidence = _live_audit_evidence_row(evidence)
        if only_suspicious and not evidence.get('suspiciousReasons'):
            continue
        if not include_full:
            evidence.pop('resultText', None)
        rows.append(evidence)
    return rows


@app.get('/api/diagnostics/live-audit/results')
async def live_audit_runner_results(key: str = '', runId: str = '', release: str = '', includeFull: int = 0, limit: int = 200, offset: int = 0):
    run = _live_audit_load_run_for_read(key, runId, release, 'live-audit-runner-results')
    if isinstance(run, JSONResponse):
        return run
    include_full = str(includeFull).lower() in {'1', 'true', 'yes', 'on'}
    try:
        offset_value = max(0, int(offset))
        limit_value = max(1, min(500, int(limit)))
    except Exception:
        offset_value = 0
        limit_value = 200
    all_rows = _live_audit_results_for_payload(run, include_full=include_full)
    rows = all_rows[offset_value:offset_value + limit_value]
    return {
        **_live_audit_public_run_summary(run, include_failures_preview=False),
        'diagnostic': 'live-audit-runner-results',
        'evidenceMode': 'case-level-proof',
        'includeFullResultText': include_full,
        'caseProofsTotal': len(all_rows),
        'caseProofsReturned': len(rows),
        'caseProofsOffset': offset_value,
        'caseProofsLimit': limit_value,
        'caseProofs': rows,
    }


@app.get('/api/diagnostics/live-audit/suspicious')
async def live_audit_runner_suspicious(key: str = '', runId: str = '', release: str = ''):
    run = _live_audit_load_run_for_read(key, runId, release, 'live-audit-runner-suspicious')
    if isinstance(run, JSONResponse):
        return run
    rows = _live_audit_results_for_payload(run, include_full=False, only_suspicious=True)
    return {
        **_live_audit_public_run_summary(run, include_failures_preview=False),
        'diagnostic': 'live-audit-runner-suspicious',
        'suspiciousPassedCount': sum(1 for item in rows if item.get('ok')),
        'suspiciousReturned': len(rows),
        'suspicious': rows,
    }


@app.get('/api/diagnostics/live-audit/acceptance')
async def live_audit_runner_acceptance(key: str = '', runId: str = '', release: str = ''):
    run = _live_audit_load_run_for_read(key, runId, release, 'live-audit-runner-acceptance')
    if isinstance(run, JSONResponse):
        return run
    summary = _live_audit_public_run_summary(run, include_failures_preview=False)
    evidence_rows = _live_audit_results_for_payload(run, include_full=False)
    suspicious = [row for row in evidence_rows if row.get('suspiciousReasons')]
    issues = _live_audit_acceptance_blockers(run)
    final_acceptance = not issues
    return {
        **summary,
        'diagnostic': 'live-audit-runner-acceptance',
        'acceptancePolicy': 'V296.03 accepts section only if aggregate, external API evidence, failures, suspicious and case-level proofs all pass.',
        'finalAcceptance': final_acceptance,
        'acceptancePassed': final_acceptance,
        'acceptanceIssues': issues,
        'caseProofsTotal': len(evidence_rows),
        'suspiciousCount': len(suspicious),
        'suspiciousPassedCount': sum(1 for row in suspicious if row.get('ok')),
        'proofHashes': [row.get('proofHash') for row in evidence_rows],
        'acceptanceSummary': {
            'release': APP_RELEASE,
            'section': run.get('section'),
            'planned': int(run.get('planned') or 0),
            'completed': int(run.get('completed') or 0),
            'passed': int(run.get('passed') or 0),
            'failed': int(run.get('failed') or 0),
            'externalApiCallsTotalIncludingCache': int(run.get('externalApiCalls') or 0) + int(run.get('cachedExternalApiCalls') or 0),
            'finalAcceptance': final_acceptance,
        },
    }


@app.get('/api/diagnostics/live-audit/evidence')
async def live_audit_runner_evidence(key: str = '', runId: str = '', release: str = '', limit: int = 500, offset: int = 0):
    run = _live_audit_load_run_for_read(key, runId, release, 'live-audit-runner-evidence')
    if isinstance(run, JSONResponse):
        return run
    try:
        offset_value = max(0, int(offset))
        limit_value = max(1, min(500, int(limit)))
    except Exception:
        offset_value = 0
        limit_value = 500
    all_rows = _live_audit_evidence_list(run)
    rows = all_rows[offset_value:offset_value + limit_value]
    return {
        **_live_audit_public_run_summary(run, include_failures_preview=False),
        'diagnostic': 'live-audit-runner-evidence',
        'evidenceMode': 'strict-case-level-proof',
        'evidenceRowsTotal': len(all_rows),
        'evidenceRowsReturned': len(rows),
        'evidenceRowsOffset': offset_value,
        'evidenceRowsLimit': limit_value,
        'evidenceRows': rows,
    }


@app.get('/api/diagnostics/live-audit/report')
async def live_audit_runner_report(key: str = '', runId: str = '', release: str = ''):
    run = _live_audit_load_run_for_read(key, runId, release, 'live-audit-runner-report')
    if isinstance(run, JSONResponse):
        return run
    acceptance = await live_audit_runner_acceptance(key=key, runId=runId, release=release)
    if isinstance(acceptance, JSONResponse):
        return acceptance
    failures = list(run.get('failures') or [])
    evidence_rows = _live_audit_evidence_list(run)
    suspicious = [row for row in evidence_rows if isinstance(row, dict) and row.get('suspiciousReasons')]
    return {
        **acceptance,
        'diagnostic': 'live-audit-runner-report',
        'reportKind': 'V296.03 proof audit report',
        'operatorInstruction': 'Пришлите эту ссылку ChatGPT. Aggregate summary без report/acceptance/evidence не считается основанием для принятия раздела.',
        'counts': {
            'failures': len(failures),
            'suspicious': len(suspicious),
            'evidenceRows': len(evidence_rows),
        },
        'failureSamples': [_compact_live_audit_result(item) for item in failures[:20]],
        'suspiciousSamples': suspicious[:20],
        'evidenceSample': evidence_rows[:10],
    }


@app.get('/api/diagnostics/math-audit')
async def math_audit_diagnostics():
    return await run_math_audit()


@app.post('/api/diagnostics/math-audit')
async def math_audit_diagnostics_custom(request: Request):
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON'})
    cases = data.get('cases') if isinstance(data, dict) else None
    if not isinstance(cases, list):
        return _json_error(400, {'error': 'Нужно передать JSON вида {"cases": [{"text": "...", "expected": ["..."]}]}'})
    return await run_math_audit(cases)


@app.post('/')
async def proxy(request: Request):
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON'})
    action = data.get('action')
    if action != 'explain':
        return _json_error(400, {'error': 'Invalid action'})
    text = data.get('text')
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data))


@app.post('/api/explanations')
@app.post('/api/explain')
async def explain_v2(request: Request):
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON'})
    text = str(data.get('text') or '').strip()
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data))


@app.post('/explanations')
async def explain_without_api_prefix(request: Request):
    # Compatibility route for frontends configured with API_BASE_URL pointing to
    # the backend root instead of backend /api.  It returns the same JSON shape
    # as /api/explanations and prevents an HTML/static fallback from being
    # interpreted as an unclear server response.
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON'})
    text = str(data.get('text') or '').strip()
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data))


@app.post('/api/auth/register')
async def auth_register(request: Request):
    payload = await request.json()
    try:
        return get_access_service().register(
            name=str(payload.get('name') or ''),
            email=str(payload.get('email') or ''),
            password=str(payload.get('password') or ''),
            install_id=_extract_install_id(request, payload),
        )
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.post('/api/auth/login')
async def auth_login(request: Request):
    payload = await request.json()
    try:
        return get_access_service().login(
            email=str(payload.get('email') or ''),
            password=str(payload.get('password') or ''),
            install_id=_extract_install_id(request, payload),
        )
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.post('/api/auth/recover')
async def auth_recover(request: Request):
    payload = await request.json()
    return get_access_service().recover(email=str(payload.get('email') or ''))


@app.post('/api/auth/logout')
async def auth_logout(request: Request):
    payload = await request.json() if request.method == 'POST' else {}
    token = _extract_bearer_token(request) or str(payload.get('token') or '') or None
    return get_access_service().logout(token=token)


@app.get('/api/user/profile')
async def get_profile(request: Request):
    try:
        return get_access_service().get_profile(token=_extract_bearer_token(request))
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.patch('/api/user/profile')
async def patch_profile(request: Request):
    payload = await request.json()
    try:
        return get_access_service().update_profile(token=_extract_bearer_token(request), payload=payload)
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.get('/api/billing/subscription')
async def get_subscription(request: Request):
    try:
        return get_access_service().get_subscription(
            token=_extract_bearer_token(request),
            install_id=_extract_install_id(request),
        )
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.get('/api/billing/access-status')
async def get_access_status(request: Request):
    try:
        return get_access_service().get_access_status(
            token=_extract_bearer_token(request),
            install_id=_extract_install_id(request),
        )
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.post('/api/billing/restore')
async def restore_billing(request: Request):
    try:
        return get_access_service().restore_purchase(token=_extract_bearer_token(request), install_id=_extract_install_id(request))
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.post('/api/billing/web-session')
async def create_web_session(request: Request):
    payload = await request.json()
    try:
        return get_access_service().create_web_billing_session(token=_extract_bearer_token(request), install_id=_extract_install_id(request, payload), payload=payload)
    except AccessServiceError as exc:
        return _error_payload(exc)
