import asyncio
import importlib.util
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / 'pdf_regression_cases.json'
REPORT_PATH = Path('/mnt/data/pdf_regression_report.txt')
MODULE_PATH = ROOT / 'main.py'

os.environ['myapp_ai_math_1_4_API_key'] = 'dummy'

spec = importlib.util.spec_from_file_location('resh_pdf_main', MODULE_PATH)
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

async def fail_if_called(payload, timeout_seconds=45.0):
    raise AssertionError('LLM should not be called for PDF regression case')

main.call_deepseek = fail_if_called


def extract_answer(text: str):
    for raw_line in str(text or '').split('\n'):
        line = raw_line.strip()
        if line.lower().startswith('ответ:'):
            return line.split(':', 1)[1].strip().rstrip('.')
    return None


def extract_lines(text: str):
    return [line.strip() for line in str(text or '').split('\n') if line.strip()]


async def run():
    cases = json.loads(CASES_PATH.read_text(encoding='utf-8'))
    rows = []
    category_ok = Counter()
    category_total = Counter()
    for case in cases:
        category = case['category']
        category_total[category] += 1
        try:
            result = await main.build_explanation(case['task'])
            answer = extract_answer(result.get('result', ''))
            ok = answer == case['expected'] and result.get('source') == 'local'
            if ok:
                category_ok[category] += 1
            rows.append({
                'ok': ok,
                'id': case['id'],
                'category': category,
                'source_ref': case['source'],
                'task': case['task'],
                'expected': case['expected'],
                'got': answer,
                'source': result.get('source'),
            })
        except Exception as exc:
            rows.append({
                'ok': False,
                'id': case['id'],
                'category': category,
                'source_ref': case['source'],
                'task': case['task'],
                'expected': case['expected'],
                'got': None,
                'source': f'ERROR: {exc}',
            })

    passed = sum(1 for row in rows if row['ok'])
    failed = len(rows) - passed
    lines = [
        'PDF regression report',
        f'Passed: {passed}',
        f'Failed: {failed}',
        '',
        'By category:',
    ]
    for category in sorted(category_total):
        lines.append(f'- {category}: {category_ok[category]}/{category_total[category]}')
    lines.append('')
    for row in rows:
        status = 'PASS' if row['ok'] else 'FAIL'
        lines.append(
            f"{status} | {row['id']} | {row['category']} | expected={row['expected']!r} | got={row['got']!r} | source={row['source']} | ref={row['source_ref']}"
        )
        lines.append(f"  task: {row['task']}")
    REPORT_PATH.write_text('\n'.join(lines), encoding='utf-8')
    print(REPORT_PATH)
    print(f'passed={passed} failed={failed}')


if __name__ == '__main__':
    asyncio.run(run())
