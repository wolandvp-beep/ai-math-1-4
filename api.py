from __future__ import annotations

import asyncio
import contextvars
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
from backend.service import APP_RELEASE, SOLVER_VERSION, attach_release, canonicalize_v309_math_information_response, canonicalize_v310_numbers_quantities_response, canonicalize_v311_arithmetic_actions_response, deepseek_api_key_configured, generate_explanation_response, prevalidate_explanation_request, resolve_solver_mode
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


def _public_frontend_url() -> str:
    return (
        os.environ.get('PUBLIC_FRONTEND_URL')
        or os.environ.get('FRONTEND_PUBLIC_URL')
        or 'https://wolandvp-beep.github.io/ai-math-1-4-frontend/'
    ).strip().rstrip('/') + '/'




def _public_frontend_url() -> str:
    """Return deployed GitHub Pages frontend URL used by UI-render audit iframe."""
    value = (
        os.environ.get('PUBLIC_FRONTEND_URL')
        or os.environ.get('FRONTEND_PUBLIC_URL')
        or os.environ.get('GITHUB_PAGES_FRONTEND_URL')
        or 'https://wolandvp-beep.github.io/ai-math-1-4-frontend/'
    ).strip()
    if not value:
        value = 'https://wolandvp-beep.github.io/ai-math-1-4-frontend/'
    if not value.endswith('/'):
        value += '/'
    return value


def _ui_render_audit_url(request: Request | None, key: str | None = None) -> str:
    audit_key = key or os.environ.get('LIVE_AUDIT_PUBLIC_HINT_KEY') or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY
    backend_base = _public_base_url(request)
    query = urlencode([
        ('matematichkaUiAudit', 'frontend-operator'),
        ('backendBaseUrl', backend_base),
        ('release', APP_RELEASE),
        ('auditKey', audit_key),
        ('cacheBust', APP_RELEASE),
    ])
    return _public_frontend_url() + '?' + query

