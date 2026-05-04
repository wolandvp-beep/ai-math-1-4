from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from typing import Any, Iterable

from backend.async_compat import run_async_compat
from backend.explanation_dispatcher import dispatch_explanation
from backend.health_case_matrix import classify_source_family, normalize_result_text
from backend.health_summary import summarize_case_results
from backend.platform.modules.health.open_source_primary_web_cases import OPEN_SOURCE_PRIMARY_WEB_CASES

RECOMMENDED_RESULT_MARKERS: tuple[str, ...] = ('Совет:',)
FAILURE_PHRASES: tuple[str, ...] = (
    'не удалось',
    'пока нет надёжного решения',
    'нет надёжного решения',
)
_STEP_RE = re.compile(r'(?m)^\d+\)')


def _iter_needles(value: Any) -> Iterable[str]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _count_solution_steps(result_text: str) -> int:
    return len(_STEP_RE.findall(result_text))


async def run_open_source_primary_web_suite() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    source_family_counts: Counter[str] = Counter()
    source_basis_counts: Counter[str] = Counter()
    advice_present = 0
    block_summary: defaultdict[str, dict[str, Any]] = defaultdict(lambda: {
        'passed': 0,
        'total': 0,
        'advice_present': 0,
        'step_coverage_passed': 0,
    })
    grade_section_summary: defaultdict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {
        'passed': 0,
        'total': 0,
        'advice_present': 0,
    })

    for case in OPEN_SOURCE_PRIMARY_WEB_CASES:
        started = time.perf_counter()
        issues: list[str] = []
        payload: dict[str, Any] = {}
        exception_issue = ''
        try:
            payload = await dispatch_explanation(case['text'])
        except Exception as exc:  # pragma: no cover - defensive runtime harness
            exception_issue = f'{type(exc).__name__}: {exc}'
        elapsed_seconds = time.perf_counter() - started
        source = str(payload.get('source', '')) if not exception_issue else f'EXCEPTION:{exception_issue.split(":", 1)[0]}'
        result_text = normalize_result_text(payload.get('result', ''))
        source_family = classify_source_family(source)
        source_family_counts[source_family] += 1
        source_basis_counts[str(case['source_basis'])] += 1

        if exception_issue:
            issues.append(f'exception during dispatch: {exception_issue}')
        for prefix in _iter_needles(case.get('forbid_source_prefixes')):
            if prefix and source.startswith(prefix):
                issues.append(f'source starts with forbidden prefix {prefix!r}: {source!r}')
        for marker in _iter_needles(case.get('required_result_markers')):
            if marker and marker not in result_text:
                issues.append(f'missing required marker {marker!r}')
        expected_answer = str(case.get('expected_answer_contains') or '').strip()
        if expected_answer and expected_answer not in result_text:
            issues.append(f'expected answer fragment {expected_answer!r} missing in result')
        lowered_result = result_text.lower()
        for phrase in FAILURE_PHRASES:
            if phrase in lowered_result:
                issues.append(f'result contains failure phrase {phrase!r}')
        step_count = _count_solution_steps(result_text)
        min_steps = int(case.get('min_solution_steps') or 0)
        step_ok = step_count >= min_steps
        if min_steps and not step_ok:
            issues.append(f'expected at least {min_steps} solution steps, found {step_count}')
        has_advice = all(marker in result_text for marker in RECOMMENDED_RESULT_MARKERS)
        if has_advice:
            advice_present += 1

        ok = not issues
        block_key = str(case['block_key'])
        grade_section_key = (str(case['block_label']), str(case['section_key']))
        block_summary[block_key]['total'] += 1
        block_summary[block_key]['advice_present'] += 1 if has_advice else 0
        block_summary[block_key]['step_coverage_passed'] += 1 if step_ok else 0
        if ok:
            block_summary[block_key]['passed'] += 1
        grade_section_summary[grade_section_key]['total'] += 1
        grade_section_summary[grade_section_key]['advice_present'] += 1 if has_advice else 0
        if ok:
            grade_section_summary[grade_section_key]['passed'] += 1

        results.append({
            'name': case['name'],
            'block_key': case['block_key'],
            'block_label': case['block_label'],
            'grade': case['grade'],
            'section_key': case['section_key'],
            'section': case['section'],
            'source_basis_key': case['source_basis_key'],
            'source_basis': case['source_basis'],
            'text': case['text'],
            'expected_answer_contains': expected_answer,
            'ok': ok,
            'issues': issues,
            'source': source,
            'source_family': source_family,
            'step_count': step_count,
            'min_solution_steps': min_steps,
            'result_preview': result_text[:280],
            'elapsed_seconds': round(elapsed_seconds, 6),
        })

    passed = sum(1 for item in results if item['ok'])
    block_summary_out = {
        block_key: {
            **values,
            'all_passed': values['passed'] == values['total'],
            'advice_coverage_ratio': round(values['advice_present'] / values['total'], 4) if values['total'] else 0.0,
            'step_coverage_ratio': round(values['step_coverage_passed'] / values['total'], 4) if values['total'] else 0.0,
        }
        for block_key, values in sorted(block_summary.items())
    }
    grade_section_out = {
        f'{block_label}:{section_key}': {
            **values,
            'all_passed': values['passed'] == values['total'],
            'advice_coverage_ratio': round(values['advice_present'] / values['total'], 4) if values['total'] else 0.0,
        }
        for (block_label, section_key), values in sorted(grade_section_summary.items())
    }

    return {
        'passed': passed,
        'total': len(results),
        'all_passed': passed == len(results),
        'category_summary': summarize_case_results(results),
        'block_summary': block_summary_out,
        'grade_section_summary': grade_section_out,
        'source_family_counts': dict(sorted(source_family_counts.items())),
        'source_basis_counts': dict(sorted(source_basis_counts.items())),
        'advice_coverage': {
            'present': advice_present,
            'missing': len(results) - advice_present,
            'ratio': round(advice_present / len(results), 4) if results else 0.0,
        },
        'results': results,
    }


def run_open_source_primary_web_suite_sync(*, fresh: bool = False) -> dict[str, Any]:
    return run_async_compat(run_open_source_primary_web_suite)


if __name__ == '__main__':
    import json

    print(json.dumps(run_open_source_primary_web_suite_sync(), ensure_ascii=False, indent=2))


__all__ = [
    'run_open_source_primary_web_suite',
    'run_open_source_primary_web_suite_sync',
]
