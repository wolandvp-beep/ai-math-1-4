from __future__ import annotations

import os
import tempfile
import time
from typing import Any

from httpx import ASGITransport, AsyncClient

from backend.async_compat import run_async_compat
from backend.main import app
from backend.platform.modules.core.public.services.access.store import STATE_FILE_ENV
from backend.service import generate_explanation_response


DIRECT_CASES: tuple[dict[str, Any], ...] = (
    {
        'name': 'compare_with_placeholder',
        'text': 'Поставь знак >, < или = : 37 + 8 ... 50 - 5',
        'expected_source': 'local-compare-expression',
        'required_fragments': ('Ответ: 37 + 8 = 50 - 5.',),
    },
    {
        'name': 'compare_with_wording',
        'text': 'Сравни 1/2 + 1/3 и 5/6',
        'expected_source': 'local-compare-expression',
        'required_fragments': ('Ответ: 1/2 + 1/3 = 5/6.',),
    },
    {
        'name': 'system_with_prefix_and_comma',
        'text': 'Реши систему: x + y = 7, x - y = 1',
        'expected_source_prefix': 'local',
        'required_fragments': ('Система уравнений:', 'Ответ: x = 4, y = 3.'),
    },
    {
        'name': 'system_with_semicolon',
        'text': 'x+y=7; x-y=1',
        'expected_source_prefix': 'local',
        'required_fragments': ('Система уравнений:', 'Ответ: x = 4, y = 3.'),
    },
    {
        'name': 'system_with_conjunction',
        'text': 'Реши систему: x+y=7 и x-y=1',
        'expected_source_prefix': 'local',
        'required_fragments': ('Система уравнений:', 'Ответ: x = 4, y = 3.'),
    },
    {
        'name': 'multi_expression_semicolon_rejected',
        'text': '2+3; 4+5',
        'expected_source': 'guard-multi-task',
        'required_fragments': ('Я решаю только одно задание за раз',),
    },
    {
        'name': 'multi_expression_comma_rejected',
        'text': '2+3, 4+5',
        'expected_source': 'guard-multi-task',
        'required_fragments': ('Я решаю только одно задание за раз',),
    },
    {
        'name': 'multi_equations_rejected',
        'text': 'x + 3 = 7; y - 2 = 5',
        'expected_source': 'guard-multi-task',
        'required_fragments': ('Я решаю только одно задание за раз',),
    },
    {
        'name': 'multi_numbered_rejected',
        'text': '1) 35+7\n2) 90-12',
        'expected_source': 'guard-multi-task',
        'required_fragments': ('Я решаю только одно задание за раз',),
    },
    {
        'name': 'compound_geometry_not_rejected',
        'text': 'Найди площадь и периметр прямоугольника со сторонами 3 см и 5 см',
        'forbidden_source': 'guard-multi-task',
        'required_fragments': ('Решение.', 'Ответ:'),
    },
    {
        'name': 'fraction_expression_not_rejected',
        'text': '1/2 + 1/3 - 1/6',
        'expected_source_prefix': 'expression_fraction',
        'required_fragments': ('Ответ: 2/3.',),
    },
    {
        'name': 'slash_division_not_fraction_compare',
        'text': '10/2+3',
        'expected_source_prefix': 'expression_mixed',
        'required_fragments': ('Ответ: 8.',),
    },
)


async def _run_direct_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    issues: list[str] = []
    payload = await generate_explanation_response(case['text'])
    elapsed_seconds = time.perf_counter() - started
    source = str(payload.get('source', ''))
    result_text = str(payload.get('result', ''))

    expected_source = case.get('expected_source')
    if expected_source and source != expected_source:
        issues.append(f'expected source {expected_source!r}, got {source!r}')
    expected_source_prefix = case.get('expected_source_prefix')
    if expected_source_prefix and not source.startswith(expected_source_prefix):
        issues.append(f'expected source prefix {expected_source_prefix!r}, got {source!r}')
    forbidden_source = case.get('forbidden_source')
    if forbidden_source and source == forbidden_source:
        issues.append(f'forbidden source matched {forbidden_source!r}')
    for fragment in case.get('required_fragments', ()):  # type: ignore[arg-type]
        if fragment not in result_text:
            issues.append(f'missing fragment {fragment!r}')

    return {
        'name': case['name'],
        'text': case['text'],
        'ok': not issues,
        'issues': issues,
        'source': source,
        'result_preview': result_text[:280],
        'elapsed_seconds': round(elapsed_seconds, 6),
    }


async def _run_api_quota_case() -> dict[str, Any]:
    issues: list[str] = []
    state_file = tempfile.NamedTemporaryFile(delete=False)
    state_file.close()
    previous_env = os.environ.get(STATE_FILE_ENV)
    os.environ[STATE_FILE_ENV] = state_file.name
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            headers = {'X-Install-Id': 'single-task-guard-suite'}
            before = (await client.get('/api/billing/access-status', headers=headers)).json()['usage']
            multi = await client.post('/api/explanations', headers=headers, json={'text': '2+3; 4+5'})
            after_multi = (await client.get('/api/billing/access-status', headers=headers)).json()['usage']
            compare = await client.post('/api/explanations', headers=headers, json={'text': 'Сравни 2+3 и 4+1'})
            after_compare = (await client.get('/api/billing/access-status', headers=headers)).json()['usage']

        multi_payload = multi.json()
        compare_payload = compare.json()
        if before['starterUsed'] != 0 or before['dailyUsed'] != 0:
            issues.append(f'expected fresh quota state, got {before!r}')
        if multi_payload.get('source') != 'guard-multi-task':
            issues.append(f'expected guard-multi-task source for multi payload, got {multi_payload.get("source")!r}')
        if after_multi['starterUsed'] != 0 or after_multi['dailyUsed'] != 0:
            issues.append(f'multi-task request consumed quota unexpectedly: {after_multi!r}')
        if compare_payload.get('source') != 'local-compare-expression':
            issues.append(f'expected compare payload source, got {compare_payload.get("source")!r}')
        if after_compare['starterUsed'] != 1 or after_compare['dailyUsed'] != 1:
            issues.append(f'valid compare request did not consume exactly one quota slot: {after_compare!r}')

        return {
            'name': 'api_quota_not_spent_on_multi_task',
            'text': 'API access policy for multi-task guard',
            'ok': not issues,
            'issues': issues,
            'source': 'api',
            'result_preview': str({
                'before': before,
                'after_multi': after_multi,
                'after_compare': after_compare,
            })[:280],
            'elapsed_seconds': 0.0,
        }
    finally:
        if previous_env is None:
            os.environ.pop(STATE_FILE_ENV, None)
        else:
            os.environ[STATE_FILE_ENV] = previous_env
        try:
            os.remove(state_file.name)
        except FileNotFoundError:
            pass


async def run_single_task_guard_suite() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in DIRECT_CASES:
        results.append(await _run_direct_case(case))
    results.append(await _run_api_quota_case())
    passed = sum(1 for item in results if item['ok'])
    return {
        'passed': passed,
        'total': len(results),
        'all_passed': passed == len(results),
        'results': results,
    }


def run_single_task_guard_suite_sync(*, fresh: bool = False) -> dict[str, Any]:
    return run_async_compat(run_single_task_guard_suite)


if __name__ == '__main__':
    import json

    print(json.dumps(run_single_task_guard_suite_sync(), ensure_ascii=False, indent=2))


__all__ = ['run_single_task_guard_suite', 'run_single_task_guard_suite_sync']
