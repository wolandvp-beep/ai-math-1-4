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

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


CARD_DATA_BLOCK_MESSAGE = (
    'Данные банковской карты нельзя отправлять в приложение. '
    'Оплата подписки проходит только на стороне Robokassa.'
)


FRONTEND_EXPECTED_BACKEND_RELEASE = APP_RELEASE


def _version_payload() -> dict:
    return {
        'release': APP_RELEASE,
        'backendBuild': APP_RELEASE,
        'solverVersion': SOLVER_VERSION,
        'frontendExpectedBackend': FRONTEND_EXPECTED_BACKEND_RELEASE,
        'solverMode': resolve_solver_mode(),
        'deepseekApiKeyConfigured': deepseek_api_key_configured(),
        'status': 'ok',
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
LIVE_AUDIT_RUNNER_PROMPT_VERSION = 'v290-deepseek-primary-json-v1'
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
        'startedAt': run.get('startedAt'),
        'updatedAt': run.get('updatedAt'),
        'finishedAt': run.get('finishedAt'),
        'planKey': run.get('planKey'),
        'stateFile': str(_live_audit_state_path()),
        'nextPlannedMapStep': 'v291: 1 класс, раздел 1 — Числа и величины',
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


@app.get('/')
@app.get('/api')
def read_root():
    product = build_public_product_config()
    return {
        **_version_payload(),
        'message': 'Математичка backend работает.',
        'provider': product['provider'],
        'platforms': product['distributionPlatforms'],
        'checkoutMode': product['checkoutMode'],
        'hint': 'POST / with action=explain or POST /api/explanations with {text}',
    }


@app.get('/version')
@app.get('/api/version')
def read_version():
    return _version_payload()


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
        'nextPlannedMapStep': 'v291: 1 класс, раздел 1 — Числа и величины',
    }


@app.get('/api/diagnostics/live-audit/start')
async def live_audit_runner_start(
    key: str = '',
    section: str = 'g1_numbers_values',
    limit: int = 100,
    offset: int = 0,
    allowExternal: int = 1,
    force: int = 0,
    maxExternalCalls: int = LIVE_AUDIT_RUNNER_DEFAULT_MAX_EXTERNAL_CALLS,
):
    if not _live_audit_key_matches(key):
        return _json_error(403, {
            'error': 'Нужен live-audit key. Передайте ?key=... или задайте LIVE_AUDIT_KEY на сервере.',
            'diagnostic': 'live-audit-runner-start',
            'hint': 'Default test key in this build: v286-live-audit. For production, set LIVE_AUDIT_KEY in Timeweb.',
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
                return existing_id, existing_run, True
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
    if run.get('status') in {'queued', 'running'}:
        _ensure_live_audit_task(run_id_value)
    summary = _live_audit_public_run_summary(run, include_failures_preview=False)
    return {
        **summary,
        'diagnostic': 'live-audit-runner-start',
        'reusedExistingRun': bool(reused),
        'runId': run_id_value,
        'statusPath': f'/api/diagnostics/live-audit/status?key={key}&runId={run_id_value}',
        'summaryPath': f'/api/diagnostics/live-audit/summary?key={key}&runId={run_id_value}',
        'failuresPath': f'/api/diagnostics/live-audit/failures?key={key}&runId={run_id_value}',
        'note': 'Повторные status/summary/failures не вызывают DeepSeek. Повторный start без force=1 переиспользует этот run/cache.',
    }


@app.get('/api/diagnostics/live-audit/status')
async def live_audit_runner_status(key: str = '', runId: str = ''):
    if not _live_audit_key_matches(key):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'live-audit-runner-status'})
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(str(runId or '').strip())
    if not isinstance(run, dict):
        return _json_error(404, {'error': 'runId не найден', 'diagnostic': 'live-audit-runner-status', 'runId': runId})
    if run.get('status') in {'queued', 'running'}:
        _ensure_live_audit_task(str(run.get('runId') or runId))
    return _live_audit_public_run_summary(run, include_failures_preview=True)


@app.get('/api/diagnostics/live-audit/summary')
async def live_audit_runner_summary(key: str = '', runId: str = ''):
    if not _live_audit_key_matches(key):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'live-audit-runner-summary'})
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(str(runId or '').strip())
    if not isinstance(run, dict):
        return _json_error(404, {'error': 'runId не найден', 'diagnostic': 'live-audit-runner-summary', 'runId': runId})
    return _live_audit_public_run_summary(run, include_failures_preview=True)


@app.get('/api/diagnostics/live-audit/failures')
async def live_audit_runner_failures(key: str = '', runId: str = '', limit: int = 50):
    if not _live_audit_key_matches(key):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'live-audit-runner-failures'})
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
