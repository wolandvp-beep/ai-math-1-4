from __future__ import annotations

import ast
import re
from fractions import Fraction
from typing import Optional

from backend.legacy_text_helpers import audit_task_line, finalize_legacy_lines

MULTI_TASK_MESSAGE = (
    'Я решаю только одно задание за раз. Похоже, вы отправили несколько заданий. '
    'Разделите их и отправьте отдельно.'
)

_PREFIX_RE = re.compile(
    r'^(?:задача|пример(?:ы)?|уравнение|дроби|геометрия|выражение|математика)\s*:\s*',
    re.IGNORECASE,
)
_COMPARE_PREFIX_RE = re.compile(
    r'^(?:сравни(?:те)?|поставь(?:те)?\s+знак(?:[^\dа-яёa-z]+)?(?:\s+между)?|какой\s+знак\s+поставить(?:\s+между)?|определи(?:те)?\s+знак)\s*:?',
    re.IGNORECASE,
)
_SYSTEM_PREFIX_RE = re.compile(
    r'^(?:реши(?:те)?\s+)?систем[ауые](?:\s+уравнений)?\s*:?',
    re.IGNORECASE,
)
_NUMBERED_TASK_RE = re.compile(r'(?:^|\n)\s*(?:№\s*\d+|\d+[.)]|[а-яa-z][)])\s*', re.IGNORECASE)
_SOLVER_VERB_RE = re.compile(r'\b(?:реши(?:те)?|вычисли(?:те)?|найди(?:те)?|сравни(?:те)?|поставь(?:те)?|определи(?:те)?|запиши(?:те)?|укажи(?:те)?)\b', re.IGNORECASE)
_ALLOWED_EXPR_CHARS_RE = re.compile(r'^[0-9xyххуу+\-*/().,:÷×·\s]+$', re.IGNORECASE)
_ALLOWED_EQ_CHARS_RE = re.compile(r'^[0-9xy+\-*/().\s=]+$', re.IGNORECASE)


