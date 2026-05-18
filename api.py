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
    host_no_port = host.split(':', 1)[0] if host else ''
    if host_no_port.endswith('.twc1.net') and scheme == 'http':
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
    # Path-based URLs are used because some web clients reorder query params or
    # render `&section` as the HTML entity `§ion`. These links contain no query
    # string, so they are stable for browser/web-tool automation.
    start_path = f'/api/diagnostics/live-audit/start-next/{release_token}/{audit_key}'
    control_path = f'/api/diagnostics/live-audit/control/{release_token}/{audit_key}'
    status_template = f'/api/diagnostics/live-audit/status-run/{release_token}/{audit_key}/{{runId}}'
    summary_template = f'/api/diagnostics/live-audit/summary-run/{release_token}/{audit_key}/{{runId}}'
    failures_template = f'/api/diagnostics/live-audit/failures-run/{release_token}/{audit_key}/{{runId}}'
    step_template = f'/api/diagnostics/live-audit/step-run/{release_token}/{audit_key}/{{runId}}'
    auto_path = f'/api/diagnostics/live-audit/auto-current/{release_token}/{audit_key}'
    step_current_path = f'/api/diagnostics/live-audit/step-current/{release_token}/{audit_key}'
    legacy_auto_path = f'/api/diagnostics/live-audit/auto/{audit_key}/{release_token}'
    # Keep legacy query links for manual debugging only. The automated flow should
    # use nextAuditStartUrlPathBased / nextAuditStartUrl.
    legacy_start_query = urlencode([
        ('section', 'g1_numbers_values'),
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
        'nextAuditPlannedMapStep': 'v298 step-runner re-audit: 1 класс, раздел 1 — Числа и величины',
        'nextAuditSection': 'g1_numbers_values',
        'nextAuditLimit': 100,
        'nextAuditRelease': APP_RELEASE,
        'nextAuditCacheBust': APP_RELEASE,
        'nextAuditControlPath': control_path,
        'nextAuditControlUrl': base_url + control_path,
        'nextAuditAutoPath': auto_path,
        'nextAuditAutoUrl': base_url + auto_path,
        'nextAuditAutoCurrentPath': auto_path,
        'nextAuditAutoCurrentUrl': base_url + auto_path,
        'nextAuditStepCurrentPath': step_current_path,
        'nextAuditStepCurrentUrl': base_url + step_current_path,
        'nextAuditZeroCopyAutomationUrl': base_url + auto_path,
        'nextAuditLegacyAutoPath': legacy_auto_path,
        'nextAuditLegacyAutoUrl': base_url + legacy_auto_path,
        'nextAuditStartPath': start_path,
        'nextAuditStartUrl': base_url + start_path,
        'nextAuditStartUrlPathBased': True,
        'nextAuditRootIsClickableDashboard': True,
        'nextAuditStatusUrlTemplate': base_url + status_template,
        'nextAuditSummaryUrlTemplate': base_url + summary_template,
        'nextAuditFailuresUrlTemplate': base_url + failures_template,
        'nextAuditStepUrlTemplate': base_url + step_template,
        'nextAuditLegacyStartPath': legacy_start_path,
        'nextAuditLegacyStartUrl': base_url + legacy_start_path,
        'nextAuditQueryOrderSafe': True,
        'nextAuditNoSectionEntityRisk': True,
        'nextAuditNoQueryParamReorderRisk': True,
        'nextAuditNote': 'Автоматизация должна открывать nextAuditAutoCurrentUrl или nextAuditStepCurrentUrl. Каждый вызов выполняет короткий step на 5 задач; status/summary/failures не вызывают DeepSeek; повторный step переиспользует cache текущего release.',
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


LIVE_PRODUCTION_AUDIT_DEFAULT_KEY = 'v286-live-audit'
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
    return category.startswith('v287_') or name.startswith('v287_')


def _select_live_production_cases(section: str) -> list[dict[str, Any]]:
    section_key = str(section or 'representative').strip().lower().replace('-', '_')
    cases = list(DEFAULT_AUDIT_CASES)
    if section_key in {'v285', 'g1_numbers_values_v285'}:
        return [case for case in cases if _case_matches_v285_numbers_values(case)]
    if section_key in {'g1_numbers_values', 'g1_section1', 'g1_numbers_values_v289', 'current_section', 'v289'}:
        return [case for case in cases if _case_matches_v289_numbers_values(case)]
    if section_key in {'g1_arithmetic_actions', 'g1_section2', 'v287'}:
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
LIVE_AUDIT_RUNNER_PROMPT_VERSION = 'v298-step-runner-cache-v7'
LIVE_AUDIT_RUNNER_MAX_LIMIT = 200
LIVE_AUDIT_RUNNER_DEFAULT_MAX_EXTERNAL_CALLS = 100
LIVE_AUDIT_RUNNER_STATE_ENV = 'LIVE_AUDIT_STATE_FILE'
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


def _compact_live_audit_result(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': row.get('id'),
        'grade': row.get('grade'),
        'category': row.get('category'),
        'name': row.get('name'),
        'ok': bool(row.get('ok')),
        'issues': row.get('issues') or [],
        'source': row.get('source'),
        'expectedFinalAnswer': row.get('expectedFinalAnswer'),
        'expectedUnit': row.get('expectedUnit'),
        'externalApiAttempts': int(row.get('externalApiAttempts') or 0),
        'externalApiCompleted': int(row.get('externalApiCompleted') or 0),
        'externalApiBlocked': int(row.get('externalApiBlocked') or 0),
        'externalApiErrors': int(row.get('externalApiErrors') or 0),
        'externalApiUsed': bool(row.get('externalApiUsed')),
        'fromCache': bool(row.get('fromCache')),
        'cacheKey': row.get('cacheKey'),
        'resultPreview': str(row.get('resultPreview') or '')[:420],
    }


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
    out = {
        **_version_payload(),
        'diagnostic': 'live-audit-runner',
        'runnerMode': 'STEP_TIMEWEB_DEEPSEEK_AUDIT_WITH_CACHE',
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
        'startedAt': run.get('startedAt'),
        'updatedAt': run.get('updatedAt'),
        'finishedAt': run.get('finishedAt'),
        'planKey': run.get('planKey'),
        'stateFile': str(_live_audit_state_path()),
        'nextPlannedMapStep': 'after v298 step-runner pass: v299 — 1 класс, раздел 2 — Арифметические действия',
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
        for item in case_items:
            case = dict(item.get('case') or {})
            cache_key = str(item.get('cacheKey') or _live_audit_case_cache_key(case, allow_external))
            state = _load_live_audit_state()
            current = state['runs'].get(run_id, {})
            if current.get('status') in {'cancelled', 'done'}:
                return
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
                if allow_external and int(current.get('externalApiCalls') or 0) >= max_external_calls:
                    row = _live_audit_build_case_limit_error(case, cache_key, 'live-audit external API budget reached before this case')
                    external_counts = {'externalApiAttempts': 0, 'externalApiCompleted': 0, 'externalApiBlocked': 0, 'externalApiErrors': 0, 'cachedExternalApiAttempts': 0}
                else:
                    row, external_counts = await _evaluate_live_audit_case(case, allow_external=allow_external, cache_key=cache_key)
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
            compact = _compact_live_audit_result(row)
            def _append_result(state):
                live_run = state['runs'].get(run_id)
                if not isinstance(live_run, dict):
                    return
                live_run.setdefault('results', []).append(compact)
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
                live_run['updatedAt'] = _now_ts()
            _mutate_live_audit_state(_append_result)
        def _mark_done(state):
            live_run = state['runs'].get(run_id)
            if not isinstance(live_run, dict):
                return
            live_run['status'] = 'done'
            live_run['finishedAt'] = _now_ts()
            live_run['updatedAt'] = live_run['finishedAt']
        _mutate_live_audit_state(_mark_done)
    except Exception as exc:
        def _mark_error(state):
            live_run = state['runs'].get(run_id)
            if not isinstance(live_run, dict):
                return
            live_run['status'] = 'error'
            live_run['error'] = str(exc)[:500]
            live_run['updatedAt'] = _now_ts()
        _mutate_live_audit_state(_mark_error)


def _ensure_live_audit_task(run_id: str) -> None:
    task = _LIVE_AUDIT_TASKS.get(run_id)
    if task is not None and not task.done():
        return
    _LIVE_AUDIT_TASKS[run_id] = asyncio.create_task(_run_live_audit_background(run_id))


def _add_live_audit_step_links(request: Request | None, key: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Attach stable path-based links for step-runner automation."""
    out = dict(summary)
    run_id = str(out.get('runId') or '')
    base_url = _public_base_url(request)
    if run_id:
        step_path = f'/api/diagnostics/live-audit/step-run/{APP_RELEASE}/{key}/{run_id}'
        status_path = f'/api/diagnostics/live-audit/status-run/{APP_RELEASE}/{key}/{run_id}'
        summary_path = f'/api/diagnostics/live-audit/summary-run/{APP_RELEASE}/{key}/{run_id}'
        failures_path = f'/api/diagnostics/live-audit/failures-run/{APP_RELEASE}/{key}/{run_id}'
        out.update({
            'stepPath': step_path,
            'stepUrl': base_url + step_path,
            'statusPath': status_path,
            'statusUrl': base_url + status_path,
            'summaryPath': summary_path,
            'summaryUrl': base_url + summary_path,
            'failuresPath': failures_path,
            'failuresUrl': base_url + failures_path,
            'pathBasedUrls': True,
        })
    return out


async def _run_live_audit_step_chunk(run_id: str, *, chunk_size: int = 5) -> dict[str, Any]:
    """Process a short deterministic chunk of one live-audit run.

    This avoids background tasks and long 50/100-case requests. Each call processes
    at most `chunk_size` pending cases, persists progress, and reuses case cache.
    """
    try:
        chunk_size_value = max(1, min(10, int(chunk_size)))
    except Exception:
        chunk_size_value = 5
    run_id = str(run_id or '').strip()
    if not run_id:
        return {'diagnostic': 'live-audit-step-runner', 'status': 'error', 'error': 'empty runId'}

    def _mark_step_running(state):
        run = state.get('runs', {}).get(run_id)
        if not isinstance(run, dict):
            return None
        if run.get('release') != APP_RELEASE:
            return {'releaseMismatch': True, 'run': run}
        if run.get('status') not in {'done', 'error', 'cancelled'}:
            run['status'] = 'running'
            run.setdefault('startedAt', _now_ts())
            run['updatedAt'] = _now_ts()
        return {'releaseMismatch': False, 'run': run}

    marker = _mutate_live_audit_state(_mark_step_running)
    if not isinstance(marker, dict) or not isinstance(marker.get('run'), dict):
        return {'diagnostic': 'live-audit-step-runner', 'status': 'not_found', 'error': 'runId не найден', 'runId': run_id}
    if marker.get('releaseMismatch'):
        run = marker['run']
        return {
            **_version_payload(),
            'diagnostic': 'live-audit-step-runner',
            'status': 'release_mismatch_no_step',
            'runId': run_id,
            'runRelease': run.get('release'),
            'currentRelease': APP_RELEASE,
            'externalApiCalls': 0,
            'externalApiUsed': False,
            'tokenSpendPrevented': True,
        }

    processed_this_step = 0
    from_cache_this_step = 0
    external_calls_this_step = 0
    external_completed_this_step = 0
    external_errors_this_step = 0
    external_blocked_this_step = 0

    for _ in range(chunk_size_value):
        state = _load_live_audit_state()
        run = state.get('runs', {}).get(run_id)
        if not isinstance(run, dict):
            break
        if run.get('status') in {'done', 'error', 'cancelled'}:
            break
        case_items = list(run.get('cases') or [])
        completed = int(run.get('completed') or 0)
        # If older state got inconsistent, use results length as a floor guard.
        results_len = len(run.get('results') or [])
        if results_len > completed:
            completed = results_len
        if completed >= len(case_items):
            def _mark_done_empty(state):
                live_run = state.get('runs', {}).get(run_id)
                if isinstance(live_run, dict):
                    live_run['completed'] = len(live_run.get('results') or [])
                    live_run['status'] = 'done'
                    live_run['finishedAt'] = _now_ts()
                    live_run['updatedAt'] = live_run['finishedAt']
            _mutate_live_audit_state(_mark_done_empty)
            break

        item = case_items[completed]
        case = dict(item.get('case') or {})
        allow_external = bool(run.get('allowExternal'))
        force = bool(run.get('force'))
        max_external_calls = int(run.get('maxExternalCalls') or LIVE_AUDIT_RUNNER_DEFAULT_MAX_EXTERNAL_CALLS)
        cache_key = str(item.get('cacheKey') or _live_audit_case_cache_key(case, allow_external))
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
            from_cache_this_step += 1
        else:
            if allow_external and int(run.get('externalApiCalls') or 0) >= max_external_calls:
                row = _live_audit_build_case_limit_error(case, cache_key, 'live-audit external API budget reached before this case')
                external_counts = {
                    'externalApiAttempts': 0,
                    'externalApiCompleted': 0,
                    'externalApiBlocked': 0,
                    'externalApiErrors': 0,
                    'cachedExternalApiAttempts': 0,
                }
            else:
                row, external_counts = await _evaluate_live_audit_case(case, allow_external=allow_external, cache_key=cache_key)
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

        compact = _compact_live_audit_result(row)

        def _append_result(state):
            live_run = state.get('runs', {}).get(run_id)
            if not isinstance(live_run, dict):
                return
            # Avoid duplicate append if another request already advanced this case.
            if len(live_run.get('results') or []) > completed:
                return
            live_run.setdefault('results', []).append(compact)
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
            live_run['updatedAt'] = _now_ts()
            if int(live_run.get('completed') or 0) >= int(live_run.get('planned') or 0):
                live_run['status'] = 'done'
                live_run['finishedAt'] = live_run['updatedAt']
            else:
                live_run['status'] = 'running'
        _mutate_live_audit_state(_append_result)
        processed_this_step += 1
        external_calls_this_step += int(external_counts.get('externalApiAttempts') or 0)
        external_completed_this_step += int(external_counts.get('externalApiCompleted') or 0)
        external_errors_this_step += int(external_counts.get('externalApiErrors') or 0)
        external_blocked_this_step += int(external_counts.get('externalApiBlocked') or 0)

    state = _load_live_audit_state()
    run = state.get('runs', {}).get(run_id)
    if not isinstance(run, dict):
        return {'diagnostic': 'live-audit-step-runner', 'status': 'not_found_after_step', 'runId': run_id}
    summary = _live_audit_public_run_summary(run, include_failures_preview=True)
    summary.update({
        'diagnostic': 'live-audit-step-runner',
        'runnerMode': 'STEP_TIMEWEB_DEEPSEEK_AUDIT_WITH_CACHE',
        'stepChunkSize': chunk_size_value,
        'stepProcessed': processed_this_step,
        'stepFromCache': from_cache_this_step,
        'stepExternalApiCalls': external_calls_this_step,
        'stepExternalApiCompleted': external_completed_this_step,
        'stepExternalApiErrors': external_errors_this_step,
        'stepExternalApiBlocked': external_blocked_this_step,
        'stepDone': bool(run.get('status') == 'done'),
        'continueNeeded': bool(run.get('status') != 'done'),
    })
    return summary


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
    step = payload.get('stepUrl') or payload.get('stepPath') or payload.get('nextAuditStepCurrentUrl') or ''
    auto = payload.get('nextAuditAutoUrl') or payload.get('autoUrl') or ''
    for label, url in [
        ('Open zero-copy audit automation entrypoint', auto),
        ('Open audit control dashboard', control),
        ('START next live DeepSeek audit', start),
        ('Check audit status', status),
        ('Open audit summary', summary),
        ('Open audit failures', failures),
        ('Continue audit step', step),
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
            'hint': 'Default test key in this build: v286-live-audit. For production, set LIVE_AUDIT_KEY in Timeweb.',
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
        'nextPlannedMapStep': 'after v298 step-runner pass: v299 — 1 класс, раздел 2 — Арифметические действия',
    }





@app.get('/api/diagnostics/live-audit/health-current/{expected_release}')
async def live_audit_health_current(request: Request, expected_release: str):
    """No-token release guard for automation.

    This endpoint is safe to open before any live audit. It never calls DeepSeek.
    If the visible server is stale, it returns releaseMatches=false and HTTP 409.
    """
    release_matches = str(expected_release or '').strip() == APP_RELEASE
    payload = {
        **_version_payload(request),
        'diagnostic': 'live-audit-health-current',
        'expectedRelease': expected_release,
        'currentRelease': APP_RELEASE,
        'releaseMatches': release_matches,
        'safeToStartAudit': release_matches,
        'externalApiCalls': 0,
        'externalApiUsed': False,
        'note': 'Open auto-current only when releaseMatches=true. This health endpoint never spends DeepSeek tokens.',
    }
    if not release_matches:
        return _html_ok(_audit_dashboard_html('Live audit health: release mismatch', payload), status_code=409)
    return _html_ok(_audit_dashboard_html('Live audit health: release OK', payload))


@app.get('/api/diagnostics/live-audit/auto-current/{expected_release}/{key_value}')
async def live_audit_auto_current_release_guard(request: Request, expected_release: str, key_value: str):
    """Stable no-query zero-copy audit entrypoint with release guard.

    The assistant can open this fixed path directly after deployment. If a stale
    server/build is visible, this endpoint returns 409 and does not spend tokens.
    """
    requested_release = str(expected_release or '').strip()
    if requested_release != APP_RELEASE:
        payload = {
            **_version_payload(request),
            'diagnostic': 'live-audit-auto-current-release-guard',
            'status': 'release_mismatch_no_audit_started',
            'requestedRelease': requested_release,
            'currentRelease': APP_RELEASE,
            'releaseMatches': False,
            'externalApiCalls': 0,
            'externalApiUsed': False,
            'tokenSpendPrevented': True,
            'note': 'Visible backend release does not match requested release. No DeepSeek calls were made.',
        }
        return _html_ok(_audit_dashboard_html('Live audit not started: release mismatch', payload), status_code=409)
    start_result = await live_audit_runner_start(
        request=request,
        key=key_value,
        section='g1_numbers_values',
        limit=100,
        offset=0,
        allowExternal=1,
        force=0,
        maxExternalCalls=150,
        release=APP_RELEASE,
        cacheBust=APP_RELEASE,
        startBackground=0,
    )
    if isinstance(start_result, JSONResponse):
        return start_result
    run_id_value = str(dict(start_result).get('runId') or '')
    step_result = await _run_live_audit_step_chunk(run_id_value, chunk_size=5)
    result = _add_live_audit_step_links(request, key_value, step_result)
    result['diagnostic'] = 'live-audit-auto-current-step-runner'
    result['automationEntrypoint'] = 'path-no-query-expected-release-guard-step-runner'
    result['expectedRelease'] = requested_release
    result['currentRelease'] = APP_RELEASE
    result['releaseMatches'] = True
    result['userCopyPasteRequired'] = False
    result['tokenSpendGuard'] = 'Release mismatch returns 409 before any DeepSeek call; each auto-current open advances at most 5 cases.'
    result['note'] = (
        'v298 step-runner automation: each open processes a short chunk and saves progress/cache. '
        'Re-open Continue audit step until completed=planned. status/summary/failures never call DeepSeek.'
    )
    return _html_ok(_audit_dashboard_html('Auto-current live audit step runner', result))


@app.get('/api/diagnostics/live-audit/auto-current/{key_value}')
async def live_audit_auto_current_latest(request: Request, key_value: str):
    """Current-release auto entrypoint without explicit expected release.

    Kept for convenience; the preferred automation path is
    /auto-current/{expected_release}/{key_value} because it prevents stale-build token spend.
    """
    return await live_audit_auto_current_release_guard(request, APP_RELEASE, key_value)


@app.get('/api/diagnostics/live-audit/auto/{key_value}')
async def live_audit_zero_copy_auto(request: Request, key_value: str):
    """Stable no-query entrypoint for zero-copy live audit automation.

    The assistant can open this fixed path directly without reading root JSON.
    It always targets the current APP_RELEASE and the next planned audit section.
    Re-opening it is safe: runner cache prevents repeated token spending unless
    a future force endpoint is used explicitly.
    """
    return await live_audit_zero_copy_auto_with_bust(request, key_value, APP_RELEASE)


@app.get('/api/diagnostics/live-audit/auto/{key_value}/{cache_bust}')
async def live_audit_zero_copy_auto_with_bust(request: Request, key_value: str, cache_bust: str):
    result = await live_audit_runner_start(
        request=request,
        key=key_value,
        section='g1_numbers_values',
        limit=100,
        offset=0,
        allowExternal=1,
        force=0,
        maxExternalCalls=150,
        release=APP_RELEASE,
        cacheBust=str(cache_bust or APP_RELEASE),
    )
    if isinstance(result, JSONResponse):
        return result
    result = dict(result)
    result['diagnostic'] = 'live-audit-zero-copy-automation'
    result['automationEntrypoint'] = 'path-no-query-current-release'
    result['currentRelease'] = APP_RELEASE
    result['cacheBustPathValue'] = cache_bust
    result['userCopyPasteRequired'] = False
    result['note'] = (
        'Zero-copy automation: assistant opens this fixed path; no root JSON or manual start URL paste is required. '
        'Repeated opens reuse the current release cache and do not spend DeepSeek tokens again.'
    )
    return _html_ok(_audit_dashboard_html('Zero-copy live audit automation', result))


@app.get('/api/diagnostics/live-audit/step-current/{expected_release}/{key_value}')
async def live_audit_step_current_release_guard(request: Request, expected_release: str, key_value: str):
    """Create/reuse the current planned audit run and process one short chunk.

    This is the preferred automation endpoint for web-tool live audits because it
    avoids background tasks and long 100-case requests.
    """
    return await live_audit_auto_current_release_guard(request, expected_release, key_value)


@app.get('/api/diagnostics/live-audit/step-run/{release_token}/{key_value}/{run_id_value}')
async def live_audit_runner_step_path(request: Request, release_token: str, key_value: str, run_id_value: str, chunkSize: int = 5):
    if not _live_audit_key_matches(key_value):
        return _html_ok(_audit_dashboard_html('Live audit step: forbidden', {
            **_version_payload(request),
            'diagnostic': 'live-audit-step-runner',
            'status': 'forbidden',
            'error': 'Нужен live-audit key.',
            'externalApiCalls': 0,
            'externalApiUsed': False,
        }), status_code=403)
    if str(release_token or '').strip() != APP_RELEASE:
        return _html_ok(_audit_dashboard_html('Live audit step: release mismatch', {
            **_version_payload(request),
            'diagnostic': 'live-audit-step-runner',
            'status': 'release_mismatch_no_step',
            'requestedRelease': release_token,
            'currentRelease': APP_RELEASE,
            'releaseMatches': False,
            'externalApiCalls': 0,
            'externalApiUsed': False,
            'tokenSpendPrevented': True,
        }), status_code=409)
    result = await _run_live_audit_step_chunk(run_id_value, chunk_size=chunkSize)
    result = _add_live_audit_step_links(request, key_value, result)
    result['releaseMatches'] = True
    result['userCopyPasteRequired'] = False
    result['note'] = 'Step-run processes at most 5–10 pending cases per request. Reopen Continue audit step until completed=planned.'
    return _html_ok(_audit_dashboard_html('Live audit step runner', result))


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
        section='g1_numbers_values',
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
    startBackground: int = 1,
):
    if not _live_audit_key_matches(key):
        return _json_error(403, {
            'error': 'Нужен live-audit key. Передайте ?key=... или задайте LIVE_AUDIT_KEY на сервере.',
            'diagnostic': 'live-audit-runner-start',
            'hint': 'Default test key in this build: v286-live-audit. For production, set LIVE_AUDIT_KEY in Timeweb.',
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
            'force': force_value,
            'maxExternalCalls': max_external_calls_value,
            'externalApiCalls': 0,
            'externalApiCompleted': 0,
            'externalApiBlocked': 0,
            'externalApiErrors': 0,
            'cachedResults': 0,
            'cachedExternalApiCalls': 0,
            'results': [],
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
    if int(startBackground or 0) and run.get('status') in {'queued', 'running'}:
        _ensure_live_audit_task(run_id_value)
    summary = _live_audit_public_run_summary(run, include_failures_preview=False)
    status_path = '/api/diagnostics/live-audit/status?' + urlencode([('key', key), ('release', APP_RELEASE), ('runId', run_id_value)])
    summary_path = '/api/diagnostics/live-audit/summary?' + urlencode([('key', key), ('release', APP_RELEASE), ('runId', run_id_value)])
    failures_path = '/api/diagnostics/live-audit/failures?' + urlencode([('key', key), ('release', APP_RELEASE), ('runId', run_id_value)])
    status_path_based = f'/api/diagnostics/live-audit/status-run/{APP_RELEASE}/{key}/{run_id_value}'
    summary_path_based = f'/api/diagnostics/live-audit/summary-run/{APP_RELEASE}/{key}/{run_id_value}'
    failures_path_based = f'/api/diagnostics/live-audit/failures-run/{APP_RELEASE}/{key}/{run_id_value}'
    base_url = _public_base_url(request)
    return {
        **summary,
        'diagnostic': 'live-audit-runner-start',
        'reusedExistingRun': bool(reused),
        'runId': run_id_value,
        'statusPath': status_path_based,
        'summaryPath': summary_path_based,
        'failuresPath': failures_path_based,
        'statusUrl': base_url + status_path_based,
        'summaryUrl': base_url + summary_path_based,
        'failuresUrl': base_url + failures_path_based,
        'legacyStatusUrl': base_url + status_path,
        'legacySummaryUrl': base_url + summary_path,
        'legacyFailuresUrl': base_url + failures_path,
        'pathBasedUrls': True,
        'note': 'Повторные status/summary/failures не вызывают DeepSeek. Повторный start без force=1 переиспользует этот run/cache. Автоматизация должна использовать path-based URL без query-параметров.',
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
    # v298: status is read-only; use step-run/auto-current to advance the audit.
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