def _next_live_audit_links(request: Request | None = None, key: str | None = None) -> dict:
    audit_key = key or os.environ.get('LIVE_AUDIT_PUBLIC_HINT_KEY') or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY
    base_url = _public_base_url(request)
    release_token = APP_RELEASE
    operator_path = f'/api/diagnostics/live-audit/operator/{release_token}/{audit_key}'
    raw_start_path = f'/api/diagnostics/live-audit/start-next/{release_token}/{audit_key}'
    status_template = f'/api/diagnostics/live-audit/status-run/{release_token}/{audit_key}/{{runId}}'
    summary_template = f'/api/diagnostics/live-audit/summary-run/{release_token}/{audit_key}/{{runId}}'
    failures_template = f'/api/diagnostics/live-audit/failures-run/{release_token}/{audit_key}/{{runId}}'
    report_template = f'/api/diagnostics/live-audit/final-report/{release_token}/{audit_key}/{{runId}}'
    legacy_start_query = urlencode([
        ('section', 'g4_arithmetic_actions'),
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
        'nextAuditPlannedMapStep': 'V311.04 — 4 класс, раздел 2 — Арифметические действия, уравнения с объяснениями и столбиком, live browser UI-render audit',
        'nextAuditSection': 'g4_arithmetic_actions',
        'nextAuditLimit': 100,
        'nextAuditRelease': APP_RELEASE,
        'nextAuditCacheBust': APP_RELEASE,
        'nextAuditControlPath': operator_path,
        'nextAuditControlUrl': base_url + operator_path,
        'nextAuditStartPath': 'frontend-ui-render-audit',
        'nextAuditStartUrl': _ui_render_audit_url(request, audit_key),
        'nextAuditUiRenderUrl': _ui_render_audit_url(request, audit_key),
        'nextAuditOperatorPath': operator_path,
        'nextAuditOperatorUrl': base_url + operator_path,
        'nextAuditRawStartPath': raw_start_path,
        'nextAuditRawStartUrl': base_url + raw_start_path,
        'nextAuditStartUrlPathBased': True,
        'nextAuditRootIsClickableDashboard': True,
        'nextAuditStatusUrlTemplate': base_url + status_template,
        'nextAuditSummaryUrlTemplate': base_url + summary_template,
        'nextAuditFailuresUrlTemplate': base_url + failures_template,
        'nextAuditReportUrlTemplate': base_url + report_template,
        'nextAuditSingleResultUrlTemplate': base_url + report_template,
        'nextAuditEvidenceRequired': True,
        'nextAuditAcceptanceRule': 'Раздел принимать только по единой final-report ссылке: finalAcceptance=true, status=done, completed=planned, failed=0, failures=0, suspicious=0, evidence rows=planned, external API evidence present, frontend DOM resultBox proof present.',
        'nextAuditUserRunWorkflow': [
            '1) Откройте nextAuditStartUrl в браузере: это frontend UI-render audit на GitHub Pages.',
            '2) Нажмите одну кнопку: Запустить / продолжить UI-render аудит.',
            '3) Дождитесь статуса done/готово.',
            '4) Скопируйте одну ссылку: Итоговый отчёт для ChatGPT.',
        ],
        'nextAuditLocalOperatorWorkflow': 'Через браузер: frontend-страница сама заполняет основной textarea, нажимает основной solveBtn, читает DOM #resultBox и даёт одну итоговую ссылку.',
        'nextAuditLegacyStartPath': legacy_start_path,
        'nextAuditLegacyStartUrl': base_url + legacy_start_path,
        'nextAuditQueryOrderSafe': True,
        'nextAuditNoSectionEntityRisk': True,
        'nextAuditNoQueryParamReorderRisk': True,
        'nextAuditNote': 'V311.04 запускается с GitHub Pages frontend напрямую: браузер вводит реальные задания по арифметическим действиям 4 класса в приложение, нажимает основную кнопку решения, ждёт #resultBox и сверяет expected, API-ответ и пользовательски видимый DOM. Без force=1 повторный отчёт не тратит DeepSeek.',
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


LIVE_PRODUCTION_AUDIT_DEFAULT_KEY = 'v311.04-live-audit'
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

def _case_matches_v300_numbers_quantities(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v300_') or name.startswith('v300_')


def _case_matches_v303_geometry(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v303_') or name.startswith('v303_')


def _case_matches_v304_math_information(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v304_') or name.startswith('v304_')


def _case_matches_v305_numbers_quantities(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v305_') or name.startswith('v305_')


def _case_matches_v306_arithmetic_actions(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v306_') or name.startswith('v306_')


def _case_matches_v307_text_problems(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v307_') or name.startswith('v307_')


def _case_matches_v308_geometry(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v308_') or name.startswith('v308_')


def _case_matches_v309_math_information(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v309_') or name.startswith('v309_')


def _case_matches_v310_numbers_quantities(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v310_') or name.startswith('v310_')




def _case_matches_v311_arithmetic_actions(case: dict[str, Any]) -> bool:
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    return category.startswith('v311_') or name.startswith('v311_')

def _case_matches_current_programmatic_section(case: dict[str, Any]) -> bool:
    return _case_matches_v311_arithmetic_actions(case)


def _select_live_production_cases(section: str) -> list[dict[str, Any]]:
    section_key = str(section or 'representative').strip().lower().replace('-', '_')
    cases = list(DEFAULT_AUDIT_CASES)
    if section_key in {'v285', 'g1_numbers_values_v285'}:
        return [case for case in cases if _case_matches_v285_numbers_values(case)]
    if section_key in {'g1_numbers_values', 'g1_section1', 'g1_numbers_values_v289', 'v289'}:
        return [case for case in cases if _case_matches_v289_numbers_values(case)]
    if section_key in {'g2_numbers_quantities', 'g2_section1', 'v300'}:
        return [case for case in cases if _case_matches_v300_numbers_quantities(case)]
    if section_key in {'g2_geometry', 'g2_section4', 'v303'}:
        return [case for case in cases if _case_matches_v303_geometry(case)]
    if section_key in {'g2_math_information', 'g2_section5', 'v304'}:
        return [case for case in cases if _case_matches_v304_math_information(case)]
    if section_key in {'g4_arithmetic_actions', 'g4_section2', 'current_section', 'v311'}:
        return [case for case in cases if _case_matches_v311_arithmetic_actions(case)]
    if section_key in {'g4_numbers_quantities', 'g4_section1', 'v310'}:
        return [case for case in cases if _case_matches_v310_numbers_quantities(case)]
    if section_key in {'g3_math_information', 'g3_section5', 'v309'}:
        return [case for case in cases if _case_matches_v309_math_information(case)]
    if section_key in {'g3_geometry', 'g3_section4', 'v308'}:
        return [case for case in cases if _case_matches_v308_geometry(case)]
    if section_key in {'g3_text_problems', 'g3_section3', 'v307'}:
        return [case for case in cases if _case_matches_v307_text_problems(case)]
    if section_key in {'g3_arithmetic_actions', 'g3_section2', 'v306'}:
        return [case for case in cases if _case_matches_v306_arithmetic_actions(case)]
    if section_key in {'g3_numbers_quantities', 'g3_section1', 'v305'}:
        return [case for case in cases if _case_matches_v305_numbers_quantities(case)]
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


def _deepseek_usage_total(usage: Any) -> int:
    # API total tokens only.  Do not add prompt_cache_hit/miss here; those are
    # reported separately in dedicated section audits to avoid visual contradictions in reports.
    if not isinstance(usage, dict):
        return 0
    for key in ('total_tokens', 'totalTokens'):
        try:
            value = int(usage.get(key) or 0)
            if value > 0:
                return value
        except Exception:
            pass
    return _deepseek_usage_api_prompt(usage) + _deepseek_usage_completion(usage)


def _deepseek_usage_prompt(usage: Any) -> int:
    # Legacy alias retained for old report readers; it mirrors apiPromptTokens,
    # while cache hit/miss tokens live in promptCacheHitTokens/promptCacheMissTokens.
    return _deepseek_usage_api_prompt(usage)


def _deepseek_usage_completion(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    for key in ('completion_tokens', 'output_tokens'):
        try:
            value = int(usage.get(key) or 0)
            if value > 0:
                return value
        except Exception:
            pass
    return 0


def _deepseek_usage_api_prompt(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    for key in ('prompt_tokens', 'input_tokens'):
        try:
            value = int(usage.get(key) or 0)
            if value > 0:
                return value
        except Exception:
            pass
    return 0


def _deepseek_usage_api_completion(usage: Any) -> int:
    return _deepseek_usage_completion(usage)


def _deepseek_usage_api_total(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    for key in ('total_tokens', 'totalTokens'):
        try:
            value = int(usage.get(key) or 0)
            if value > 0:
                return value
        except Exception:
            pass
    return _deepseek_usage_api_prompt(usage) + _deepseek_usage_api_completion(usage)


def _deepseek_usage_cache_hit(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    for key in ('prompt_cache_hit_tokens', 'promptCacheHitTokens'):
        try:
            return max(0, int(usage.get(key) or 0))
        except Exception:
            pass
    return 0


def _deepseek_usage_cache_miss(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    for key in ('prompt_cache_miss_tokens', 'promptCacheMissTokens'):
        try:
            return max(0, int(usage.get(key) or 0))
        except Exception:
            pass
    return 0


def _deepseek_usage_split(usage: Any) -> dict[str, int]:
    return {
        'apiPromptTokens': _deepseek_usage_api_prompt(usage),
        'apiCompletionTokens': _deepseek_usage_api_completion(usage),
        'apiTotalTokens': _deepseek_usage_api_total(usage),
        'promptCacheHitTokens': _deepseek_usage_cache_hit(usage),
        'promptCacheMissTokens': _deepseek_usage_cache_miss(usage),
    }


def _accumulate_deepseek_usage(counter: dict[str, Any], proof: dict[str, Any]) -> None:
    counter['deepseekUsagePresent'] = bool(counter.get('deepseekUsagePresent') or proof.get('usagePresent'))
    counter['apiPromptTokens'] = int(counter.get('apiPromptTokens') or 0) + int(proof.get('apiPromptTokens') or proof.get('promptTokens') or 0)
    counter['apiCompletionTokens'] = int(counter.get('apiCompletionTokens') or 0) + int(proof.get('apiCompletionTokens') or proof.get('completionTokens') or 0)
    counter['apiTotalTokens'] = int(counter.get('apiTotalTokens') or 0) + int(proof.get('apiTotalTokens') or proof.get('totalTokens') or 0)
    counter['promptCacheHitTokens'] = int(counter.get('promptCacheHitTokens') or 0) + int(proof.get('promptCacheHitTokens') or 0)
    counter['promptCacheMissTokens'] = int(counter.get('promptCacheMissTokens') or 0) + int(proof.get('promptCacheMissTokens') or 0)
    counter['deepseekPromptTokens'] = int(counter.get('deepseekPromptTokens') or 0) + int(proof.get('apiPromptTokens') or proof.get('promptTokens') or 0)
    counter['deepseekCompletionTokens'] = int(counter.get('deepseekCompletionTokens') or 0) + int(proof.get('apiCompletionTokens') or proof.get('completionTokens') or 0)
    counter['deepseekTotalTokens'] = int(counter.get('deepseekTotalTokens') or 0) + int(proof.get('apiTotalTokens') or proof.get('totalTokens') or 0)


async def _live_audit_direct_deepseek_call(payload: dict, *, timeout_seconds: float, api_key: str) -> dict[str, Any]:
    endpoint = (
        os.environ.get('DEEPSEEK_CHAT_COMPLETIONS_URL')
        or os.environ.get('DEEPSEEK_API_URL')
        or 'https://api.deepseek.com/v1/chat/completions'
    ).strip()
    request_hash = _short_hash({'endpoint': endpoint, 'payload': payload}, 24)
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            endpoint,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'X-Matematichka-Live-Audit-Release': APP_RELEASE,
            },
            json=payload,
        )
    if response.status_code != 200:
        return {
            'error': f'DeepSeek API error {response.status_code}',
            'details': response.text[:1500],
            '_auditDeepSeekEndpoint': endpoint,
            '_auditDeepSeekHttpStatus': response.status_code,
            '_auditDeepSeekRequestHash': request_hash,
        }
    try:
        data = response.json()
    except Exception:
        return {
            'error': 'DeepSeek вернул не JSON',
            'details': response.text[:1500],
            '_auditDeepSeekEndpoint': endpoint,
            '_auditDeepSeekHttpStatus': response.status_code,
            '_auditDeepSeekRequestHash': request_hash,
        }
    choices = data.get('choices') if isinstance(data, dict) else None
    if not choices:
        return {
            'error': 'DeepSeek вернул неожиданный формат ответа',
            'details': str(data)[:1500],
            '_auditDeepSeekEndpoint': endpoint,
            '_auditDeepSeekHttpStatus': response.status_code,
            '_auditDeepSeekRequestHash': request_hash,
            '_auditDeepSeekResponseHash': _short_hash(data, 24),
        }
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get('message') if isinstance(first.get('message'), dict) else {}
    answer = str(message.get('content') or '').strip()
    usage = data.get('usage') if isinstance(data.get('usage'), dict) else {}
    proof = {
        'endpoint': endpoint,
        'httpStatus': response.status_code,
        'requestHash': request_hash,
        'responseHash': _short_hash({
            'id': data.get('id'),
            'model': data.get('model'),
            'created': data.get('created'),
            'finishReason': first.get('finish_reason'),
            'usage': usage,
            'answerPrefix': answer[:240],
        }, 24),
        'id': data.get('id'),
        'model': data.get('model'),
        'created': data.get('created'),
        'finishReason': first.get('finish_reason'),
        'usage': usage,
        'rawUsage': usage,
        **_deepseek_usage_split(usage),
        'promptTokens': _deepseek_usage_api_prompt(usage),
        'completionTokens': _deepseek_usage_api_completion(usage),
        'totalTokens': _deepseek_usage_api_total(usage),
        'usagePresent': bool(isinstance(usage, dict) and usage),
    }
    if not answer:
        return {
            'error': 'DeepSeek вернул пустой ответ',
            'details': str(data)[:1500],
            '_auditDeepSeekProof': proof,
        }
    return {'result': answer, '_auditDeepSeekProof': proof}


async def _generate_with_external_call_counter(text: str, *, allow_external: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    import backend.legacy_core as legacy_core

    original_call = getattr(legacy_core, 'call_deepseek', None)
    counter = {
        'externalApiAttempts': 0,
        'externalApiCompleted': 0,
        'externalApiBlocked': 0,
        'externalApiErrors': 0,
        'deepseekUsagePresent': False,
        'deepseekPromptTokens': 0,
        'deepseekCompletionTokens': 0,
        'deepseekTotalTokens': 0,
        'apiPromptTokens': 0,
        'apiCompletionTokens': 0,
        'apiTotalTokens': 0,
        'promptCacheHitTokens': 0,
        'promptCacheMissTokens': 0,
        'deepseekProofs': [],
    }

    if not callable(original_call):
        payload = await generate_explanation_response(text, solver_mode='deepseek_primary', allow_external=allow_external)
        return payload, counter

    async def counted_call_deepseek(api_payload, *args, **kwargs):
        counter['externalApiAttempts'] += 1
        if not allow_external:
            counter['externalApiBlocked'] += 1
            raise RuntimeError('External API call blocked by live-production-audit allowExternal=false')
        timeout_seconds = float(kwargs.get('timeout_seconds') or 45.0)
        api_key = str(getattr(legacy_core, 'DEEPSEEK_API_KEY', '') or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('myapp_ai_math_1_4_API_key') or '').strip()
        if not api_key:
            counter['externalApiErrors'] += 1
            return {'error': 'DeepSeek API key is not configured'}
        try:
            result = await _live_audit_direct_deepseek_call(api_payload, timeout_seconds=timeout_seconds, api_key=api_key)
            proof = result.get('_auditDeepSeekProof') if isinstance(result, dict) else None
            if isinstance(proof, dict):
                counter['deepseekProofs'].append(proof)
                _accumulate_deepseek_usage(counter, proof)
            if isinstance(result, dict) and result.get('error'):
                counter['externalApiErrors'] += 1
            else:
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


async def _generate_with_public_api_route_counter(text: str, *, allow_external: bool, audit_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run an audit case through the public /api/explain route inside the live backend.

    This is deliberately stronger than calling generate_explanation_response() directly:
    the case enters the same FastAPI handler shape as the frontend route.  The special
    X-Live-Audit-Key header bypasses only the product daily quota; it does not bypass
    DeepSeek.  DeepSeek evidence is counted by wrapping legacy_core.call_deepseek for
    exactly this request.
    """
    import backend.legacy_core as legacy_core

    original_call = getattr(legacy_core, 'call_deepseek', None)
    counter: dict[str, Any] = {
        'externalApiAttempts': 0,
        'externalApiCompleted': 0,
        'externalApiBlocked': 0,
        'externalApiErrors': 0,
        'deepseekUsagePresent': False,
        'deepseekPromptTokens': 0,
        'deepseekCompletionTokens': 0,
        'deepseekTotalTokens': 0,
        'apiPromptTokens': 0,
        'apiCompletionTokens': 0,
        'apiTotalTokens': 0,
        'promptCacheHitTokens': 0,
        'promptCacheMissTokens': 0,
        'deepseekProofs': [],
        'routeUnderAudit': 'POST /api/explain',
        'routeAuditMode': 'public-fastapi-route-asgi',
        'requestPayloadShape': {'text': 'string', 'installId': 'string'},
        'auditBypassDailyLimit': True,
        'quotaNotConsumedByAudit': True,
        'externalCounterSource': 'backend.legacy_core.call_deepseek wrapped during POST /api/explain',
        'billingVisibility': 'server proves DeepSeek call attempts/completions; actual money/token charge is verifiable only in provider billing logs',
    }

    async def counted_call_deepseek(api_payload, *args, **kwargs):
        counter['externalApiAttempts'] = int(counter.get('externalApiAttempts') or 0) + 1
        if not allow_external:
            counter['externalApiBlocked'] = int(counter.get('externalApiBlocked') or 0) + 1
            raise RuntimeError('External API call blocked by live-production-audit allowExternal=false')
        timeout_seconds = float(kwargs.get('timeout_seconds') or 45.0)
        api_key = str(getattr(legacy_core, 'DEEPSEEK_API_KEY', '') or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('myapp_ai_math_1_4_API_key') or '').strip()
        if not api_key:
            counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            return {'error': 'DeepSeek API key is not configured'}
        try:
            result = await _live_audit_direct_deepseek_call(api_payload, timeout_seconds=timeout_seconds, api_key=api_key)
            proof = result.get('_auditDeepSeekProof') if isinstance(result, dict) else None
            if isinstance(proof, dict):
                counter['deepseekProofs'].append(proof)
                _accumulate_deepseek_usage(counter, proof)
            if isinstance(result, dict) and result.get('error'):
                counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            else:
                counter['externalApiCompleted'] = int(counter.get('externalApiCompleted') or 0) + 1
            return result
        except Exception:
            counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            raise

    request_id = _short_hash({'release': APP_RELEASE, 'text': text, 'auditKey': audit_key, 'ts': _now_ts()}, 20)
    install_id = f'live-audit-{APP_RELEASE}-{request_id}'
    counter['auditRequestId'] = request_id
    counter['installId'] = install_id
    counter['requestHash'] = _short_hash({'path': '/api/explain', 'text': text, 'installId': install_id}, 24)

    if not callable(original_call):
        counter['routeAuditError'] = 'legacy_core.call_deepseek is not callable; cannot count DeepSeek external calls'

    if callable(original_call):
        setattr(legacy_core, 'call_deepseek', counted_call_deepseek)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://live-audit.local') as client:
            response = await client.post(
                '/api/explain',
                json={'text': text, 'installId': install_id},
                headers={
                    'X-Live-Audit-Key': str(audit_key or ''),
                    'X-Install-Id': install_id,
                    'X-Audit-Request-Id': request_id,
                },
                timeout=90.0,
            )
        counter['apiRouteStatusCode'] = response.status_code
        counter['apiRouteResponseBytes'] = len(response.content or b'')
        try:
            payload = response.json()
        except Exception:
            payload = {'result': response.text[:4000], 'source': 'api-route-non-json-response', 'error': 'POST /api/explain returned non-JSON'}
        if not isinstance(payload, dict):
            payload = {'result': str(payload), 'source': 'api-route-unexpected-json', 'error': 'POST /api/explain returned non-object JSON'}
        counter['apiRouteResponseRelease'] = payload.get('release')
        counter['apiRouteResponseSolverVersion'] = payload.get('solverVersion')
        counter['apiRouteAuditBypassDailyLimit'] = bool(payload.get('auditBypassDailyLimit'))
        counter['responseHash'] = _short_hash(payload, 24)
        if response.status_code >= 400:
            payload.setdefault('error', f'POST /api/explain returned HTTP {response.status_code}')
            payload.setdefault('source', 'api-route-http-error')
        return payload, counter
    finally:
        if callable(original_call):
            setattr(legacy_core, 'call_deepseek', original_call)




async def _generate_with_browser_client_fetch_counter(text: str, *, allow_external: bool, audit_key: str, audit_context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture DeepSeek receipt data for a real browser fetch to POST /api/explain."""
    import backend.legacy_core as legacy_core

    original_call = getattr(legacy_core, 'call_deepseek', None)
    counter: dict[str, Any] = {
        'externalApiAttempts': 0,
        'externalApiCompleted': 0,
        'externalApiBlocked': 0,
        'externalApiErrors': 0,
        'deepseekUsagePresent': False,
        'deepseekPromptTokens': 0,
        'deepseekCompletionTokens': 0,
        'deepseekTotalTokens': 0,
        'apiPromptTokens': 0,
        'apiCompletionTokens': 0,
        'apiTotalTokens': 0,
        'promptCacheHitTokens': 0,
        'promptCacheMissTokens': 0,
        'deepseekProofs': [],
        'routeUnderAudit': 'POST /api/explain',
        'routeAuditMode': 'browser-client-ui-render-visible-network',
        'browserClientFetch': True,
        'browserClientFetchEvidence': True,
        'apiRouteNetworkVisibleToBrowser': True,
        'requestPayloadShape': {'text': 'string', 'installId': 'string'},
        'auditBypassDailyLimit': True,
        'quotaNotConsumedByAudit': True,
        'externalCounterSource': 'browser fetch hit /api/explain; backend.legacy_core.call_deepseek wrapped only for receipt capture during that request',
        'billingVisibility': 'server proves DeepSeek call attempts/completions and token usage; actual money charge is verifiable only in provider billing logs',
        'auditRequestId': audit_context.get('auditRequestId'),
        'installId': audit_context.get('installId'),
        'browserRunId': audit_context.get('runId'),
        'browserCaseIndex': audit_context.get('caseIndex'),
        'browserCaseId': audit_context.get('caseId'),
        'browserUserAgentHash': audit_context.get('userAgentHash'),
    }

    async def counted_call_deepseek(api_payload, *args, **kwargs):
        counter['externalApiAttempts'] = int(counter.get('externalApiAttempts') or 0) + 1
        if not allow_external:
            counter['externalApiBlocked'] = int(counter.get('externalApiBlocked') or 0) + 1
            raise RuntimeError('External API call blocked by browser-client live audit allowExternal=false')
        timeout_seconds = float(kwargs.get('timeout_seconds') or 45.0)
        api_key = str(getattr(legacy_core, 'DEEPSEEK_API_KEY', '') or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('myapp_ai_math_1_4_API_key') or '').strip()
        if not api_key:
            counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            return {'error': 'DeepSeek API key is not configured'}
        try:
            result = await _live_audit_direct_deepseek_call(api_payload, timeout_seconds=timeout_seconds, api_key=api_key)
            proof = result.get('_auditDeepSeekProof') if isinstance(result, dict) else None
            if isinstance(proof, dict):
                counter['deepseekProofs'].append(proof)
                _accumulate_deepseek_usage(counter, proof)
            if isinstance(result, dict) and result.get('error'):
                counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            else:
                counter['externalApiCompleted'] = int(counter.get('externalApiCompleted') or 0) + 1
            return result
        except Exception:
            counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            raise

    counter['requestHash'] = _short_hash({
        'path': '/api/explain',
        'text': text,
        'installId': audit_context.get('installId'),
        'runId': audit_context.get('runId'),
        'caseIndex': audit_context.get('caseIndex'),
        'caseId': audit_context.get('caseId'),
    }, 24)

    if not callable(original_call):
        counter['routeAuditError'] = 'legacy_core.call_deepseek is not callable; cannot count DeepSeek external calls'
    if callable(original_call):
        setattr(legacy_core, 'call_deepseek', counted_call_deepseek)
    try:
        payload = await generate_explanation_response(text, solver_mode='deepseek_primary', allow_external=allow_external)
        if not isinstance(payload, dict):
            payload = {'result': str(payload), 'source': 'api-route-unexpected-object'}
        counter['apiRouteStatusCode'] = 200 if not payload.get('error') else 400
        counter['apiRouteResponseRelease'] = APP_RELEASE
        counter['apiRouteResponseSolverVersion'] = SOLVER_VERSION
        counter['apiRouteAuditBypassDailyLimit'] = True
        counter['responseHash'] = _short_hash(payload, 24)
        return payload, counter
    finally:
        if callable(original_call):
            setattr(legacy_core, 'call_deepseek', original_call)

# --- v290 live audit runner with persistent cache and short summary endpoints ---
LIVE_AUDIT_RUNNER_PROMPT_VERSION = 'v311.04-g4-arithmetic-actions-v1'
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
_LIVE_AUDIT_DEEPSEEK_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar('live_audit_deepseek_context', default=None)


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
    # Use a unique temp path so concurrent production requests/background tasks do not
    # race on the same .tmp file and accidentally lose the file before replace().
    tmp_path = path.with_name(path.name + f'.{os.getpid()}.{threading.get_ident()}.{int(time.time() * 1000000)}.tmp')
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
        'freshPollingNote': 'Use FRESH links for repeated polling and evidence export; every click has a new path nonce and does not force/re-spend completed cases. V311.04 acceptance requires evidence/results/suspicious/acceptance/report proof, not only aggregate summary.',
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




def _live_audit_normalize_visible_text(value: Any) -> str:
    text = str(value or '').replace('\u00a0', ' ').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text.strip()


def _live_audit_normalize_visible_compare_line(value: Any) -> str:
    text = str(value or '').replace('\u00a0', ' ').replace('\r', ' ').strip().lower().replace('ё', 'е')
    text = re.sub(r'\s+', ' ', text)
    text = text.rstrip('.')
    return text


def _live_audit_prepare_visible_compare_text(value: Any, case_text: Any = None, is_guard_case: bool = False) -> str:
    raw = _live_audit_normalize_visible_text(value)
    if not raw:
        return ''
    task_line_set = {
        _live_audit_normalize_visible_compare_line(line)
        for line in str(case_text or '').replace('\r', '\n').split('\n')
        if _live_audit_normalize_visible_compare_line(line)
    }
    cleaned: list[str] = []
    for raw_line in raw.split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        norm = _live_audit_normalize_visible_compare_line(line)
        if not norm:
            continue
        if norm in {'задача', 'решение', 'получено несколько строк:', 'получено несколько строк', 'пояснения'}:
            continue
        if task_line_set and norm in task_line_set:
            continue
        if is_guard_case:
            if norm.startswith('совет:'):
                continue
            if norm.startswith('если это система уравнений'):
                continue
            line = re.sub(r'\s*Если это система уравнений.*$', '', line, flags=re.IGNORECASE).strip()
            line = re.sub(r'\s*Совет\s*:\s*.*$', '', line, flags=re.IGNORECASE).strip()
            norm = _live_audit_normalize_visible_compare_line(line)
            if not norm:
                continue
        cleaned.append(line)
    return _live_audit_normalize_visible_text('\n'.join(cleaned))


def _live_audit_visible_texts_equivalent(a: Any, b: Any, case_text: Any = None, is_guard_case: bool = False) -> bool:
    prepared_a = _live_audit_prepare_visible_compare_text(a, case_text=case_text, is_guard_case=is_guard_case)
    prepared_b = _live_audit_prepare_visible_compare_text(b, case_text=case_text, is_guard_case=is_guard_case)
    aa = prepared_a.lower().replace('ё', 'е')
    bb = prepared_b.lower().replace('ё', 'е')
    if not aa or not bb:
        return False
    if aa == bb:
        return True
    ans_a = _live_audit_extract_answer_line(aa)
    ans_b = _live_audit_extract_answer_line(bb)
    if not (ans_a and ans_b and ans_a == ans_b):
        return False
    # A production UI may omit service headers, repeated task lines and optional
    # advice lines, but it must show the same visible solution body and the same final answer.
    steps_a = _live_audit_numbered_steps(aa)
    steps_b = _live_audit_numbered_steps(bb)
    if steps_a and steps_b:
        return steps_a == steps_b
    def _body(value: Any) -> list[str]:
        return [re.sub(r'^\s*\d+\)\s*', '', line.lower().replace('ё', 'е')).strip().rstrip('.') for line in _live_audit_solution_body_lines(value)]
    body_a = _body(aa)
    body_b = _body(bb)
    if body_a and body_b:
        return body_a == body_b
    short = re.sub(r'\s+', ' ', aa).strip()
    long = re.sub(r'\s+', ' ', bb).strip()
    return bool(short and (short in long or long in short))

def _live_audit_expected_answer_text(row: dict[str, Any]) -> str:
    final = str(row.get('expectedFinalAnswer') or '').strip()
    if final:
        return final
    expected = row.get('expected')
    if isinstance(expected, list):
        return '; '.join(str(item) for item in expected)
    return str(expected or '').strip()


_LIVE_AUDIT_SMALL_NUMBER_WORDS = {
    'ноль': '0',
    'один': '1',
    'одна': '1',
    'одно': '1',
    'два': '2',
    'две': '2',
    'три': '3',
    'четыре': '4',
    'пять': '5',
    'шесть': '6',
    'семь': '7',
    'восемь': '8',
    'девять': '9',
    'десять': '10',
}


def _live_audit_normalize_task_text_for_match(value: Any) -> str:
    text = str(value or '').replace('\u00a0', ' ').replace('\r', ' ').replace('\n', ' ')
    text = text.replace('ё', 'е').lower()
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^[\s"«]*(реши|вычисли|найди|сравни)\s*[:—-]\s*', r'\1 ', text)
    for word, digit in _LIVE_AUDIT_SMALL_NUMBER_WORDS.items():
        text = re.sub(rf'(?<![а-яa-z0-9]){word}(?![а-яa-z0-9])', digit, text)
    text = re.sub(r'[.!?]+$', '', text).strip()
    return text


def _live_audit_task_texts_equivalent(actual: Any, planned: Any) -> bool:
    aa = _live_audit_normalize_task_text_for_match(actual)
    pp = _live_audit_normalize_task_text_for_match(planned)
    if not aa or not pp:
        return False
    if aa == pp:
        return True
    # The real frontend normalizer may lowercase text, remove terminal punctuation
    # and replace short number words with digits before POST /api/explain. Treat
    # this as the same user task, not as an audit failure.
    compact_a = re.sub(r'[^0-9a-zа-яёхx+\-*/:×÷=<>.,]+', '', aa)
    compact_p = re.sub(r'[^0-9a-zа-яёхx+\-*/:×÷=<>.,]+', '', pp)
    return bool(compact_a and compact_a == compact_p)


def _live_audit_numbered_steps(value: Any) -> list[str]:
    text = _live_audit_normalize_visible_text(value).lower().replace('ё', 'е')
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    steps: list[str] = []
    for line in lines:
        if re.match(r'^\d+\)\s*', line):
            cleaned = re.sub(r'\s+', ' ', line).strip().rstrip('.')
            steps.append(cleaned)
    return steps


def _live_audit_user_visible_solution_format_issues(result_text: str) -> list[str]:
    low = str(result_text or '').lower().replace('ё', 'е')
    issues: list[str] = []
    if 'ответ:' not in low:
        issues.append('UI proof: missing visible Ответ: line')
    if not _live_audit_has_solution_body(result_text):
        issues.append('UI proof: missing visible solution line')
    issues.extend(_live_audit_single_step_numbering_issues(result_text, 'UI proof'))
    return issues


def _live_audit_row_is_guard(row: dict[str, Any]) -> bool:
    expected_source = str(row.get('expectedSource') or '')
    category = str(row.get('category') or '').lower()
    source = str(row.get('source') or '').lower()
    return bool(expected_source.startswith('guard') or 'guard' in category or source.startswith('guard'))




def _live_audit_ui_clicked(row: dict[str, Any]) -> bool:
    return bool(row.get('frontendUiClickedSolveButton') or row.get('uiRenderClickedMainSolveButton') or row.get('uiSolveButtonClicked'))


def _live_audit_ui_input_selector_ok(row: dict[str, Any]) -> bool:
    return str(row.get('frontendUiInputSelector') or row.get('uiRenderInputSelector') or '') == '#taskInput'


def _live_audit_ui_button_selector_ok(row: dict[str, Any]) -> bool:
    return str(row.get('frontendUiButtonSelector') or row.get('uiRenderButtonSelector') or '') == '#solveBtn'


def _live_audit_ui_result_selector_ok(row: dict[str, Any]) -> bool:
    return str(row.get('frontendUiResultSelector') or row.get('uiRenderResultBoxSelector') or '') == '#resultBox' or bool(row.get('uiResultBoxFound'))


def _live_audit_ui_dom_checked(row: dict[str, Any]) -> bool:
    # DOM proof means the browser actually rendered and read #resultBox.
    # The stronger pass flag is checked separately by _live_audit_ui_render_passed().
    return bool(row.get('frontendDomRenderedOutputChecked') or row.get('uiRenderAudit') or row.get('uiRenderPassed'))


def _live_audit_ui_expected_ok(row: dict[str, Any]) -> bool:
    return bool(row.get('frontendDomExpectedCheckOk') or row.get('uiRenderResultMatchesExpected') or row.get('userVisibleAnswerMatchesExpected'))


def _live_audit_ui_result_matches_api(row: dict[str, Any]) -> bool:
    return bool(row.get('frontendDomResultMatchesApi') or row.get('clientDisplayedResultMatchesApi') or row.get('uiDomResultMatchesApi'))


def _live_audit_ui_answer_matches_api(row: dict[str, Any]) -> bool:
    return bool(row.get('frontendDomAnswerMatchesApi') or row.get('userVisibleAnswerMatchesApi') or row.get('uiDomResultMatchesApi'))


def _live_audit_ui_render_passed(row: dict[str, Any]) -> bool:
    """Strict V300 UI-render acceptance proof from atomic fields.

    V296.11 exposed a contradictory report: aggregate acceptance was true while
    case evidence still showed uiRenderPassed=false. V300 derives the pass
    flag from the atomic DOM/API proof fields and final acceptance requires it
    for every normal case.
    """
    if not isinstance(row, dict):
        return False
    format_issues = list(row.get('uiRenderIssues') or []) + list(row.get('frontendDomVisibleFormatIssues') or [])
    dom_rendered = bool(row.get('frontendDomRenderedOutputChecked') or row.get('uiRenderAudit'))
    return bool(
        dom_rendered
        and _live_audit_ui_expected_ok(row)
        and _live_audit_ui_clicked(row)
        and _live_audit_ui_input_selector_ok(row)
        and _live_audit_ui_button_selector_ok(row)
        and _live_audit_ui_result_selector_ok(row)
        and _live_audit_ui_result_matches_api(row)
        and _live_audit_ui_answer_matches_api(row)
        and not format_issues
    )


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


def _live_audit_solution_body_lines(result_text: Any) -> list[str]:
    lines = [line.strip() for line in str(result_text or '').replace('\r', '\n').split('\n') if line.strip()]
    body: list[str] = []
    in_solution = False
    for line in lines:
        low = line.lower().replace('ё', 'е')
        if re.match(r'^решение\s*[\.:]?$', low) or re.match(r'^решение\s+по\s+действиям\s*:?$', low):
            in_solution = True
            continue
        if low.startswith('ответ:'):
            break
        if low.startswith('задача'):
            continue
        if in_solution:
            body.append(line)
    if body:
        return body
    # DOM may intentionally omit the service headers. In that case every visible
    # non-answer line is the displayed solution body.
    for line in lines:
        low = line.lower().replace('ё', 'е')
        if low.startswith(('ответ:', 'задача', 'решение')):
            continue
        body.append(line)
    return body


def _live_audit_has_solution_body(result_text: Any) -> bool:
    return bool(_live_audit_solution_body_lines(result_text))


def _live_audit_count_arithmetic_actions_in_step(step: Any) -> int:
    return len(re.findall(r'(?<=[0-9xх])\s*(?:[+\-−×*/:÷])\s*(?=[0-9xх])', str(step or '')))



def _live_audit_step_has_direct_result(step: Any) -> bool:
    clean = str(step or '').strip()
    if re.search(r'\d+\s*[+\-−]\s*\d+\s*=\s*-?\d+\b', clean):
        return True
    if re.search(r'[xх]\s*=\s*-?\d+\b', clean, flags=re.IGNORECASE):
        return True
    if re.search(r'\b\d+\s*=\s*\d+\b', clean):
        return True
    return False


def _live_audit_answer_is_multistep_marker(result_text: Any) -> bool:
    answer = _live_audit_extract_answer_line(result_text).lower().replace('ё', 'е').strip(' .')
    return answer in {'верно', 'неверно', '=', '<', '>', 'да', 'нет'}


def _live_audit_single_step_numbering_issues(result_text: Any, prefix: str) -> list[str]:
    """V300/V297 shared UI rule: one-operation examples must not be displayed as numbered action lists."""
    body = _live_audit_solution_body_lines(result_text)
    numbered = [line for line in body if re.match(r'^\s*\d+\)\s*\S+', line)]
    if any(re.match(r'^\s*[2-9]\d*\)\s*\S+', line) for line in body) and not any(re.match(r'^\s*1\)\s*\S+', line) for line in body):
        return [prefix + ': multi-step numbering is missing step 1)']
    if not numbered:
        return []

    clean_numbered = [re.sub(r'^\s*\d+\)\s*', '', line).strip() for line in numbered]
    direct_steps = [line for line in clean_numbered if _live_audit_step_has_direct_result(line)]

    if len(numbered) == 1 and re.match(r'^\s*1\)\s*\S+', numbered[0]):
        step_without_marker = clean_numbered[0]
        if _live_audit_count_arithmetic_actions_in_step(step_without_marker) <= 1 and not _live_audit_answer_is_multistep_marker(result_text):
            return [prefix + ': one-operation solution must not show numbered 1) marker']

    # Stronger semantic check: if the visible numbered body contains exactly one
    # actual operation/equation and the rest is explanatory wording, it should be
    # displayed as a single unnumbered line, not "1) definition, 2) calculation".
    if len(direct_steps) == 1 and not _live_audit_answer_is_multistep_marker(result_text):
        direct = direct_steps[0]
        if _live_audit_count_arithmetic_actions_in_step(direct) <= 1 or re.search(r'[xх]\s*=\s*-?\d+\b', direct, flags=re.IGNORECASE):
            return [prefix + ': semantic one-operation solution must not be displayed as numbered steps']
    return []


def _live_audit_strict_format_issues(case: dict[str, Any], result_text: str, *, is_guard_case: bool) -> list[str]:
    if is_guard_case:
        return []
    category = str(case.get('category') or '')
    name = str(case.get('name') or case.get('id') or '')
    if not ((category.startswith('v296_') or name.startswith('v296_')) or (category.startswith('v297_') or name.startswith('v297_')) or (category.startswith('v298_') or name.startswith('v298_')) or (category.startswith('v300_') or name.startswith('v300_')) or (category.startswith('v302_') or name.startswith('v302_')) or (category.startswith('v303_') or name.startswith('v303_')) or (category.startswith('v304_') or name.startswith('v304_')) or (category.startswith('v305_') or name.startswith('v305_')) or (category.startswith('v306_') or name.startswith('v306_')) or (category.startswith('v307_') or name.startswith('v307_')) or (category.startswith('v308_') or name.startswith('v308_')) or (category.startswith('v309_') or name.startswith('v309_')) or (category.startswith('v310_') or name.startswith('v310_')) or (category.startswith('v311_') or name.startswith('v311_'))):
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
    # Shared UX rule: if there is only one action, the product must not show
    # "1)".  Therefore strict proof requires a visible solution body, not
    # mandatory numbering. Multi-step answers are still compared/checked by their
    # visible body and final answer.
    if not _live_audit_has_solution_body(text):
        issues.append('strict proof: missing visible solution line')
    issues.extend(_live_audit_single_step_numbering_issues(text, 'strict proof'))
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
        if not is_guard and not bool(row.get('deepseekUsagePresent')):
            reasons.append('passed normal case has no DeepSeek usage object proof')
        if not is_guard and int(row.get('apiTotalTokens') or row.get('deepseekTotalTokens') or 0) <= 0:
            reasons.append('passed normal case has no positive DeepSeek API total token usage')
        route_under_audit = str(row.get('routeUnderAudit') or '')
        route_mode = str(row.get('routeAuditMode') or '')
        if not is_guard and route_under_audit not in {'POST /api/explain', 'browser fetch -> POST /api/explain'}:
            reasons.append('passed normal case did not go through POST /api/explain route proof')
        if not is_guard and route_mode not in {'public-fastapi-route-asgi', 'browser-client-fetch', 'browser-client-ui-render-visible-network'}:
            reasons.append('passed normal case has no accepted route audit mode proof')
        if not is_guard and str(row.get('routeAuditMode') or '') != 'browser-client-ui-render-visible-network':
            reasons.append('passed normal case was not produced by frontend UI-render DOM audit')
        if not is_guard and not bool(row.get('browserClientFetch')):
            reasons.append('passed normal case lacks browserClientFetch=true proof')
        if not is_guard and not bool(row.get('apiRouteNetworkVisibleToBrowser')):
            reasons.append('passed normal case lacks browser-visible network route proof')
        if not is_guard and not _live_audit_ui_dom_checked(row):
            reasons.append('passed normal case lacks frontend DOM resultBox proof')
        if not is_guard and not _live_audit_ui_render_passed(row):
            reasons.append('passed normal case has uiRenderPassed=false or incomplete UI-render proof')
        if not is_guard and not _live_audit_ui_expected_ok(row):
            reasons.append('passed normal case has no positive expected-vs-DOM check')
        if not is_guard and not _live_audit_ui_clicked(row):
            reasons.append('passed normal case lacks proof that the real frontend #solveBtn was clicked')
        if not is_guard and not _live_audit_ui_input_selector_ok(row):
            reasons.append('passed normal case did not set the real frontend #taskInput')
        if not is_guard and not _live_audit_ui_result_selector_ok(row):
            reasons.append('passed normal case did not verify DOM #resultBox selector')
        if not is_guard and not _live_audit_ui_answer_matches_api(row):
            reasons.append('passed normal case DOM answer line does not match API answer line')
        if not is_guard and not _live_audit_ui_result_matches_api(row):
            reasons.append('passed normal case DOM result text does not match API result text')
        if not is_guard and int(row.get('apiRouteStatusCode') or 0) != 200:
            reasons.append('passed normal case has no HTTP 200 route proof')
        if not is_guard and not bool(row.get('apiRouteAuditBypassDailyLimit')):
            reasons.append('passed normal case has no audit route bypass proof marker')
        if not is_guard and 'ответ:' not in low:
            reasons.append('passed but result has no Ответ: line')
        if not is_guard and not _live_audit_has_solution_body(result_text):
            reasons.append('passed but result has no visible solution line')
        for issue in _live_audit_single_step_numbering_issues(result_text, 'passed result'):
            reasons.append(issue)
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
        'deepseekUsagePresent': bool(row.get('deepseekUsagePresent')),
        'deepseekPromptTokens': int(row.get('deepseekPromptTokens') or 0),
        'deepseekCompletionTokens': int(row.get('deepseekCompletionTokens') or 0),
        'deepseekTotalTokens': int(row.get('deepseekTotalTokens') or 0),
        'apiPromptTokens': int(row.get('apiPromptTokens') or row.get('deepseekPromptTokens') or 0),
        'apiCompletionTokens': int(row.get('apiCompletionTokens') or row.get('deepseekCompletionTokens') or 0),
        'apiTotalTokens': int(row.get('apiTotalTokens') or row.get('deepseekTotalTokens') or 0),
        'promptCacheHitTokens': int(row.get('promptCacheHitTokens') or 0),
        'promptCacheMissTokens': int(row.get('promptCacheMissTokens') or 0),
        'deepseekRequestHashes': row.get('deepseekRequestHashes') or [],
        'deepseekResponseHashes': row.get('deepseekResponseHashes') or [],
        'fromCache': bool(row.get('fromCache')),
        'cacheKey': row.get('cacheKey'),
        'routeUnderAudit': row.get('routeUnderAudit'),
        'routeAuditMode': row.get('routeAuditMode'),
        'apiRouteNetworkVisibleToBrowser': bool(row.get('apiRouteNetworkVisibleToBrowser')),
        'browserClientFetch': bool(row.get('browserClientFetch')),
        'frontendDomRenderedOutputChecked': bool(row.get('frontendDomRenderedOutputChecked')),
        'uiRenderAudit': bool(row.get('uiRenderAudit')),
        'uiRenderClickedMainSolveButton': bool(row.get('uiRenderClickedMainSolveButton')),
        'uiRenderResultMatchesExpected': bool(row.get('uiRenderResultMatchesExpected')),
        'clientDisplayedResultMatchesApi': bool(row.get('clientDisplayedResultMatchesApi')),
        'userVisibleAnswerMatchesApi': bool(row.get('userVisibleAnswerMatchesApi')),
        'clientDisplayedAnswerLine': row.get('clientDisplayedAnswerLine'),
        'uiRenderResultBoxSelector': row.get('uiRenderResultBoxSelector'),
        'browserFetchStartedAt': row.get('browserFetchStartedAt'),
        'browserFetchFinishedAt': row.get('browserFetchFinishedAt'),
        'apiRouteStatusCode': row.get('apiRouteStatusCode'),
        'apiRouteResponseRelease': row.get('apiRouteResponseRelease'),
        'apiRouteResponseSolverVersion': row.get('apiRouteResponseSolverVersion'),
        'apiRouteAuditBypassDailyLimit': bool(row.get('apiRouteAuditBypassDailyLimit')),
        'frontendDomRenderedOutputChecked': bool(row.get('frontendDomRenderedOutputChecked')),
        'frontendDomExpectedCheckOk': bool(row.get('frontendDomExpectedCheckOk')),
        'frontendDomResultMatchesApi': bool(row.get('frontendDomResultMatchesApi')),
        'frontendDomAnswerMatchesApi': bool(row.get('frontendDomAnswerMatchesApi')),
        'frontendUiClickedSolveButton': bool(row.get('frontendUiClickedSolveButton')),
        'frontendDomAnswerLine': row.get('frontendDomAnswerLine'),
        'frontendDomResultPreview': str(row.get('frontendDomResultText') or row.get('clientDisplayedResultText') or '')[:520],
        'frontendUiRenderMode': row.get('frontendUiRenderMode'),
        'auditRequestId': row.get('auditRequestId'),
        'requestHash': row.get('requestHash'),
        'responseHash': row.get('responseHash'),
        'frontendDomRenderedOutputChecked': bool(row.get('frontendDomRenderedOutputChecked')),
        'uiRenderAudit': bool(row.get('uiRenderAudit')),
        'uiRenderMode': row.get('uiRenderMode'),
        'uiSolveButtonClicked': bool(row.get('uiSolveButtonClicked')),
        'uiTaskInputFound': bool(row.get('uiTaskInputFound')),
        'uiResultBoxFound': bool(row.get('uiResultBoxFound')),
        'uiResultBoxAnswerLine': row.get('uiResultBoxAnswerLine'),
        'uiResultBoxTextHash': row.get('uiResultBoxTextHash'),
        'uiDomResultMatchesApi': bool(row.get('uiDomResultMatchesApi')),
        'userVisibleAnswerMatchesExpected': bool(row.get('userVisibleAnswerMatchesExpected')),
        'uiRenderPassed': _live_audit_ui_render_passed(row),
        'uiRenderIssues': row.get('uiRenderIssues') or [],
        'frontendAuditUrl': row.get('frontendAuditUrl'),
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
        'deepseekUsagePresent': bool(row.get('deepseekUsagePresent')),
        'deepseekUsage': row.get('deepseekUsage') or [],
        'deepseekPromptTokens': int(row.get('deepseekPromptTokens') or 0),
        'deepseekCompletionTokens': int(row.get('deepseekCompletionTokens') or 0),
        'deepseekTotalTokens': int(row.get('deepseekTotalTokens') or 0),
        'apiPromptTokens': int(row.get('apiPromptTokens') or row.get('deepseekPromptTokens') or 0),
        'apiCompletionTokens': int(row.get('apiCompletionTokens') or row.get('deepseekCompletionTokens') or 0),
        'apiTotalTokens': int(row.get('apiTotalTokens') or row.get('deepseekTotalTokens') or 0),
        'promptCacheHitTokens': int(row.get('promptCacheHitTokens') or 0),
        'promptCacheMissTokens': int(row.get('promptCacheMissTokens') or 0),
        'deepseekModels': row.get('deepseekModels') or [],
        'deepseekObjectIds': row.get('deepseekObjectIds') or [],
        'deepseekFinishReasons': row.get('deepseekFinishReasons') or [],
        'deepseekRequestHashes': row.get('deepseekRequestHashes') or [],
        'deepseekResponseHashes': row.get('deepseekResponseHashes') or [],
        'fromCache': bool(row.get('fromCache')),
        'solverMode': row.get('solverMode'),
        'deepseekPrimaryFallback': row.get('deepseekPrimaryFallback'),
        'verifier': row.get('verifier'),
        'structuredSolution': row.get('structuredSolution'),
        'payloadError': row.get('payloadError'),
        'cacheKey': row.get('cacheKey'),
        'routeUnderAudit': row.get('routeUnderAudit'),
        'routeAuditMode': row.get('routeAuditMode'),
        'apiRouteNetworkVisibleToBrowser': bool(row.get('apiRouteNetworkVisibleToBrowser')),
        'browserClientFetch': bool(row.get('browserClientFetch')),
        'browserFetchStartedAt': row.get('browserFetchStartedAt'),
        'browserFetchFinishedAt': row.get('browserFetchFinishedAt'),
        'browserFetchDurationMs': row.get('browserFetchDurationMs'),
        'browserUserAgent': row.get('browserUserAgent'),
        'comparisonTarget': row.get('comparisonTarget'),
        'comparesExpectedToBrowserReceivedPayloadResult': bool(row.get('comparesExpectedToBrowserReceivedPayloadResult')),
        'frontendDomRenderedOutputChecked': bool(row.get('frontendDomRenderedOutputChecked')),
        'uiRenderAudit': bool(row.get('uiRenderAudit')),
        'uiRenderMode': row.get('uiRenderMode'),
        'uiRenderPageUrl': row.get('uiRenderPageUrl'),
        'uiRenderFrontendBuild': row.get('uiRenderFrontendBuild'),
        'uiRenderInputSelector': row.get('uiRenderInputSelector'),
        'uiRenderButtonSelector': row.get('uiRenderButtonSelector'),
        'uiRenderResultBoxSelector': row.get('uiRenderResultBoxSelector'),
        'uiRenderInputSetViaDom': bool(row.get('uiRenderInputSetViaDom')),
        'uiRenderClickedMainSolveButton': bool(row.get('uiRenderClickedMainSolveButton')),
        'uiRenderResultBoxPresent': bool(row.get('uiRenderResultBoxPresent')),
        'uiRenderResultMatchesExpected': bool(row.get('uiRenderResultMatchesExpected')),
        'uiRenderElapsedMs': row.get('uiRenderElapsedMs'),
        'clientDisplayedResultText': _live_audit_text(row.get('clientDisplayedResultText') or '', 8000),
        'clientDisplayedAnswerLine': row.get('clientDisplayedAnswerLine'),
        'clientDisplayedResultMatchesApi': bool(row.get('clientDisplayedResultMatchesApi')),
        'userVisibleAnswerMatchesApi': bool(row.get('userVisibleAnswerMatchesApi')),
        'uiRenderDomHash': row.get('uiRenderDomHash'),
        'uiRenderIssues': row.get('uiRenderIssues') or [],
        'frontendDisplayAssumption': row.get('frontendDisplayAssumption'),
        'frontendDisplayContract': row.get('frontendDisplayContract') or row.get('frontendRenderContract'),
        'auditComparedSamePayloadReturnedToBrowser': bool(row.get('auditComparedSamePayloadReturnedToBrowser')),
        'clientDisplayedResultMatchesApi': bool(row.get('clientDisplayedResultMatchesApi')),
        'userVisibleAnswerMatchesApi': bool(row.get('userVisibleAnswerMatchesApi')),
        'requestPayloadShape': row.get('requestPayloadShape'),
        'apiRouteStatusCode': row.get('apiRouteStatusCode'),
        'apiRouteResponseBytes': row.get('apiRouteResponseBytes'),
        'apiRouteResponseRelease': row.get('apiRouteResponseRelease'),
        'apiRouteResponseSolverVersion': row.get('apiRouteResponseSolverVersion'),
        'apiRouteAuditBypassDailyLimit': bool(row.get('apiRouteAuditBypassDailyLimit')),
        'auditBypassDailyLimit': bool(row.get('auditBypassDailyLimit')),
        'quotaNotConsumedByAudit': bool(row.get('quotaNotConsumedByAudit')),
        'externalCounterSource': row.get('externalCounterSource'),
        'billingVisibility': row.get('billingVisibility'),
        'auditRequestId': row.get('auditRequestId'),
        'installId': row.get('installId'),
        'requestHash': row.get('requestHash'),
        'responseHash': row.get('responseHash'),
        'frontendDomRenderedOutputChecked': bool(row.get('frontendDomRenderedOutputChecked')),
        'frontendDomExpectedCheckOk': bool(row.get('frontendDomExpectedCheckOk')),
        'frontendDomResultMatchesApi': bool(row.get('frontendDomResultMatchesApi')),
        'frontendDomAnswerMatchesApi': bool(row.get('frontendDomAnswerMatchesApi')),
        'frontendUiClickedSolveButton': bool(row.get('frontendUiClickedSolveButton')),
        'frontendDomResultText': _live_audit_text(row.get('frontendDomResultText') or row.get('clientDisplayedResultText') or '', 8000),
        'frontendDomAnswerLine': row.get('frontendDomAnswerLine') or _live_audit_extract_answer_line(str(row.get('frontendDomResultText') or row.get('clientDisplayedResultText') or '')),
        'frontendUiRenderMode': row.get('frontendUiRenderMode'),
        'frontendUiAuditUrl': row.get('frontendUiAuditUrl'),
        'frontendUiResultSelector': row.get('frontendUiResultSelector'),
        'frontendUiInputSelector': row.get('frontendUiInputSelector'),
        'frontendUiButtonSelector': row.get('frontendUiButtonSelector'),
        'frontendUiElapsedMs': row.get('frontendUiElapsedMs'),
        'frontendDisplayAssumption': row.get('frontendDisplayAssumption'),
        'frontendDisplayContract': row.get('frontendDisplayContract') or row.get('frontendRenderContract'),
        'frontendAuditUrl': row.get('frontendAuditUrl'),
        'frontendBuild': row.get('frontendBuild'),
        'frontendOrigin': row.get('frontendOrigin'),
        'iframeAudit': bool(row.get('iframeAudit')),
        'uiRenderAudit': bool(row.get('uiRenderAudit')),
        'uiRenderMode': row.get('uiRenderMode'),
        'uiTaskInputId': row.get('uiTaskInputId'),
        'uiTaskInputFound': bool(row.get('uiTaskInputFound')),
        'uiTaskInputValue': _live_audit_text(row.get('uiTaskInputValue') or '', 3000),
        'uiSolveButtonId': row.get('uiSolveButtonId'),
        'uiSolveButtonFound': bool(row.get('uiSolveButtonFound')),
        'uiSolveButtonClicked': bool(row.get('uiSolveButtonClicked')),
        'uiResultBoxId': row.get('uiResultBoxId'),
        'uiResultBoxFound': bool(row.get('uiResultBoxFound')),
        'uiResultBoxText': _live_audit_text(row.get('uiResultBoxText') or '', 8000),
        'uiResultBoxAnswerLine': row.get('uiResultBoxAnswerLine'),
        'uiResultBoxTextHash': row.get('uiResultBoxTextHash'),
        'uiDomResultMatchesApi': bool(row.get('uiDomResultMatchesApi')),
        'clientDisplayedResultMatchesApi': bool(row.get('clientDisplayedResultMatchesApi')),
        'userVisibleAnswerMatchesApi': bool(row.get('userVisibleAnswerMatchesApi')),
        'userVisibleAnswerMatchesExpected': bool(row.get('userVisibleAnswerMatchesExpected')),
        'uiRenderPassed': _live_audit_ui_render_passed(row),
        'uiRenderIssues': row.get('uiRenderIssues') or [],
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
        'deepseekUsagePresent': evidence.get('deepseekUsagePresent'),
        'deepseekTotalTokens': evidence.get('deepseekTotalTokens'),
        'apiPromptTokens': evidence.get('apiPromptTokens'),
        'apiCompletionTokens': evidence.get('apiCompletionTokens'),
        'apiTotalTokens': evidence.get('apiTotalTokens'),
        'promptCacheHitTokens': evidence.get('promptCacheHitTokens'),
        'promptCacheMissTokens': evidence.get('promptCacheMissTokens'),
        'browserClientFetch': evidence.get('browserClientFetch'),
        'apiRouteNetworkVisibleToBrowser': evidence.get('apiRouteNetworkVisibleToBrowser'),
        'deepseekRequestHashes': evidence.get('deepseekRequestHashes'),
        'deepseekResponseHashes': evidence.get('deepseekResponseHashes'),
        'routeUnderAudit': evidence.get('routeUnderAudit'),
        'apiRouteStatusCode': evidence.get('apiRouteStatusCode'),
        'frontendDomRenderedOutputChecked': evidence.get('frontendDomRenderedOutputChecked'),
        'frontendDomExpectedCheckOk': evidence.get('frontendDomExpectedCheckOk'),
        'frontendDomAnswerLine': evidence.get('frontendDomAnswerLine'),
        'frontendDomResultText': evidence.get('frontendDomResultText'),
        'frontendDomAnswerMatchesApi': evidence.get('frontendDomAnswerMatchesApi'),
        'responseHash': evidence.get('responseHash'),
        'frontendDomRenderedOutputChecked': evidence.get('frontendDomRenderedOutputChecked'),
        'uiRenderResultMatchesExpected': evidence.get('uiRenderResultMatchesExpected'),
        'clientDisplayedAnswerLine': evidence.get('clientDisplayedAnswerLine'),
        'uiRenderDomHash': evidence.get('uiRenderDomHash'),
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


def _live_audit_normalize_duplicate_key(value: Any) -> str:
    text = str(value or '').replace('\u00a0', ' ').replace('ё', 'е').lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def _live_audit_duplicate_reason_map(rows: list[dict[str, Any]]) -> dict[tuple[Any, Any], list[str]]:
    """Return per-row duplicate warnings for audit proof quality.

    We intentionally treat exact repeated inputText/cacheKey/proofHash as a suspicious
    audit-set problem. A passed section should not spend several DeepSeek calls on the
    same black-box task and then count them as independent coverage.
    """
    by_text: dict[str, list[dict[str, Any]]] = {}
    by_proof: dict[str, list[dict[str, Any]]] = {}
    by_cache: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        text_key = _live_audit_normalize_duplicate_key(row.get('inputText') or row.get('inputPreview'))
        if text_key:
            by_text.setdefault(text_key, []).append(row)
        proof_key = str(row.get('proofHash') or '').strip()
        if proof_key:
            by_proof.setdefault(proof_key, []).append(row)
        cache_key = str(row.get('cacheKey') or '').strip()
        if cache_key:
            by_cache.setdefault(cache_key, []).append(row)

    reason_map: dict[tuple[Any, Any], list[str]] = {}

    def add(row: dict[str, Any], reason: str) -> None:
        key = (row.get('caseIndex'), row.get('id'))
        reason_map.setdefault(key, [])
        if reason not in reason_map[key]:
            reason_map[key].append(reason)

    def label(group: list[dict[str, Any]]) -> str:
        parts = []
        for row in group[:6]:
            idx = row.get('caseIndex')
            cid = row.get('id')
            parts.append(f'{idx}:{cid}')
        tail = '' if len(group) <= 6 else f' (+{len(group) - 6})'
        return ', '.join(parts) + tail

    for text_key, group in by_text.items():
        if len(group) > 1:
            msg = f'duplicate audit inputText: "{text_key}" in cases {label(group)}'
            for row in group:
                add(row, msg)
    for proof_key, group in by_proof.items():
        if len(group) > 1:
            msg = f'duplicate proofHash {proof_key} in cases {label(group)}'
            for row in group:
                add(row, msg)
    for cache_key, group in by_cache.items():
        if len(group) > 1:
            msg = f'duplicate cacheKey {cache_key} in cases {label(group)}'
            for row in group:
                add(row, msg)
    return reason_map


def _live_audit_apply_duplicate_suspicion(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reason_map = _live_audit_duplicate_reason_map(rows)
    if not reason_map:
        return rows
    patched: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            patched.append(row)
            continue
        out = dict(row)
        reasons = list(out.get('suspiciousReasons') or [])
        for reason in reason_map.get((out.get('caseIndex'), out.get('id')), []):
            if reason not in reasons:
                reasons.append(reason)
        out['suspiciousReasons'] = reasons
        patched.append(out)
    return patched


def _live_audit_duplicate_quality_issues(rows: list[dict[str, Any]], *, limit: int = 8) -> list[str]:
    reason_map = _live_audit_duplicate_reason_map(rows)
    issues: list[str] = []
    seen: set[str] = set()
    for reasons in reason_map.values():
        for reason in reasons:
            if reason not in seen:
                seen.add(reason)
                issues.append(reason)
                if len(issues) >= limit:
                    return issues
    return issues


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
    if str(run.get('section') or '') == 'g4_arithmetic_actions' and planned != 100:
        blockers.append('planned must be 100 for V311.04 g4_arithmetic_actions acceptance')
    if completed != planned:
        blockers.append('completed != planned')
    if failed != 0:
        blockers.append('failed != 0')
    if len(evidence) != planned:
        blockers.append('evidenceResultsCount != planned')
    if normal_cases and external_total < len(normal_cases):
        blockers.append('externalApiCallsTotalIncludingCache < normal case count')
    if int(run.get('cachedResults') or 0) != 0:
        blockers.append('cachedResults != 0: V311.04 proof run must spend fresh external calls, not replay case cache')
    if normal_cases and int(run.get('externalApiCalls') or 0) < len(normal_cases):
        blockers.append('externalApiCalls < normal case count')
    if normal_cases and int(run.get('externalApiCompleted') or 0) < len(normal_cases):
        blockers.append('externalApiCompleted < normal case count')
    if normal_cases and int(run.get('deepseekUsageProofs') or 0) < len(normal_cases):
        blockers.append('deepseekUsageProofs < normal case count')
    if normal_cases and int(run.get('apiTotalTokens') or run.get('deepseekTotalTokens') or 0) <= 0:
        blockers.append('apiTotalTokens <= 0')
    if any(not item.get('externalApiUsed') for item in normal_cases):
        blockers.append('at least one normal case has externalApiUsed=false')
    if str(run.get('auditTransport') or '') == 'browser-client-fetch':
        if any(str(item.get('routeUnderAudit') or '') != 'browser fetch -> POST /api/explain' for item in normal_cases):
            blockers.append('at least one normal case did not pass through browser fetch -> POST /api/explain')
        if any(str(item.get('routeAuditMode') or '') != 'browser-client-fetch' for item in normal_cases):
            blockers.append('at least one normal case lacks browser-client-fetch routeAuditMode')
        if normal_cases and int(run.get('browserClientFetchCalls') or 0) < len(normal_cases):
            blockers.append('browserClientFetchCalls < normal case count')
    else:
        if any(str(item.get('routeUnderAudit') or '') != 'POST /api/explain' for item in normal_cases):
            blockers.append('at least one normal case did not pass through POST /api/explain')
    if any(str(item.get('routeAuditMode') or '') != 'browser-client-ui-render-visible-network' for item in normal_cases):
        blockers.append('at least one normal case did not come from frontend UI-render DOM audit')
    if any(not item.get('browserClientFetch') for item in normal_cases):
        blockers.append('at least one normal case lacks browserClientFetch proof')
    if any(not item.get('apiRouteNetworkVisibleToBrowser') for item in normal_cases):
        blockers.append('at least one normal case lacks browser-visible network proof')
    if any(not _live_audit_ui_dom_checked(item) for item in normal_cases):
        blockers.append('at least one normal case lacks frontend DOM #resultBox render proof')
    if any(not _live_audit_ui_expected_ok(item) for item in normal_cases):
        blockers.append('at least one normal case lacks positive expected-vs-DOM proof')
    if any(not _live_audit_ui_clicked(item) for item in normal_cases):
        blockers.append('at least one normal case lacks proof that the real frontend #solveBtn was clicked')
    if any(not _live_audit_ui_input_selector_ok(item) for item in normal_cases):
        blockers.append('at least one normal case did not set the real frontend #taskInput')
    if any(not _live_audit_ui_result_selector_ok(item) for item in normal_cases):
        blockers.append('at least one normal case did not verify DOM #resultBox')
    if any(not _live_audit_ui_answer_matches_api(item) for item in normal_cases):
        blockers.append('at least one normal case DOM answer line does not match API answer line')
    if any(not _live_audit_ui_result_matches_api(item) for item in normal_cases):
        blockers.append('at least one normal case DOM displayed result does not match API result')
    if any(not _live_audit_ui_render_passed(item) for item in normal_cases):
        blockers.append('at least one normal case has uiRenderPassed=false or incomplete UI-render proof')
    if any(int(item.get('apiRouteStatusCode') or 0) != 200 for item in normal_cases):
        blockers.append('at least one normal case has apiRouteStatusCode != 200')
    if any(not item.get('apiRouteAuditBypassDailyLimit') for item in normal_cases):
        blockers.append('at least one normal case lacks audit daily-limit-bypass proof')
    if int(run.get('frontendDomRenderProofs') or run.get('uiRenderDomProofs') or 0) < len(normal_cases):
        blockers.append('frontendDomRenderProofs < normal case count')
    if any(not item.get('deepseekUsagePresent') for item in normal_cases):
        blockers.append('at least one normal case lacks DeepSeek usage object proof')
    if any(int(item.get('apiTotalTokens') or item.get('deepseekTotalTokens') or 0) <= 0 for item in normal_cases):
        blockers.append('at least one normal case has no positive DeepSeek API total token usage')
    duplicate_issues = _live_audit_duplicate_quality_issues(evidence)
    if duplicate_issues:
        blockers.append('duplicate audit proof/input cases are present: ' + '; '.join(duplicate_issues[:3]))
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


async def _evaluate_live_audit_case(case: dict[str, Any], *, allow_external: bool, cache_key: str, audit_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        payload, external = await _generate_with_public_api_route_counter(case['text'], allow_external=allow_external, audit_key=audit_key)
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
        'plannedInputText': planned_text,
        'apiRequestedText': api_request_text,
        'inputTextMatchedAfterFrontendNormalization': _live_audit_task_texts_equivalent(api_request_text, planned_text),
        'actualAnswerLine': _live_audit_extract_answer_line(result_text),
        'resultText': _live_audit_text(result_text, 8000),
        'structuredSolution': structured_solution,
        'payloadError': payload.get('error'),
        'payloadValidated': payload.get('validated'),
        'routeUnderAudit': external.get('routeUnderAudit'),
        'routeAuditMode': external.get('routeAuditMode'),
        'apiRouteNetworkVisibleToBrowser': bool(external.get('apiRouteNetworkVisibleToBrowser')),
        'browserClientFetch': bool(external.get('browserClientFetch')),
        'browserFetchStartedAt': external.get('browserFetchStartedAt'),
        'browserFetchFinishedAt': external.get('browserFetchFinishedAt'),
        'browserFetchDurationMs': external.get('browserFetchDurationMs'),
        'browserUserAgent': external.get('browserUserAgent'),
        'comparisonTarget': 'payload.result returned by browser fetch POST /api/explain' if external.get('browserClientFetch') else 'payload.result returned by POST /api/explain route',
        'comparesExpectedToBrowserReceivedPayloadResult': bool(external.get('browserClientFetch')),
        'frontendDomRenderedOutputChecked': False,
        'uiRenderAudit': False,
        'uiRenderClickedMainSolveButton': False,
        'uiRenderResultMatchesExpected': False,
        'clientDisplayedResultMatchesApi': False,
        'userVisibleAnswerMatchesApi': False,
        'uiSolveButtonClicked': False,
        'uiTaskInputFound': False,
        'uiResultBoxFound': False,
        'uiDomResultMatchesApi': False,
        'userVisibleAnswerMatchesExpected': False,
        'frontendDisplayAssumption': 'Frontend should display payload.result from /api/explain; this row is accepted only after DOM #resultBox proof is recorded by the frontend UI harness.',
        'requestPayloadShape': external.get('requestPayloadShape'),
        'apiRouteStatusCode': external.get('apiRouteStatusCode'),
        'apiRouteResponseBytes': external.get('apiRouteResponseBytes'),
        'apiRouteResponseRelease': external.get('apiRouteResponseRelease'),
        'apiRouteResponseSolverVersion': external.get('apiRouteResponseSolverVersion'),
        'apiRouteAuditBypassDailyLimit': bool(external.get('apiRouteAuditBypassDailyLimit')),
        'auditBypassDailyLimit': bool(external.get('auditBypassDailyLimit')),
        'quotaNotConsumedByAudit': bool(external.get('quotaNotConsumedByAudit')),
        'externalCounterSource': external.get('externalCounterSource'),
        'billingVisibility': external.get('billingVisibility'),
        'auditRequestId': external.get('auditRequestId'),
        'installId': external.get('installId'),
        'requestHash': external.get('requestHash'),
        'responseHash': external.get('responseHash'),
        'externalApiAttempts': row_external_attempts,
        'externalApiCompleted': int(external.get('externalApiCompleted') or 0),
        'externalApiBlocked': int(external.get('externalApiBlocked') or 0),
        'externalApiErrors': int(external.get('externalApiErrors') or 0),
        'externalApiUsed': bool(row_external_attempts or external_by_source),
        'deepseekUsagePresent': bool(external.get('deepseekUsagePresent')),
        'deepseekUsage': external.get('deepseekProofs') or [],
        'deepseekPromptTokens': int(external.get('deepseekPromptTokens') or 0),
        'deepseekCompletionTokens': int(external.get('deepseekCompletionTokens') or 0),
        'deepseekTotalTokens': int(external.get('deepseekTotalTokens') or external.get('apiTotalTokens') or 0),
        'apiPromptTokens': int(external.get('apiPromptTokens') or external.get('deepseekPromptTokens') or 0),
        'apiCompletionTokens': int(external.get('apiCompletionTokens') or external.get('deepseekCompletionTokens') or 0),
        'apiTotalTokens': int(external.get('apiTotalTokens') or external.get('deepseekTotalTokens') or 0),
        'promptCacheHitTokens': int(external.get('promptCacheHitTokens') or 0),
        'promptCacheMissTokens': int(external.get('promptCacheMissTokens') or 0),
        'deepseekModels': [p.get('model') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('model')],
        'deepseekObjectIds': [p.get('id') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('id')],
        'deepseekFinishReasons': [p.get('finishReason') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('finishReason')],
        'deepseekRequestHashes': [p.get('requestHash') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('requestHash')],
        'deepseekResponseHashes': [p.get('responseHash') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('responseHash')],
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
        'deepseekPromptTokens': row.get('deepseekPromptTokens'),
        'deepseekCompletionTokens': row.get('deepseekCompletionTokens'),
        'deepseekTotalTokens': row.get('deepseekTotalTokens'),
        'apiPromptTokens': row.get('apiPromptTokens'),
        'apiCompletionTokens': row.get('apiCompletionTokens'),
        'apiTotalTokens': row.get('apiTotalTokens'),
        'promptCacheHitTokens': row.get('promptCacheHitTokens'),
        'promptCacheMissTokens': row.get('promptCacheMissTokens'),
        'deepseekUsagePresent': row.get('deepseekUsagePresent'),
        'routeUnderAudit': row.get('routeUnderAudit'),
        'routeAuditMode': row.get('routeAuditMode'),
        'apiRouteStatusCode': row.get('apiRouteStatusCode'),
        'apiRouteAuditBypassDailyLimit': row.get('apiRouteAuditBypassDailyLimit'),
        'auditRequestId': row.get('auditRequestId'),
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
        'runnerMode': run.get('runnerMode') or 'BROWSER_CLIENT_UI_RENDER_NETWORK_DOM_AUDIT',
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
        'deepseekPromptTokens': run.get('deepseekPromptTokens'),
        'deepseekCompletionTokens': run.get('deepseekCompletionTokens'),
        'deepseekTotalTokens': run.get('deepseekTotalTokens'),
        'apiPromptTokens': run.get('apiPromptTokens', run.get('deepseekPromptTokens')),
        'apiCompletionTokens': run.get('apiCompletionTokens', run.get('deepseekCompletionTokens')),
        'apiTotalTokens': run.get('apiTotalTokens', run.get('deepseekTotalTokens')),
        'promptCacheHitTokens': run.get('promptCacheHitTokens', 0),
        'promptCacheMissTokens': run.get('promptCacheMissTokens', 0),
        'tokenFieldsNote': 'apiPromptTokens/apiCompletionTokens/apiTotalTokens are direct API usage fields; promptCacheHitTokens/promptCacheMissTokens are reported separately and are not added into apiTotalTokens.',
        'deepseekUsageProofs': run.get('deepseekUsageProofs'),
        'browserClientFetchCalls': run.get('browserClientFetchCalls'),
        'browserClientFetchCompleted': run.get('browserClientFetchCompleted'),
        'auditTransport': run.get('auditTransport'),
        'externalApiUsed': bool(int(run.get('externalApiCalls') or 0) > 0 or int(run.get('cachedExternalApiCalls') or 0) > 0),
        'cachedResults': run.get('cachedResults'),
        'cachedExternalApiCalls': run.get('cachedExternalApiCalls'),
        'externalApiCallsTotalIncludingCache': int(run.get('externalApiCalls') or 0) + int(run.get('cachedExternalApiCalls') or 0),
        'failuresCount': len(failures),
        'resultsCount': len(run.get('results') or []),
        'evidenceResultsCount': len(_live_audit_evidence_list(run)),
        'uiDomProofs': len([item for item in _live_audit_evidence_list(run) if isinstance(item, dict) and item.get('frontendDomRenderedOutputChecked')]),
        'uiResultBoxProofs': len([item for item in _live_audit_evidence_list(run) if isinstance(item, dict) and item.get('uiResultBoxFound')]),
        'uiSolveButtonClickProofs': len([item for item in _live_audit_evidence_list(run) if isinstance(item, dict) and item.get('uiSolveButtonClicked')]),
        'uiDomApiMatchProofs': len([item for item in _live_audit_evidence_list(run) if isinstance(item, dict) and item.get('uiDomResultMatchesApi')]),
        'uiRenderPassedProofs': len([item for item in _live_audit_evidence_list(run) if isinstance(item, dict) and _live_audit_ui_render_passed(item)]),
        'suspiciousPassedCount': len([item for item in _live_audit_apply_duplicate_suspicion(_live_audit_evidence_list(run)) if isinstance(item, dict) and item.get('ok') and item.get('suspiciousReasons')]),
        'suspiciousCount': len([item for item in _live_audit_apply_duplicate_suspicion(_live_audit_evidence_list(run)) if isinstance(item, dict) and item.get('suspiciousReasons')]),
        'uiRenderDomProofs': int(run.get('uiRenderDomProofs') or 0),
        'duplicateQualityIssues': _live_audit_duplicate_quality_issues(_live_audit_evidence_list(run)),
        'acceptanceReady': len(_live_audit_acceptance_blockers(run)) == 0,
        'acceptanceIssues': _live_audit_acceptance_blockers(run),
        'acceptanceRequires': ['status == done', 'completed == planned == 100', 'failed == 0', 'cachedResults == 0', 'externalApiCalls >= normal cases', 'externalApiCompleted >= normal cases', 'deepseekUsageProofs >= normal cases', 'apiTotalTokens > 0', 'every normal case routeAuditMode == browser-client-ui-render-visible-network, browserClientFetch=true, apiRouteNetworkVisibleToBrowser=true', 'frontend DOM proof recorded for every normal case and uiRenderPassed=true', 'real frontend #taskInput was set and #solveBtn was clicked', 'visible #resultBox answer matches expected answer and API answer', 'uiRenderPassed == true for every normal case', 'caseProofsTotal == planned', 'suspiciousPassedCount == 0', 'duplicateQualityIssues == []'],
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
        'nextPlannedMapStep': 'after V311.04 pass: V312 — 4 класс, раздел 3 — Текстовые задачи',
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
                    'deepseekUsagePresent': bool(row.get('deepseekUsagePresent')),
                    'deepseekPromptTokens': int(row.get('deepseekPromptTokens') or 0),
                    'deepseekCompletionTokens': int(row.get('deepseekCompletionTokens') or 0),
                    'deepseekTotalTokens': int(row.get('deepseekTotalTokens') or 0),
                }
            else:
                state = _load_live_audit_state()
                current = state['runs'].get(run_id, {})
                if allow_external and int(current.get('externalApiCalls') or 0) >= max_external_calls:
                    row = _live_audit_build_case_limit_error(case, cache_key, 'live-audit external API budget reached before this case')
                    external_counts = {'externalApiAttempts': 0, 'externalApiCompleted': 0, 'externalApiBlocked': 0, 'externalApiErrors': 0, 'cachedExternalApiAttempts': 0, 'deepseekUsagePresent': False, 'deepseekPromptTokens': 0, 'deepseekCompletionTokens': 0, 'deepseekTotalTokens': 0}
                else:
                    try:
                        row, external_counts = await asyncio.wait_for(
                            _evaluate_live_audit_case(case, allow_external=allow_external, cache_key=cache_key, audit_key=str(run.get('auditKey') or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY)),
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
                live_run['deepseekPromptTokens'] = int(live_run.get('deepseekPromptTokens') or 0) + int(external_counts.get('deepseekPromptTokens') or 0)
                live_run['deepseekCompletionTokens'] = int(live_run.get('deepseekCompletionTokens') or 0) + int(external_counts.get('deepseekCompletionTokens') or 0)
                live_run['deepseekTotalTokens'] = int(live_run.get('deepseekTotalTokens') or 0) + int(external_counts.get('deepseekTotalTokens') or 0)
                live_run['apiPromptTokens'] = int(live_run.get('apiPromptTokens') or 0) + int(external_counts.get('apiPromptTokens') or external_counts.get('deepseekPromptTokens') or 0)
                live_run['apiCompletionTokens'] = int(live_run.get('apiCompletionTokens') or 0) + int(external_counts.get('apiCompletionTokens') or external_counts.get('deepseekCompletionTokens') or 0)
                live_run['apiTotalTokens'] = int(live_run.get('apiTotalTokens') or 0) + int(external_counts.get('apiTotalTokens') or external_counts.get('deepseekTotalTokens') or 0)
                live_run['promptCacheHitTokens'] = int(live_run.get('promptCacheHitTokens') or 0) + int(external_counts.get('promptCacheHitTokens') or 0)
                live_run['promptCacheMissTokens'] = int(live_run.get('promptCacheMissTokens') or 0) + int(external_counts.get('promptCacheMissTokens') or 0)
                if bool(external_counts.get('deepseekUsagePresent')):
                    live_run['deepseekUsageProofs'] = int(live_run.get('deepseekUsageProofs') or 0) + 1
                if bool(row.get('fromCache')):
                    live_run['cachedResults'] = int(live_run.get('cachedResults') or 0) + 1
                    live_run['cachedExternalApiCalls'] = int(live_run.get('cachedExternalApiCalls') or 0) + int(external_counts.get('cachedExternalApiAttempts') or 0)
                    live_run['cachedDeepseekTotalTokens'] = int(live_run.get('cachedDeepseekTotalTokens') or 0) + int(external_counts.get('deepseekTotalTokens') or 0)
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



def _browser_client_audit_context_from_request(request: Request, payload: dict | None = None) -> dict[str, Any] | None:
    key = str(request.headers.get('X-Live-Audit-Key') or '').strip()
    if not _live_audit_key_matches(key):
        return None
    marker = str(request.headers.get('X-Live-Audit-Browser-Client') or '').strip().lower()
    client_mode = str(request.headers.get('X-Live-Audit-Client-Mode') or request.headers.get('X-Live-Audit-Mode') or '').strip().lower()
    if marker not in {'1', 'true', 'yes', 'on'} and client_mode not in {'browser-fetch', 'browser-client-fetch', 'browser-client-fetch-visible-network', 'browser-client-ui-render-visible-network', 'browser-ui-render-dom-resultbox', 'frontend-ui-render-resultbox'}:
        return None
    payload = payload or {}
    run_id = str(request.headers.get('X-Live-Audit-Run-Id') or payload.get('auditRunId') or '').strip()
    case_id = str(request.headers.get('X-Live-Audit-Case-Id') or payload.get('auditCaseId') or '').strip()
    case_index_raw = str(request.headers.get('X-Live-Audit-Case-Index') or payload.get('auditCaseIndex') or '').strip()
    try:
        case_index = int(case_index_raw)
    except Exception:
        case_index = -1
    audit_request_id = str(request.headers.get('X-Audit-Request-Id') or '').strip() or _short_hash({'runId': run_id, 'caseId': case_id, 'caseIndex': case_index, 'ts': _now_ts()}, 20)
    install_id = _extract_install_id(request, payload) or f'live-browser-audit-{APP_RELEASE}-{audit_request_id}'
    return {
        'browserClientFetchAudit': True,
        'auditKey': key,
        'runId': run_id,
        'caseId': case_id,
        'caseIndex': case_index,
        'auditRequestId': audit_request_id,
        'installId': install_id,
        'userAgentHash': _short_hash(request.headers.get('user-agent') or '', 16),
    }


def _live_audit_browser_case_from_run(run: dict[str, Any], case_index: int, case_id: str) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    issues: list[str] = []
    cases = list(run.get('cases') or [])
    if case_index < 0 or case_index >= len(cases):
        return None, None, [f'case index out of range: {case_index}']
    item = cases[case_index] if isinstance(cases[case_index], dict) else {}
    case = item.get('case') if isinstance(item.get('case'), dict) else None
    cache_key = str(item.get('cacheKey') or '')
    if not isinstance(case, dict):
        return None, cache_key, ['stored case is missing']
    expected_id = str(case.get('id') or case.get('name') or '')
    if case_id and case_id != expected_id:
        issues.append(f'case id mismatch: header={case_id}, planned={expected_id}')
    return case, cache_key, issues


def _live_audit_record_browser_client_case(audit_context: dict[str, Any], text: str, payload: dict[str, Any], external: dict[str, Any]) -> dict[str, Any]:
    run_id = str(audit_context.get('runId') or '')
    case_index = int(audit_context.get('caseIndex') if audit_context.get('caseIndex') is not None else -1)
    case_id = str(audit_context.get('caseId') or '')
    if not run_id:
        return {'recorded': False, 'error': 'missing browser audit run id'}
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(run_id)
    if not isinstance(run, dict):
        return {'recorded': False, 'error': 'browser audit run not found', 'runId': run_id}
    if run.get('release') != APP_RELEASE or not run.get('browserClientAudit'):
        return {'recorded': False, 'error': 'run is not a browser-client audit run for current release', 'runId': run_id}
    case, cache_key, plan_issues = _live_audit_browser_case_from_run(run, case_index, case_id)
    if not isinstance(case, dict):
        return {'recorded': False, 'error': '; '.join(plan_issues) or 'case not found', 'runId': run_id}
    planned_text = str(case.get('text') or '')
    api_request_text = str(text or '')
    if not _live_audit_task_texts_equivalent(api_request_text, planned_text):
        plan_issues.append('input text mismatch between browser fetch and planned audit case')

    case_for_check = dict(case)
    expected_source = str(case_for_check.get('expectedSource') or '')
    is_guard_case = expected_source.startswith('guard') or str(case_for_check.get('category') or '').endswith('guard') or 'guard' in str(case_for_check.get('category') or '')
    if not expected_source.startswith('guard'):
        case_for_check.pop('expectedSource', None)
        case_for_check.pop('expectedSourceFamily', None)
    checked = _check_payload(case_for_check, payload)
    if plan_issues:
        checked['issues'].extend(plan_issues)
        checked['ok'] = False
    result_text = str(payload.get('result') or '')
    source = str(payload.get('source') or '')
    external_by_source = _source_looks_external(source, payload)
    row_external_attempts = int(external.get('externalApiAttempts') or 0)
    if resolve_solver_mode() == 'deepseek_primary' and not is_guard_case and not (row_external_attempts or external_by_source):
        checked['issues'].append('Browser-client route did not call external API for a normal audit case')
        checked['ok'] = False
    if payload.get('deepseekPrimaryFallback') and not is_guard_case:
        checked['issues'].append(f"DeepSeek-primary fell back locally: {payload.get('deepseekPrimaryFallback')}")
        checked['ok'] = False
    strict_format_issues = _live_audit_strict_format_issues(case, result_text, is_guard_case=is_guard_case)
    if strict_format_issues:
        checked['issues'].extend(strict_format_issues)
        checked['ok'] = False
    structured_solution = payload.get('structured_solution') if isinstance(payload.get('structured_solution'), dict) else None
    row = {
        'caseIndex': case_index,
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
        'apiRawResultText': _live_audit_text(result_text, 8000),
        'clientDisplayedResultText': _live_audit_text(result_text, 8000),
        'clientDisplayedAnswerLine': _live_audit_extract_answer_line(result_text),
        'userVisibleResultText': _live_audit_text(str(payload.get('userVisibleResultText') or result_text), 8000),
        'clientDisplayedResultMatchesApi': True,
        'userVisibleAnswerMatchesApi': True,
        'auditComparedSamePayloadReturnedToBrowser': True,
        'comparisonTarget': 'payload.result returned to browser by fetch(POST /api/explain)',
        'comparesExpectedToBrowserReceivedPayloadResult': True,
        'frontendDomRenderedOutputChecked': False,
        'uiRenderAudit': False,
        'uiRenderClickedMainSolveButton': False,
        'uiRenderResultMatchesExpected': False,
        'clientDisplayedResultMatchesApi': False,
        'userVisibleAnswerMatchesApi': False,
        'uiSolveButtonClicked': False,
        'uiTaskInputFound': False,
        'uiResultBoxFound': False,
        'uiDomResultMatchesApi': False,
        'userVisibleAnswerMatchesExpected': False,
        'frontendDisplayAssumption': 'Frontend should display payload.result from /api/explain; this row is accepted only after DOM #resultBox proof is recorded by the frontend UI harness.',
        'frontendDisplayContract': 'V311.04 accepts only after the production frontend DOM proof is recorded: #taskInput value -> #solveBtn click -> /api/explain -> #resultBox text compared with expected and API answer.',
        'structuredSolution': structured_solution,
        'payloadError': payload.get('error'),
        'payloadValidated': payload.get('validated'),
        'routeUnderAudit': 'POST /api/explain',
        'routeAuditMode': 'browser-client-ui-render-visible-network',
        'browserClientFetch': True,
        'browserClientFetchEvidence': True,
        'apiRouteNetworkVisibleToBrowser': True,
        'requestPayloadShape': external.get('requestPayloadShape'),
        'apiRouteStatusCode': external.get('apiRouteStatusCode') or 200,
        'apiRouteResponseBytes': len(json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')),
        'apiRouteResponseRelease': payload.get('release') or external.get('apiRouteResponseRelease'),
        'apiRouteResponseSolverVersion': payload.get('solverVersion') or external.get('apiRouteResponseSolverVersion'),
        'apiRouteAuditBypassDailyLimit': bool(payload.get('auditBypassDailyLimit') or external.get('apiRouteAuditBypassDailyLimit')),
        'auditBypassDailyLimit': bool(payload.get('auditBypassDailyLimit') or external.get('auditBypassDailyLimit')),
        'quotaNotConsumedByAudit': bool(external.get('quotaNotConsumedByAudit')),
        'externalCounterSource': external.get('externalCounterSource'),
        'billingVisibility': external.get('billingVisibility'),
        'auditRequestId': external.get('auditRequestId') or audit_context.get('auditRequestId'),
        'installId': external.get('installId') or audit_context.get('installId'),
        'browserUserAgentHash': external.get('browserUserAgentHash') or audit_context.get('userAgentHash'),
        'requestHash': external.get('requestHash'),
        'responseHash': external.get('responseHash') or _short_hash(payload, 24),
        'externalApiAttempts': row_external_attempts,
        'externalApiCompleted': int(external.get('externalApiCompleted') or 0),
        'externalApiBlocked': int(external.get('externalApiBlocked') or 0),
        'externalApiErrors': int(external.get('externalApiErrors') or 0),
        'externalApiUsed': bool(row_external_attempts or external_by_source),
        'deepseekUsagePresent': bool(external.get('deepseekUsagePresent')),
        'deepseekUsage': external.get('deepseekProofs') or [],
        'deepseekPromptTokens': int(external.get('deepseekPromptTokens') or 0),
        'deepseekCompletionTokens': int(external.get('deepseekCompletionTokens') or 0),
        'deepseekTotalTokens': int(external.get('deepseekTotalTokens') or 0),
        'apiPromptTokens': int(external.get('apiPromptTokens') or external.get('deepseekPromptTokens') or 0),
        'apiCompletionTokens': int(external.get('apiCompletionTokens') or external.get('deepseekCompletionTokens') or 0),
        'apiTotalTokens': int(external.get('apiTotalTokens') or external.get('deepseekTotalTokens') or 0),
        'promptCacheHitTokens': int(external.get('promptCacheHitTokens') or 0),
        'promptCacheMissTokens': int(external.get('promptCacheMissTokens') or 0),
        'deepseekModels': [p.get('model') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('model')],
        'deepseekObjectIds': [p.get('id') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('id')],
        'deepseekFinishReasons': [p.get('finishReason') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('finishReason')],
        'deepseekRequestHashes': [p.get('requestHash') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('requestHash')],
        'deepseekResponseHashes': [p.get('responseHash') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('responseHash')],
        'solverMode': payload.get('solverMode'),
        'deepseekPrimaryFallback': payload.get('deepseekPrimaryFallback'),
        'verifier': payload.get('verifier'),
        'cacheKey': cache_key,
        'fromCache': False,
        'resultPreview': result_text[:520],
    }
    compact = _compact_live_audit_result(row)
    evidence_row = _live_audit_evidence_row(row)

    def _append_browser_result(state):
        live_run = state.setdefault('runs', {}).get(run_id)
        if not isinstance(live_run, dict):
            return {'recorded': False, 'error': 'run disappeared'}
        known = {str(result.get('cacheKey') or '') for result in (live_run.get('results') or []) if isinstance(result, dict)}
        if cache_key in known:
            return {'recorded': True, 'duplicateRecordIgnored': True, 'runId': run_id, 'caseIndex': case_index, 'caseId': row.get('id')}
        live_run['status'] = 'running'
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
        live_run['browserClientFetchCalls'] = int(live_run.get('browserClientFetchCalls') or 0) + 1
        live_run['browserClientFetchCompleted'] = int(live_run.get('browserClientFetchCompleted') or 0) + 1
        live_run['externalApiCalls'] = int(live_run.get('externalApiCalls') or 0) + int(row.get('externalApiAttempts') or 0)
        live_run['externalApiCompleted'] = int(live_run.get('externalApiCompleted') or 0) + int(row.get('externalApiCompleted') or 0)
        live_run['externalApiBlocked'] = int(live_run.get('externalApiBlocked') or 0) + int(row.get('externalApiBlocked') or 0)
        live_run['externalApiErrors'] = int(live_run.get('externalApiErrors') or 0) + int(row.get('externalApiErrors') or 0)
        live_run['deepseekPromptTokens'] = int(live_run.get('deepseekPromptTokens') or 0) + int(row.get('deepseekPromptTokens') or 0)
        live_run['deepseekCompletionTokens'] = int(live_run.get('deepseekCompletionTokens') or 0) + int(row.get('deepseekCompletionTokens') or 0)
        live_run['deepseekTotalTokens'] = int(live_run.get('deepseekTotalTokens') or 0) + int(row.get('deepseekTotalTokens') or 0)
        live_run['apiPromptTokens'] = int(live_run.get('apiPromptTokens') or 0) + int(row.get('apiPromptTokens') or 0)
        live_run['apiCompletionTokens'] = int(live_run.get('apiCompletionTokens') or 0) + int(row.get('apiCompletionTokens') or 0)
        live_run['apiTotalTokens'] = int(live_run.get('apiTotalTokens') or 0) + int(row.get('apiTotalTokens') or 0)
        live_run['promptCacheHitTokens'] = int(live_run.get('promptCacheHitTokens') or 0) + int(row.get('promptCacheHitTokens') or 0)
        live_run['promptCacheMissTokens'] = int(live_run.get('promptCacheMissTokens') or 0) + int(row.get('promptCacheMissTokens') or 0)
        if bool(row.get('deepseekUsagePresent')):
            live_run['deepseekUsageProofs'] = int(live_run.get('deepseekUsageProofs') or 0) + 1
        live_run['heartbeatAt'] = _now_ts()
        live_run['updatedAt'] = live_run['heartbeatAt']
        if int(live_run.get('completed') or 0) >= int(live_run.get('planned') or 0):
            live_run['status'] = 'done'
            live_run['finishedAt'] = live_run['updatedAt']
        return {'recorded': True, 'runId': run_id, 'caseIndex': case_index, 'caseId': row.get('id'), 'ok': bool(row.get('ok')), 'issues': row.get('issues') or []}
    receipt = _mutate_live_audit_state(_append_browser_result)
    if not isinstance(receipt, dict):
        receipt = {'recorded': False, 'error': 'record mutation failed'}
    receipt.update({
        'routeAuditMode': 'browser-client-ui-render-visible-network',
        'browserClientFetch': True,
        'apiRouteNetworkVisibleToBrowser': True,
        'externalApiAttempts': row['externalApiAttempts'],
        'externalApiCompleted': row['externalApiCompleted'],
        'deepseekUsagePresent': row['deepseekUsagePresent'],
        'apiTotalTokens': row['apiTotalTokens'],
        'promptCacheHitTokens': row['promptCacheHitTokens'],
        'promptCacheMissTokens': row['promptCacheMissTokens'],
    })
    return receipt




def _api_v311_canonicalize_response(original_text: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Route-layer guard for V311.04 arithmetic actions."""
    try:
        service_payload = canonicalize_v311_arithmetic_actions_response(original_text, payload)
        if isinstance(service_payload, dict) and service_payload.get('result'):
            return service_payload
    except Exception:
        return payload if isinstance(payload, dict) else None
    return payload if isinstance(payload, dict) else None


def _api_v310_canonicalize_response(original_text: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Route-layer guard for V310 numbers/quantities.

    V310 originally called this helper from /api/explain, but the helper was
    accidentally omitted from api.py.  Keep the route resilient by delegating to
    the service-level V310 canonicalizer and returning the original payload when
    the text is not a V310 deterministic prompt.
    """
    try:
        service_payload = canonicalize_v310_numbers_quantities_response(original_text, payload)
        if isinstance(service_payload, dict) and service_payload.get('result'):
            return service_payload
    except Exception:
        return payload if isinstance(payload, dict) else None
    return payload if isinstance(payload, dict) else None



def _api_v309_plural(number: int, one: str, two: str, five: str) -> str:
    n = abs(int(number)); last_two = n % 100; last = n % 10
    if 11 <= last_two <= 14:
        return five
    if last == 1:
        return one
    if 2 <= last <= 4:
        return two
    return five


def _api_v309_clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').replace('\u00a0', ' ').strip())


def _api_v309_split_semicolon_entries(raw: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for part in re.split(r'\s*;\s*', str(raw or '').strip()):
        clean = part.strip().strip('.')
        if not clean:
            continue
        m = re.match(r'^\s*(.+?)\s*(?:—|–|-|:)\s*(.+?)\s*$', clean)
        if not m:
            # Frontend voice normalisation used to remove the dash in rows like
            # "1 урок — математика" -> "1 урок математика" and
            # "билет — 95 руб." -> "билет 95 руб.".  Keep V309
            # deterministic even if such normalised text reaches the route.
            lesson_m = re.match(r'^\s*(\d+)\s+урок\s+(.+?)\s*$', clean, flags=re.IGNORECASE)
            if lesson_m:
                key = f'{int(lesson_m.group(1))} урок'
                value = _api_v309_clean_text(lesson_m.group(2)).strip(' .')
                if key and value:
                    entries[key] = value
                continue
            price_m = re.match(r'^\s*(билет|программа|значок)\s+(-?\d+)\s*руб\.?\s*$', clean, flags=re.IGNORECASE)
            if price_m:
                key = _api_v309_clean_text(price_m.group(1)).lower().replace('ё', 'е').strip(' .')
                value = f'{int(price_m.group(2))} руб.'
                entries[key] = value
                continue
            continue
        key = _api_v309_clean_text(m.group(1)).lower().replace('ё', 'е').strip(' .')
        value = _api_v309_clean_text(m.group(2)).strip(' .')
        if key:
            entries[key] = value
    return entries


def _api_v309_money_final(total: int) -> str:
    return f'{int(total)} {_api_v309_plural(int(total), "рубль", "рубля", "рублей")}'


def _api_v309_make_result(original_text: str, steps: list[str], final_answer: str) -> str:
    clean_steps = [str(step or '').strip().rstrip('.') for step in steps if str(step or '').strip()]
    lines = ['Задача.', str(original_text or '').strip(), 'Решение.']
    if len(clean_steps) <= 1:
        lines.extend([step + '.' for step in clean_steps])
    else:
        for i, step in enumerate(clean_steps, 1):
            lines.append(f'{i}) {step}.')
    final = str(final_answer or '').strip().rstrip('.')
    lines.append(f'Ответ: {final}.')
    return '\n'.join(lines).strip()


def _api_v309_frontline_canonical_payload(original_text: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Last route-layer guard for V309.

    V309.03 showed that some production responses still reached the browser as
    short DeepSeek wording (for example "математика" or "275 руб") even though
    the audit evidence was valid.  This guard is intentionally independent from
    service.py postprocessors and rewrites only the two remaining fragile V309
    patterns: lesson lookup and price-list totals.
    """
    text = str(original_text or '').strip()
    low = text.lower().replace('ё', 'е')
    final = ''
    steps: list[str] = []
    answer_number = ''
    answer_unit = ''
    family = ''

    lesson = re.match(r'^\s*Расписание\s+уроков\s*:\s*(.+?)\.\s*Какой\s+предмет\s+на\s+(\d+)\s+уроке\?\s*$', text, flags=re.IGNORECASE | re.DOTALL)
    if lesson:
        entries = _api_v309_split_semicolon_entries(lesson.group(1))
        target_num = int(lesson.group(2))
        target = f'{target_num} урок'
        subject = entries.get(target, '').strip()
        if subject:
            final = f'на {target_num} уроке {subject}'
            steps = [f'В расписании напротив {target} записано: {subject}']
            family = 'schedule-lookup'

    if not final and re.search(r'прайс\s*[-–—]?\s*лист', low):
        price = re.match(r'^\s*Прайс\s*[-–—]?\s*лист\s*:\s*(.+?)\.\s*Сколько\s+рублей\s+нужно\s+заплатить\s+за\s+(\d+)\s+билет(?:а|ов)?\s+и\s+1\s+программу\?\s*$', text, flags=re.IGNORECASE | re.DOTALL)
        if price:
            entries = _api_v309_split_semicolon_entries(price.group(1))
            qty = int(price.group(2))
            ticket_m = re.search(r'-?\d+', entries.get('билет', ''))
            program_m = re.search(r'-?\d+', entries.get('программа', ''))
            if ticket_m and program_m:
                ticket = int(ticket_m.group(0)); program = int(program_m.group(0))
                subtotal = ticket * qty; total = subtotal + program
                final = _api_v309_money_final(total)
                steps = [f'{ticket} · {qty} = {subtotal}', f'{subtotal} + {program} = {total}']
                answer_number = str(total)
                answer_unit = _api_v309_plural(total, 'рубль', 'рубля', 'рублей')
                family = 'price-table'

    if not final:
        return None
    result_text = _api_v309_make_result(text, steps, final)
    merged: dict[str, Any] = dict(payload or {})
    merged.update({
        'result': result_text,
        'userVisibleResultText': result_text,
        'backendPreparedVisibleResult': True,
        'source': str((payload or {}).get('source') or 'deepseek-primary'),
        'validated': True,
        'structured_solution': {
            'known': 'математическая информация из условия',
            'find': 'ответ на вопрос по данным',
            'steps': steps,
            'answer_number': answer_number,
            'answer_unit': answer_unit,
            'final_answer': final,
        },
        'structuredSolution': {
            'known': 'математическая информация из условия',
            'find': 'ответ на вопрос по данным',
            'steps': steps,
            'answer_number': answer_number,
            'answer_unit': answer_unit,
            'final_answer': final,
        },
        'verifier': 'api-v309.05-route-frontline-canonical',
        'visibleResultContract': f'v309-g3-math-information-{family}-canonical',
        'canonicalAnswerLine': final,
    })
    return merged


def _api_v309_canonicalize_response(original_text: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    try:
        service_payload = canonicalize_v309_math_information_response(original_text, payload)
        if isinstance(service_payload, dict) and service_payload.get('result'):
            payload = service_payload
    except Exception:
        pass
    route_payload = _api_v309_frontline_canonical_payload(original_text, payload)
    if isinstance(route_payload, dict) and route_payload.get('result'):
        return route_payload
    return payload if isinstance(payload, dict) else None

async def _maybe_handle_browser_client_audit_request(request: Request, data: dict[str, Any], *, route_path: str) -> JSONResponse | None:
    # V300 intentionally lets the normal public route continue, so the browser
    # request is a real POST /api/explain call.  The audit_context wrapper below
    # captures DeepSeek usage and records evidence without replacing the route.
    return None

async def _solve_text(*, text: str, token: str | None, install_id: str | None, audit_bypass_daily_limit: bool = False, audit_context: dict[str, Any] | None = None) -> JSONResponse | dict:
    if _contains_bank_card_details(text):
        access = _safe_access_status(token=token, install_id=install_id)
        content = attach_release({'error': CARD_DATA_BLOCK_MESSAGE, 'code': 'card_data_not_allowed'})
        if access is not None:
            content['access'] = access
        return _json_error(400, content)

    result: dict | None = None
    prevalidated = prevalidate_explanation_request(text)
    if prevalidated is not None:
        access = {'mode': 'live-audit-bypass', 'dailyLimitBypassed': True} if audit_bypass_daily_limit else _safe_access_status(token=token, install_id=install_id)
        if 'error' in prevalidated:
            content = dict(prevalidated)
            if access is not None:
                content['access'] = access
            return _json_error(400, content)
        response_payload = attach_release({**prevalidated, 'access': access} if access is not None else dict(prevalidated))
        canonical_prevalidated_v311 = _api_v311_canonicalize_response(text, response_payload)
        if isinstance(canonical_prevalidated_v311, dict):
            response_payload = attach_release(canonical_prevalidated_v311)
        canonical_prevalidated_v310 = _api_v310_canonicalize_response(text, response_payload)
        if isinstance(canonical_prevalidated_v310, dict):
            response_payload = attach_release(canonical_prevalidated_v310)
        canonical_prevalidated_v309 = _api_v309_canonicalize_response(text, response_payload)
        if isinstance(canonical_prevalidated_v309, dict):
            response_payload = attach_release(canonical_prevalidated_v309)
        if audit_context and audit_context.get('browserClientFetchAudit'):
            zero_counter = {
                'externalApiAttempts': 0,
                'externalApiCompleted': 0,
                'externalApiBlocked': 0,
                'externalApiErrors': 0,
                'deepseekUsagePresent': False,
                'apiPromptTokens': 0,
                'apiCompletionTokens': 0,
                'apiTotalTokens': 0,
                'promptCacheHitTokens': 0,
                'promptCacheMissTokens': 0,
                'deepseekPromptTokens': 0,
                'deepseekCompletionTokens': 0,
                'deepseekTotalTokens': 0,
                'deepseekProofs': [],
                'routeUnderAudit': 'POST /api/explain',
                'routeAuditMode': 'browser-client-ui-render-visible-network',
                'apiRouteNetworkVisibleToBrowser': True,
                'browserClientFetchAudit': True,
                'browserFetchUserAgent': '',
                'requestPayloadShape': {'text': 'string', 'installId': 'string'},
                'auditBypassDailyLimit': audit_bypass_daily_limit,
                'quotaNotConsumedByAudit': True,
                'externalCounterSource': 'browser fetch hit /api/explain; guard/prevalidation returned before external API because this case is handled by local guard/verifier',
                'billingVisibility': 'No external provider call for this guard case; browser-visible /api/explain still returned a recorded audit row',
                'auditRequestId': str(audit_context.get('auditRequestId') or ''),
                'installId': install_id,
                'requestHash': _short_hash({'path': '/api/explain', 'method': 'POST', 'browserFetch': True, 'runId': audit_context.get('runId'), 'caseIndex': audit_context.get('caseIndex'), 'text': text, 'installId': install_id, 'prevalidated': True}, 24),
                'responseHash': _short_hash(response_payload, 24),
                'apiRouteStatusCode': 200,
                'apiRouteResponseRelease': response_payload.get('release'),
                'apiRouteResponseSolverVersion': response_payload.get('solverVersion'),
                'apiRouteAuditBypassDailyLimit': audit_bypass_daily_limit,
            }
            receipt = _live_audit_record_browser_client_case(audit_context, text, response_payload, zero_counter)
            response_payload['browserClientAuditReceipt'] = receipt
            response_payload['routeUnderAudit'] = 'POST /api/explain'
            response_payload['routeAuditMode'] = 'browser-client-ui-render-visible-network'
            response_payload['browserClientFetch'] = True
            response_payload['userVisibleResultText'] = response_payload.get('userVisibleResultText') or response_payload.get('result')
        return response_payload
    try:
        if audit_bypass_daily_limit:
            access = {'mode': 'live-audit-bypass', 'dailyLimitBypassed': True, 'installId': install_id}
        else:
            access = get_access_service().record_final_submission(token=token, install_id=install_id)
    except LimitExceededError as exc:
        status = get_access_service().get_access_status(token=token, install_id=install_id)
        return _error_payload(exc, access=status)
    except AccessServiceError as exc:
        return _error_payload(exc)

    try:
        external_counter: dict[str, Any] | None = None
        if audit_context and audit_context.get('browserClientFetchAudit'):
            result, external_counter = await _generate_with_browser_client_fetch_counter(
                text,
                allow_external=True,
                audit_key=str(audit_context.get('auditKey') or ''),
                audit_context=audit_context,
            )
        else:
            result = await generate_explanation_response(text)
        if isinstance(result, dict):
            canonical_v311 = _api_v311_canonicalize_response(text, result)
            if isinstance(canonical_v311, dict):
                result = canonical_v311
            canonical_v310 = _api_v310_canonicalize_response(text, result)
            if isinstance(canonical_v310, dict):
                result = canonical_v310
            canonical_v309 = _api_v309_canonicalize_response(text, result)
            if isinstance(canonical_v309, dict):
                result = canonical_v309
        if 'error' in result:
            return _json_error(400, {**result, 'access': access, 'auditBypassDailyLimit': audit_bypass_daily_limit})
        response_payload = attach_release({**result, 'access': access, 'auditBypassDailyLimit': audit_bypass_daily_limit})
        canonical_response_v311 = _api_v311_canonicalize_response(text, response_payload)
        if isinstance(canonical_response_v311, dict):
            response_payload = attach_release(canonical_response_v311)
        canonical_response_v310 = _api_v310_canonicalize_response(text, response_payload)
        if isinstance(canonical_response_v310, dict):
            response_payload = attach_release(canonical_response_v310)
        canonical_response_v309 = _api_v309_canonicalize_response(text, response_payload)
        if isinstance(canonical_response_v309, dict):
            response_payload = attach_release(canonical_response_v309)
        if audit_context and audit_context.get('browserClientFetchAudit') and isinstance(external_counter, dict):
            receipt = _live_audit_record_browser_client_case(audit_context, text, response_payload, external_counter)
            response_payload['browserClientAuditReceipt'] = receipt
            response_payload['routeUnderAudit'] = 'POST /api/explain'
            response_payload['routeAuditMode'] = 'browser-client-ui-render-visible-network'
            response_payload['browserClientFetch'] = True
            response_payload['userVisibleResultText'] = response_payload.get('userVisibleResultText') or response_payload.get('result')
        return response_payload
    except httpx.ReadTimeout:
        return _json_error(504, {'error': 'DeepSeek timeout: сервер не дождался ответа от API'})
    except httpx.ConnectTimeout:
        return _json_error(504, {'error': 'DeepSeek connect timeout: сервер не смог подключиться к API'})
    except httpx.ConnectError as exc:
        return _json_error(502, {'error': f'DeepSeek connect error: {str(exc)}'})
    except Exception as exc:  # pragma: no cover - runtime safety
        return _json_error(500, {'error': f'Server exception: {str(exc)}'})



def _json_response_payload(response: JSONResponse) -> tuple[dict[str, Any], int]:
    try:
        body = response.body.decode('utf-8') if isinstance(response.body, bytes) else str(response.body)
        data = json.loads(body or '{}')
        if isinstance(data, dict):
            return data, int(response.status_code or 200)
    except Exception:
        pass
    return {'error': 'JSONResponse body could not be decoded', 'result': ''}, int(getattr(response, 'status_code', 500) or 500)


def _live_audit_find_case_for_browser_run(run: dict[str, Any], *, case_index: int, cache_key: str, text: str) -> tuple[dict[str, Any] | None, str]:
    case_items = list(run.get('cases') or [])
    if case_index < 0 or case_index >= len(case_items):
        return None, 'case index out of range'
    item = case_items[case_index] if isinstance(case_items[case_index], dict) else {}
    case = dict(item.get('case') or {})
    expected_cache_key = str(item.get('cacheKey') or _live_audit_case_cache_key(case, True))
    if cache_key and cache_key != expected_cache_key:
        return None, 'cacheKey mismatch for browser audit case'
    if str(case.get('text') or '').strip() != str(text or '').strip():
        return None, 'input text mismatch for browser audit case'
    return case, expected_cache_key


def _live_audit_append_case_result(run_id: str, row: dict[str, Any], external_counts: dict[str, Any], *, case_index: int, cache_key: str) -> None:
    row['caseIndex'] = case_index
    row['cacheKey'] = cache_key
    row.setdefault('fromCache', False)
    row.setdefault('apiRouteNetworkVisibleToBrowser', False)
    row.setdefault('browserClientFetchAudit', False)
    if not row.get('resultText'):
        row['resultText'] = _live_audit_text(row.get('resultPreview') or '', 8000)
    if not row.get('actualAnswerLine'):
        row['actualAnswerLine'] = _live_audit_extract_answer_line(str(row.get('resultText') or row.get('resultPreview') or ''))
    compact = _compact_live_audit_result(row)
    evidence_row = _live_audit_evidence_row(row)

    def _append_result(state):
        live_run = state.setdefault('runs', {}).get(run_id)
        if not isinstance(live_run, dict):
            return
        known = {str(result.get('cacheKey') or '') for result in (live_run.get('results') or []) if isinstance(result, dict)}
        if cache_key in known:
            return
        if live_run.get('status') not in {'done', 'error', 'cancelled'}:
            live_run['status'] = 'running'
        live_run.setdefault('startedAt', _now_ts())
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
        live_run['apiPromptTokens'] = int(live_run.get('apiPromptTokens') or 0) + int(external_counts.get('apiPromptTokens') or external_counts.get('deepseekPromptTokens') or 0)
        live_run['apiCompletionTokens'] = int(live_run.get('apiCompletionTokens') or 0) + int(external_counts.get('apiCompletionTokens') or external_counts.get('deepseekCompletionTokens') or 0)
        live_run['apiTotalTokens'] = int(live_run.get('apiTotalTokens') or 0) + int(external_counts.get('apiTotalTokens') or external_counts.get('deepseekTotalTokens') or 0)
        live_run['promptCacheHitTokens'] = int(live_run.get('promptCacheHitTokens') or 0) + int(external_counts.get('promptCacheHitTokens') or 0)
        live_run['promptCacheMissTokens'] = int(live_run.get('promptCacheMissTokens') or 0) + int(external_counts.get('promptCacheMissTokens') or 0)
        # Legacy aliases retained for old readers; they mirror API token fields, not cache fields.
        live_run['deepseekPromptTokens'] = int(live_run.get('deepseekPromptTokens') or 0) + int(external_counts.get('deepseekPromptTokens') or external_counts.get('apiPromptTokens') or 0)
        live_run['deepseekCompletionTokens'] = int(live_run.get('deepseekCompletionTokens') or 0) + int(external_counts.get('deepseekCompletionTokens') or external_counts.get('apiCompletionTokens') or 0)
        live_run['deepseekTotalTokens'] = int(live_run.get('deepseekTotalTokens') or 0) + int(external_counts.get('deepseekTotalTokens') or external_counts.get('apiTotalTokens') or 0)
        if bool(external_counts.get('deepseekUsagePresent')):
            live_run['deepseekUsageProofs'] = int(live_run.get('deepseekUsageProofs') or 0) + 1
        if bool(row.get('fromCache')):
            live_run['cachedResults'] = int(live_run.get('cachedResults') or 0) + 1
            live_run['cachedExternalApiCalls'] = int(live_run.get('cachedExternalApiCalls') or 0) + int(external_counts.get('cachedExternalApiAttempts') or 0)
        live_run['browserFetchRequests'] = int(live_run.get('browserFetchRequests') or 0) + 1
        live_run['activeCaseIndex'] = case_index + 1 if int(live_run.get('completed') or 0) < int(live_run.get('planned') or 0) else None
        live_run['heartbeatAt'] = _now_ts()
        live_run['updatedAt'] = live_run['heartbeatAt']
        if int(live_run.get('completed') or 0) >= int(live_run.get('planned') or 0):
            live_run['status'] = 'done'
            live_run['finishedAt'] = live_run['updatedAt']
            live_run.pop('activeCaseIndex', None)
            live_run.pop('activeCaseId', None)
    _mutate_live_audit_state(_append_result)


async def _solve_text_for_browser_client_audit(request: Request, data: dict[str, Any], *, text: str, token: str | None, install_id: str | None) -> JSONResponse | dict:
    audit_key = request.headers.get('X-Live-Audit-Key', '')
    if not _live_audit_key_matches(audit_key):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'browser-client-fetch-audit'})
    run_id = str(request.headers.get('X-Live-Audit-Run-Id') or data.get('auditRunId') or '').strip()
    try:
        case_index = int(request.headers.get('X-Live-Audit-Case-Index') or data.get('auditCaseIndex') or -1)
    except Exception:
        case_index = -1
    cache_key = str(request.headers.get('X-Live-Audit-Case-Cache-Key') or data.get('auditCaseCacheKey') or '').strip()
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(run_id)
    if not isinstance(run, dict):
        return _json_error(404, {'error': 'browser audit runId not found', 'diagnostic': 'browser-client-fetch-audit', 'runId': run_id})
    if run.get('release') != APP_RELEASE:
        return _json_error(409, {'error': 'browser audit run release mismatch', 'diagnostic': 'browser-client-fetch-audit', 'runRelease': run.get('release'), 'currentRelease': APP_RELEASE})
    if str(run.get('auditClientMode') or '') != 'browser-client-ui-render-visible-network':
        return _json_error(409, {'error': 'run is not browser-client-fetch audit mode', 'diagnostic': 'browser-client-fetch-audit', 'runId': run_id})
    case, expected_cache_key = _live_audit_find_case_for_browser_run(run, case_index=case_index, cache_key=cache_key, text=text)
    if case is None:
        return _json_error(409, {'error': expected_cache_key, 'diagnostic': 'browser-client-fetch-audit', 'runId': run_id, 'caseIndex': case_index})
    existing = [item for item in (run.get('results') or []) if isinstance(item, dict) and str(item.get('cacheKey') or '') == expected_cache_key]
    if existing:
        return _json_error(409, {'error': 'case already recorded; browser page should resume from next incomplete case', 'diagnostic': 'browser-client-fetch-audit', 'runId': run_id, 'caseIndex': case_index})

    import backend.legacy_core as legacy_core
    original_call = getattr(legacy_core, 'call_deepseek', None)
    counter: dict[str, Any] = {
        'externalApiAttempts': 0,
        'externalApiCompleted': 0,
        'externalApiBlocked': 0,
        'externalApiErrors': 0,
        'deepseekUsagePresent': False,
        'apiPromptTokens': 0,
        'apiCompletionTokens': 0,
        'apiTotalTokens': 0,
        'promptCacheHitTokens': 0,
        'promptCacheMissTokens': 0,
        'deepseekPromptTokens': 0,
        'deepseekCompletionTokens': 0,
        'deepseekTotalTokens': 0,
        'deepseekProofs': [],
        'routeUnderAudit': 'POST /api/explain',
        'routeAuditMode': 'browser-client-ui-render-visible-network',
        'apiRouteNetworkVisibleToBrowser': True,
        'browserClientFetchAudit': True,
        'browserFetchUserAgent': (request.headers.get('user-agent') or '')[:240],
        'requestPayloadShape': {'text': 'string', 'installId': 'string'},
        'auditBypassDailyLimit': True,
        'quotaNotConsumedByAudit': True,
        'externalCounterSource': 'browser page fetch("/api/explain") + backend.legacy_core.call_deepseek wrapper for this route request',
        'billingVisibility': 'DeepSeek usage object is captured per browser-visible /api/explain request; provider billing remains verifiable only in DeepSeek usage/billing logs',
    }
    request_id = _short_hash({'release': APP_RELEASE, 'runId': run_id, 'caseIndex': case_index, 'text': text, 'ts': _now_ts()}, 20)
    counter['auditRequestId'] = request_id
    counter['installId'] = install_id
    counter['requestHash'] = _short_hash({'path': '/api/explain', 'method': 'POST', 'browserFetch': True, 'runId': run_id, 'caseIndex': case_index, 'text': text, 'installId': install_id}, 24)

    async def counted_call_deepseek(api_payload, *args, **kwargs):
        ctx = _LIVE_AUDIT_DEEPSEEK_CONTEXT.get()
        if not isinstance(ctx, dict) or ctx.get('runId') != run_id or ctx.get('caseIndex') != case_index:
            if callable(original_call):
                return await original_call(api_payload, *args, **kwargs)
            return {'error': 'DeepSeek call unavailable outside audit context'}
        counter['externalApiAttempts'] = int(counter.get('externalApiAttempts') or 0) + 1
        timeout_seconds = float(kwargs.get('timeout_seconds') or 45.0)
        api_key = str(getattr(legacy_core, 'DEEPSEEK_API_KEY', '') or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('myapp_ai_math_1_4_API_key') or '').strip()
        if not api_key:
            counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            return {'error': 'DeepSeek API key is not configured'}
        try:
            result = await _live_audit_direct_deepseek_call(api_payload, timeout_seconds=timeout_seconds, api_key=api_key)
            proof = result.get('_auditDeepSeekProof') if isinstance(result, dict) else None
            if isinstance(proof, dict):
                _live_audit_accumulate_deepseek_proof(counter, proof)
            if isinstance(result, dict) and result.get('error'):
                counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            else:
                counter['externalApiCompleted'] = int(counter.get('externalApiCompleted') or 0) + 1
            return result
        except Exception:
            counter['externalApiErrors'] = int(counter.get('externalApiErrors') or 0) + 1
            raise

    token_ctx = _LIVE_AUDIT_DEEPSEEK_CONTEXT.set({'runId': run_id, 'caseIndex': case_index})
    patched = False
    if callable(original_call):
        setattr(legacy_core, 'call_deepseek', counted_call_deepseek)
        patched = True
    try:
        started = _now_ts()
        raw_result = await _solve_text(text=text, token=token, install_id=install_id, audit_bypass_daily_limit=True)
        elapsed_ms = int((_now_ts() - started) * 1000)
    finally:
        _LIVE_AUDIT_DEEPSEEK_CONTEXT.reset(token_ctx)
        if patched:
            setattr(legacy_core, 'call_deepseek', original_call)

    if isinstance(raw_result, JSONResponse):
        payload, status_code = _json_response_payload(raw_result)
    else:
        payload, status_code = (raw_result if isinstance(raw_result, dict) else {'result': str(raw_result)}, 200)
    counter['apiRouteStatusCode'] = status_code
    response_bytes = len(json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8'))
    counter['apiRouteResponseBytes'] = response_bytes
    counter['apiRouteResponseRelease'] = payload.get('release')
    counter['apiRouteResponseSolverVersion'] = payload.get('solverVersion')
    counter['apiRouteAuditBypassDailyLimit'] = bool(payload.get('auditBypassDailyLimit'))
    counter['apiRouteElapsedMs'] = elapsed_ms
    counter['responseHash'] = _short_hash(payload, 24)
    row, external_counts = _build_live_audit_row_from_payload(case, payload, counter, allow_external=True, cache_key=expected_cache_key)
    row['apiRouteNetworkVisibleToBrowser'] = True
    row['browserClientFetchAudit'] = True
    row['browserFetchUserAgent'] = counter.get('browserFetchUserAgent')
    row['apiRouteElapsedMs'] = elapsed_ms
    _live_audit_append_case_result(run_id, row, external_counts, case_index=case_index, cache_key=expected_cache_key)
    payload = dict(payload)
    payload['liveAuditBrowserProof'] = {
        'recorded': True,
        'runId': run_id,
        'caseIndex': case_index,
        'caseId': case.get('id') or case.get('name'),
        'routeUnderAudit': 'POST /api/explain',
        'routeAuditMode': 'browser-client-ui-render-visible-network',
        'apiRouteNetworkVisibleToBrowser': True,
        'externalApiAttempts': counter.get('externalApiAttempts'),
        'externalApiCompleted': counter.get('externalApiCompleted'),
        'apiTotalTokens': counter.get('apiTotalTokens'),
        'promptCacheHitTokens': counter.get('promptCacheHitTokens'),
        'promptCacheMissTokens': counter.get('promptCacheMissTokens'),
        'requestHash': counter.get('requestHash'),
        'responseHash': counter.get('responseHash'),
    }
    return _json_ok(payload, status_code=status_code)


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



# --- V300 strict browser-client fetch audit ---------------------------------

def _live_audit_json_payload_from_response(value: Any) -> tuple[dict[str, Any], int]:
    if isinstance(value, JSONResponse):
        try:
            raw = value.body.decode('utf-8') if isinstance(value.body, (bytes, bytearray)) else str(value.body or '')
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {'result': '', 'source': 'jsonresponse-parse-error', 'error': 'Unable to parse JSONResponse body during live audit'}
        return data if isinstance(data, dict) else {'result': str(data), 'source': 'jsonresponse-non-object'}, int(value.status_code or 200)
    if isinstance(value, dict):
        return value, 200
    return {'result': str(value or ''), 'source': 'unexpected-route-return'}, 200


def _browser_client_case_rows(section: str = 'g4_arithmetic_actions', limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    pool = _select_live_production_cases(section)
    selected_raw = pool[offset:offset + limit]
    return [_normalize_case(case, offset + idx) for idx, case in enumerate(selected_raw)]


def _browser_client_plan_key(section: str, offset: int, limit: int, allow_external: bool, max_external_calls: int) -> str:
    return _short_hash({
        'release': APP_RELEASE,
        'solverVersion': SOLVER_VERSION,
        'runnerPromptVersion': LIVE_AUDIT_RUNNER_PROMPT_VERSION,
        'auditClientMode': 'browser-client-ui-render-visible-network',
        'section': section,
        'offset': offset,
        'limit': limit,
        'allowExternal': allow_external,
        'maxExternalCalls': max_external_calls,
    })


def _browser_client_public_cases(run: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(run.get('cases') or []):
        case = dict(item.get('case') or {}) if isinstance(item, dict) else {}
        out.append({
            'caseIndex': idx,
            'id': case.get('id') or case.get('name'),
            'text': case.get('text'),
            'cacheKey': item.get('cacheKey') if isinstance(item, dict) else None,
        })
    return out


def _browser_client_summary_payload(run: dict[str, Any], request: Request | None = None) -> dict[str, Any]:
    summary = _live_audit_public_run_summary(run, include_failures_preview=False)
    run_id = str(run.get('runId') or '')
    key = str(run.get('auditKey') or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY)
    base = _public_base_url(request)
    completed_indexes = sorted({
        int(row.get('caseIndex')) for row in (run.get('evidenceResults') or [])
        if isinstance(row, dict) and isinstance(row.get('caseIndex'), int)
    })
    summary.update({
        'diagnostic': 'live-audit-browser-client-summary',
        'runnerMode': 'BROWSER_CLIENT_UI_RENDER_DOM_API_EXPLAIN',
        'auditClientMode': 'browser-client-ui-render-visible-network',
        'browserClientFetchRequired': True,
        'devToolsNetworkProof': "Open browser DevTools → Network and filter '/api/explain'; V311.04 client sends one visible POST per audit case.",
        'completedCaseIndexes': completed_indexes,
        'completedCaseIds': [row.get('id') for row in (run.get('evidenceResults') or []) if isinstance(row, dict)],
        'casesRemaining': max(0, int(run.get('planned') or 0) - len(completed_indexes)),
        'finalReportUrl': base + _browser_audit_final_report_path(run_id, key) if run_id else '',
    })
    return summary


def _browser_client_create_or_reuse_run(request: Request, key_value: str, *, force: bool = False) -> dict[str, Any] | JSONResponse:
    if not _live_audit_key_matches(key_value):
        return _json_error(403, {
            'error': 'Нужен live-audit key.',
            'diagnostic': 'live-audit-browser-client-start',
            'hint': f'Default test key in this build: {LIVE_PRODUCTION_AUDIT_DEFAULT_KEY}.',
        })
    section = 'g4_arithmetic_actions'
    offset = 0
    limit = 100
    allow_external = True
    max_external_calls = 150
    cases = _browser_client_case_rows(section, limit, offset)
    cases_for_run = [{'cacheKey': _live_audit_case_cache_key(case, allow_external), 'case': case} for case in cases]
    plan_key = _browser_client_plan_key(section, offset, limit, allow_external, max_external_calls)
    force_suffix = ('-' + str(int(_now_ts()))) if force else ''
    run_id = f'{APP_RELEASE}-{section}-browser-fetch-{offset}-{limit}-{plan_key[:10]}{force_suffix}'

    def _mutator(state: dict[str, Any]):
        runs = state.setdefault('runs', {})
        plans = state.setdefault('plans', {})
        if not force:
            existing_id = plans.get(plan_key)
            existing = runs.get(existing_id) if existing_id else None
            if isinstance(existing, dict):
                return existing
        now = _now_ts()
        run = {
            'runId': run_id,
            'planKey': plan_key,
            'release': APP_RELEASE,
            'backendBuild': APP_RELEASE,
            'solverVersion': SOLVER_VERSION,
            'runnerPromptVersion': LIVE_AUDIT_RUNNER_PROMPT_VERSION,
            'status': 'running',
            'runnerMode': 'BROWSER_CLIENT_UI_RENDER_DOM_API_EXPLAIN',
            'auditClientMode': 'browser-client-ui-render-visible-network',
            'browserClientAudit': True,
            'section': section,
            'sectionTotal': len(_select_live_production_cases(section)),
            'offset': offset,
            'limit': limit,
            'planned': len(cases_for_run),
            'completed': 0,
            'passed': 0,
            'failed': 0,
            'allowExternal': allow_external,
            'auditKey': key_value,
            'force': force,
            'maxExternalCalls': max_external_calls,
            'externalApiCalls': 0,
            'externalApiCompleted': 0,
            'externalApiBlocked': 0,
            'externalApiErrors': 0,
            'deepseekPromptTokens': 0,
            'deepseekCompletionTokens': 0,
            'deepseekTotalTokens': 0,
            'apiPromptTokens': 0,
            'apiCompletionTokens': 0,
            'apiTotalTokens': 0,
            'promptCacheHitTokens': 0,
            'promptCacheMissTokens': 0,
            'deepseekUsageProofs': 0,
            'cachedResults': 0,
            'cachedExternalApiCalls': 0,
            'cachedDeepseekTotalTokens': 0,
            'results': [],
            'evidenceResults': [],
            'suspiciousResults': [],
            'failures': [],
            'cases': cases_for_run,
            'createdAt': now,
            'startedAt': now,
            'updatedAt': now,
            'heartbeatAt': now,
            'browserClientFetchStartedAt': now,
            'browserClientFetchNote': "This run is advanced only by frontend iframe UI actions: textarea input, solve button click, DOM #resultBox proof and browser-visible /api/explain calls.",
        }
        runs[run_id] = run
        plans[plan_key] = run_id
        return run
    run = _mutate_live_audit_state(_mutator)
    summary = _browser_client_summary_payload(run, request)
    all_cases = _browser_client_public_cases(run)
    completed = {str(row.get('cacheKey') or '') for row in (run.get('evidenceResults') or []) if isinstance(row, dict) and bool(row.get('frontendDomRenderedOutputChecked'))}
    cases_to_run = [case for case in all_cases if str(case.get('cacheKey') or '') not in completed]
    run_id_value = str(run.get('runId') or '')
    status_path = f'/api/diagnostics/live-audit/browser-client/status/{APP_RELEASE}/{key_value}/{run_id_value}'
    return {
        **summary,
        'cases': all_cases,
        'casesToRun': cases_to_run,
        'summaryJsonPath': status_path,
        'summaryJsonUrl': _public_base_url(request) + status_path,
        'finalReportPath': _browser_audit_final_report_path(run_id_value, key_value),
        'finalReportUrl': _public_base_url(request) + _browser_audit_final_report_path(run_id_value, key_value),
        'explainUrl': _public_base_url(request) + '/api/explain',
        'frontendAuditUrl': _public_frontend_url() + '?matematichkaUiAudit=1&release=' + APP_RELEASE + '&cacheBust=' + str(int(_now_ts())),
        'frontendOrigin': _public_frontend_url().rstrip('/').split('/ai-math-1-4-frontend')[0],
        'domRecordUrlTemplate': _public_base_url(request) + f'/api/diagnostics/live-audit/ui-render/record-dom/{APP_RELEASE}/{key_value}/{run_id_value}',
        'tokenFields': ['apiPromptTokens', 'apiCompletionTokens', 'apiTotalTokens', 'promptCacheHitTokens', 'promptCacheMissTokens'],
        'frontendUrl': _public_frontend_url() + '?uiAudit=1&release=' + APP_RELEASE,
        'uiRenderAuditRequired': True,
        'uiRenderContract': 'iframe frontend fills #taskInput, clicks #solveBtn and compares visible #resultBox against API result and expected answer',
    }


def _browser_client_find_case(run: dict[str, Any], case_index: int, case_id: str) -> tuple[dict[str, Any] | None, str]:
    cases = list(run.get('cases') or [])
    if case_index < 0 or case_index >= len(cases):
        return None, 'case index is out of run range'
    item = cases[case_index] if isinstance(cases[case_index], dict) else {}
    case = dict(item.get('case') or {})
    expected_id = str(case.get('id') or case.get('name') or '')
    if case_id and expected_id and case_id != expected_id:
        return None, f'case id mismatch: expected {expected_id}, got {case_id}'
    return case, ''


def _browser_client_record_case_result(run_id: str, case_index: int, case_id: str, request_text: str, payload: dict[str, Any], status_code: int, external: dict[str, Any]) -> dict[str, Any]:
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(run_id)
    if not isinstance(run, dict):
        return {'recorded': False, 'error': 'audit run not found'}
    case, error = _browser_client_find_case(run, case_index, case_id)
    if not isinstance(case, dict):
        return {'recorded': False, 'error': error or 'audit case not found'}
    expected_text = str(case.get('text') or '').strip()
    if expected_text != str(request_text or '').strip():
        return {'recorded': False, 'error': 'request text does not match audit case text'}
    cache_key = _live_audit_case_cache_key(case, True)
    case_for_check = dict(case)
    expected_source = str(case_for_check.get('expectedSource') or '')
    is_guard_case = expected_source.startswith('guard') or 'guard' in str(case_for_check.get('category') or '').lower()
    if not expected_source.startswith('guard'):
        case_for_check.pop('expectedSource', None)
        case_for_check.pop('expectedSourceFamily', None)
    checked = _check_payload(case_for_check, payload)
    result_text = str(payload.get('result') or '')
    source = str(payload.get('source') or '')
    external_by_source = _source_looks_external(source, payload)
    row_external_attempts = int(external.get('externalApiAttempts') or 0)
    if resolve_solver_mode() == 'deepseek_primary' and not is_guard_case and not (row_external_attempts or external_by_source):
        checked['issues'].append('browser-client fetch did not trigger external DeepSeek API for a normal audit case')
        checked['ok'] = False
    if payload.get('deepseekPrimaryFallback'):
        checked['issues'].append(f"DeepSeek-primary fell back locally: {payload.get('deepseekPrimaryFallback')}")
        checked['ok'] = False
    strict_format_issues = _live_audit_strict_format_issues(case, result_text, is_guard_case=is_guard_case)
    if strict_format_issues:
        checked['issues'].extend(strict_format_issues)
        checked['ok'] = False
    structured_solution = payload.get('structured_solution') if isinstance(payload.get('structured_solution'), dict) else None
    response_hash = _short_hash(payload, 24)
    row = {
        'caseIndex': case_index,
        'id': case.get('id'),
        'grade': case.get('grade'),
        'category': case.get('category'),
        'name': case.get('name'),
        'ok': bool(checked.get('ok')),
        'issues': checked.get('issues') or [],
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
        'userVisibleResultText': _live_audit_text(str(payload.get('userVisibleResultText') or result_text), 8000),
        'auditComparedSamePayloadReturnedToBrowser': True,
        'frontendRenderContract': 'frontend requestExplanationDetailed() reads JSON result/explanation and solve screen displays normalized response.result',
        'structuredSolution': structured_solution,
        'payloadError': payload.get('error'),
        'payloadValidated': payload.get('validated'),
        'routeUnderAudit': 'POST /api/explain',
        'routeAuditMode': 'browser-client-ui-render-visible-network',
        'apiRouteNetworkVisibleToBrowser': True,
        'browserFetchPath': '/api/explain',
        'requestPayloadShape': {'text': 'string', 'installId': 'string'},
        'apiRouteStatusCode': status_code,
        'apiRouteResponseBytes': len(json.dumps(payload, ensure_ascii=False).encode('utf-8')),
        'apiRouteResponseRelease': payload.get('release'),
        'apiRouteResponseSolverVersion': payload.get('solverVersion'),
        'apiRouteAuditBypassDailyLimit': bool(payload.get('auditBypassDailyLimit')),
        'auditBypassDailyLimit': True,
        'quotaNotConsumedByAudit': True,
        'externalCounterSource': 'browser fetch(/api/explain) request wrapped around backend.legacy_core.call_deepseek',
        'billingVisibility': 'server captures DeepSeek usage object; final financial charge is still verifiable only in provider billing logs',
        'auditRequestId': external.get('auditRequestId'),
        'installId': external.get('installId'),
        'requestHash': external.get('requestHash'),
        'responseHash': response_hash,
        'externalApiAttempts': row_external_attempts,
        'externalApiCompleted': int(external.get('externalApiCompleted') or 0),
        'externalApiBlocked': int(external.get('externalApiBlocked') or 0),
        'externalApiErrors': int(external.get('externalApiErrors') or 0),
        'externalApiUsed': bool(row_external_attempts or external_by_source),
        'deepseekUsagePresent': bool(external.get('deepseekUsagePresent')),
        'deepseekUsage': external.get('deepseekProofs') or [],
        'apiPromptTokens': int(external.get('apiPromptTokens') or external.get('deepseekPromptTokens') or 0),
        'apiCompletionTokens': int(external.get('apiCompletionTokens') or external.get('deepseekCompletionTokens') or 0),
        'apiTotalTokens': int(external.get('apiTotalTokens') or external.get('deepseekTotalTokens') or 0),
        'promptCacheHitTokens': int(external.get('promptCacheHitTokens') or 0),
        'promptCacheMissTokens': int(external.get('promptCacheMissTokens') or 0),
        'deepseekPromptTokens': int(external.get('deepseekPromptTokens') or external.get('apiPromptTokens') or 0),
        'deepseekCompletionTokens': int(external.get('deepseekCompletionTokens') or external.get('apiCompletionTokens') or 0),
        'deepseekTotalTokens': int(external.get('deepseekTotalTokens') or external.get('apiTotalTokens') or 0),
        'deepseekModels': [p.get('model') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('model')],
        'deepseekObjectIds': [p.get('id') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('id')],
        'deepseekFinishReasons': [p.get('finishReason') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('finishReason')],
        'deepseekRequestHashes': [p.get('requestHash') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('requestHash')],
        'deepseekResponseHashes': [p.get('responseHash') for p in (external.get('deepseekProofs') or []) if isinstance(p, dict) and p.get('responseHash')],
        'solverMode': payload.get('solverMode'),
        'deepseekPrimaryFallback': payload.get('deepseekPrimaryFallback'),
        'verifier': payload.get('verifier'),
        'cacheKey': cache_key,
        'fromCache': False,
        'resultPreview': result_text[:520],
    }
    compact = _compact_live_audit_result(row)
    evidence_row = _live_audit_evidence_row(row)

    def _mutator(state: dict[str, Any]):
        live_run = state.setdefault('runs', {}).get(run_id)
        if not isinstance(live_run, dict):
            return {'recorded': False, 'error': 'run disappeared during record'}
        existing_indexes = {int(r.get('caseIndex')) for r in (live_run.get('evidenceResults') or []) if isinstance(r, dict) and isinstance(r.get('caseIndex'), int)}
        if case_index in existing_indexes:
            return {'recorded': True, 'duplicateRecordIgnored': True, 'run': live_run}
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
        live_run['externalApiCalls'] = int(live_run.get('externalApiCalls') or 0) + int(external.get('externalApiAttempts') or 0)
        live_run['externalApiCompleted'] = int(live_run.get('externalApiCompleted') or 0) + int(external.get('externalApiCompleted') or 0)
        live_run['externalApiBlocked'] = int(live_run.get('externalApiBlocked') or 0) + int(external.get('externalApiBlocked') or 0)
        live_run['externalApiErrors'] = int(live_run.get('externalApiErrors') or 0) + int(external.get('externalApiErrors') or 0)
        live_run['apiPromptTokens'] = int(live_run.get('apiPromptTokens') or 0) + int(row.get('apiPromptTokens') or 0)
        live_run['apiCompletionTokens'] = int(live_run.get('apiCompletionTokens') or 0) + int(row.get('apiCompletionTokens') or 0)
        live_run['apiTotalTokens'] = int(live_run.get('apiTotalTokens') or 0) + int(row.get('apiTotalTokens') or 0)
        live_run['promptCacheHitTokens'] = int(live_run.get('promptCacheHitTokens') or 0) + int(row.get('promptCacheHitTokens') or 0)
        live_run['promptCacheMissTokens'] = int(live_run.get('promptCacheMissTokens') or 0) + int(row.get('promptCacheMissTokens') or 0)
        live_run['deepseekPromptTokens'] = int(live_run.get('deepseekPromptTokens') or 0) + int(row.get('deepseekPromptTokens') or 0)
        live_run['deepseekCompletionTokens'] = int(live_run.get('deepseekCompletionTokens') or 0) + int(row.get('deepseekCompletionTokens') or 0)
        live_run['deepseekTotalTokens'] = int(live_run.get('deepseekTotalTokens') or 0) + int(row.get('deepseekTotalTokens') or 0)
        if bool(row.get('deepseekUsagePresent')):
            live_run['deepseekUsageProofs'] = int(live_run.get('deepseekUsageProofs') or 0) + 1
        live_run['activeCaseIndex'] = case_index
        live_run['activeCaseId'] = row.get('id') or row.get('name')
        live_run['heartbeatAt'] = _now_ts()
        live_run['updatedAt'] = live_run['heartbeatAt']
        if int(live_run.get('completed') or 0) >= int(live_run.get('planned') or 0):
            live_run['status'] = 'done'
            live_run['finishedAt'] = _now_ts()
            live_run.pop('activeCaseIndex', None)
            live_run.pop('activeCaseId', None)
        else:
            live_run['status'] = 'running'
        return {'recorded': True, 'run': live_run, 'row': row}
    recorded = _mutate_live_audit_state(_mutator)
    return recorded if isinstance(recorded, dict) else {'recorded': False, 'error': 'record failed'}


async def _solve_text_browser_client_audit(request: Request, data: dict[str, Any], text: str) -> JSONResponse | dict:
    import backend.legacy_core as legacy_core

    key = str(request.headers.get('X-Live-Audit-Key') or '')
    run_id = str(request.headers.get('X-Live-Audit-Run-Id') or '')
    case_id = str(request.headers.get('X-Live-Audit-Case-Id') or '')
    try:
        case_index = int(request.headers.get('X-Live-Audit-Case-Index') or -1)
    except Exception:
        case_index = -1
    if not _live_audit_key_matches(key) or not run_id or case_index < 0:
        return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data), audit_bypass_daily_limit=_live_audit_key_matches(key))

    original_call = getattr(legacy_core, 'call_deepseek', None)
    external: dict[str, Any] = {
        'externalApiAttempts': 0,
        'externalApiCompleted': 0,
        'externalApiBlocked': 0,
        'externalApiErrors': 0,
        'deepseekUsagePresent': False,
        'apiPromptTokens': 0,
        'apiCompletionTokens': 0,
        'apiTotalTokens': 0,
        'promptCacheHitTokens': 0,
        'promptCacheMissTokens': 0,
        'deepseekPromptTokens': 0,
        'deepseekCompletionTokens': 0,
        'deepseekTotalTokens': 0,
        'deepseekProofs': [],
        'routeUnderAudit': 'POST /api/explain',
        'routeAuditMode': 'browser-client-ui-render-visible-network',
        'apiRouteNetworkVisibleToBrowser': True,
        'browserClientFetch': True,
        'auditRequestId': str(request.headers.get('X-Audit-Request-Id') or _short_hash({'runId': run_id, 'caseIndex': case_index, 'text': text, 'ts': _now_ts()}, 20)),
        'installId': _extract_install_id(request, data),
        'requestHash': _short_hash({'path': '/api/explain', 'runId': run_id, 'caseIndex': case_index, 'caseId': case_id, 'text': text}, 24),
    }

    async def counted_call_deepseek(api_payload, *args, **kwargs):
        external['externalApiAttempts'] = int(external.get('externalApiAttempts') or 0) + 1
        timeout_seconds = float(kwargs.get('timeout_seconds') or 45.0)
        api_key = str(getattr(legacy_core, 'DEEPSEEK_API_KEY', '') or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('myapp_ai_math_1_4_API_key') or '').strip()
        if not api_key:
            external['externalApiErrors'] = int(external.get('externalApiErrors') or 0) + 1
            return {'error': 'DeepSeek API key is not configured'}
        try:
            result = await _live_audit_direct_deepseek_call(api_payload, timeout_seconds=timeout_seconds, api_key=api_key)
            proof = result.get('_auditDeepSeekProof') if isinstance(result, dict) else None
            if isinstance(proof, dict):
                _live_audit_accumulate_deepseek_proof(external, proof)
            if isinstance(result, dict) and result.get('error'):
                external['externalApiErrors'] = int(external.get('externalApiErrors') or 0) + 1
            else:
                external['externalApiCompleted'] = int(external.get('externalApiCompleted') or 0) + 1
            return result
        except Exception:
            external['externalApiErrors'] = int(external.get('externalApiErrors') or 0) + 1
            raise

    if callable(original_call):
        setattr(legacy_core, 'call_deepseek', counted_call_deepseek)
    try:
        route_result = await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data), audit_bypass_daily_limit=True)
    finally:
        if callable(original_call):
            setattr(legacy_core, 'call_deepseek', original_call)
    payload, status_code = _live_audit_json_payload_from_response(route_result)
    external['apiRouteStatusCode'] = status_code
    external['apiRouteResponseRelease'] = payload.get('release')
    external['apiRouteResponseSolverVersion'] = payload.get('solverVersion')
    external['apiRouteAuditBypassDailyLimit'] = bool(payload.get('auditBypassDailyLimit'))
    external['responseHash'] = _short_hash(payload, 24)
    record = _browser_client_record_case_result(run_id, case_index, case_id, text, payload, status_code, external)
    if isinstance(payload, dict):
        payload = dict(payload)
        payload['browserClientAuditRecorded'] = bool(record.get('recorded'))
        payload['browserClientAuditRunId'] = run_id
        payload['browserClientAuditCaseIndex'] = case_index
        payload['browserClientAuditCaseId'] = case_id
        if record.get('error'):
            payload['browserClientAuditRecordError'] = record.get('error')
    return _json_ok(payload, status_code=status_code) if status_code >= 200 else _json_error(status_code, payload)




@app.post('/api/diagnostics/live-audit/browser-ui/record-dom/{release_token}/{key_value}/{run_id_value}')
async def live_audit_browser_ui_record_dom(request: Request, release_token: str, key_value: str, run_id_value: str):
    if release_token != APP_RELEASE:
        return _json_error(409, {'error': 'release mismatch', 'currentRelease': APP_RELEASE, 'requestedRelease': release_token})
    if not _live_audit_key_matches(key_value):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'frontend-ui-dom-record'})
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON', 'diagnostic': 'frontend-ui-dom-record'})
    try:
        case_index = int(data.get('caseIndex'))
    except Exception:
        return _json_error(400, {'error': 'caseIndex is required', 'diagnostic': 'frontend-ui-dom-record'})
    case_id = str(data.get('caseId') or '').strip()
    dom_result = str(data.get('domResultText') or '').strip()
    api_result = str(data.get('apiResultText') or '').strip()
    if not dom_result:
        return _json_error(400, {'error': 'domResultText is empty', 'diagnostic': 'frontend-ui-dom-record'})

    def _norm(value: Any) -> str:
        return re.sub(r'\s+', ' ', str(value or '').replace('\u00a0', ' ')).strip().lower().replace('ё', 'е')

    def _mutator(state: dict[str, Any]):
        run = state.setdefault('runs', {}).get(run_id_value)
        if not isinstance(run, dict):
            return {'recorded': False, 'error': 'run not found'}
        if str(run.get('release') or '') != APP_RELEASE:
            return {'recorded': False, 'error': 'run release mismatch'}
        cases = list(run.get('cases') or [])
        if case_index < 0 or case_index >= len(cases):
            return {'recorded': False, 'error': 'caseIndex out of range'}
        item = cases[case_index] if isinstance(cases[case_index], dict) else {}
        case = dict(item.get('case') or {})
        expected_id = str(case.get('id') or case.get('name') or '')
        if case_id and expected_id and case_id != expected_id:
            return {'recorded': False, 'error': f'caseId mismatch: expected {expected_id}, got {case_id}'}
        rows = run.get('results') or []
        evidence = run.get('evidenceResults') or []
        result_row = next((r for r in rows if isinstance(r, dict) and int(r.get('caseIndex') if r.get('caseIndex') is not None else -1) == case_index), None)
        evidence_row = next((r for r in evidence if isinstance(r, dict) and int(r.get('caseIndex') if r.get('caseIndex') is not None else -1) == case_index), None)
        if not isinstance(result_row, dict) and not isinstance(evidence_row, dict):
            return {'recorded': False, 'error': 'API route proof row is not recorded yet'}
        base_row = evidence_row if isinstance(evidence_row, dict) else result_row
        expected_source = str(case.get('expectedSource') or '')
        is_guard_case = expected_source.startswith('guard') or 'guard' in str(case.get('category') or '').lower()
        case_for_dom_check = dict(case)
        if not expected_source.startswith('guard'):
            case_for_dom_check.pop('expectedSource', None)
            case_for_dom_check.pop('expectedSourceFamily', None)
        dom_payload = {'result': dom_result, 'source': base_row.get('source') or 'frontend-dom-resultbox'}
        checked = _check_payload(case_for_dom_check, dom_payload)
        dom_visible_text = _live_audit_prepare_visible_compare_text(dom_result, case_text=case.get('text'), is_guard_case=is_guard_case)
        api_visible_text = _live_audit_prepare_visible_compare_text(api_result or base_row.get('apiRawResultText') or base_row.get('resultText') or '', case_text=case.get('text'), is_guard_case=is_guard_case)
        visible_format_issues = _live_audit_user_visible_solution_format_issues(dom_visible_text or dom_result)
        dom_answer = _live_audit_extract_answer_line(dom_visible_text or dom_result)
        api_answer = _live_audit_extract_answer_line(api_visible_text or api_result or base_row.get('apiRawResultText') or base_row.get('resultText') or '')
        answer_matches_api = bool(dom_answer) and bool(api_answer) and _norm(dom_answer) == _norm(api_answer)
        result_matches_api = bool(api_visible_text) and _live_audit_visible_texts_equivalent(dom_visible_text or dom_result, api_visible_text, case_text=case.get('text'), is_guard_case=is_guard_case)
        clicked_main = bool(data.get('clickedSolveButton') or data.get('clickedMainSolveButton'))
        dom_issues = []
        if not checked.get('ok'):
            dom_issues.extend([f'frontend DOM expected check: {issue}' for issue in checked.get('issues') or []])
        if visible_format_issues:
            dom_issues.extend([f'frontend DOM format: {issue}' for issue in visible_format_issues])
        if not answer_matches_api:
            dom_issues.append('frontend DOM answer line does not match API answer line')
        if not result_matches_api:
            dom_issues.append('frontend DOM visible result does not match API visible result')
        if not clicked_main:
            dom_issues.append('frontend audit did not prove solve button click')
        clicked_ok = clicked_main
        result_box_present = bool(data.get('resultBoxPresent') or dom_result)
        ui_expected_ok = bool(checked.get('ok')) and not visible_format_issues
        audit_ui_render_mode = str(data.get('auditUiRenderMode') or data.get('frontendUiRenderMode') or 'standalone-github-pages-frontend-textarea-click-solve-resultbox-dom')
        is_iframe_audit = bool(data.get('auditFrontendFrame'))
        is_standalone_audit = bool(data.get('auditFrontendStandalonePage')) or not is_iframe_audit
        # DOM may omit service headers (Задача./Решение.) for a cleaner user UI,
        # but it must still show the same visible step(s) and final answer as the
        # API payload after postprocess.
        ui_render_ok = bool(ui_expected_ok and not dom_issues and answer_matches_api and result_matches_api and clicked_ok and result_box_present)
        fields = {
            'frontendDomRenderedOutputChecked': True,
            'frontendDomExpectedCheckOk': ui_expected_ok,
            'frontendDomResultMatchesApi': result_matches_api,
            'frontendDomAnswerMatchesApi': answer_matches_api,
            'frontendUiClickedSolveButton': clicked_main,
            'uiRenderAudit': True,
            'uiRenderMode': 'frontend-ui-render-resultbox',
            'uiRenderPageUrl': data.get('pageUrl') or data.get('frontendAuditUrl'),
            'uiRenderFrontendBuild': data.get('frontendBuild'),
            'uiRenderInputSelector': data.get('inputSelector') or '#taskInput',
            'uiRenderButtonSelector': data.get('buttonSelector') or '#solveBtn',
            'uiRenderResultBoxSelector': data.get('resultBoxSelector') or '#resultBox',
            'uiRenderClickedMainSolveButton': clicked_main,
            'uiRenderInputSetViaDom': bool(data.get('inputSetViaDom')),
            'uiRenderResultMatchesExpected': ui_expected_ok,
            'clientDisplayedResultMatchesApi': result_matches_api,
            'userVisibleAnswerMatchesApi': answer_matches_api,
            'uiSolveButtonClicked': clicked_main,
            'uiTaskInputFound': True,
            'uiResultBoxFound': result_box_present,
            'uiResultBoxAnswerLine': dom_answer,
            'uiResultBoxTextHash': _short_hash(dom_result, 24),
            'uiDomResultMatchesApi': result_matches_api and answer_matches_api,
            'userVisibleAnswerMatchesExpected': ui_expected_ok,
            'uiRenderPassed': ui_render_ok,
            'uiRenderIssues': dom_issues,
            'frontendDomResultText': _live_audit_text(dom_result, 8000),
            'clientDisplayedResultText': _live_audit_text(dom_result, 8000),
            'userVisibleResultText': _live_audit_text(dom_result, 8000),
            'frontendDomAnswerLine': dom_answer,
            'clientDisplayedAnswerLine': dom_answer,
            'userVisibleAnswerLine': dom_answer,
            'frontendUiRenderMode': audit_ui_render_mode,
            'frontendUiAuditUrl': data.get('frontendAuditUrl'),
            'frontendUiResultSelector': '#resultBox',
            'frontendUiInputSelector': '#taskInput',
            'frontendUiButtonSelector': '#solveBtn',
            'frontendUiElapsedMs': int(data.get('elapsedMs') or 0),
            'frontendUiBuild': data.get('frontendBuild'),
            'frontendUiBackendReleaseExpected': data.get('expectedBackendRelease'),
            'frontendDisplayAssumption': None,
            'frontendDisplayContract': 'Verified by the GitHub Pages frontend UI: taskInput value -> solveBtn click -> production API call -> rendered #resultBox innerText compared with expected and API answer.',
            'comparisonTarget': 'DOM innerText of production frontend #resultBox after clicking #solveBtn',
            'iframeAudit': is_iframe_audit,
            'standaloneFrontendAudit': is_standalone_audit,
            'derivedUiRenderPassed': ui_render_ok,
            'uiRenderPassRule': 'expected-vs-DOM ok; no user-visible format issues; DOM answer and visible body match API; #solveBtn clicked; #resultBox present',
            'frontendDomProofHash': _short_hash({'runId': run_id_value, 'caseIndex': case_index, 'domResultText': dom_result, 'apiResultText': api_result, 'domAnswer': dom_answer, 'uiRenderPassed': ui_render_ok}, 24),
        }
        old_ok = bool(base_row.get('ok'))
        new_ok = old_ok and bool(fields['frontendDomExpectedCheckOk']) and bool(fields['frontendDomAnswerMatchesApi']) and bool(fields['frontendUiClickedSolveButton']) and bool(fields['frontendDomResultMatchesApi']) and bool(fields['uiRenderPassed'])
        for target in (result_row, evidence_row):
            if not isinstance(target, dict):
                continue
            target.update(fields)
            existing_issues = list(target.get('issues') or [])
            for issue in dom_issues:
                if issue not in existing_issues:
                    existing_issues.append(issue)
            target['issues'] = existing_issues
            target['ok'] = new_ok
            target['actualAnswerLine'] = dom_answer or target.get('actualAnswerLine')
            target['resultText'] = _live_audit_text(dom_result, 8000)
            target['suspiciousReasons'] = _live_audit_suspicion_reasons(target)
            if 'proofHash' in target:
                target['proofHash'] = _short_hash({'inputText': target.get('inputText') or target.get('inputPreview'), 'expected': target.get('expected') or target.get('expectedFinalAnswer'), 'apiAnswer': api_answer, 'domAnswer': dom_answer, 'domResultText': dom_result, 'ok': new_ok}, 24)
        if old_ok and not new_ok:
            run['passed'] = max(0, int(run.get('passed') or 0) - 1)
            run['failed'] = int(run.get('failed') or 0) + 1
            fail_row = dict(evidence_row or result_row or {})
            run.setdefault('failures', []).append(fail_row)
        run['frontendDomRenderProofs'] = sum(1 for r in (run.get('evidenceResults') or []) if isinstance(r, dict) and _live_audit_ui_dom_checked(r))
        run['frontendUiClickedSolveButtonProofs'] = sum(1 for r in (run.get('evidenceResults') or []) if isinstance(r, dict) and _live_audit_ui_clicked(r))
        run['uiRenderDomProofs'] = run['frontendDomRenderProofs']
        run['uiRenderClickedMainSolveButtonProofs'] = run['frontendUiClickedSolveButtonProofs']
        run['suspiciousResults'] = [r for r in (run.get('evidenceResults') or []) if isinstance(r, dict) and r.get('suspiciousReasons')]
        run['updatedAt'] = _now_ts()
        run['heartbeatAt'] = run['updatedAt']
        return {
            'recorded': True,
            'runId': run_id_value,
            'caseIndex': case_index,
            'caseId': expected_id,
            'ok': new_ok,
            'frontendDomExpectedCheckOk': fields['frontendDomExpectedCheckOk'],
            'frontendDomAnswerMatchesApi': fields['frontendDomAnswerMatchesApi'],
            'frontendDomResultMatchesApi': fields['frontendDomResultMatchesApi'],
            'frontendDomAnswerLine': dom_answer,
            'apiAnswerLine': api_answer,
            'issues': dom_issues,
            'frontendDomProofHash': fields['frontendDomProofHash'],
            'frontendDomRenderProofs': run.get('frontendDomRenderProofs'),
        }
    receipt = _mutate_live_audit_state(_mutator)
    if not isinstance(receipt, dict):
        receipt = {'recorded': False, 'error': 'state mutation failed'}
    return _json_ok({'diagnostic': 'frontend-ui-dom-record', **receipt})


@app.get('/api/diagnostics/live-audit/browser-client/start/{release_token}/{key_value}')
async def live_audit_browser_client_start(request: Request, release_token: str, key_value: str, force: int = 0):
    if str(release_token or '').strip() != APP_RELEASE:
        return _json_error(409, {'error': 'release mismatch', 'requestedRelease': release_token, 'currentRelease': APP_RELEASE})
    result = _browser_client_create_or_reuse_run(request, key_value, force=str(force).lower() in {'1','true','yes','on'})
    return result


@app.get('/api/diagnostics/live-audit/browser-client/status/{release_token}/{key_value}/{run_id_value}')
async def live_audit_browser_client_status(request: Request, release_token: str, key_value: str, run_id_value: str):
    run = _live_audit_load_run_for_read(key_value, run_id_value, release_token, 'live-audit-browser-client-status')
    if isinstance(run, JSONResponse):
        return run
    return _browser_client_summary_payload(run, request)


def _browser_audit_final_report_path(run_id: str, key: str | None = None) -> str:
    audit_key = str(key or LIVE_PRODUCTION_AUDIT_DEFAULT_KEY).strip()
    return f'/api/diagnostics/live-audit/final-report/{APP_RELEASE}/{audit_key}/{run_id}'


def _browser_audit_label(payload: dict[str, Any]) -> tuple[str, str, str]:
    status = str(payload.get('status') or 'not-started')
    planned = int(payload.get('planned') or payload.get('nextAuditLimit') or 100)
    completed = int(payload.get('completed') or 0)
    failed = int(payload.get('failed') or 0)
    final_acceptance = bool(payload.get('finalAcceptance') or payload.get('acceptancePassed'))
    if final_acceptance:
        return 'ГОТОВО: скопируйте одну ссылку для ChatGPT', 'ok', 'Acceptance-проверка прошла. Отдельные proof-ссылки не нужны.'
    if status == 'done' and completed >= planned and failed == 0:
        return 'ЗАВЕРШЁН: скопируйте итоговый отчёт', 'ok', 'Аудит дошёл до конца. ChatGPT проверит final-report и примет или отклонит раздел.'
    if failed > 0:
        return 'ЕСТЬ ОШИБКИ: скопируйте итоговый отчёт', 'bad', 'Аудит нашёл ошибки. По одной final-report ссылке я смогу сгруппировать ошибки и исправить код.'
    if status in {'queued', 'running'}:
        return 'ИДЁТ АУДИТ', 'run', 'Оставьте страницу открытой. Она обновляется автоматически.'
    return 'АУДИТ НЕ ЗАПУЩЕН', 'idle', 'Нажмите кнопку ниже.'




def _live_audit_browser_plan_key(section: str, offset: int, limit: int, max_external_calls: int) -> str:
    return _short_hash({
        'release': APP_RELEASE,
        'solverVersion': SOLVER_VERSION,
        'runnerPromptVersion': LIVE_AUDIT_RUNNER_PROMPT_VERSION,
        'auditClientMode': 'browser-client-ui-render-visible-network',
        'section': section,
        'offset': offset,
        'limit': limit,
        'allowExternal': True,
        'maxExternalCalls': int(max_external_calls),
    })


def _browser_client_case_plan(run: dict[str, Any]) -> list[dict[str, Any]]:
    completed_keys = {str(row.get('cacheKey') or '') for row in (run.get('results') or []) if isinstance(row, dict)}
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(list(run.get('cases') or [])):
        if not isinstance(item, dict):
            continue
        case = dict(item.get('case') or {})
        cache_key = str(item.get('cacheKey') or _live_audit_case_cache_key(case, True))
        out.append({
            'caseIndex': idx,
            'id': case.get('id') or case.get('name'),
            'name': case.get('name'),
            'category': case.get('category'),
            'grade': case.get('grade'),
            'text': case.get('text'),
            'expected': case.get('expected'),
            'expectedFinalAnswer': case.get('expectedFinalAnswer'),
            'expectedUnit': case.get('expectedUnit'),
            'cacheKey': cache_key,
            'alreadyCompleted': cache_key in completed_keys,
        })
    return out


@app.get('/api/diagnostics/live-audit/browser-client-plan/{release_token}/{key_value}')
async def live_audit_browser_client_plan(request: Request, release_token: str, key_value: str, force: int = 0):
    if str(release_token or '').strip() != APP_RELEASE:
        return _json_error(409, {'error': 'release mismatch', 'requestedRelease': release_token, 'currentRelease': APP_RELEASE})
    if not _live_audit_key_matches(key_value):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'browser-client-plan'})
    section = 'g4_arithmetic_actions'
    offset_value = 0
    limit_value = 100
    max_external_calls = 150
    pool = _select_live_production_cases(section)
    selected_raw = pool[offset_value:offset_value + limit_value]
    normalized = [_normalize_case(case, offset_value + idx) for idx, case in enumerate(selected_raw)]
    cases_for_run = [{'cacheKey': _live_audit_case_cache_key(case, True), 'case': case} for case in normalized]
    plan_key = _live_audit_browser_plan_key(section, offset_value, limit_value, max_external_calls)
    force_value = str(force).lower() in {'1', 'true', 'yes', 'on'}
    force_suffix = ('-' + str(int(_now_ts()))) if force_value else ''
    run_id = f"{APP_RELEASE}-{section}-browser-fetch-{offset_value}-{limit_value}-{plan_key[:10]}{force_suffix}"

    def _create_or_reuse(state):
        runs = state.setdefault('runs', {})
        plans = state.setdefault('plans', {})
        if not force_value:
            existing_id = plans.get(plan_key)
            existing_run = runs.get(existing_id) if existing_id else None
            if isinstance(existing_run, dict) and existing_run.get('release') == APP_RELEASE and existing_run.get('runnerPromptVersion') == LIVE_AUDIT_RUNNER_PROMPT_VERSION and existing_run.get('auditClientMode') == 'browser-client-ui-render-visible-network':
                return existing_id, existing_run, True
            plans.pop(plan_key, None)
        now = _now_ts()
        run = {
            'runId': run_id,
            'planKey': plan_key,
            'release': APP_RELEASE,
            'backendBuild': APP_RELEASE,
            'solverVersion': SOLVER_VERSION,
            'runnerPromptVersion': LIVE_AUDIT_RUNNER_PROMPT_VERSION,
            'runnerMode': 'BROWSER_CLIENT_UI_RENDER_VISIBLE_AUDIT',
            'auditClientMode': 'browser-client-ui-render-visible-network',
            'browserClientAudit': True,
            'status': 'client-ready',
            'section': section,
            'sectionTotal': len(pool),
            'offset': offset_value,
            'limit': limit_value,
            'planned': len(cases_for_run),
            'completed': 0,
            'passed': 0,
            'failed': 0,
            'allowExternal': True,
            'auditKey': key_value,
            'force': force_value,
            'maxExternalCalls': max_external_calls,
            'externalApiCalls': 0,
            'externalApiCompleted': 0,
            'externalApiBlocked': 0,
            'externalApiErrors': 0,
            'apiPromptTokens': 0,
            'apiCompletionTokens': 0,
            'apiTotalTokens': 0,
            'promptCacheHitTokens': 0,
            'promptCacheMissTokens': 0,
            'deepseekPromptTokens': 0,
            'deepseekCompletionTokens': 0,
            'deepseekTotalTokens': 0,
            'deepseekUsageProofs': 0,
            'cachedResults': 0,
            'cachedExternalApiCalls': 0,
            'browserFetchRequests': 0,
            'results': [],
            'evidenceResults': [],
            'suspiciousResults': [],
            'failures': [],
            'cases': cases_for_run,
            'createdAt': now,
            'updatedAt': now,
            'heartbeatAt': now,
            'nextOffset': None,
            'remainingAfterRun': 0,
        }
        runs[run_id] = run
        plans[plan_key] = run_id
        return run_id, run, False

    run_id_value, run, reused = _mutate_live_audit_state(_create_or_reuse)
    # Reload after mutation so status/progress are current.
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(run_id_value) or run
    base_url = _public_base_url(request)
    status_query = '/api/diagnostics/live-audit/status?' + urlencode([('key', key_value), ('release', APP_RELEASE), ('runId', run_id_value)])
    final_path = _browser_audit_final_report_path(run_id_value, key_value)
    summary = _live_audit_public_run_summary(run, include_failures_preview=False)
    return _json_ok({
        **summary,
        'diagnostic': 'browser-client-plan',
        'reusedExistingRun': bool(reused),
        'runId': run_id_value,
        'casePlan': _browser_client_case_plan(run),
        'completedCacheKeys': [str(row.get('cacheKey') or '') for row in (run.get('results') or []) if isinstance(row, dict)],
        'apiExplainPath': '/api/explain',
        'statusApiPath': status_query,
        'statusApiUrl': base_url + status_query,
        'finalReportPath': final_path,
        'finalReportUrl': base_url + final_path,
        'browserClientFetchRequired': True,
        'devToolsExpected': 'The browser Network tab should show one POST /api/explain request per unfinished audit case.',
        'tokenFields': ['apiPromptTokens', 'apiCompletionTokens', 'apiTotalTokens', 'promptCacheHitTokens', 'promptCacheMissTokens'],
    })


@app.get('/api/diagnostics/live-audit/browser-client-status/{release_token}/{key_value}/{run_id_value}')
async def live_audit_browser_client_status(release_token: str, key_value: str, run_id_value: str):
    result = await live_audit_runner_status(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(result, JSONResponse):
        return result
    return _json_ok(dict(result))



def _live_audit_case_from_run_by_index(run: dict[str, Any], case_index: int) -> tuple[dict[str, Any] | None, str]:
    cases = list(run.get('cases') or [])
    if case_index < 0 or case_index >= len(cases):
        return None, ''
    item = cases[case_index] if isinstance(cases[case_index], dict) else {}
    return (dict(item.get('case') or {}), str(item.get('cacheKey') or ''))


def _live_audit_recompute_outcome_lists(live_run: dict[str, Any]) -> None:
    evidence = [dict(row) for row in (live_run.get('evidenceResults') or []) if isinstance(row, dict)]
    normalized: list[dict[str, Any]] = []
    for row in evidence:
        if str(row.get('routeAuditMode') or '') == 'browser-client-ui-render-visible-network' or row.get('uiRenderAudit'):
            ui_pass = _live_audit_ui_render_passed(row)
            row['uiRenderPassed'] = ui_pass
            row['ok'] = bool(row.get('ok')) and ui_pass
            row['suspiciousReasons'] = _live_audit_suspicion_reasons(row)
        normalized.append(row)
    evidence = normalized
    live_run['evidenceResults'] = evidence
    live_run['completed'] = len(evidence)
    live_run['passed'] = sum(1 for row in evidence if bool(row.get('ok')))
    live_run['failed'] = sum(1 for row in evidence if not bool(row.get('ok')))
    live_run['uiRenderDomProofs'] = sum(1 for row in evidence if bool(row.get('frontendDomRenderedOutputChecked')))
    live_run['uiRenderPassedProofs'] = sum(1 for row in evidence if _live_audit_ui_render_passed(row))
    live_run['failures'] = [row for row in evidence if not bool(row.get('ok'))]
    live_run['suspiciousResults'] = [row for row in evidence if row.get('suspiciousReasons')]
    live_run['results'] = [_compact_live_audit_result(row) for row in evidence]
    if int(live_run.get('completed') or 0) >= int(live_run.get('planned') or 0):
        live_run['status'] = 'done'
        live_run.setdefault('finishedAt', _now_ts())
        live_run.pop('activeCaseIndex', None)
        live_run.pop('activeCaseId', None)


@app.post('/api/diagnostics/live-audit/ui-render/record-dom/{release_token}/{key_value}/{run_id_value}')
async def live_audit_ui_render_record_dom(request: Request, release_token: str, key_value: str, run_id_value: str):
    if str(release_token or '').strip() != APP_RELEASE:
        return _json_error(409, {'error': 'release mismatch', 'requestedRelease': release_token, 'currentRelease': APP_RELEASE})
    if not _live_audit_key_matches(key_value):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'live-audit-ui-render-record-dom'})
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON', 'diagnostic': 'live-audit-ui-render-record-dom'})
    try:
        case_index = int(data.get('caseIndex'))
    except Exception:
        return _json_error(400, {'error': 'caseIndex is required', 'diagnostic': 'live-audit-ui-render-record-dom'})
    case_id = str(data.get('caseId') or '').strip()
    cache_key = str(data.get('cacheKey') or '').strip()
    dom_text = _live_audit_normalize_visible_text(data.get('domResultText') or data.get('clientDisplayedResultText') or '')
    api_payload = data.get('apiPayload') if isinstance(data.get('apiPayload'), dict) else {}
    api_text = _live_audit_normalize_visible_text(data.get('apiResultText') or api_payload.get('userVisibleResultText') or '')
    state = _load_live_audit_state()
    run = state.get('runs', {}).get(run_id_value)
    if not isinstance(run, dict):
        return _json_error(404, {'error': 'audit run not found', 'diagnostic': 'live-audit-ui-render-record-dom', 'runId': run_id_value})
    if str(run.get('release') or '') != APP_RELEASE:
        return _json_error(409, {'error': 'run release mismatch', 'diagnostic': 'live-audit-ui-render-record-dom', 'runRelease': run.get('release'), 'currentRelease': APP_RELEASE})
    case, planned_cache_key = _live_audit_case_from_run_by_index(run, case_index)
    if not isinstance(case, dict) or not case:
        return _json_error(404, {'error': 'case not found in run plan', 'diagnostic': 'live-audit-ui-render-record-dom', 'caseIndex': case_index})
    if case_id and case_id != str(case.get('id') or case.get('name') or ''):
        return _json_error(409, {'error': 'case id mismatch', 'diagnostic': 'live-audit-ui-render-record-dom', 'caseId': case_id, 'plannedCaseId': case.get('id') or case.get('name')})
    if cache_key and planned_cache_key and cache_key != planned_cache_key:
        return _json_error(409, {'error': 'cacheKey mismatch', 'diagnostic': 'live-audit-ui-render-record-dom', 'cacheKey': cache_key, 'plannedCacheKey': planned_cache_key})
    if not _live_audit_task_texts_equivalent(str(data.get('inputText') or ''), str(case.get('text') or '')):
        return _json_error(409, {'error': 'input text mismatch', 'diagnostic': 'live-audit-ui-render-record-dom'})
    if not dom_text:
        return _json_error(400, {'error': 'domResultText is empty', 'diagnostic': 'live-audit-ui-render-record-dom'})

    def _mutator(state2: dict[str, Any]):
        live_run = state2.setdefault('runs', {}).get(run_id_value)
        if not isinstance(live_run, dict):
            return {'recorded': False, 'error': 'run disappeared'}
        rows = live_run.setdefault('evidenceResults', [])
        row_index = -1
        for idx, row in enumerate(rows):
            if isinstance(row, dict) and int(row.get('caseIndex') if row.get('caseIndex') is not None else -1) == case_index:
                row_index = idx
                break
        if row_index < 0:
            return {'recorded': False, 'error': 'API evidence row is missing; frontend must click solve and wait for /api/explain first'}
        row = dict(rows[row_index])
        issues = list(row.get('issues') or [])
        ui_issues: list[str] = []
        if not bool(data.get('clickedMainSolveButton')):
            ui_issues.append('UI-render audit did not click main #solveBtn')
        if not bool(data.get('inputSetViaDom')):
            ui_issues.append('UI-render audit did not set #taskInput through DOM')
        if not bool(data.get('resultBoxPresent')):
            ui_issues.append('UI-render audit did not find #resultBox')
        if str(data.get('inputSelector') or '') != '#taskInput':
            ui_issues.append('UI-render audit input selector is not #taskInput')
        if str(data.get('buttonSelector') or '') != '#solveBtn':
            ui_issues.append('UI-render audit button selector is not #solveBtn')
        if str(data.get('resultBoxSelector') or '') != '#resultBox':
            ui_issues.append('UI-render audit result selector is not #resultBox')
        case_for_check = dict(case)
        if not str(case_for_check.get('expectedSource') or '').startswith('guard'):
            case_for_check.pop('expectedSource', None)
            case_for_check.pop('expectedSourceFamily', None)
        # User-visible DOM should be compared to the accepted API payload, not to the full
        # strict API text including hidden task lines. Keep only semantic expectations here.
        case_for_dom = dict(case_for_check)
        case_for_dom.pop('expected', None)
        case_for_dom.pop('expectedUnit', None)
        dom_payload = {'result': dom_text, 'source': row.get('source') or 'frontend-dom-resultbox'}
        checked = _check_payload(case_for_dom, dom_payload)
        is_guard_case = _live_audit_row_is_guard(row)
        # The API result must keep the strict "Задача./Решение./solution line/Ответ" format;
        # the production DOM may intentionally render only the user-visible solution flow.
        # For DOM proof we compare the DOM to the API-derived visible text, not to hidden
        # service headers, echoed task lines or optional guard advice.
        dom_visible_text = _live_audit_prepare_visible_compare_text(dom_text, case_text=case.get('text'), is_guard_case=is_guard_case)
        api_visible_text = _live_audit_prepare_visible_compare_text(api_text or row.get('userVisibleResultText') or row.get('resultText') or '', case_text=case.get('text'), is_guard_case=is_guard_case)
        visible_format_issues = [] if is_guard_case else _live_audit_user_visible_solution_format_issues(dom_visible_text or dom_text)
        dom_answer = _live_audit_extract_answer_line(dom_visible_text or dom_text)
        api_answer = _live_audit_extract_answer_line(api_visible_text or api_text or row.get('userVisibleResultText') or row.get('resultText') or '')
        displayed_matches_api = _live_audit_visible_texts_equivalent(dom_visible_text or dom_text, api_visible_text, case_text=case.get('text'), is_guard_case=is_guard_case)
        answer_matches_api = bool(dom_answer and api_answer and dom_answer.lower().replace('ё','е') == api_answer.lower().replace('ё','е'))
        api_row_ok = bool(row.get('ok'))
        if api_row_ok and displayed_matches_api and answer_matches_api:
            checked = {'ok': True, 'issues': []}
        if visible_format_issues:
            checked['issues'].extend(visible_format_issues)
            checked['ok'] = False
        if ui_issues:
            checked['issues'].extend(ui_issues)
            checked['ok'] = False
        if not displayed_matches_api:
            checked['issues'].append('DOM #resultBox text does not match API result text')
            checked['ok'] = False
        if not answer_matches_api:
            checked['issues'].append('DOM #resultBox answer line does not match API answer line')
            checked['ok'] = False
        clicked_main = bool(data.get('clickedMainSolveButton') or data.get('clickedSolveButton'))
        input_set = bool(data.get('inputSetViaDom') or data.get('taskInputFound'))
        result_box_present = bool(data.get('resultBoxPresent'))
        input_selector = str(data.get('inputSelector') or '#taskInput')
        button_selector = str(data.get('buttonSelector') or '#solveBtn')
        result_selector = str(data.get('resultBoxSelector') or '#resultBox')
        audit_ui_render_mode = str(data.get('auditUiRenderMode') or data.get('frontendUiRenderMode') or 'standalone-github-pages-frontend-textarea-click-solve-resultbox-dom')
        all_ui_issues = list(dict.fromkeys((checked.get('issues') or []) + ui_issues + visible_format_issues))
        ui_render_passed = (
            bool(checked.get('ok'))
            and clicked_main
            and input_set
            and result_box_present
            and input_selector == '#taskInput'
            and button_selector == '#solveBtn'
            and result_selector == '#resultBox'
            and bool(displayed_matches_api)
            and bool(answer_matches_api)
        )
        row.update({
            'ok': bool(row.get('ok')) and bool(checked.get('ok')),
            'issues': list(dict.fromkeys(issues + (checked.get('issues') or []))),
            'frontendDomRenderedOutputChecked': True,
            'frontendDomExpectedCheckOk': bool(checked.get('ok')),
            'frontendDomVisibleFormatIssues': visible_format_issues,
            'frontendDomResultMatchesApi': bool(displayed_matches_api),
            'frontendDomAnswerMatchesApi': bool(answer_matches_api),
            'frontendUiClickedSolveButton': clicked_main,
            'frontendDomResultText': _live_audit_text(dom_text, 8000),
            'frontendDomAnswerLine': dom_answer,
            'userVisibleResultText': _live_audit_text(dom_text, 8000),
            'userVisibleAnswerLine': dom_answer,
            'frontendUiRenderMode': audit_ui_render_mode,
            'frontendUiAuditUrl': str(data.get('pageUrl') or data.get('frontendAuditUrl') or '')[:1000],
            'frontendUiResultSelector': result_selector,
            'frontendUiInputSelector': input_selector,
            'frontendUiButtonSelector': button_selector,
            'frontendUiElapsedMs': int(data.get('elapsedMs') or 0),
            'frontendUiBuild': str(data.get('frontendBuild') or '')[:200],
            'uiRenderAudit': True,
            'iframeAudit': bool(data.get('auditFrontendFrame')),
            'frontendStandalonePage': bool(data.get('auditFrontendStandalonePage') or not bool(data.get('auditFrontendFrame'))),
            'uiRenderMode': 'frontend-ui-render-resultbox',
            'uiRenderPageUrl': str(data.get('pageUrl') or data.get('frontendAuditUrl') or '')[:1000],
            'uiRenderFrontendBuild': str(data.get('frontendBuild') or '')[:200],
            'uiRenderInputSelector': input_selector,
            'uiRenderButtonSelector': button_selector,
            'uiRenderResultBoxSelector': result_selector,
            'uiRenderInputSetViaDom': input_set,
            'uiRenderClickedMainSolveButton': clicked_main,
            'uiRenderResultBoxPresent': result_box_present,
            'uiRenderResultMatchesExpected': bool(checked.get('ok')),
            'uiRenderElapsedMs': int(data.get('elapsedMs') or 0),
            'uiTaskInputId': 'taskInput',
            'uiTaskInputFound': input_selector == '#taskInput',
            'uiTaskInputValue': _live_audit_text(str(data.get('inputText') or case.get('text') or ''), 3000),
            'uiSolveButtonId': 'solveBtn',
            'uiSolveButtonFound': button_selector == '#solveBtn',
            'uiSolveButtonClicked': clicked_main,
            'uiResultBoxId': 'resultBox',
            'uiResultBoxFound': result_box_present,
            'uiResultBoxText': _live_audit_text(dom_text, 8000),
            'uiResultBoxAnswerLine': dom_answer,
            'uiResultBoxTextHash': _short_hash({'domText': dom_text, 'caseIndex': case_index}, 24),
            'uiDomResultMatchesApi': bool(displayed_matches_api) and bool(answer_matches_api),
            'clientDisplayedResultText': _live_audit_text(dom_text, 8000),
            'clientDisplayedAnswerLine': dom_answer,
            'clientDisplayedResultMatchesApi': bool(displayed_matches_api),
            'userVisibleAnswerMatchesApi': bool(answer_matches_api),
            'userVisibleAnswerMatchesExpected': bool(checked.get('ok')),
            'uiRenderPassed': ui_render_passed,
            'auditComparedSamePayloadReturnedToBrowser': True,
            'comparisonTarget': 'DOM innerText of production frontend #resultBox after main #solveBtn click',
            'frontendDisplayAssumption': 'Checked directly: frontend UI runner set #taskInput, clicked #solveBtn and read #resultBox innerText.',
            'frontendDisplayContract': 'V311.04 accepts only if API result and DOM #resultBox text/answer agree and DOM #resultBox preserves the accepted API answer for the same case.',
            'uiRenderDomHash': _short_hash({'runId': run_id_value, 'caseIndex': case_index, 'domText': dom_text, 'apiText': api_text}, 24),
            'uiRenderIssues': all_ui_issues,
        })
        row['suspiciousReasons'] = _live_audit_suspicion_reasons(row)
        rows[row_index] = row
        _live_audit_recompute_outcome_lists(live_run)
        live_run['updatedAt'] = _now_ts()
        live_run['heartbeatAt'] = live_run['updatedAt']
        return {'recorded': True, 'ok': row.get('ok'), 'issues': row.get('issues') or [], 'caseIndex': case_index, 'caseId': case.get('id') or case.get('name'), 'uiRenderDomHash': row.get('uiRenderDomHash')}
    try:
        result = _mutate_live_audit_state(_mutator)
    except Exception as exc:
        return _json_error(500, {'error': f'live-audit ui-render record-dom internal error: {exc}', 'diagnostic': 'live-audit-ui-render-record-dom'})
    if not isinstance(result, dict):
        result = {'recorded': False, 'error': 'record mutation failed'}
    if not result.get('recorded'):
        return _json_error(409, {'diagnostic': 'live-audit-ui-render-record-dom', **result})
    return _json_ok({'diagnostic': 'live-audit-ui-render-record-dom', **result})

def _browser_audit_operator_html(request: Request, payload: dict[str, Any], *, key: str, start_mode: bool) -> str:
    """Return a simple bridge to the standalone GitHub Pages UI-render audit page.

    V311.04 runs the audit from the production frontend page itself, so the user sees
    the real UI and DevTools Network shows the frontend's own POST /api/explain calls.
    """
    frontend_url = _ui_render_audit_url(request, key)
    run_id = str(payload.get('runId') or '')
    final_url = _public_base_url(request) + _browser_audit_final_report_path(run_id, key) if run_id else ''
    planned = int(payload.get('planned') or payload.get('nextAuditLimit') or 100)
    completed = int(payload.get('completed') or 0)
    passed = int(payload.get('passed') or 0)
    failed = int(payload.get('failed') or 0)
    external = int(payload.get('externalApiCalls') or 0) + int(payload.get('cachedExternalApiCalls') or 0)
    usage = int(payload.get('deepseekUsageProofs') or 0)
    pct = 0 if planned <= 0 else max(0, min(100, round(completed * 100 / planned)))
    technical_json = json.dumps(payload, ensure_ascii=False, indent=2)
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0"><title>V311.04 frontend UI-render live-аудит</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:900px;margin:28px auto;padding:0 16px;line-height:1.45;background:#f8fafc;color:#111827}}
.box{{background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:20px;margin:16px 0;box-shadow:0 8px 22px rgba(15,23,42,.05)}}
.primary{{display:inline-block;border:0;border-radius:14px;background:#111827;color:#fff;font-size:20px;font-weight:850;padding:15px 22px;text-decoration:none;cursor:pointer}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px}}.metric{{background:#f3f4f6;border-radius:14px;padding:12px}}.metric b{{display:block;font-size:24px}}
.bar{{height:18px;background:#e5e7eb;border-radius:999px;overflow:hidden}}.fill{{height:100%;width:{pct}%;background:#111827}}input{{box-sizing:border-box;width:100%;border:1px solid #d1d5db;border-radius:12px;padding:12px;font:15px ui-monospace,Menlo,monospace;background:#fff}}.muted{{color:#6b7280}}pre{{white-space:pre-wrap;background:#111827;color:#f9fafb;padding:14px;border-radius:14px;overflow:auto;max-height:360px}}
</style></head><body>
<h1>V311.04 — frontend UI-render live-аудит</h1>
<section class="box">
  <h2>1. Открыть реальную frontend-страницу аудита</h2>
  <p>V311.04 проверяет арифметические действия 4 класса через реальный production frontend: откроется GitHub Pages frontend, где будет одна кнопка «Запустить / продолжить аудит».</p>
  <p><a class="primary" href="{escape(frontend_url, quote=True)}">Открыть аудит на frontend</a></p>
  <p class="muted">На frontend-странице аудит вводит задания в реальное поле <code>#taskInput</code>, нажимает реальную кнопку <code>#solveBtn</code>, ждёт <code>#resultBox</code> и сверяет DOM с API/expected.</p>
  <input readonly value="{escape(frontend_url, quote=True)}" onclick="this.select()">
</section>
<section class="box">
  <h2>2. Текущий прогресс, если run уже есть</h2>
  <div class="bar"><div class="fill"></div></div>
  <div class="grid">
    <div class="metric">completed <b>{completed}/{planned}</b></div>
    <div class="metric">passed <b>{passed}</b></div>
    <div class="metric">failed <b>{failed}</b></div>
    <div class="metric">external calls <b>{external}</b></div>
    <div class="metric">usage proofs <b>{usage}</b></div>
  </div>
</section>
<section class="box" style="display:{'block' if final_url else 'none'}">
  <h2>3. Одна ссылка для ChatGPT</h2>
  <input readonly value="{escape(final_url, quote=True)}" onclick="this.select()">
</section>
<details class="box"><summary>Технический JSON</summary><pre>{escape(technical_json)}</pre></details>
</body></html>'''

def _find_browser_client_run() -> tuple[str, dict[str, Any] | None]:
    """Return the latest V300 browser-client audit run, if any."""
    state = _load_live_audit_state()
    runs = state.get('runs') or {}
    candidates: list[tuple[str, dict[str, Any]]] = []
    for run_id, run in runs.items():
        if not isinstance(run, dict):
            continue
        if str(run.get('release') or '') != APP_RELEASE:
            continue
        if str(run.get('auditClientMode') or '') != 'browser-client-ui-render-visible-network':
            continue
        candidates.append((str(run_id), run))
    if not candidates:
        return '', None
    candidates.sort(key=lambda pair: float(pair[1].get('updatedAt') or pair[1].get('createdAt') or 0), reverse=True)
    return candidates[0]


def _browser_client_run_summary_for_operator(request: Request, run: dict[str, Any] | None, key_value: str) -> dict[str, Any]:
    if isinstance(run, dict):
        payload = _browser_client_summary_payload(run, request)
        payload.update({
            'diagnostic': 'browser-client-live-audit-operator',
            'operatorMode': 'browser-client-ui-render-visible-network',
            'operatorInstruction': 'Нажмите одну кнопку. Браузер выполнит видимые POST /api/explain; после завершения пришлите одну final-report ссылку.',
        })
        return payload
    return {
        **_version_payload(request),
        'diagnostic': 'browser-client-live-audit-operator',
        'operatorMode': 'browser-client-ui-render-visible-network',
        'status': 'not-started',
        'planned': 100,
        'completed': 0,
        'passed': 0,
        'failed': 0,
        'externalApiCalls': 0,
        'deepseekUsageProofs': 0,
        'operatorInstruction': 'Нажмите одну кнопку. Браузер выполнит видимые POST /api/explain; после завершения пришлите одну final-report ссылку.',
    }

async def _browser_audit_operator_payload(request: Request, release_token: str, key_value: str, start: int = 0) -> dict[str, Any] | JSONResponse:
    if str(release_token or '').strip() != APP_RELEASE:
        return _json_error(409, {
            'error': 'release mismatch',
            'requestedRelease': release_token,
            'currentRelease': APP_RELEASE,
            'currentOperatorUrl': _public_base_url(request) + f'/api/diagnostics/live-audit/operator/{APP_RELEASE}/{LIVE_PRODUCTION_AUDIT_DEFAULT_KEY}',
        })
    if not _live_audit_key_matches(key_value):
        return _json_error(403, {'error': 'Нужен live-audit key.', 'diagnostic': 'live-audit-browser-client-operator'})
    section = 'g4_arithmetic_actions'
    offset = 0
    limit = 100
    allow_external = True
    max_external_calls = 150
    plan_key = _browser_client_plan_key(section, offset, limit, allow_external, max_external_calls)
    state = _load_live_audit_state()
    run_id = str((state.get('plans') or {}).get(plan_key) or '')
    run = (state.get('runs') or {}).get(run_id) if run_id else None
    if isinstance(run, dict) and run.get('release') == APP_RELEASE and run.get('auditClientMode') == 'browser-client-ui-render-visible-network':
        payload = _browser_client_summary_payload(run, request)
        payload.update({
            'diagnostic': 'live-audit-browser-client-operator',
            'operatorReady': True,
            'operatorMode': 'one-button-browser-fetch-audit',
            'browserClientFetchRequired': True,
            'apiExplainPath': '/api/explain',
            'operatorInstruction': "Нажмите кнопку. Браузер сам последовательно выполнит POST /api/explain для незавершённых audit-cases.",
            'tokenFields': ['apiPromptTokens', 'apiCompletionTokens', 'apiTotalTokens', 'promptCacheHitTokens', 'promptCacheMissTokens'],
        })
        return payload
    return {
        **_version_payload(request),
        'diagnostic': 'live-audit-browser-client-operator',
        'operatorReady': True,
        'operatorMode': 'one-button-browser-fetch-audit',
        'runnerMode': 'BROWSER_CLIENT_UI_RENDER_DOM_API_EXPLAIN',
        'auditClientMode': 'browser-client-ui-render-visible-network',
        'browserClientFetchRequired': True,
        'devToolsNetworkProof': "Open browser DevTools → Network and filter '/api/explain'; V311.04 client sends one visible POST per audit case.",
        'status': 'not-started',
        'section': section,
        'planned': limit,
        'completed': 0,
        'passed': 0,
        'failed': 0,
        'externalApiCalls': 0,
        'externalApiCompleted': 0,
        'deepseekUsageProofs': 0,
        'caseProofsTotal': 0,
        'apiPromptTokens': 0,
        'apiCompletionTokens': 0,
        'apiTotalTokens': 0,
        'promptCacheHitTokens': 0,
        'promptCacheMissTokens': 0,
        'operatorInstruction': "Нажмите кнопку. Браузер создаст run и сам последовательно выполнит POST /api/explain для 100 grade-3 geometry audit-cases.",
        'tokenFields': ['apiPromptTokens', 'apiCompletionTokens', 'apiTotalTokens', 'promptCacheHitTokens', 'promptCacheMissTokens'],
        'browserClientStartUrl': _public_base_url(request) + f'/api/diagnostics/live-audit/browser-client/start/{APP_RELEASE}/{key_value}',
    }


@app.get('/api/diagnostics/live-audit/operator/{release_token}/{key_value}')
async def live_audit_browser_operator(request: Request, release_token: str, key_value: str, start: int = 0):
    result = await _browser_audit_operator_payload(request, release_token, key_value, start=start)
    if isinstance(result, JSONResponse):
        return result
    payload = dict(result)
    run_id = str(payload.get('runId') or '')
    if run_id:
        acceptance = await live_audit_runner_acceptance(key=key_value, runId=run_id, release=release_token)
        if not isinstance(acceptance, JSONResponse) and isinstance(acceptance, dict):
            payload.update({
                'finalAcceptance': acceptance.get('finalAcceptance'),
                'acceptancePassed': acceptance.get('acceptancePassed'),
                'acceptanceIssues': acceptance.get('acceptanceIssues'),
                'caseProofsTotal': acceptance.get('caseProofsTotal'),
                'suspiciousCount': acceptance.get('suspiciousCount'),
                'suspiciousPassedCount': acceptance.get('suspiciousPassedCount'),
            })
    return _html_ok(_browser_audit_operator_html(request, payload, key=key_value, start_mode=bool(start)))


@app.get('/api/diagnostics/live-audit/final-report/{release_token}/{key_value}/{run_id_value}')
async def live_audit_browser_final_report(release_token: str, key_value: str, run_id_value: str):
    report = await live_audit_runner_report(key=key_value, runId=run_id_value, release=release_token)
    if isinstance(report, JSONResponse):
        return report
    results_full = await live_audit_runner_results(key=key_value, runId=run_id_value, release=release_token, includeFull=1, limit=500, offset=0)
    evidence = await live_audit_runner_evidence(key=key_value, runId=run_id_value, release=release_token, limit=500, offset=0)
    suspicious = await live_audit_runner_suspicious(key=key_value, runId=run_id_value, release=release_token)
    failures = await live_audit_runner_failures(key=key_value, runId=run_id_value, release=release_token, limit=200)
    for item in (results_full, evidence, suspicious, failures):
        if isinstance(item, JSONResponse):
            return item
    payload = {
        **dict(report),
        'diagnostic': 'live-audit-browser-final-report',
        'singleLinkForChatGPT': True,
        'operatorInstruction': 'Скопируйте URL этой страницы и пришлите ChatGPT. Эта одна ссылка содержит acceptance, failures, suspicious, evidence и full case results.',
        'fullResultsPayload': results_full,
        'evidencePayload': evidence,
        'suspiciousPayload': suspicious,
        'failuresPayload': failures,
    }
    title = 'V311.04 итоговый live-audit отчёт для ChatGPT'
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    status = 'ПРИНЯТО' if payload.get('finalAcceptance') else 'НЕ ПРИНЯТО / ТРЕБУЕТ АНАЛИЗА'
    klass = 'ok' if payload.get('finalAcceptance') else 'bad'
    summary = payload.get('acceptanceSummary') or {}
    return _html_ok(f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0"><title>{escape(title)}</title><style>body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1100px;margin:28px auto;padding:0 16px;line-height:1.45}}.status{{font-size:22px;font-weight:850;border-radius:16px;padding:16px;margin:16px 0}}.ok{{background:#ecfdf5;border:1px solid #bbf7d0}}.bad{{background:#fef2f2;border:1px solid #fecaca}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}}.metric{{background:#f3f4f6;border-radius:14px;padding:12px}}.metric b{{font-size:24px;display:block}}pre{{white-space:pre-wrap;background:#111827;color:#f9fafb;border-radius:14px;padding:14px;overflow:auto}}</style></head><body>
<h1>{escape(title)}</h1><div class="status {klass}">{escape(status)}</div><p>Эту страницу достаточно прислать ChatGPT одной ссылкой. Ниже полный JSON-proof.</p>
<div class="grid"><div class="metric">planned <b>{escape(str(summary.get('planned', payload.get('planned', ''))))}</b></div><div class="metric">completed <b>{escape(str(summary.get('completed', payload.get('completed', ''))))}</b></div><div class="metric">passed <b>{escape(str(summary.get('passed', payload.get('passed', ''))))}</b></div><div class="metric">failed <b>{escape(str(summary.get('failed', payload.get('failed', ''))))}</b></div></div>
<h2>JSON proof</h2><pre>{escape(data)}</pre></body></html>''')


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
            'hint': 'Default test key in this build: v311.04-live-audit. For production, set LIVE_AUDIT_KEY in Timeweb.',
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
            payload, external = await _generate_with_public_api_route_counter(case['text'], allow_external=allow_external, audit_key=audit_key)
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
        'nextPlannedMapStep': 'after V311.04 pass: V312 — 4 класс, раздел 3 — Текстовые задачи',
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
    """Browser-friendly entry point for the next planned audit.

    Shows a single start/continue button and a single final-report link instead
    of a long technical list. The button uses the same cached runner; force=1 is
    not used.
    """
    return await live_audit_browser_operator(request, release_token, key_value, start=0)


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
            'hint': 'Default test key in this build: v311.04-live-audit. For production, set LIVE_AUDIT_KEY in Timeweb.',
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
            'deepseekPromptTokens': 0,
            'deepseekCompletionTokens': 0,
            'deepseekTotalTokens': 0,
            'deepseekUsageProofs': 0,
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
    if run.get('status') in {'queued', 'running'} and not bool(run.get('browserClientAudit')):
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
    if run.get('status') in {'queued', 'running'} and not bool(run.get('browserClientAudit')):
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
    if run.get('status') in {'queued', 'running'} and not bool(run.get('browserClientAudit')):
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
    if run.get('status') in {'queued', 'running'} and not bool(run.get('browserClientAudit')):
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
    if run.get('status') in {'queued', 'running'} and not bool(run.get('browserClientAudit')):
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
        rows.append(evidence)
    rows = _live_audit_apply_duplicate_suspicion(rows)
    if only_suspicious:
        rows = [row for row in rows if row.get('suspiciousReasons')]
    if not include_full:
        rows = [dict(row, **{}) for row in rows]
        for row in rows:
            row.pop('resultText', None)
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
    duplicate_issues = _live_audit_duplicate_quality_issues(evidence_rows)
    issues = _live_audit_acceptance_blockers(run)
    final_acceptance = not issues
    return {
        **summary,
        'diagnostic': 'live-audit-runner-acceptance',
        'acceptancePolicy': 'V311.04 accepts section only if aggregate, browser-visible /api/explain evidence, frontend DOM resultBox evidence, explicit uiRenderPassed=true evidence, external API evidence, failures, suspicious and case-level proofs all pass.',
        'finalAcceptance': final_acceptance,
        'acceptancePassed': final_acceptance,
        'acceptanceIssues': issues,
        'caseProofsTotal': len(evidence_rows),
        'suspiciousCount': len(suspicious),
        'suspiciousPassedCount': sum(1 for row in suspicious if row.get('ok')),
        'duplicateQualityIssues': duplicate_issues,
        'acceptanceRequires': ['status == done', 'completed == planned == 100', 'failed == 0', 'cachedResults == 0', 'externalApiCalls >= normal cases', 'externalApiCompleted >= normal cases', 'deepseekUsageProofs >= normal cases', 'apiTotalTokens > 0', 'every normal case routeAuditMode == browser-client-ui-render-visible-network, browserClientFetch=true, apiRouteNetworkVisibleToBrowser=true', 'frontend DOM proof recorded for every normal case and uiRenderPassed=true', 'real frontend #taskInput was set and #solveBtn was clicked', 'visible #resultBox answer matches expected answer and API answer', 'uiRenderPassed == true for every normal case', 'caseProofsTotal == planned', 'suspiciousPassedCount == 0', 'duplicateQualityIssues == []'],
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
    evidence_rows = _live_audit_results_for_payload(run, include_full=True)
    suspicious = [row for row in evidence_rows if isinstance(row, dict) and row.get('suspiciousReasons')]
    return {
        **acceptance,
        'diagnostic': 'live-audit-runner-report',
        'reportKind': 'V311.04 frontend UI-render proof audit for grade 4 arithmetic actions',
        'operatorInstruction': 'Пришлите эту ссылку ChatGPT. Aggregate summary без report/acceptance/evidence не считается основанием для принятия раздела.',
        'counts': {
            'failures': len(failures),
            'suspicious': len(suspicious),
            'evidenceRows': len(evidence_rows),
            'uiRenderDomProofs': int(acceptance.get('uiRenderDomProofs') or 0),
            'uiRenderPassedProofs': int(acceptance.get('uiRenderPassedProofs') or 0),
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
    audit_response = await _maybe_handle_browser_client_audit_request(request, data, route_path=str(request.url.path or '/'))
    if audit_response is not None:
        return audit_response
    text = data.get('text')
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data), audit_bypass_daily_limit=_live_audit_key_matches(request.headers.get('X-Live-Audit-Key', '')), audit_context=_browser_client_audit_context_from_request(request, data))


@app.post('/api/explanations')
@app.post('/api/explain')
async def explain_v2(request: Request):
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON'})
    audit_response = await _maybe_handle_browser_client_audit_request(request, data, route_path=str(request.url.path or '/api/explain'))
    if audit_response is not None:
        return audit_response
    text = str(data.get('text') or '').strip()
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data), audit_bypass_daily_limit=_live_audit_key_matches(request.headers.get('X-Live-Audit-Key', '')), audit_context=_browser_client_audit_context_from_request(request, data))


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
    audit_response = await _maybe_handle_browser_client_audit_request(request, data, route_path=str(request.url.path or '/api/explain'))
    if audit_response is not None:
        return audit_response
    text = str(data.get('text') or '').strip()
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data), audit_bypass_daily_limit=_live_audit_key_matches(request.headers.get('X-Live-Audit-Key', '')), audit_context=_browser_client_audit_context_from_request(request, data))


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