def _normalize_text(text: str) -> str:
    cleaned = str(text or '').strip()
    cleaned = _PREFIX_RE.sub('', cleaned)
    # UI/input hardening: common live-input wrappers should not make a single
    # task look like multiple tasks, especially "Реши задачу: Задание N. ...".
    prefix_patterns = (
        r'^\s*(?:пожалуйста,?\s*)?(?:реши(?:те)?|помоги(?:те)?\s+решить)\s+(?:задачу|пример(?:ы)?|задание|уравнение)\s*[:.!?\-–—]*\s*',
        r'^\s*(?:пожалуйста,?\s*)?(?:реши(?:те)?|помоги(?:те)?\s+решить)\s*[:.!?\-–—]+\s*',
        r'^\s*(?:найди(?:те)?\s+ответ|ответь(?:те)?(?:\s+кратко)?)\s*[:.!?\-–—]+\s*',
        r'^\s*математика\s*,?\s*\d\s*класс\s*[.:\-–—]?\s*',
        r'^\s*(?:задача|задание|пример|уравнение)\s*(?:№\s*)?\d+\s*[.)\]:;\-–—]*\s*',
        r'^\s*(?:№\s*)?\d+\s*[.)\]]+\s*',
    )
    for _ in range(4):
        before = cleaned
        for pattern in prefix_patterns:
            cleaned = re.sub(pattern, '', cleaned, count=1, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        if cleaned == before:
            break
    cleaned = cleaned.replace('−', '-').replace('–', '-').replace('—', '-')
    cleaned = cleaned.replace('Х', 'x').replace('х', 'x')
    cleaned = cleaned.replace('Ё', 'Е').replace('ё', 'е')
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    cleaned = re.sub(r'\s+([?.!,;])', r'\1', cleaned)
    cleaned = re.sub(r'\t+', ' ', cleaned)
    return cleaned.strip()


def _strip_compare_prefix(text: str) -> str:
    return _COMPARE_PREFIX_RE.sub('', text).strip(' :')


def _strip_system_prefix(text: str) -> str:
    return _SYSTEM_PREFIX_RE.sub('', text).strip(' :')


def _normalize_expression_fragment(fragment: str) -> str:
    text = str(fragment or '').strip()
    text = text.strip('[]{}')
    text = text.replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    text = re.sub(r'\s+', '', text)
    return text


def _looks_like_expression_fragment(fragment: str) -> bool:
    raw = str(fragment or '').strip()
    if not raw or '=' in raw:
        return False
    if not _ALLOWED_EXPR_CHARS_RE.fullmatch(raw):
        return False
    if not re.search(r'\d|[xyххуy]', raw, flags=re.IGNORECASE):
        return False
    try:
        _eval_fraction_expression(raw)
        return True
    except Exception:
        return False


def _fraction_to_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f'{value.numerator}/{value.denominator}'



_ORDINAL_EXAMPLE_WORDS = [
    'первый', 'второй', 'третий', 'четвёртый', 'пятый',
    'шестой', 'седьмой', 'восьмой', 'девятый', 'десятый',
]

_MULTI_EXAMPLE_SEPARATOR_RE = re.compile(r'\n+|;')
_DIRECT_ARITH_LINE_RE = re.compile(r'^[0-9+\-*/().,:÷×·\s]+$')
_EXAMPLE_WRAPPER_LINE_RE = re.compile(
    r'^\s*(?:пожалуйста\s*,?\s*)?(?:(?:реши(?:те)?|вычисли(?:те)?|найди(?:те)?)\s+(?:пример(?:ы)?|задани[ея]|уравнени[ея])|реши(?:те)?|вычисли(?:те)?|найди(?:те)?|пример(?:ы)?|задани[ея]|уравнени[ея])\s*[:.!?\-–—]*\s*$',
    re.IGNORECASE,
)


def _strip_line_task_marker(line: str) -> str:
    value = str(line or '').strip()
    value = re.sub(r'^(?:(?:№\s*)?\d+\s*[.)\]]|[а-яa-z][.)\]])\s*', '', value, flags=re.IGNORECASE)
    return value.strip()


def _looks_like_direct_arithmetic_line(line: str) -> bool:
    value = _strip_line_task_marker(line)
    if not value or '=' in value:
        return False
    if not _DIRECT_ARITH_LINE_RE.fullmatch(value):
        return False
    if not re.search(r'\d', value):
        return False
    if not re.search(r'[+\-*/:÷×·]', value):
        return False
    try:
        _eval_fraction_expression(value)
        return True
    except Exception:
        return False


def _pretty_direct_arithmetic_expression(line: str) -> str:
    value = _strip_line_task_marker(line)
    value = value.replace('×', '*').replace('·', '*').replace('÷', ':').replace('/', ':')
    value = re.sub(r'\s+', '', value)
    value = value.replace('*', '×')
    value = re.sub(r'(?<=\d)\s*([+\-×:])\s*(?=\d|\()', r' \1 ', value)
    value = re.sub(r'(?<=\))\s*([+\-×:])\s*(?=\d|\()', r' \1 ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return value


def _ordinal_example_word(index: int) -> str:
    if 1 <= index <= len(_ORDINAL_EXAMPLE_WORDS):
        return _ORDINAL_EXAMPLE_WORDS[index - 1]
    return f'{index}-й'


def build_multiline_direct_examples_payload(raw_text: str) -> Optional[dict]:
    """Solve several simple arithmetic examples entered on separate lines.

    This is intentionally narrow: word problems and mixed natural-language tasks
    still go through the one-task guard.  The goal is to prevent mobile/newline
    input like "2+2\n32-8" from being glued into a false expression.
    """
    text = _normalize_text(raw_text)
    if not text:
        return None
    parts = [part.strip() for part in _MULTI_EXAMPLE_SEPARATOR_RE.split(text) if part.strip()]
    parts = [part for part in parts if not _EXAMPLE_WRAPPER_LINE_RE.fullmatch(part)]
    if len(parts) < 2 or len(parts) > 10:
        return None
    if not all(_looks_like_direct_arithmetic_line(part) for part in parts):
        return None

    rows: list[tuple[str, str]] = []
    for part in parts:
        value = _eval_fraction_expression(_strip_line_task_marker(part))
        rows.append((_pretty_direct_arithmetic_expression(part), _fraction_to_text(value)))

    solution_lines = ['Задача.', 'Дано несколько отдельных примеров.']
    for idx, (expr, _) in enumerate(rows, start=1):
        ordinal = _ordinal_example_word(idx).capitalize()
        solution_lines.append(f'{ordinal} пример: {expr}.')
    solution_lines.append('Решение.')
    for idx, (expr, answer) in enumerate(rows, start=1):
        ordinal = _ordinal_example_word(idx).capitalize()
        solution_lines.append(f'{ordinal} пример: {expr} = {answer}.')

    answer_parts = [f'{_ordinal_example_word(idx)} пример равен {answer}' for idx, (_, answer) in enumerate(rows, start=1)]
    solution_lines.append('Ответ: ' + '; '.join(answer_parts) + '.')
    solution_lines.append('Совет: если нужен подробный разбор каждого примера, можно отправлять примеры по одному.')
    return {
        'result': finalize_legacy_lines(solution_lines),
        'source': 'local-multiline-direct-examples',
        'validated': True,
    }

def _looks_like_collapsed_direct_examples(text: str) -> bool:
    """Detect a common newline-loss artifact: two direct examples glued by space."""
    source = str(text or '').strip()
    if '\n' in source or not source:
        return False
    if not _DIRECT_ARITH_LINE_RE.fullmatch(source):
        return False
    if len(re.findall(r'[+\-*/:÷×·]', source)) < 2:
        return False
    for match in re.finditer(r'(?<!\d)(\d{1,3}(?:\s+\d{1,3})+)(?!\d)', source):
        parts = match.group(1).split()
        if len(parts) >= 2 and all(len(part) == 3 for part in parts[1:]):
            continue
        return True
    return False


def _eval_fraction_expression(fragment: str) -> Fraction:
    source = _normalize_expression_fragment(fragment)
    tree = ast.parse(source, mode='eval')

    def _eval(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return Fraction(int(node.value), 1)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -_eval(node.operand)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return _eval(node.operand)
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError('division by zero')
                return left / right
        raise ValueError('unsupported expression fragment')

    return _eval(tree)


def _display_fragment(fragment: str) -> str:
    text = str(fragment or '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def extract_compare_expressions(raw_text: str) -> Optional[tuple[str, str]]:
    text = _normalize_text(raw_text)
    if not text:
        return None
    lower = text.lower()
    has_compare_cue = bool(
        re.search(r'\b(?:сравни(?:те)?|поставь(?:те)?\s+знак|какой\s+знак\s+поставить|определи(?:те)?\s+знак)\b', lower)
        or '...' in text
        or '…' in text
    )
    body = _strip_compare_prefix(text) if has_compare_cue else text
    body = re.sub(r'^между\s+', '', body, flags=re.IGNORECASE).strip()

    placeholder_match = re.split(r'\s*(?:\.\.\.|…|_{2,}|□|◻)\s*', body, maxsplit=1)
    if len(placeholder_match) == 2 and all(_looks_like_expression_fragment(part) for part in placeholder_match):
        return placeholder_match[0].strip(), placeholder_match[1].strip()

    between_match = re.search(r'между\s+(.+?)\s+и\s+(.+)$', body, flags=re.IGNORECASE)
    if between_match:
        left, right = between_match.group(1).strip(), between_match.group(2).strip()
        if _looks_like_expression_fragment(left) and _looks_like_expression_fragment(right):
            return left, right

    if has_compare_cue:
        split_parts = re.split(r'\s+и\s+', body, maxsplit=1, flags=re.IGNORECASE)
        if len(split_parts) == 2 and all(_looks_like_expression_fragment(part) for part in split_parts):
            return split_parts[0].strip(), split_parts[1].strip()

    return None


def _normalize_system_equation_line(compact: str) -> str:
    """Normalize grade-school two-variable lines to forms the legacy system solver handles well."""
    line = compact.replace('х', 'x').replace('у', 'y')
    # x=y+3 -> x-y=3; x=y-3 -> x-y=-3
    match = re.fullmatch(r'([xy])=([xy])([+-])(\d+)', line, flags=re.IGNORECASE)
    if match and match.group(1).lower() != match.group(2).lower():
        left_var = match.group(1).lower()
        right_var = match.group(2).lower()
        sign = match.group(3)
        value = int(match.group(4))
        delta = value if sign == '+' else -value
        if left_var == 'x' and right_var == 'y':
            return f'x-y={delta}'
        if left_var == 'y' and right_var == 'x':
            return f'x-y={-delta}'
    # x+3=y -> x-y=-3; x-3=y -> x-y=3
    match = re.fullmatch(r'([xy])([+-])(\d+)=([xy])', line, flags=re.IGNORECASE)
    if match and match.group(1).lower() != match.group(4).lower():
        left_var = match.group(1).lower()
        right_var = match.group(4).lower()
        sign = match.group(2)
        value = int(match.group(3))
        delta = value if sign == '+' else -value
        # left_var + delta = right_var -> left_var - right_var = -delta.
        if left_var == 'x' and right_var == 'y':
            return f'x-y={-delta}'
        if left_var == 'y' and right_var == 'x':
            return f'x-y={delta}'
    return line


def build_compare_expression_payload(raw_text: str) -> Optional[dict]:
    parts = extract_compare_expressions(raw_text)
    if not parts:
        return None
    left_raw, right_raw = parts
    try:
        left_value = _eval_fraction_expression(left_raw)
        right_value = _eval_fraction_expression(right_raw)
    except Exception:
        return None
    sign = '>' if left_value > right_value else '<' if left_value < right_value else '='
    left_text = _display_fragment(left_raw)
    right_text = _display_fragment(right_raw)
    left_value_text = _fraction_to_text(left_value)
    right_value_text = _fraction_to_text(right_value)
    result_text = finalize_legacy_lines([
        'Задача.',
        audit_task_line(raw_text),
        'Решение.',
        f'1) Вычисляем первое выражение: {left_text} = {left_value_text}.',
        f'2) Вычисляем второе выражение: {right_text} = {right_value_text}.',
        f'3) Сравниваем полученные значения: {left_value_text} {sign} {right_value_text}.',
        f'Ответ: {left_text} {sign} {right_text}.',
        'Совет: в задании на сравнение сначала вычисли оба выражения, а потом поставь знак между их значениями.',
    ])
    return {
        'result': result_text,
        'source': 'local-compare-expression',
        'validated': True,
    }


def canonicalize_system_submission(raw_text: str) -> Optional[str]:
    text = _normalize_text(raw_text)
    if not text or text.count('=') < 2:
        return None
    lower = text.lower()
    system_cue = bool(re.search(r'\bсистем[ауые]\b', lower))
    body = _strip_system_prefix(text)
    body = body.strip(' {}[]')
    if system_cue and body.count('=') >= 2 and ';' not in body and ',' not in body and '\n' not in body:
        body = re.sub(r'\s+и\s+', '\n', body, flags=re.IGNORECASE)
    body = re.sub(r'\s*[;]\s*', '\n', body)
    body = re.sub(r'\s*,\s*', '\n', body)
    lines = []
    for raw_line in body.split('\n'):
        line = raw_line.strip()
        line = re.sub(r'^(?:№\s*\d+|\d+[.)])\s*', '', line, flags=re.IGNORECASE)
        if not line:
            continue
        if line.count('=') != 1:
            continue
        compact = re.sub(r'\s+', '', line)
        if not _ALLOWED_EQ_CHARS_RE.fullmatch(compact):
            return None
        if not re.search(r'[xy]', compact, flags=re.IGNORECASE):
            return None
        lines.append(_normalize_system_equation_line(compact))
    if len(lines) < 2 or len(lines) > 3:
        return None
    var_sets = [set(re.findall(r'[xy]', line.lower())) for line in lines]
    if any(not var_set for var_set in var_sets):
        return None
    all_vars = set().union(*var_sets)
    if len(all_vars) == 1 and not system_cue:
        return None
    shared_vars = set.intersection(*var_sets) if len(var_sets) > 1 else set()
    if not system_cue and not shared_vars:
        return None
    return '\n'.join(lines)



_ORDINAL_FOR_BATCH = {
    1: 'первый', 2: 'второй', 3: 'третий', 4: 'четвёртый', 5: 'пятый',
    6: 'шестой', 7: 'седьмой', 8: 'восьмой', 9: 'девятый', 10: 'десятый',
    11: 'одиннадцатый', 12: 'двенадцатый', 13: 'тринадцатый', 14: 'четырнадцатый', 15: 'пятнадцатый',
    16: 'шестнадцатый', 17: 'семнадцатый', 18: 'восемнадцатый', 19: 'девятнадцатый', 20: 'двадцатый',
}


_BATCH_WRAPPER_RE = _EXAMPLE_WRAPPER_LINE_RE


def _strip_batch_line_prefix(line: str) -> str:
    value = str(line or '').strip()
    value = re.sub(r'^\s*№\s*\d{1,3}\s*[.)\]:;\-–—]*\s*', '', value, flags=re.IGNORECASE)
    value = re.sub(r'^\s*\d{1,3}\s*[.)\]]\s*', '', value, flags=re.IGNORECASE)
    marker = re.match(r'^\s*\d{1,2}\s*[:;]\s+(.+)$', value, flags=re.IGNORECASE)
    if marker:
        remainder = marker.group(1).strip()
        if re.search(r'\d\s*[+\-*/:÷×·=]\s*\d|[xyх]\s*[+\-*/=]|[+\-*/=]\s*[xyх]', remainder, flags=re.IGNORECASE):
            return remainder
    return value


def _looks_like_whitespace_joined_expressions(raw_text: str) -> bool:
    """Catch expressions that were accidentally joined after a lost newline.

    Example: a textarea value ``2+2\n32-8`` could be normalized into
    ``2 + 2 32 - 8``.  That must never be evaluated as one expression.
    """
    raw = str(raw_text or '').strip()
    if not raw or '\n' in raw or ';' in raw or ',' in raw:
        return False
    if not _ALLOWED_EXPR_CHARS_RE.fullmatch(raw):
        return False
    parts = [part.strip() for part in re.split(r'(?<=[0-9)])\s+(?=[0-9xyх(])', raw, flags=re.IGNORECASE) if part.strip()]
    if len(parts) < 2:
        return False
    return all(re.search(r'\d\s*[+\-*/:÷×·]\s*\d', part) and _looks_like_expression_fragment(part) for part in parts)


def _split_candidate_batch_lines(raw_text: str) -> list[str]:
    text = _normalize_text(raw_text)
    if not text:
        return []
    if '\n' in text:
        raw_parts = [part.strip() for part in text.split('\n') if part.strip()]
    elif ';' in text:
        raw_parts = [part.strip() for part in text.split(';') if part.strip()]
    elif _looks_like_whitespace_joined_expressions(text):
        raw_parts = [part.strip() for part in re.split(r'(?<=[0-9)])\s+(?=[0-9xyх(])', text, flags=re.IGNORECASE) if part.strip()]
    else:
        return []
    parts: list[str] = []
    for part in raw_parts:
        if _BATCH_WRAPPER_RE.fullmatch(part):
            continue
        stripped = _strip_batch_line_prefix(part)
        if stripped:
            parts.append(stripped)
    return parts


def _looks_like_standalone_arithmetic_or_equation(line: str) -> bool:
    value = _strip_batch_line_prefix(line)
    if not value or len(value) > 120:
        return False
    if not re.search(r'\d', value):
        return False
    if re.search(r'[а-яёa-z]', value, flags=re.IGNORECASE):
        letters = ''.join(re.findall(r'[а-яёa-z]', value, flags=re.IGNORECASE))
        letters = re.sub(r'[xyххуy]', '', letters, flags=re.IGNORECASE)
        if letters:
            return False
    if value.count('=') > 1:
        return False
    if '=' in value:
        compact = re.sub(r'\s+', '', value).replace('х', 'x').replace('Х', 'x').replace('у', 'y').replace('У', 'y')
        compact = compact.replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
        return bool(re.fullmatch(r'[0-9xy+\-*/().=]+', compact, flags=re.IGNORECASE) and re.search(r'[xy]', compact, flags=re.IGNORECASE))
    return _looks_like_expression_fragment(value)


def _display_batch_expression(line: str) -> str:
    value = _strip_batch_line_prefix(line)
    value = value.replace('−', '-').replace('–', '-').replace('—', '-')
    value = value.replace('×', '*').replace('·', '*').replace('÷', ':')
    value = re.sub(r'\s+', '', value)
    value = value.replace('*', ' × ')
    value = re.sub(r'(?<!^)\+', ' + ', value)
    value = re.sub(r'(?<!^)-', ' - ', value)
    value = value.replace(':', ' : ')
    value = value.replace('=', ' = ')
    return re.sub(r'\s+', ' ', value).strip()


def _solve_linear_one_variable_equation(line: str) -> Optional[tuple[str, str]]:
    compact = re.sub(r'\s+', '', _strip_batch_line_prefix(line)).replace('х', 'x').replace('Х', 'x')
    compact = compact.replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    if compact.count('=') != 1 or 'x' not in compact.lower():
        return None
    left, right = compact.split('=', 1)
    if not re.fullmatch(r'-?\d+', right):
        return None
    rhs = int(right)
    ans: Optional[int] = None
    if left == 'x':
        ans = rhs
    else:
        match = re.fullmatch(r'x([+\-*/])(\d+)', left)
        if match:
            op, raw = match.groups()
            a = int(raw)
            if op == '+':
                ans = rhs - a
            elif op == '-':
                ans = rhs + a
            elif op == '*' and a != 0 and rhs % a == 0:
                ans = rhs // a
            elif op == '/' and a != 0:
                ans = rhs * a
        if ans is None:
            match = re.fullmatch(r'(\d+)([+\-*])x', left)
            if match:
                a, op = int(match.group(1)), match.group(2)
                if op == '+':
                    ans = rhs - a
                elif op == '-':
                    ans = a - rhs
                elif op == '*' and a != 0 and rhs % a == 0:
                    ans = rhs // a
        if ans is None:
            match = re.fullmatch(r'(\d+)/x', left)
            if match and rhs != 0:
                a = int(match.group(1))
                if a % rhs == 0:
                    ans = a // rhs
    if ans is None:
        return None
    return 'x', str(ans)


def build_multiline_arithmetic_payload(raw_text: str) -> Optional[dict]:
    """Solve several bare examples line-by-line instead of gluing digits.

    Limited to simple arithmetic/equation lines; word problems still go through
    the ordinary one-task router and multi-task guard.
    """
    parts = _split_candidate_batch_lines(raw_text)
    if len(parts) < 2 or len(parts) > 20:
        return None
    if not all(_looks_like_standalone_arithmetic_or_equation(part) for part in parts):
        return None

    task_lines: list[str] = ['Задача.', 'Дано несколько отдельных примеров.']
    steps: list[str] = ['Решение.']
    answer_bits: list[str] = []
    for index, part in enumerate(parts, start=1):
        ordinal = _ORDINAL_FOR_BATCH.get(index, f'{index}-й')
        ordinal_title = ordinal.capitalize()
        display = _display_batch_expression(part)
        task_lines.append(f'{ordinal_title} пример: {display}.')
        equation_solution = _solve_linear_one_variable_equation(part)
        if equation_solution:
            var_name, value = equation_solution
            steps.append(f'{ordinal_title} пример: {display}, {var_name} = {value}.')
            answer_bits.append(f'{ordinal} пример: {var_name} = {value}')
            continue
        try:
            result_value = _eval_fraction_expression(part)
        except Exception:
            return None
        answer = _fraction_to_text(result_value)
        steps.append(f'{ordinal_title} пример: {display} = {answer}.')
        answer_bits.append(f'{ordinal} пример равен {answer}')

    result_text = finalize_legacy_lines([
        *task_lines,
        *steps,
        'Ответ: ' + ('; '.join(answer_bits)).capitalize() + '.',
        'Совет: каждая строка — отдельный пример, поэтому решаем их по очереди.',
    ])
    return {
        'result': result_text,
        'source': 'local-multiline-arithmetic',
        'validated': True,
    }

def build_multi_task_payload(raw_text: str) -> dict:
    result_text = finalize_legacy_lines([
        'Задача.',
        audit_task_line(raw_text),
        'Решение.',
        MULTI_TASK_MESSAGE,
        'Ответ: разделите задания и отправьте их по отдельности.',
        'Совет: систему уравнений и сравнение двух выражений можно отправлять одним запросом только как одно общее задание.',
    ])
    return {
        'result': result_text,
        'source': 'guard-multi-task',
        'validated': True,
        'code': 'multi_task_not_allowed',
    }


def _segments_with_math(parts: list[str]) -> int:
    count = 0
    for part in parts:
        lowered = part.lower()
        has_math_operator = bool(re.search(r'\d\s*[+\-*/=×÷:]\s*\d', part))
        if re.search(r'\d', part) and (_SOLVER_VERB_RE.search(lowered) or has_math_operator or '?' in part):
            count += 1
    return count


def is_multi_task_submission(raw_text: str) -> bool:
    text = _normalize_text(raw_text)
    if not text:
        return False
    if extract_compare_expressions(text) or canonicalize_system_submission(text):
        return False
    if build_multiline_arithmetic_payload(text):
        return False

    lowered = text.lower()
    if re.search(r'\b(?:продолжи(?:те)?|закономерност|ряд)\b', lowered):
        return False

    numbered_matches = _NUMBERED_TASK_RE.findall(text)
    if len(numbered_matches) >= 2 or ('№1' in text and '№2' in text):
        return True

    if _looks_like_collapsed_direct_examples(text):
        return True

    if ';' in text:
        parts = [part.strip() for part in text.split(';') if part.strip()]
        if _segments_with_math(parts) >= 2:
            return True

    if ',' in text:
        comma_parts = [part.strip() for part in re.split(r'\s*,\s*', text) if part.strip()]
        if len(comma_parts) >= 2:
            mathy_parts = 0
            for part in comma_parts:
                if _looks_like_expression_fragment(part):
                    mathy_parts += 1
                    continue
                compact = re.sub(r'\s+', '', part)
                if compact.count('=') == 1 and re.search(r'[xy]', compact, flags=re.IGNORECASE):
                    mathy_parts += 1
            if mathy_parts >= 2:
                return True

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) >= 2 and _segments_with_math(lines) >= 2:
        return True

    expr_and_expr_match = re.match(
        r'^\s*(?:реши(?:те)?|вычисли(?:те)?|найди(?:те)?|пример|выражение)?\s*:?' \
        r'\s*([^;\n]+?)\s+и\s+([^;\n]+?)\s*$',
        text,
        flags=re.IGNORECASE,
    )
    if expr_and_expr_match:
        left, right = expr_and_expr_match.group(1), expr_and_expr_match.group(2)
        if _looks_like_expression_fragment(left) and _looks_like_expression_fragment(right):
            return True

    equation_and_equation_match = re.match(
        r'^\s*(?:реши(?:те)?|найди(?:те)?|вычисли(?:те)?)?\s*:?\s*([^;\n]+?=[^;\n]+?)\s+и\s+([^;\n]+?=[^;\n]+?)\s*$',
        text,
        flags=re.IGNORECASE,
    )
    if equation_and_equation_match:
        return True

    sentences = [segment.strip() for segment in re.split(r'(?<=[.!?])\s+', text) if segment.strip()]
    if len(sentences) >= 2:
        mathy_sentence_count = 0
        for sentence in sentences:
            lower = sentence.lower()
            if re.search(r'\d', sentence) and (_SOLVER_VERB_RE.search(lower) or '?' in sentence):
                mathy_sentence_count += 1
        if mathy_sentence_count >= 2:
            return True

    return False


__all__ = [
    'MULTI_TASK_MESSAGE',
    'build_compare_expression_payload',
    'build_multi_task_payload',
    'build_multiline_arithmetic_payload',
    'build_multiline_direct_examples_payload',
    'canonicalize_system_submission',
    'extract_compare_expressions',
    'is_multi_task_submission',
]
