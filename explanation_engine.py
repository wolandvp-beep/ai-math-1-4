import ast
import math
import os
import re
from fractions import Fraction
from typing import Optional
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
DEEPSEEK_API_KEY = os.environ.get('myapp_ai_math_1_4_API_key')
SYSTEM_PROMPT = '''
Ты — методичный и очень точный учитель математики для детей 1–4 классов.

Твоя задача — дать короткое, понятное и проверяемое объяснение решения.

Пиши только по-русски.
Не используй markdown, списки, нумерацию, смайлики, похвалу и пустые вступления.
Нельзя писать «Молодец», «Отлично», «Давай разберёмся», «Хорошо», «Посмотрим».
Одна строка = одна мысль.
Сначала идёт объяснение, потом ответ.
Не выводи итог в первой строке.
Не выдумывай числа, предметы, единицы измерения и промежуточные данные, которых нет в условии.

Формат ответа всегда такой:
несколько коротких строк объяснения;
строка «Проверка: ...» только там, где она действительно нужна;
строка «Ответ: ...»;
строка «Совет: ...».

Требования к объяснению:
Для текстовой задачи коротко назови вопрос задачи.
Явно выбирай действие по смыслу: «Сложением, потому что ...», «Вычитанием, потому что ...», «Умножением, потому что ...», «Делением, потому что ...».
Для задач на неизвестный компонент прямо проговаривай правило: «Чтобы найти неизвестное слагаемое, нужно ...», «Чтобы найти неизвестное уменьшаемое, нужно ...», «Чтобы найти неизвестное вычитаемое, нужно ...», «Чтобы найти неизвестный множитель, нужно ...», «Чтобы найти неизвестное делимое, нужно ...», «Чтобы найти неизвестный делитель, нужно ...».
Для составной задачи строй мысль так: «Можем ли мы сразу ответить?», «Нет.», «Почему нет?», «Сначала узнаем ...», «Потом узнаем ...».
Если задача на цену, количество, стоимость, движение, приведение к единице или пропорциональное деление, можно дать очень короткое текстовое краткое условие.
Для дробей сначала смотри на знаменатели, а в задачах на долю объясняй, что знаменатель показывает, на сколько частей делим целое, если это помогает.
Для геометрии сначала назови правило, потом подставь числа.

Не повторяй одну и ту же мысль разными словами.
Не оставляй общих фраз без пользы.
Если запись не похожа на задачу по математике или непонятна, спокойно попроси записать её понятнее.
'''.strip()
SYSTEM_PROMPT_V10 = SYSTEM_PROMPT
BANNED_OPENERS = re.compile('^(?:отлично|давай(?:те)?|хорошо|молодец|правильно|посмотрим|разбер[её]мся|начн[её]м)\\b', re.IGNORECASE)
LEADING_FILLER_SENTENCE = re.compile('^(?:отлично|давай(?:те)?|хорошо|молодец|правильно|посмотрим|разбер[её]мся|начн[её]м)\\b[^.!?\\n]*[.!?]\\s*', re.IGNORECASE)
NON_MATH_REPLY = 'Не видно точной математической записи.\nНапишите пример или задачу понятнее.\nОтвет: сначала нужно уточнить запись.\nСовет: пишите числа и знаки действия полностью.'
DEFAULT_ADVICE = {'expression': 'считай по порядку и не пропускай действие.', 'equation': 'в уравнении оставляй x отдельно и делай проверку.', 'fraction': 'сначала смотри на знаменатели, потом выполняй действие.', 'geometry': 'сначала пойми, что нужно найти, а потом выбирай правило.', 'word': 'сначала пойми смысл задачи, а потом выбирай действие.', 'other': 'прочитай запись ещё раз и решай по шагам.'}
OPERATOR_SYMBOLS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '×', ast.Div: ':'}
OPERATOR_VERBS = {ast.Add: 'складываем', ast.Sub: 'вычитаем', ast.Mult: 'умножаем', ast.Div: 'делим'}
PRECEDENCE = {ast.Add: 1, ast.Sub: 1, ast.Mult: 2, ast.Div: 2}

def is_int_literal_node(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int

def int_from_literal_node(node: ast.AST) -> int:
    if not is_int_literal_node(node):
        raise ValueError('Expected integer literal node')
    return int(node.value)
WORD_GAIN_HINTS = ('еще', 'ещё', 'добав', 'купил', 'купила', 'купили', 'подар', 'наш', 'принес', 'принёс', 'принесли', 'положил', 'положила', 'положили', 'стало', 'теперь', 'прилетели', 'приехали')
WORD_LOSS_HINTS = ('отдал', 'отдала', 'отдали', 'съел', 'съела', 'съели', 'убрал', 'убрала', 'убрали', 'забрал', 'забрала', 'забрали', 'потер', 'потрат', 'продал', 'продала', 'продали', 'ушло', 'остал', 'сломал', 'сломала', 'сломали', 'снял', 'сняла', 'сняли')
WORD_COMPARISON_HINTS = ('на сколько больше', 'на сколько меньше')
GROUPING_VERBS = ('разлож', 'раздал', 'раздала', 'раздали', 'расстав', 'упакова', 'улож', 'постав', 'посад', 'слож')
GEOMETRY_UNIT_RE = re.compile('\\b(мм|см|дм|м|км)\\b', re.IGNORECASE)

def strip_known_prefix(text: str) -> str:
    cleaned = str(text or '').strip()
    cleaned = re.sub('^(?:задача|пример|уравнение|дроби|геометрия|выражение|математика)\\s*:\\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def normalize_dashes(text: str) -> str:
    return str(text or '').replace('−', '-').replace('–', '-').replace('—', '-')

def normalize_cyrillic_x(text: str) -> str:
    return str(text or '').replace('Х', 'x').replace('х', 'x')

def to_expression_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(text)
    text = normalize_cyrillic_x(text)
    text = text.replace('×', '*').replace('÷', '/').replace(':', '/')
    text = re.sub('(?<=\\d)\\s*[xXx]\\s*(?=\\d)', ' * ', text)
    text = re.sub('\\s*=\\s*\\??\\s*$', '', text).strip()
    text = re.sub('\\s*\\?\\s*$', '', text).strip()
    if re.search('[A-Za-zА-Яа-я]', text):
        return None
    if not re.fullmatch('[\\d\\s()+\\-*/]+', text):
        return None
    compact = re.sub('\\s+', '', text)
    if not compact or not re.search('[+\\-*/]', compact):
        return None
    return compact

def to_equation_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(text)
    text = normalize_cyrillic_x(text)
    text = text.replace('X', 'x')
    text = text.replace('×', '*').replace('÷', '/').replace(':', '/')
    text = re.sub('\\s+', '', text)
    if text.count('=') != 1 or text.count('x') != 1:
        return None
    if not re.fullmatch('[\\dx=+\\-*/]+', text):
        return None
    return text

def to_fraction_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(text)
    text = re.sub('[=?]+$', '', text).strip()
    if not re.fullmatch('\\s*\\d+\\s*/\\s*\\d+\\s*[+\\-]\\s*\\d+\\s*/\\s*\\d+\\s*', text):
        return None
    return text

def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f'{value.numerator}/{value.denominator}'

def format_number(value: int) -> str:
    return str(value)

def normalize_sentence(text: str) -> str:
    line = str(text or '').strip()
    if not line:
        return ''
    line = line.rstrip()
    if line[-1] not in '.!?':
        line += '.'
    return line

def join_explanation_lines(*lines: str) -> str:
    parts = [normalize_sentence(line) for line in lines if str(line or '').strip()]
    return '\n'.join(parts)

def normalize_word_problem_text(text: str) -> str:
    cleaned = strip_known_prefix(text)
    cleaned = normalize_dashes(cleaned)
    cleaned = cleaned.replace('ё', 'е').replace('Ё', 'Е')
    cleaned = re.sub('\\s+', ' ', cleaned)
    return cleaned.strip()

def extract_ordered_numbers(text: str):
    return [int(value) for value in re.findall('\\d+', str(text or ''))]

def contains_any_fragment(text: str, fragments) -> bool:
    base = str(text or '')
    return any((fragment in base for fragment in fragments))

def geometry_unit(text: str) -> str:
    match = GEOMETRY_UNIT_RE.search(str(text or ''))
    return match.group(1).lower() if match else ''

def with_unit(value: int, unit: str, square: bool=False) -> str:
    suffix = ''
    if unit:
        suffix = f' {unit}²' if square else f' {unit}'
    return f'{value}{suffix}'

def plural_form(count: int, one: str, few: str, many: str) -> str:
    value = abs(int(count)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return many
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many

def explain_ratio_word_problem(first: int, second: int) -> Optional[str]:
    bigger = max(first, second)
    smaller = min(first, second)
    if smaller == 0:
        return join_explanation_lines('На ноль делить нельзя', 'Ответ: деление на ноль невозможно', "Совет: в задачах 'во сколько раз' нужно делить на ненулевое число")
    if bigger % smaller != 0:
        return None
    result = bigger // smaller
    return join_explanation_lines('Нужно узнать, во сколько раз одно число больше или меньше другого', f'Для этого делим большее число на меньшее: {bigger} : {smaller} = {result}', f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}", "Совет: вопрос 'во сколько раз больше или меньше' обычно решаем делением")
SEQUENTIAL_GAIN_STEMS = ('еще', 'ещё', 'добав', 'купил', 'купила', 'купили', 'подар', 'наш', 'принес', 'принёс', 'принесли', 'положил', 'положила', 'положили', 'дала', 'дали', 'получил', 'получила', 'получили', 'вош', 'заш', 'прилет', 'приех', 'прибав')
SEQUENTIAL_LOSS_STEMS = ('отдал', 'отдала', 'отдали', 'съел', 'съела', 'съели', 'убрал', 'убрала', 'убрали', 'забрал', 'забрала', 'забрали', 'потер', 'потрат', 'продал', 'продала', 'продали', 'выш', 'уш', 'снял', 'сняла', 'сняли', 'улетел', 'улетели', 'уех', 'завял')

def has_word_stem(text: str, stems) -> bool:
    fragment = str(text or '').lower().replace('ё', 'е')
    return any((re.search(f'\\b{re.escape(stem)}', fragment) for stem in stems))

def apply_more_less(base: int, delta: int, mode: str) -> Optional[int]:
    if mode == 'больше':
        return base + delta
    result = base - delta
    return result if result >= 0 else None

def extract_relation_pairs(text: str):
    return [(int(match.group(1)), match.group(2)) for match in re.finditer('на\\s+(\\d+)\\s+(больше|меньше)', str(text or ''))]

def classify_change_fragment(fragment: str) -> Optional[str]:
    part = str(fragment or '').lower().replace('ё', 'е')
    gain = has_word_stem(part, SEQUENTIAL_GAIN_STEMS)
    loss = has_word_stem(part, SEQUENTIAL_LOSS_STEMS)
    if gain and (not loss):
        return 'gain'
    if loss and (not gain):
        return 'loss'
    return None

def split_between_change_fragment(fragment: str):
    part = str(fragment or '')
    pieces = re.split('(?:,\\s*)?(?:а\\s+потом|потом|а\\s+затем|затем)\\b', part, maxsplit=1)
    if len(pieces) == 2:
        return (pieces[0], pieces[1])
    return (part, part)

def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None
    lower = text.lower()
    if not re.search('[а-я]', lower):
        return None
    numbers = extract_ordered_numbers(lower)
    if len(numbers) < 2:
        return None
    asks_total = bool(re.search('сколько[^.?!]*\\b(всего|вместе)\\b', lower))
    asks_current = bool(re.search('сколько[^.?!]*\\b(стало|теперь|осталось)\\b', lower))
    asks_plain_quantity = 'сколько' in lower and (not asks_total) and (not asks_current) and ('на сколько' not in lower) and ('во сколько' not in lower)
    asks_named_value = bool(re.search(r'сколько|какое|какова|каков|чему\s+рав', lower))
    relation_pairs = extract_relation_pairs(lower)
    if len(numbers) == 2 and len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        if delta == numbers[1]:
            if asks_total:
                return explain_related_total_word_problem(numbers[0], delta, mode)
            if asks_plain_quantity:
                return explain_related_quantity_word_problem(numbers[0], delta, mode)
    if len(numbers) == 3 and len(relation_pairs) == 2 and asks_plain_quantity:
        (delta1, mode1), (delta2, mode2) = relation_pairs
        if delta1 == numbers[1] and delta2 == numbers[2]:
            chain = explain_relation_chain_word_problem(numbers[0], delta1, mode1, delta2, mode2)
            if chain:
                return chain
    if len(numbers) == 3 and asks_total and ('ещё' in lower or 'еще' in lower or 'отдельно' in lower) and ('по' in lower):
        groups_match = re.search('\\b(?:в|на)?\\s*(\\d+)\\s+[а-я]+\\s+по\\s+(\\d+)\\b', lower)
        if groups_match:
            groups = int(groups_match.group(1))
            per_group = int(groups_match.group(2))
            remaining = list(numbers)
            for value in (groups, per_group):
                if value in remaining:
                    remaining.remove(value)
            if len(remaining) == 1:
                return explain_groups_plus_extra_word_problem(groups, per_group, remaining[0])
    if len(numbers) == 3 and (asks_total or asks_current):
        fragments = re.split('\\d+', lower)
        if len(fragments) >= 4:
            first_following, second_leading = split_between_change_fragment(fragments[2])
            first_mode = classify_change_fragment(fragments[1]) or classify_change_fragment(first_following)
            second_mode = classify_change_fragment(second_leading) or classify_change_fragment(fragments[3])
            if first_mode and second_mode:
                sequential = explain_sequential_change_word_problem(numbers[0], numbers[1], first_mode, numbers[2], second_mode)
                if sequential:
                    return sequential
    return None

def try_local_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None
    lower = text.lower()
    if not re.search('[а-я]', lower):
        return None
    numbers = extract_ordered_numbers(lower)
    if len(numbers) != 2:
        return None
    first, second = numbers
    per_group_match = re.search('\\bпо\\s+(\\d+)\\b', lower)
    per_group = int(per_group_match.group(1)) if per_group_match else None
    other_numbers = list(numbers)
    if per_group is not None and per_group in other_numbers:
        other_numbers.remove(per_group)
    other_value = other_numbers[0] if other_numbers else None
    asks_ratio = 'во сколько' in lower and ('больше' in lower or 'меньше' in lower)
    asks_compare = contains_any_fragment(lower, WORD_COMPARISON_HINTS) or ('на сколько' in lower and ('больше' in lower or 'меньше' in lower))
    asks_initial = 'сколько было' in lower
    asks_left = bool(re.search('сколько[^.?!]*\\bосталось\\b', lower))
    asks_now = bool(re.search('сколько[^.?!]*\\b(стало|теперь)\\b', lower))
    asks_total = bool(re.search('сколько[^.?!]*\\b(всего|вместе)\\b', lower))
    asks_each = 'кажд' in lower or 'поровну' in lower
    asks_added = contains_any_fragment(lower, ('сколько добав', 'сколько подар', 'сколько куп', 'сколько прин', 'сколько полож'))
    asks_removed = contains_any_fragment(lower, ('сколько отдал', 'сколько съел', 'сколько убрал', 'сколько забрал', 'сколько потрат', 'сколько продал', 'сколько потер'))
    asks_groups = contains_any_fragment(lower, ('сколько короб', 'сколько корзин', 'сколько пакет', 'сколько тарел', 'сколько полок', 'сколько ряд', 'сколько групп', 'сколько ящик', 'сколько банок', 'сколько парт', 'сколько машин', 'сколько мест'))
    asks_remainder = 'остат' in lower or 'сколько остан' in lower or 'полных' in lower
    needs_extra_group = contains_any_fragment(lower, ('нужно', 'нужны', 'понадоб', 'потребует'))
    has_gain = contains_any_fragment(lower, WORD_GAIN_HINTS)
    has_loss = contains_any_fragment(lower, WORD_LOSS_HINTS)
    has_grouping = contains_any_fragment(lower, GROUPING_VERBS)
    if asks_ratio:
        ratio = explain_ratio_word_problem(first, second)
        if ratio:
            return ratio
    relation_pairs = extract_relation_pairs(lower)
    if relation_pairs:
        return None
    if asks_compare:
        return explain_comparison_word_problem(first, second)
    if asks_initial and has_loss:
        return explain_find_initial_after_loss_problem(first, second)
    if asks_initial and has_gain:
        explanation = explain_find_initial_after_gain_problem(max(first, second), min(first, second))
        return explanation or None
    if asks_added:
        return explain_find_added_problem(first, second)
    if asks_removed:
        return explain_find_removed_problem(first, second)
    if asks_each and ('раздел' in lower or 'раздал' in lower or 'раздала' in lower or ('раздали' in lower) or ('получ' in lower) or ('достал' in lower) or ('достан' in lower)):
        return explain_sharing_word_problem(first, second)
    if 'по' in lower and (asks_groups or has_grouping):
        total = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        grouped = explain_group_count_word_problem(total, size, needs_extra_group=needs_extra_group, explicit_remainder=asks_remainder)
        if grouped:
            return grouped
    if 'по' in lower and asks_total:
        groups = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        return explain_multiplication_word_problem(groups, size)
    if has_loss and (asks_left or asks_now):
        explanation = explain_subtraction_word_problem(first, second)
        return explanation or None
    if has_gain and (asks_total or asks_now) or (asks_total and (not has_loss) and ('по' not in lower)):
        return explain_addition_word_problem(first, second)
    return None

def infer_task_kind(text: str) -> str:
    base = strip_known_prefix(text)
    lowered = normalize_cyrillic_x(base).lower()
    if re.search('\\d+\\s*/\\s*\\d+\\s*[+\\-]\\s*\\d+\\s*/\\s*\\d+', lowered):
        return 'fraction'
    if 'x' in lowered and '=' in lowered:
        return 'equation'
    if re.search('периметр|площадь|прямоугольник|квадрат|сторон|длина|ширина|сторона', lowered):
        return 'geometry'
    if re.search('[а-я]', lowered):
        return 'word'
    if re.search('[+\\-*/()×÷:]', lowered):
        return 'expression'
    return 'other'

def sanitize_model_text(text: str) -> str:
    cleaned = str(text or '')
    while True:
        updated = LEADING_FILLER_SENTENCE.sub('', cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
    cleaned = cleaned.replace('\r', '')
    cleaned = cleaned.replace('**', '').replace('__', '').replace('`', '')
    cleaned = re.sub('^\\s*#{1,6}\\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace('\\(', '').replace('\\)', '')
    cleaned = cleaned.replace('\\[', '').replace('\\]', '')
    cleaned = cleaned.replace('\\', '')
    cleaned = re.sub('^\\s*[-*•]\\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub('^\\s*\\d+[.)]\\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub('^\\s*Шаг\\s*\\d+\\s*:?\\s*', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub('\\b(Запомни|Памятка)\\b\\s*[—:-]?', 'Совет:', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub('\\s*(Ответ\\s*:)', '\\n\\1', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub('\\s*(Совет\\s*:)', '\\n\\1', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub('\\s*(Проверка\\s*:)', '\\n\\1', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub('\\n{3,}', '\n\n', cleaned)
    raw_lines = [line.strip() for line in cleaned.split('\n')]
    lines = []
    seen = set()
    for raw in raw_lines:
        if not raw:
            continue
        if BANNED_OPENERS.match(raw):
            continue
        line = re.sub('\\s+', ' ', raw)
        line = re.sub('^Совет:\\s*Совет:\\s*', 'Совет: ', line, flags=re.IGNORECASE)
        line = re.sub('^Ответ:\\s*Ответ:\\s*', 'Ответ: ', line, flags=re.IGNORECASE)
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return '\n'.join(lines).strip()
GENERIC_BODY_LINE_RE = re.compile('^(?:известны два количества|сначала смотрим, сколько было|сначала находим второе количество|сначала узна(?:е|ё)м, сколько предметов в одинаковых группах|нужно оставить x отдельно)[.!?]?$', re.IGNORECASE)

def line_has_math_signal(text: str) -> bool:
    return bool(re.search('\\d|x|х|[+\\-=:×÷/]', str(text or ''), flags=re.IGNORECASE))

def normalize_body_lines(lines):
    raw = []
    seen = set()
    for line in lines:
        cleaned = shorten_body_line(line)
        if not cleaned:
            continue
        key = cleaned.lower().rstrip('.!?')
        if key in seen:
            continue
        seen.add(key)
        raw.append(cleaned)
    informative_exists = any((line_has_math_signal(line) for line in raw))
    result = []
    for line in raw:
        if informative_exists and GENERIC_BODY_LINE_RE.match(line.strip()):
            continue
        result.append(line)
    if not result:
        return raw
    return result

def validate_expression_ast(node: ast.AST) -> bool:
    if isinstance(node, ast.Expression):
        return validate_expression_ast(node.body)
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)) and validate_expression_ast(node.left) and validate_expression_ast(node.right)
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, ast.USub) and validate_expression_ast(node.operand)
    return is_int_literal_node(node)

def parse_expression_ast(source: str) -> Optional[ast.AST]:
    try:
        parsed = ast.parse(source, mode='eval')
    except SyntaxError:
        return None
    if not validate_expression_ast(parsed):
        return None
    return parsed.body

def eval_fraction_node(node: ast.AST) -> Fraction:
    if is_int_literal_node(node):
        return Fraction(int_from_literal_node(node), 1)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -eval_fraction_node(node.operand)
    if isinstance(node, ast.BinOp):
        left = eval_fraction_node(node.left)
        right = eval_fraction_node(node.right)
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
    raise ValueError('Unsupported expression')

def precedence_for_node(node: ast.AST) -> int:
    if isinstance(node, ast.BinOp):
        return PRECEDENCE[type(node.op)]
    if isinstance(node, ast.UnaryOp):
        return 3
    return 4

def render_node(node: ast.AST, parent_precedence: int=0, is_right_child: bool=False) -> str:
    if is_int_literal_node(node):
        return str(int_from_literal_node(node))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = render_node(node.operand, 3)
        return f'-{inner}'
    if isinstance(node, ast.BinOp):
        current_precedence = PRECEDENCE[type(node.op)]
        left_text = render_node(node.left, current_precedence, False)
        right_text = render_node(node.right, current_precedence, True)
        text = f'{left_text} {OPERATOR_SYMBOLS[type(node.op)]} {right_text}'
        needs_brackets = current_precedence < parent_precedence or (is_right_child and isinstance(node.op, (ast.Add, ast.Sub)) and (parent_precedence == current_precedence))
        if needs_brackets:
            return f'({text})'
        return text
    raise ValueError('Unsupported node')

def build_eval_steps(node: ast.AST):
    if is_int_literal_node(node):
        return (eval_fraction_node(node), [])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return (eval_fraction_node(node), [])
    if not isinstance(node, ast.BinOp):
        return (eval_fraction_node(node), [])
    left_value, left_steps = build_eval_steps(node.left)
    right_value, right_steps = build_eval_steps(node.right)
    result_value = eval_fraction_node(node)
    step = {'verb': OPERATOR_VERBS[type(node.op)], 'left': format_fraction(left_value), 'operator': OPERATOR_SYMBOLS[type(node.op)], 'right': format_fraction(right_value), 'result': format_fraction(result_value)}
    return (result_value, left_steps + right_steps + [step])

def format_step_lines(steps, raw_source: str):
    lines = []
    has_brackets = '(' in raw_source or ')' in raw_source
    for index, step in enumerate(steps):
        if index == 0 and has_brackets and (len(steps) > 1):
            prefix = 'Сначала считаем в скобках'
            lines.append(f"{prefix}: {step['left']} {step['operator']} {step['right']} = {step['result']}")
            continue
        if index == 0:
            prefix = 'Сначала'
        elif index == 1:
            prefix = 'Потом'
        else:
            prefix = 'Дальше'
        lines.append(f"{prefix} {step['verb']}: {step['left']} {step['operator']} {step['right']} = {step['result']}")
    return lines

def root_operator_name(node: ast.AST) -> Optional[str]:
    if not isinstance(node, ast.BinOp):
        return None
    if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        return type(node.op).__name__.lower()
    return None

def advice_for_expression(node: ast.AST, source: str) -> str:
    if '(' in source or ')' in source:
        return 'в выражении со скобками сначала считай в скобках.'
    kinds = []
    for child in ast.walk(node):
        if isinstance(child, ast.BinOp):
            kinds.append(type(child.op))
    unique_kinds = {kind for kind in kinds}
    if len(unique_kinds) > 1:
        return 'сначала выполняй умножение и деление, потом сложение и вычитание.'
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return 'большие числа удобно складывать по частям.'
        if isinstance(node.op, ast.Sub):
            return 'в вычитании удобно идти по частям.'
        if isinstance(node.op, ast.Mult):
            return 'умножение удобно разложить на десятки и единицы.'
        if isinstance(node.op, ast.Div):
            return 'после деления полезно сделать проверку умножением.'
    return default_advice('expression')

def try_simple_binary_int_expression(node: ast.AST) -> Optional[dict]:
    if not isinstance(node, ast.BinOp):
        return None
    if not is_int_literal_node(node.left) or not is_int_literal_node(node.right):
        return None
    left = int_from_literal_node(node.left)
    right = int_from_literal_node(node.right)
    if left < 0 or right < 0:
        return None
    return {'operator': type(node.op), 'left': left, 'right': right}

def try_local_expression_explanation(raw_text: str) -> Optional[str]:
    source = to_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    simple = try_simple_binary_int_expression(node)
    if simple:
        operator = simple['operator']
        left = simple['left']
        right = simple['right']
        if operator is ast.Add:
            return explain_simple_addition(left, right)
        if operator is ast.Sub:
            return explain_simple_subtraction(left, right)
        if operator is ast.Mult:
            return explain_simple_multiplication(left, right)
        if operator is ast.Div:
            return explain_simple_division(left, right)
    try:
        value, steps = build_eval_steps(node)
    except ZeroDivisionError:
        return join_explanation_lines('На ноль делить нельзя', 'Ответ: деление на ноль невозможно', 'Совет: проверь делитель перед вычислением')
    except Exception:
        return None
    if not steps:
        return None
    body_lines = format_step_lines(steps, source)
    answer = format_fraction(value)
    advice = advice_for_expression(node, source)
    return join_explanation_lines(*body_lines, f'Ответ: {answer}', f'Совет: {advice}')

def swap_equation_sides_if_needed(lhs: str, rhs: str):
    if 'x' not in lhs and 'x' in rhs:
        return (rhs, lhs)
    return (lhs, rhs)

def format_equation_check(template: str, value_text: str, expected_text: str) -> str:
    expression = template.replace('x', value_text)
    return f'Проверка: {expression} = {expected_text}'

async def call_deepseek(payload: dict, timeout_seconds: float=45.0):
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post('https://api.deepseek.com/v1/chat/completions', headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'}, json=payload)
    if response.status_code != 200:
        return {'error': f'DeepSeek API error {response.status_code}', 'details': response.text[:1500]}
    try:
        result = response.json()
    except Exception:
        return {'error': 'DeepSeek вернул не JSON', 'details': response.text[:1500]}
    if 'choices' not in result or not result['choices']:
        return {'error': 'DeepSeek вернул неожиданный формат ответа', 'details': str(result)[:1500]}
    message = result['choices'][0].get('message', {})
    answer = (message.get('content') or '').strip()
    if not answer:
        return {'error': 'DeepSeek вернул пустой ответ', 'details': str(result)[:1500]}
    return {'result': answer}
COMPACT_DEFAULT_ADVICE = {'expression': 'считай по порядку.', 'equation': 'оставляй x отдельно.', 'fraction': 'сначала смотри на знаменатели.', 'geometry': 'сначала выбери правило.', 'word': 'сначала пойми, что нужно найти.', 'other': 'решай по шагам.'}
LOW_VALUE_BODY_PATTERNS = [re.compile('^это (?:составная )?задача(?:[^.!?]*)$', re.IGNORECASE), re.compile('^известны два количества$', re.IGNORECASE), re.compile('^сначала смотрим, сколько было$', re.IGNORECASE), re.compile('^сравниваем, на сколько стало (?:больше|меньше)$', re.IGNORECASE), re.compile('^у квадрата все стороны равны$', re.IGNORECASE), re.compile('^у прямоугольника длина и ширина повторяются по два раза$', re.IGNORECASE), re.compile('^площадь квадрата равна стороне, умноженной на сторону$', re.IGNORECASE), re.compile('^площадь прямоугольника равна длине, умноженной на ширину$', re.IGNORECASE)]
BODY_LINE_LIMITS = {'expression': 4, 'fraction': 4, 'equation': 4, 'geometry': 3, 'word': 3, 'other': 3}

def shorten_body_line(line: str) -> str:
    text = str(line or '').strip()
    if not text:
        return ''
    replacements = [('^Это (?:составная )?задача, поэтому решаем по действиям$', 'Решаем по действиям'), ('^Это задача на два действия$', 'Решаем по действиям'), ('^Нужно узнать, сколько ', 'Ищем, сколько '), ('^Нужно узнать разницу между двумя числами$', 'Ищем разницу между числами'), ('^Сначала смотрим, сколько было$', ''), ('^Потом узнаем, сколько убрали:?\\s*(.+)$', 'Убрали: \\1'), ('^Потом узнаем, сколько добавили:?\\s*(.+)$', 'Добавили: \\1'), ('^Потом узнаем, сколько прибавили:?\\s*(.+)$', 'Прибавили: \\1'), ('^При\\s+переносе\\s+через\\s+знак\\s+равно\\s+умножение\\s+меняется\\s+на\\s+деление[.!?]?$', 'Умножение меняем на деление'), ('^При\\s+переносе\\s+через\\s+знак\\s+равно\\s+деление\\s+меняется\\s+на\\s+умножение[.!?]?$', 'Деление меняем на умножение'), ('^При\\s+переносе\\s+через\\s+знак\\s+равно\\s+плюс\\s+меняется\\s+на\\s+минус[.!?]?$', 'Плюс меняем на минус'), ('^При\\s+переносе\\s+через\\s+знак\\s+равно\\s+минус\\s+меняется\\s+на\\s+плюс[.!?]?$', 'Минус меняем на плюс'), ('^Нужно оставить x отдельно$', 'Ищем x'), ('^Число\\s+([\\d/]+)\\s+переносим\\s+вправо$', 'Переносим \\1 вправо'), ('^Если периметр равен\\s+(\\d+),\\s+одну сторону находим делением на 4$', 'Делим периметр на 4'), ('^Чтобы найти ширину, делим площадь на длину:\\s*(.+)$', 'Делим площадь на длину: \\1'), ('^Чтобы найти длину, делим площадь на ширину:\\s*(.+)$', 'Делим площадь на ширину: \\1'), ('^Чтобы узнать, сколько было сначала, нужно\\s+', 'Чтобы узнать, сколько было сначала, '), ('^Чтобы узнать, сколько получилось вместе, используем\\s+', 'Чтобы узнать итог, используем '), ('^Чтобы узнать, сколько всего, используем\\s+', 'Чтобы узнать итог, используем '), ('^Потом меняем число ещё раз:\\s*(.+)$', 'Потом: \\1'), ('^Теперь считаем вместе:\\s*(.+)$', 'Потом: \\1')]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    text = re.sub('\\bобычно\\b', '', text, flags=re.IGNORECASE)
    text = re.sub('\\bчасто\\b', '', text, flags=re.IGNORECASE)
    text = re.sub('\\bудобно\\b', '', text, flags=re.IGNORECASE)
    text = re.sub('\\s{2,}', ' ', text).strip(' ,.;')
    return capitalize_if_needed(text)

def shorten_advice_line(line: str, kind: str) -> str:
    text = str(line or '').strip()
    if not text:
        return default_advice(kind)
    replacements = [('^большие числа удобно складывать по частям$', 'большие числа складывай по частям'), ('^в вычитании удобно сначала убрать десятки, потом единицы$', 'сначала убирай десятки, потом единицы'), ('^в вычитании удобно идти по частям$', 'вычитай по частям'), ('^если трудно, представь умножение как одинаковые группы$', 'умножение можно представить как одинаковые группы'), ('^после деления полезно сделать проверку умножением$', 'проверяй деление умножением'), ('^остаток всегда должен быть меньше делителя$', 'остаток меньше делителя'), ('^множитель переносим через знак равно делением$', 'множитель переносим делением'), ('^при переносе множителя вправо выполняем деление$', 'множитель переносим делением'), ('^если x делят на число, справа нужно умножить$', 'деление меняем на умножение'), ('^если x стоит в делителе, раздели делимое на результат$', 'если x в делителе, дели делимое на результат'), ('^если x стоит после минуса, вычти ответ из первого числа$', 'если x после минуса, вычитай из первого числа'), ('^если знаменатели одинаковые, меняется только числитель$', 'при одинаковых знаменателях меняется только числитель'), ('^если знаменатели разные, сначала приведи дроби к общему знаменателю$', 'сначала приведи дроби к общему знаменателю'), ('^если нужно узнать, сколько всего, складывай$', 'если спрашивают про всё вместе, складывай'), ('^если что-то убрали, используй вычитание$', 'если что-то убрали, используй вычитание'), ('^если что-то убрали, отдали или съели, нужно вычитание$', 'если что-то убрали, используй вычитание'), ('^если одно количество больше или меньше другого, сначала найди его значение$', 'сначала найди второе число'), ('^если одно количество зависит от другого, сначала найди его, потом считай всё вместе$', 'сначала найди второе число'), ('^в задачах в два действия считай изменения по порядку$', 'считай по порядку'), ('^если числа зависят друг от друга по цепочке, решай по шагам$', 'решай по шагам'), ('^у квадрата 4 равные стороны$', 'у квадрата 4 равные стороны'), ('^если известны площадь и длина, ширину находим делением$', 'ширина = площадь : длина'), ('^если известны площадь и ширина, длину находим делением$', 'длина = площадь : ширина'), ('^по периметру прямоугольника сначала находи половину периметра$', 'сначала найди половину периметра')]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    text = re.sub('\\bобычно\\b', '', text, flags=re.IGNORECASE)
    text = re.sub('\\bчасто\\b', '', text, flags=re.IGNORECASE)
    text = re.sub('\\bудобно\\b', '', text, flags=re.IGNORECASE)
    text = re.sub('\\s{2,}', ' ', text).strip(' ,.;')
    return text or default_advice(kind)

def line_relevance_score(line: str, index: int) -> int:
    text = str(line or '')
    lower = text.lower()
    score = 0
    if '=' in text:
        score += 5
    if re.search('\\d|x|х', lower):
        score += 2
    if re.search('\\b(складываем|вычитаем|умножаем|делим|получаем|переносим|проверка|приводим|ищем|решаем|сначала|потом)\\b', lower):
        score += 3
    if lower.startswith('ищем'):
        score += 2
    if index == 0:
        score += 1
    if is_low_value_body_line(text):
        score -= 4
    return score

def try_local_equation_explanation(raw_text: str) -> Optional[str]:
    source = to_equation_source(raw_text)
    if not source:
        return None
    lhs, rhs = source.split('=', 1)
    lhs, rhs = swap_equation_sides_if_needed(lhs, rhs)
    try:
        rhs_value = Fraction(int(rhs), 1)
    except ValueError:
        return None
    patterns = [('^x\\+(\\d+)$', 'x_plus'), ('^x-(\\d+)$', 'x_minus'), ('^x\\*(\\d+)$', 'x_mul'), ('^x/(\\d+)$', 'x_div'), ('^(\\d+)\\+x$', 'plus_x'), ('^(\\d+)-x$', 'minus_x'), ('^(\\d+)\\*x$', 'mul_x'), ('^(\\d+)/x$', 'div_x')]
    for pattern, kind in patterns:
        match = re.fullmatch(pattern, lhs)
        if not match:
            continue
        number = Fraction(int(match.group(1)), 1)
        number_text = format_fraction(number)
        rhs_text = format_fraction(rhs_value)
        if kind in {'x_plus', 'plus_x'}:
            answer = rhs_value - number
            check = format_equation_check('x + ' + number_text if kind == 'x_plus' else number_text + ' + x', format_fraction(answer), rhs_text)
            return join_explanation_lines('Ищем x', f'Вычитаем {number_text}: x = {rhs_text} - {number_text} = {format_fraction(answer)}', check, f'Ответ: {format_fraction(answer)}', 'Совет: число после плюса переносим вычитанием')
        if kind == 'x_minus':
            answer = rhs_value + number
            return join_explanation_lines('Ищем x', f'Прибавляем {number_text}: x = {rhs_text} + {number_text} = {format_fraction(answer)}', format_equation_check(f'x - {number_text}', format_fraction(answer), rhs_text), f'Ответ: {format_fraction(answer)}', 'Совет: число после минуса переносим сложением')
        if kind == 'minus_x':
            answer = number - rhs_value
            return join_explanation_lines('Ищем x', f'Вычитаем {rhs_text} из {number_text}: x = {number_text} - {rhs_text} = {format_fraction(answer)}', format_equation_check(f'{number_text} - x', format_fraction(answer), rhs_text), f'Ответ: {format_fraction(answer)}', 'Совет: если x после минуса, вычитай из первого числа')
        if kind in {'x_mul', 'mul_x'}:
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines('0 при умножении всегда даёт 0', 'Ответ: подходит любое число', 'Совет: умножение на ноль всегда даёт ноль')
                return join_explanation_lines('0 при умножении не может дать другой результат', 'Ответ: решения нет', 'Совет: проверь уравнение')
            answer = rhs_value / number
            check = format_equation_check('x × ' + number_text if kind == 'x_mul' else number_text + ' × x', format_fraction(answer), rhs_text)
            return join_explanation_lines('Ищем x', f'Делим {rhs_text} на {number_text}: x = {rhs_text} : {number_text} = {format_fraction(answer)}', check, f'Ответ: {format_fraction(answer)}', 'Совет: множитель переносим делением')
        if kind == 'x_div':
            if number == 0:
                return join_explanation_lines('На ноль делить нельзя', 'Ответ: решения нет', 'Совет: проверь делитель')
            answer = rhs_value * number
            return join_explanation_lines('Ищем x', f'Умножаем {rhs_text} на {number_text}: x = {rhs_text} × {number_text} = {format_fraction(answer)}', format_equation_check(f'x : {number_text}', format_fraction(answer), rhs_text), f'Ответ: {format_fraction(answer)}', 'Совет: деление меняем на умножение')
        if kind == 'div_x':
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines('0, делённое на ненулевое число, всегда равно 0', 'Ответ: любое число, кроме 0', 'Совет: в делителе ноль быть не может')
                return join_explanation_lines('0, делённое на ненулевое число, не может дать другой результат', 'Ответ: решения нет', 'Совет: проверь делимое и результат')
            if rhs_value == 0:
                return join_explanation_lines('Ненулевое число при делении не может дать 0', 'Ответ: решения нет', 'Совет: проверь уравнение')
            answer = number / rhs_value
            return join_explanation_lines('Ищем x', f'Делим {number_text} на {rhs_text}: x = {number_text} : {rhs_text} = {format_fraction(answer)}', format_equation_check(f'{number_text} : x', format_fraction(answer), rhs_text), f'Ответ: {format_fraction(answer)}', 'Совет: если x в делителе, дели делимое на результат')
    return None

def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines('Ищем, сколько всего или сколько стало', f'Считаем: {first} + {second} = {result}', f'Ответ: {result}', 'Совет: если спрашивают про всё вместе, складывай')

def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ''
    return join_explanation_lines('Ищем, сколько осталось', f'Считаем: {first} - {second} = {result}', f'Ответ: {result}', 'Совет: если что-то убрали, используй вычитание')

def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines('Ищем разницу между числами', f'Считаем: {bigger} - {smaller} = {result}', f'Ответ: {result}', "Совет: вопрос 'на сколько' решаем вычитанием")

def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines('Ищем, сколько было сначала', f'Считаем: {remaining} + {removed} = {result}', f'Ответ: {result}', 'Совет: если часть убрали, начальное число находим сложением')

def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ''
    return join_explanation_lines('Ищем, сколько было сначала', f'Считаем: {final_total} - {added} = {result}', f'Ответ: {result}', 'Совет: если что-то добавили, начальное число находим вычитанием')

def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines('Ищем, сколько добавили', f'Считаем: {bigger} - {smaller} = {result}', f'Ответ: {result}', 'Совет: сравни число было и число стало')

def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines('Ищем, сколько убрали', f'Считаем: {bigger} - {smaller} = {result}', f'Ответ: {result}', 'Совет: вычти, сколько осталось, из того, что было')

def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines('Ищем, сколько всего', f'Считаем: {groups} × {per_group} = {result}', f'Ответ: {result}', "Совет: слова 'по ... в каждой' подсказывают умножение")

def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines('На ноль делить нельзя', 'Ответ: деление на ноль невозможно', 'Совет: проверь, на сколько частей делят')
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines('Ищем, сколько получит каждый', f'Считаем: {total} : {groups} = {quotient}', f'Ответ: {quotient}', "Совет: слова 'поровну' и 'каждый' подсказывают деление")
    return join_explanation_lines('Ищем, сколько получит каждый', f'Считаем: {total} : {groups} = {quotient}, остаток {remainder}', f'Ответ: каждому по {quotient}, остаток {remainder}', 'Совет: остаток меньше делителя')

def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool=False, explicit_remainder: bool=False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines('В группе не может быть 0 предметов', 'Ответ: запись задачи неверная', 'Совет: проверь размер группы')
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines('Ищем, сколько групп получится', f'Считаем: {total} : {per_group} = {quotient}', f'Ответ: {quotient}', 'Совет: число групп находим делением')
    if needs_extra_group:
        return join_explanation_lines(f'Считаем: {total} : {per_group} = {quotient}, остаток {remainder}', 'Осталось ещё несколько предметов, нужна ещё одна группа', f'Ответ: {quotient + 1}', 'Совет: если что-то осталось, иногда нужна ещё одна коробка')
    if explicit_remainder:
        full_group_phrase = plural_form(quotient, 'полная группа', 'полные группы', 'полных групп')
        return join_explanation_lines('Ищем, сколько полных групп получится', f'Считаем: {total} : {per_group} = {quotient}, остаток {remainder}', f'Ответ: {quotient} {full_group_phrase}, остаток {remainder}', 'Совет: остаток меньше размера группы')
    return None

def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = '+' if mode == 'больше' else '-'
    return join_explanation_lines('Ищем второе количество', f'Считаем: {base} {sign} {delta} = {result}', f'Ответ: {result}', 'Совет: сначала найди второе число')

def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = '+' if mode == 'больше' else '-'
    total = base + related
    return join_explanation_lines(f'Сначала находим второе количество: {base} {sign} {delta} = {related}', f'Потом считаем вместе: {base} + {related} = {total}', f'Ответ: {total}', 'Совет: сначала найди второе число')

def explain_sequential_change_word_problem(start: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = apply_more_less(start, first_delta, 'больше' if first_mode == 'gain' else 'меньше')
    if middle is None:
        return None
    result = apply_more_less(middle, second_delta, 'больше' if second_mode == 'gain' else 'меньше')
    if result is None:
        return None
    first_sign = '+' if first_mode == 'gain' else '-'
    second_sign = '+' if second_mode == 'gain' else '-'
    first_action = 'прибавляем' if first_mode == 'gain' else 'вычитаем'
    second_action = 'прибавляем' if second_mode == 'gain' else 'вычитаем'
    return join_explanation_lines(f'Сначала {first_action} {first_delta}: {start} {first_sign} {first_delta} = {middle}', f'Потом {second_action} {second_delta}: {middle} {second_sign} {second_delta} = {result}', f'Ответ: {result}', 'Совет: считай по порядку')

def explain_relation_chain_word_problem(base: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = apply_more_less(base, first_delta, first_mode)
    if middle is None:
        return None
    result = apply_more_less(middle, second_delta, second_mode)
    if result is None:
        return None
    first_sign = '+' if first_mode == 'больше' else '-'
    second_sign = '+' if second_mode == 'больше' else '-'
    return join_explanation_lines(f'Сначала находим второе число: {base} {first_sign} {first_delta} = {middle}', f'Потом третье: {middle} {second_sign} {second_delta} = {result}', f'Ответ: {result}', 'Совет: решай по шагам')

def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(f'Сначала считаем группы: {groups} × {per_group} = {grouped_total}', f'Потом прибавляем ещё {extra}: {grouped_total} + {extra} = {result}', f'Ответ: {result}', 'Совет: сначала посчитай одинаковые группы')

def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    unit = geometry_unit(lower)
    question_parts = [part.strip() for part in re.split('[?.!]', lower) if part.strip()]
    question = question_parts[-1] if question_parts else lower
    asks_perimeter = 'периметр' in lower
    asks_area = 'площад' in lower
    asks_side = any((fragment in question for fragment in ('найди сторону', 'найди длину стороны', 'одной стороны', 'какова сторона')))
    asks_width = any((fragment in question for fragment in ('найди ширину', 'какова ширина')))
    asks_length = any((fragment in question for fragment in ('найди длину', 'какова длина'))) and (not asks_width)
    if 'квадрат' in lower and asks_perimeter and asks_side and nums:
        perimeter = nums[0]
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        return join_explanation_lines('Ищем сторону квадрата', f'Делим периметр на 4: {perimeter} : 4 = {side}', f'Ответ: {with_unit(side, unit)}', 'Совет: у квадрата 4 равные стороны')
    if 'прямоугольник' in lower and asks_perimeter and asks_width and (len(nums) >= 2):
        perimeter, length = (nums[0], nums[1])
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        width = half - length
        if width < 0:
            return None
        return join_explanation_lines('Ищем ширину прямоугольника', f'Сначала делим периметр пополам: {perimeter} : 2 = {half}', f'Потом вычитаем длину: {half} - {length} = {width}', f'Ответ: {with_unit(width, unit)}', 'Совет: половина периметра — это длина плюс ширина')
    if 'прямоугольник' in lower and asks_perimeter and asks_length and (len(nums) >= 2):
        perimeter, width = (nums[0], nums[1])
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        length = half - width
        if length < 0:
            return None
        return join_explanation_lines('Ищем длину прямоугольника', f'Сначала делим периметр пополам: {perimeter} : 2 = {half}', f'Потом вычитаем ширину: {half} - {width} = {length}', f'Ответ: {with_unit(length, unit)}', 'Совет: половина периметра — это длина плюс ширина')
    if 'квадрат' in lower and asks_area and asks_side and nums:
        area = nums[0]
        side = int(math.isqrt(area))
        if side * side != area:
            return None
        return join_explanation_lines('Ищем сторону квадрата', f'Нужно число, которое в квадрате даёт {area}', f'Это {side}, потому что {side} × {side} = {area}', f'Ответ: {with_unit(side, unit)}', 'Совет: сторона квадрата в квадрате даёт площадь')
    if 'прямоугольник' in lower and asks_area and asks_width and (len(nums) >= 2):
        area, length = (nums[0], nums[1])
        if length == 0 or area % length != 0:
            return None
        width = area // length
        return join_explanation_lines('Ищем ширину прямоугольника', f'Делим площадь на длину: {area} : {length} = {width}', f'Ответ: {with_unit(width, unit)}', 'Совет: ширина = площадь : длина')
    if 'прямоугольник' in lower and asks_area and asks_length and (len(nums) >= 2):
        area, width = (nums[0], nums[1])
        if width == 0 or area % width != 0:
            return None
        length = area // width
        return join_explanation_lines('Ищем длину прямоугольника', f'Делим площадь на ширину: {area} : {width} = {length}', f'Ответ: {with_unit(length, unit)}', 'Совет: длина = площадь : ширина')
    if 'квадрат' in lower and asks_perimeter and nums:
        side = nums[0]
        result = side * 4
        return join_explanation_lines('Ищем периметр квадрата', f'Считаем: {side} × 4 = {result}', f'Ответ: {with_unit(result, unit)}', 'Совет: у квадрата 4 равные стороны')
    if 'прямоугольник' in lower and asks_perimeter and (len(nums) >= 2):
        length, width = (nums[0], nums[1])
        result = 2 * (length + width)
        return join_explanation_lines('Ищем периметр прямоугольника', f'Сначала: {length} + {width} = {length + width}', f'Потом: {length + width} × 2 = {result}', f'Ответ: {with_unit(result, unit)}', 'Совет: сначала сложи длину и ширину')
    if 'квадрат' in lower and asks_area and nums:
        side = nums[0]
        result = side * side
        return join_explanation_lines('Ищем площадь квадрата', f'Считаем: {side} × {side} = {result}', f'Ответ: {with_unit(result, unit, square=True)}', 'Совет: площадь квадрата — это сторона на сторону')
    if 'прямоугольник' in lower and asks_area and (len(nums) >= 2):
        length, width = (nums[0], nums[1])
        result = length * width
        return join_explanation_lines('Ищем площадь прямоугольника', f'Считаем: {length} × {width} = {result}', f'Ответ: {with_unit(result, unit, square=True)}', 'Совет: площадь = длина × ширина')
    return None

def capitalize_if_needed(text: str) -> str:
    line = str(text or '').strip()
    if not line:
        return ''
    first = line[0]
    if first.isalpha() and first.islower():
        return first.upper() + line[1:]
    return line
TEACHING_DEFAULT_ADVICE_V9 = {'expression': 'двигайся по шагам и называй каждое действие', 'equation': 'сначала оставь x один, потом сделай проверку', 'fraction': 'сначала смотри на знаменатели, потом считай', 'geometry': 'сначала назови правило, потом подставь числа', 'word': 'сначала пойми, что известно и что нужно найти', 'other': 'решай по шагам'}
BODY_LINE_LIMITS_V9 = {'expression': 6, 'fraction': 5, 'equation': 5, 'geometry': 5, 'word': 5, 'other': 4}
LOW_VALUE_BODY_PATTERNS_V9 = [re.compile('^это (?:составная )?задача(?:[^.!?]*)$', re.IGNORECASE), re.compile('^решаем по действиям$', re.IGNORECASE), re.compile('^известны два количества$', re.IGNORECASE), re.compile('^сначала смотрим, сколько было$', re.IGNORECASE), re.compile('^нужно оставить x отдельно$', re.IGNORECASE)]
DIRECT_RESULT_INTRO_RE_V9 = re.compile('^(?:делим|складываем|вычитаем|умножаем|считаем)\\s*:?\\s*[^=]+=\\s*([^=]+)$', re.IGNORECASE)
SECTION_PREFIX_RE_V9 = re.compile('^(ответ|совет|проверка)\\s*:\\s*', re.IGNORECASE)

def default_advice(kind: str) -> str:
    return TEACHING_DEFAULT_ADVICE_V9.get(kind, TEACHING_DEFAULT_ADVICE_V9['other'])

def _normalize_body_line_v9(line: str) -> str:
    text = re.sub('\\s+', ' ', str(line or '').strip())
    if not text:
        return ''
    replacements = [('^Нужно оставить x отдельно[.!?]?$', 'Ищем x'), ('^Нужно узнать, сколько всего вместе[.!?]?$', 'Ищем, сколько всего вместе'), ('^Нужно узнать, сколько осталось[.!?]?$', 'Ищем, сколько осталось'), ('^Нужно узнать, сколько получилось вместе[.!?]?$', 'Ищем, сколько получилось вместе'), ('^Потом узнаем, сколько убрали:\\s*(.+)$', 'Потом смотрим, сколько убрали: \\1'), ('^Потом узнаём, сколько убрали:\\s*(.+)$', 'Потом смотрим, сколько убрали: \\1'), ('^Потом узнаем, сколько добавили:\\s*(.+)$', 'Потом смотрим, сколько добавили: \\1'), ('^Потом узнаём, сколько добавили:\\s*(.+)$', 'Потом смотрим, сколько добавили: \\1'), ('^При\\s+переносе\\s+через\\s+знак\\s+равно\\s+умножение\\s+меняется\\s+на\\s+деление[.!?]?$', 'Умножение меняем на деление'), ('^При\\s+переносе\\s+через\\s+знак\\s+равно\\s+деление\\s+меняется\\s+на\\s+умножение[.!?]?$', 'Деление меняем на умножение'), ('^При\\s+переносе\\s+через\\s+знак\\s+равно\\s+плюс\\s+меняется\\s+на\\s+минус[.!?]?$', 'Плюс меняем на минус'), ('^При\\s+переносе\\s+через\\s+знак\\s+равно\\s+минус\\s+меняется\\s+на\\s+плюс[.!?]?$', 'Минус меняем на плюс'), ('^Сначала:\\s*(.+)$', 'Сначала \\1'), ('^Потом:\\s*(.+)$', 'Потом \\1')]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    text = re.sub('\\b(?:обычно|часто)\\b', '', text, flags=re.IGNORECASE)
    text = re.sub('\\s{2,}', ' ', text).strip(' ,.;')
    return capitalize_if_needed(text)

def _normalize_advice_line_v9(text: str, kind: str) -> str:
    value = str(text or '').strip().rstrip('.!?')
    if not value:
        return default_advice(kind)
    replacements = [('^проверяй деление умножением$', 'в делении столбиком повторяй шаги: подбери, умножь, вычти'), ('^остаток меньше делителя$', 'остаток всегда должен быть меньше делителя'), ('^решай по шагам$', 'двигайся по шагам и не перескакивай'), ('^считай по порядку$', 'называй каждое действие по порядку'), ('^большие числа складывай по частям$', 'разбивай большие числа на десятки и единицы'), ('^сначала убирай десятки, потом единицы$', 'сначала работай с десятками, потом с единицами'), ('^вычитай по частям$', 'удобно вычитать по частям'), ('^умножение можно представить как одинаковые группы$', 'умножение можно представить как одинаковые группы'), ('^сначала приведи дроби к общему знаменателю$', 'сначала делай одинаковые знаменатели'), ('^при одинаковых знаменателях меняется только числитель$', 'при одинаковых знаменателях меняется только числитель'), ('^множитель переносим делением$', 'множитель переносим делением'), ('^деление меняем на умножение$', 'если x делят на число, справа умножаем'), ('^если x в делителе, дели делимое на результат$', 'если x стоит в делителе, дели делимое на результат'), ('^у квадрата 4 равные стороны$', 'у квадрата все стороны равны'), ('^половина периметра — это длина плюс ширина$', 'сначала находи половину периметра'), ('^ширина = площадь : длина$', 'ширину находим делением площади на длину'), ('^длина = площадь : ширина$', 'длину находим делением площади на ширину'), ('^площадь = длина × ширина$', 'для площади умножай длину на ширину'), ('^сначала пойми, что нужно найти$', 'сначала пойми, что спрашивают'), ('^сначала выбери правило$', 'сначала выбери нужное правило')]
    for pattern, repl in replacements:
        if re.fullmatch(pattern, value, flags=re.IGNORECASE):
            value = repl
            break
    value = re.sub('\\s{2,}', ' ', value).strip(' ,.;')
    return value or default_advice(kind)

def _is_low_value_body_line_v9(line: str) -> bool:
    text = str(line or '').strip()
    return any((pattern.fullmatch(text) for pattern in LOW_VALUE_BODY_PATTERNS_V9))

def _body_line_has_math_signal_v9(line: str) -> bool:
    return bool(re.search('\\d|x|х|[+\\-=:×÷/]', str(line or ''), flags=re.IGNORECASE))

def _extract_answer_value_v9(answer_line: str) -> str:
    if not answer_line:
        return ''
    return re.sub('^Ответ:\\s*', '', answer_line, flags=re.IGNORECASE).strip().rstrip('.!?').strip()

def _looks_like_direct_result_intro_v9(line: str, answer_value: str, kind: str) -> bool:
    if kind == 'equation':
        return False
    text = str(line or '').strip().rstrip('.!?').strip()
    if not text or '=' not in text:
        return False
    match = DIRECT_RESULT_INTRO_RE_V9.match(text)
    if not match:
        return False
    if answer_value:
        right_value = match.group(1).strip().rstrip('.!?').strip()
        if right_value != answer_value:
            return False
    return True

def _limit_body_lines_v9(lines, kind: str):
    limit = BODY_LINE_LIMITS_V9.get(kind, BODY_LINE_LIMITS_V9['other'])
    return lines[:limit]

def _teaching_intro_from_direct_result_v9(line: str) -> str:
    lower = str(line or '').lower()
    if lower.startswith('делим'):
        return 'Ищем частное'
    if lower.startswith('складываем'):
        return 'Ищем сумму'
    if lower.startswith('вычитаем'):
        return 'Ищем разность'
    if lower.startswith('умножаем'):
        return 'Ищем произведение'
    if lower.startswith('считаем'):
        return 'Решаем по шагам'
    return ''

def shape_explanation(text: str, kind: str, forced_answer: Optional[str]=None, forced_advice: Optional[str]=None) -> str:
    cleaned = sanitize_model_text(text)
    if not cleaned:
        advice = _normalize_advice_line_v9(forced_advice or '', kind)
        if forced_answer:
            return join_explanation_lines(f'Ответ: {forced_answer}', f'Совет: {advice}')
        return join_explanation_lines('Напишите задачу понятнее', 'Ответ: нужно уточнить запись', f'Совет: {advice}')
    body_lines = []
    answer_line = None
    advice_line = None
    check_line = None
    for raw_line in cleaned.split('\n'):
        line = str(raw_line or '').strip()
        if not line:
            continue
        normalized = SECTION_PREFIX_RE_V9.sub(lambda m: f'{m.group(1).capitalize()}: ', line)
        lower = normalized.lower()
        if lower.startswith('ответ:'):
            value = normalized.split(':', 1)[1].strip()
            if value:
                answer_line = f'Ответ: {value}'
            continue
        if lower.startswith('совет:'):
            value = normalized.split(':', 1)[1].strip()
            if value:
                advice_line = value
            continue
        if lower.startswith('проверка:'):
            value = normalized.split(':', 1)[1].strip()
            if value:
                check_line = f'Проверка: {value}'
            continue
        body_lines.append(normalized)
    normalized_body = []
    seen = set()
    for line in body_lines:
        normalized = _normalize_body_line_v9(line)
        if not normalized:
            continue
        key = normalized.lower().rstrip('.!?')
        if key in seen:
            continue
        seen.add(key)
        normalized_body.append(normalized)
    body_lines = normalized_body
    if any((_body_line_has_math_signal_v9(line) for line in body_lines)):
        body_lines = [line for line in body_lines if not _is_low_value_body_line_v9(line)]
    if kind != 'equation':
        check_line = None
    if forced_answer is not None:
        answer_line = f'Ответ: {forced_answer}'
    answer_value = _extract_answer_value_v9(answer_line or '')
    if body_lines:
        first_line = body_lines[0]
        if _looks_like_direct_result_intro_v9(first_line, answer_value, kind):
            if len(body_lines) > 1:
                body_lines = body_lines[1:]
            else:
                intro = _teaching_intro_from_direct_result_v9(first_line)
                if intro:
                    body_lines = [intro]
    if answer_line is None and body_lines:
        tail = body_lines[-1]
        match = re.search('=\\s*([^=]+)$', tail)
        if match:
            answer_line = f'Ответ: {match.group(1).strip()}'
    if answer_line is None:
        answer_line = 'Ответ: проверь запись задачи'
    body_lines = _limit_body_lines_v9(body_lines, kind)
    advice_value = _normalize_advice_line_v9(forced_advice or advice_line or '', kind)
    final_lines = list(body_lines)
    if check_line:
        final_lines.append(check_line)
    final_lines.append(answer_line)
    final_lines.append(f'Совет: {advice_value}')
    return join_explanation_lines(*final_lines)

def _build_long_division_steps_v9(dividend: int, divisor: int):
    digits = list(str(dividend))
    steps = []
    current = ''
    quotient = ''
    started = False
    for index, digit in enumerate(digits):
        current += digit
        current_number = int(current)
        if current_number < divisor:
            if started:
                quotient += '0'
            continue
        started = True
        q_digit = current_number // divisor
        product = q_digit * divisor
        remainder = current_number - product
        steps.append({'current': current_number, 'q_digit': q_digit, 'product': product, 'remainder': remainder, 'next_digit': int(digits[index + 1]) if index + 1 < len(digits) else None})
        quotient += str(q_digit)
        current = str(remainder)
    if not started:
        quotient = '0'
    remainder = int(current or '0')
    return {'steps': steps, 'quotient': quotient, 'remainder': remainder}

def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if left >= 10 or right >= 10:
        left_tens, left_units = (left - left % 10, left % 10)
        right_tens, right_units = (right - right % 10, right % 10)
        return join_explanation_lines('Ищем сумму', f'Складываем десятки: {left_tens} + {right_tens} = {left_tens + right_tens}', f'Складываем единицы: {left_units} + {right_units} = {left_units + right_units}', f'Теперь складываем результаты: {left_tens + right_tens} + {left_units + right_units} = {total}', f'Ответ: {total}', 'Совет: разбивай большие числа на десятки и единицы')
    return join_explanation_lines('Ищем сумму', f'Считаем: {left} + {right} = {total}', f'Ответ: {total}', 'Совет: называй числа по порядку')

def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines('Сначала сравниваем числа', f'{left} меньше {right}, поэтому ответ будет отрицательным', f'Считаем: {left} - {right} = {result}', f'Ответ: {result}', 'Совет: перед вычитанием полезно сравнить числа')
    if right >= 10:
        tens = right - right % 10
        units = right % 10
        middle = left - tens
        return join_explanation_lines('Ищем разность', f'Сначала вычитаем десятки: {left} - {tens} = {middle}', f'Потом вычитаем единицы: {middle} - {units} = {result}', f'Ответ: {result}', 'Совет: удобно сначала работать с десятками, потом с единицами')
    return join_explanation_lines('Ищем разность', f'Считаем: {left} - {right} = {result}', f'Ответ: {result}', 'Совет: вычитай спокойно и не пропускай знак минус')

def explain_simple_multiplication(left: int, right: int) -> str:
    result = left * right
    big = max(left, right)
    small = min(left, right)
    if big >= 10 and small <= 10:
        tens = big - big % 10
        units = big % 10
        return join_explanation_lines('Ищем произведение', f'Разбиваем {big} на {tens} и {units}', f'{tens} × {small} = {tens * small}', f'{units} × {small} = {units * small}', f'Теперь складываем части: {tens * small} + {units * small} = {result}', f'Ответ: {result}', 'Совет: умножение удобно разбирать на части')
    return join_explanation_lines('Ищем произведение', f'Считаем: {left} × {right} = {result}', f'Ответ: {result}', 'Совет: умножение показывает одинаковые группы')

def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines('На ноль делить нельзя', 'Ответ: деление на ноль невозможно', 'Совет: сначала смотри на делитель')
    quotient, remainder = divmod(left, right)
    if left < 100 and right < 10:
        if remainder == 0:
            return join_explanation_lines('Ищем, сколько раз делитель помещается в делимом', f'{quotient} × {right} = {left}, значит {left} : {right} = {quotient}', f'Ответ: {quotient}', 'Совет: в делении ищи число, которое при умножении даёт делимое')
        return join_explanation_lines('Ищем, сколько полных раз делитель помещается в делимом', f'{quotient} × {right} = {quotient * right}', f'После вычитания остаётся {left - quotient * right}', f'Ответ: {quotient}, остаток {remainder}', 'Совет: остаток всегда должен быть меньше делителя')
    model = _build_long_division_steps_v9(left, right)
    steps = model['steps']
    lines = ['Ищем частное']
    if not steps:
        lines.append(f'{left} меньше {right}, значит в частном будет 0')
        if remainder:
            lines.append(f'Остаток равен {remainder}')
        answer_text = '0' if remainder == 0 else f'0, остаток {remainder}'
        return join_explanation_lines(*lines, f'Ответ: {answer_text}', 'Совет: если делимое меньше делителя, частное начинается с нуля')
    first_step = steps[0]
    lines.append(f"Сначала берём первое неполное делимое {first_step['current']}")
    for index, step in enumerate(steps):
        current = step['current']
        q_digit = step['q_digit']
        product = step['product']
        remainder_value = step['remainder']
        next_current = steps[index + 1]['current'] if index + 1 < len(steps) else None
        next_try = (q_digit + 1) * right
        if next_try > current:
            choice_part = f'Подбираем {q_digit}, потому что {q_digit} × {right} = {product}, а {q_digit + 1} × {right} = {next_try}, это уже больше'
        else:
            choice_part = f'Подбираем {q_digit}, потому что {q_digit} × {right} = {product}'
        if next_current is not None:
            lines.append(f'{choice_part}. После вычитания остаётся {remainder_value}, сносим следующую цифру и получаем {next_current}')
        elif remainder_value == 0:
            lines.append(f'{choice_part}. После вычитания остаётся 0, деление закончено')
        else:
            lines.append(f'{choice_part}. После вычитания остаётся {remainder_value}, это и есть остаток')
    answer_text = str(quotient) if remainder == 0 else f'{quotient}, остаток {remainder}'
    advice = 'в делении столбиком повторяй шаги: взял, подобрал, умножил, вычел'
    return join_explanation_lines(*lines, f'Ответ: {answer_text}', f'Совет: {advice}')

def try_local_fraction_explanation(raw_text: str) -> Optional[str]:
    source = to_fraction_source(raw_text)
    if not source:
        return None
    match = re.fullmatch('\\s*(\\d+)\\s*/\\s*(\\d+)\\s*([+\\-])\\s*(\\d+)\\s*/\\s*(\\d+)\\s*', source)
    if not match:
        return None
    a, b, operator, c, d = match.groups()
    a = int(a)
    b = int(b)
    c = int(c)
    d = int(d)
    if b == 0 or d == 0:
        return join_explanation_lines('У дроби знаменатель не может быть равен нулю', 'Ответ: запись дроби неверная', 'Совет: сначала проверь знаменатели')
    action_symbol = '+' if operator == '+' else '-'
    result = Fraction(a, b) + Fraction(c, d) if operator == '+' else Fraction(a, b) - Fraction(c, d)
    if b == d:
        top_result = a + c if operator == '+' else a - c
        lines = ['Смотрим на знаменатели. Они одинаковые', f'Значит, работаем только с числителями: {a} {action_symbol} {c} = {top_result}', f'Получаем дробь {top_result}/{b}']
        if format_fraction(result) != f'{top_result}/{b}':
            lines.append(f'Сокращаем: {top_result}/{b} = {format_fraction(result)}')
        lines.extend([f'Ответ: {format_fraction(result)}', 'Совет: при одинаковых знаменателях меняется только числитель'])
        return join_explanation_lines(*lines)
    common = math.lcm(b, d)
    a_scaled = a * (common // b)
    c_scaled = c * (common // d)
    top_result = a_scaled + c_scaled if operator == '+' else a_scaled - c_scaled
    simplified = Fraction(top_result, common)
    lines = [f'Сначала делаем одинаковые знаменатели: {common}', f'{a}/{b} = {a_scaled}/{common}, а {c}/{d} = {c_scaled}/{common}', f'Теперь считаем: {a_scaled}/{common} {action_symbol} {c_scaled}/{common} = {top_result}/{common}']
    if format_fraction(simplified) != f'{top_result}/{common}':
        lines.append(f'Сокращаем: {top_result}/{common} = {format_fraction(simplified)}')
    lines.extend([f'Ответ: {format_fraction(result)}', 'Совет: сначала делай одинаковые знаменатели'])
    return join_explanation_lines(*lines)


def try_local_methodical_geometry_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    unit = geometry_unit(lower) or 'см'

    if 'треугольник' in lower and 'периметр' in lower and len(nums) >= 3:
        a, b, c = nums[:3]
        total = a + b + c
        return join_explanation_lines(
            'Периметр треугольника — это сумма всех сторон',
            f'Считаем: {a} + {b} + {c} = {total}',
            f'Ответ: {with_unit(total, unit)}',
            'Совет: чтобы найти периметр, сложи все стороны',
        )

    match = re.search(r'периметр\s+прямоугольник\w*[^\d]*(\d+).*?длин\w*[^\d]*(\d+).*?площад', lower)
    if match:
        perimeter = int(match.group(1))
        length = int(match.group(2))
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        width = half - length
        if width < 0:
            return None
        area = length * width
        return join_explanation_lines(
            'Сначала найдём сумму длины и ширины',
            f'{perimeter} : 2 = {half}',
            f'Потом найдём ширину: {half} - {length} = {width}',
            f'Теперь найдём площадь: {length} × {width} = {area}',
            f'Ответ: {with_unit(area, unit or "см", square=True)}',
            'Совет: если известен периметр, сначала дели его на 2',
        )

    match = re.search(r'площадь\s+прямоугольник\w*[^\d]*(\d+).*?длин\w*[^\d]*(\d+).*?периметр', lower)
    if match:
        area = int(match.group(1))
        length = int(match.group(2))
        if length == 0 or area % length != 0:
            return None
        width = area // length
        perimeter = 2 * (length + width)
        return join_explanation_lines(
            'Сначала найдём ширину по площади',
            f'{area} : {length} = {width}',
            f'Потом найдём периметр: ({length} + {width}) × 2 = {perimeter}',
            f'Ответ: {with_unit(perimeter, unit or "см")}',
            'Совет: если известна площадь, ширину находи делением',
        )

    match = re.search(r'сторон[аы]\s+равносторонн\w*\s+треугольник\w*[^\d]*(\d+).*?сторон[аы]\s+квадрат', lower)
    if match and 'периметр' in lower:
        triangle_side = int(match.group(1))
        triangle_perimeter = triangle_side * 3
        if triangle_perimeter % 4 != 0:
            return None
        square_side = triangle_perimeter // 4
        return join_explanation_lines(
            'Сначала найдём периметр равностороннего треугольника',
            f'{triangle_side} × 3 = {triangle_perimeter}',
            f'Потом найдём сторону квадрата: {triangle_perimeter} : 4 = {square_side}',
            f'Ответ: {with_unit(square_side, unit)}',
            'Совет: у квадрата все 4 стороны равны',
        )

    return None


def try_local_methodical_story_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    numbers = extract_ordered_numbers(lower)
    if not text or not re.search('[а-я]', lower):
        return None

    def first_measure_unit(source: str) -> str:
        match = re.search(r'\d+\s*(км/ч|м/мин|м/с|км|л|кг|руб|см²|см2|см|м²|м2|м|мин|ч)\b', source)
        if not match:
            return ''
        return match.group(1).replace('2', '²')

    def time_symbol(value: str) -> str:
        raw = str(value or '').lower()
        if raw.startswith('ч'):
            return 'ч'
        if raw.startswith('мин'):
            return 'мин'
        return 'с'

    def speed_unit(distance_unit: str, time_unit: str) -> str:
        if not distance_unit:
            return ''
        return f'{distance_unit}/{time_symbol(time_unit)}'

    asks_total = bool(re.search(r'сколько[^.?!]*\b(всего|вместе)\b', lower))
    asks_current = bool(re.search(r'сколько[^.?!]*\b(стало|теперь|осталось)\b', lower))
    asks_plain_quantity = 'сколько' in lower and (not asks_total) and (not asks_current) and ('на сколько' not in lower) and ('во сколько' not in lower)
    asks_named_value = bool(re.search(r'сколько|какое|какова|каков|чему\s+рав', lower))

    match = re.search(r'стоит\s*(\d+)\s*руб\w*.*?сколько\s+сто\w*\s*(\d+)', lower)
    if match and ('таких' in lower or 'такие' in lower):
        price, qty = map(int, match.groups())
        total_cost = price * qty
        return join_explanation_lines(
            'Ищем стоимость покупки',
            'Чтобы найти стоимость, нужно цену умножить на количество',
            f'{price} × {qty} = {total_cost}',
            f'Ответ: {with_unit(total_cost, "руб")}',
            'Совет: стоимость = цена × количество',
        )

    match = re.search(r'(\d+)\s+[а-яё-]+\s+сто\w*\s*(\d+)\s*руб', lower)
    if match and re.search(r'сколько\s+сто\w*\s+(?:1|одна|один)\b', lower):
        qty, total_cost = map(int, match.groups())
        if qty == 0 or total_cost % qty != 0:
            return None
        price = total_cost // qty
        return join_explanation_lines(
            'Ищем цену одного предмета',
            'Чтобы найти цену, нужно стоимость разделить на количество',
            f'{total_cost} : {qty} = {price}',
            f'Ответ: {with_unit(price, "руб")}',
            'Совет: цена = стоимость : количество',
        )

    match = re.search(r'стоит\s*(\d+)\s*руб\w*.*?у\s+[а-яё]+\s*(\d+)\s*руб\w*.*?у\s+[а-яё]+\s*(\d+)\s*руб', lower)
    if match and asks_plain_quantity:
        price, money1, money2 = map(int, match.groups())
        total_money = money1 + money2
        if price == 0 or total_money % price != 0:
            return None
        qty = total_money // price
        return join_explanation_lines(
            'Можем ли мы сразу ответить? Нет',
            f'Сначала узнаем, сколько денег всего: {money1} + {money2} = {total_money}',
            f'Потом узнаем, сколько предметов можно купить: {total_money} : {price} = {qty}',
            f'Ответ: {qty}',
            'Совет: если покупают вместе, сначала сложи деньги',
        )

    if len(numbers) == 2 and asks_plain_quantity and ('по' not in lower):
        total, known = numbers[:2]
        addend_markers = ('на двух', 'за два дня', 'всего', 'вместе', 'из них', 'остальные', 'нашли', 'прочитал', 'прочитала', 'заплатил', 'заплатила', 'на всем', 'на всём')
        part_markers = ('перв', 'втор', 'осталь', 'из них', 'синего', 'свекл', 'капуст', 'наш', 'прочитал', 'прочитала', 'заплатил', 'заплатила')
        if total >= known and any(marker in lower for marker in addend_markers) and any(marker in lower for marker in part_markers):
            answer = total - known
            return join_explanation_lines(
                'В задаче неизвестно одно слагаемое',
                'Чтобы найти неизвестное слагаемое, нужно из суммы вычесть известное слагаемое',
                f'{total} - {known} = {answer}',
                f'Ответ: {answer}',
                'Совет: если известно, сколько всего, и одна часть, вторую часть находим вычитанием',
            )

    if len(numbers) == 2 and 'осталось' in lower and re.search(r'сколько[^.?!]*\bбыло\b', lower):
        removed, remaining = numbers[:2]
        answer = removed + remaining
        return join_explanation_lines(
            'В задаче неизвестно уменьшаемое',
            'Чтобы найти неизвестное уменьшаемое, нужно к разности прибавить вычитаемое',
            f'{remaining} + {removed} = {answer}',
            f'Ответ: {answer}',
            'Совет: если известно, сколько осталось и сколько убрали, начальное число находим сложением',
        )

    if len(numbers) == 2 and 'осталось' in lower and re.search(r'сколько[^.?!]*\b(отдали|взяли|съели|забрали|продали|заболело|вышло)\b', lower):
        before, remaining = numbers[:2]
        if before >= remaining:
            answer = before - remaining
            return join_explanation_lines(
                'В задаче неизвестно вычитаемое',
                'Чтобы найти неизвестное вычитаемое, нужно из уменьшаемого вычесть разность',
                f'{before} - {remaining} = {answer}',
                f'Ответ: {answer}',
                'Совет: если известно, сколько было и сколько осталось, убранную часть находим вычитанием',
            )

    if len(numbers) == 2 and 'по' in lower and any(fragment in lower for fragment in ('сколько потреб', 'сколько сет', 'сколько короб', 'сколько корзин', 'сколько пакет', 'сколько нужно')):
        total, per_group = numbers[:2]
        if per_group == 0 or total % per_group != 0:
            return None
        groups = total // per_group
        return join_explanation_lines(
            'В задаче неизвестно, сколько групп получилось',
            'Это неизвестный множитель',
            'Чтобы найти неизвестный множитель, нужно произведение разделить на известный множитель',
            f'{total} : {per_group} = {groups}',
            f'Ответ: {groups}',
            'Совет: если известно, сколько всего и сколько в одной группе, число групп находим делением',
        )

    match = re.search(r'за\s*(\d+)\s+пакет\w*\s+сок\w*\s+заплатил\w*\s*(\d+)\s*руб.*?за\s+столько\s+же\s+пакет\w*\s+молок\w*\s+.*?(\d+)\s*руб.*?на\s+сколько', lower)
    if match:
        qty, juice_total, milk_total = map(int, match.groups())
        if qty == 0 or juice_total % qty != 0 or milk_total % qty != 0:
            return None
        juice_price = juice_total // qty
        milk_price = milk_total // qty
        diff = abs(juice_price - milk_price)
        return join_explanation_lines(
            'Сначала найдём цену одного пакета сока',
            f'{juice_total} : {qty} = {juice_price}',
            'Потом найдём цену одного пакета молока',
            f'{milk_total} : {qty} = {milk_price}',
            f'Теперь сравним цены: {max(juice_price, milk_price)} - {min(juice_price, milk_price)} = {diff}',
            f'Ответ: {with_unit(diff, "руб")}',
            'Совет: если количество одинаковое, сначала находи цену одного предмета',
        )

    match = re.search(r'за\s*(\d+)\s+короб\w*\s+карандаш\w*\s+заплатил\w*\s*(\d+)\s*руб.*?на\s*(\d+)\s*руб', lower)
    if match and 'таких короб' in lower:
        qty, total_cost, target_cost = map(int, match.groups())
        if qty == 0 or total_cost % qty != 0:
            return None
        unit_price = total_cost // qty
        if unit_price == 0 or target_cost % unit_price != 0:
            return None
        answer = target_cost // unit_price
        return join_explanation_lines(
            'Сначала узнаем цену одной коробки',
            f'{total_cost} : {qty} = {unit_price}',
            f'Потом узнаем, сколько коробок можно купить на {target_cost} руб: {target_cost} : {unit_price} = {answer}',
            f'Ответ: {answer}',
            'Совет: слова «таких же» подсказывают, что цена одинаковая',
        )

    match = re.search(r'в\s*(\d+)\s+коробк\w*\s*(\d+)\s*кг.*?разложить\s*(\d+)\s*кг', lower)
    if match:
        boxes, total_weight, target_weight = map(int, match.groups())
        if boxes == 0 or total_weight % boxes != 0:
            return None
        one_box = total_weight // boxes
        if one_box == 0 or target_weight % one_box != 0:
            return None
        answer = target_weight // one_box
        return join_explanation_lines(
            'Сначала найдём, сколько в одной коробке',
            f'{total_weight} : {boxes} = {one_box}',
            f'Потом найдём, сколько коробок нужно: {target_weight} : {one_box} = {answer}',
            f'Ответ: {answer}',
            'Совет: в задачах на приведение к единице сначала находи одну коробку',
        )

    match = re.search(r'за\s*(\d+)\s+дн\w*\s+бригад\w*\s+проложил\w*\s*(\d+)\s*м.*?(\d+)\s+бригад\w*\s+за\s*(\d+)\s+дн', lower)
    if match:
        days, total_work, brigades, target_days = map(int, match.groups())
        if days == 0 or total_work % days != 0:
            return None
        one_per_day = total_work // days
        answer = one_per_day * brigades * target_days
        return join_explanation_lines(
            'Сначала узнаем, сколько делает 1 бригада за 1 день',
            f'{total_work} : {days} = {one_per_day}',
            f'Потом узнаем, сколько сделают {brigades} бригады за {target_days} дней: {one_per_day} × {brigades} × {target_days} = {answer}',
            f'Ответ: {with_unit(answer, "м")}',
            'Совет: в сложной задаче на приведение к единице сначала ищи работу одной бригады за один день',
        )

    match = re.search(r'перв\w*\s+насос\w*.*?(\d+)\s+вед\w*\s+вод\w*\s+за\s*(\d+)\s*мин.*?втор\w*.*?за\s*(\d+)\s*мин.*?(\d+)\s+вед', lower)
    if match:
        same_volume, t1, t2, target_volume = map(int, match.groups())
        if t1 == 0 or t2 == 0:
            return None
        r1 = Fraction(same_volume, t1)
        r2 = Fraction(same_volume, t2)
        common_rate = r1 + r2
        time_needed = Fraction(target_volume, common_rate)
        return join_explanation_lines(
            'Сначала найдём, сколько за 1 минуту делает первый насос',
            f'{same_volume} : {t1} = {format_fraction(r1)}',
            'Потом найдём, сколько за 1 минуту делает второй насос',
            f'{same_volume} : {t2} = {format_fraction(r2)}',
            f'Вместе они делают {format_fraction(common_rate)} ведер за 1 минуту, значит {target_volume} : {format_fraction(common_rate)} = {format_fraction(time_needed)}',
            f'Ответ: {format_fraction(time_needed)} мин',
            'Совет: в совместной работе сначала находи производительность каждого',
        )

    match = re.search(r'купили\s*(\d+)\s+набор\w*.*?и\s*(\d+)\s+набор\w*.*?заплатили\s*(\d+)\s*руб', lower)
    if match and 'цена' in lower and 'одинаков' in lower:
        blue_sets, red_sets, total_cost = map(int, match.groups())
        total_sets = blue_sets + red_sets
        if total_sets == 0 or total_cost % total_sets != 0:
            return None
        one_price = total_cost // total_sets
        blue_cost = one_price * blue_sets
        red_cost = one_price * red_sets
        return join_explanation_lines(
            'Сначала найдём общее количество наборов',
            f'{blue_sets} + {red_sets} = {total_sets}',
            f'Потом найдём цену одного набора: {total_cost} : {total_sets} = {one_price}',
            f'Голубые наборы: {one_price} × {blue_sets} = {blue_cost}',
            f'Красные наборы: {one_price} × {red_sets} = {red_cost}',
            f'Ответ: {with_unit(blue_cost, "руб")} и {with_unit(red_cost, "руб")}',
            'Совет: в пропорциональном делении сначала находи цену одной равной части',
        )

    match = re.search(r'скорост\w*\s*(\d+)\s*(км/ч|м/мин|м/с).*?за\s*(\d+)\s*(ч|час\w*|мин\w*|сек\w*)', lower)
    if match and any(fragment in lower for fragment in ('какое расстояние', 'какой путь', 'сколько километров', 'сколько метров')):
        speed, speed_unit_text, time_value, time_unit_text = match.groups()
        speed = int(speed)
        time_value = int(time_value)
        distance = speed * time_value
        distance_unit = speed_unit_text.split('/')[0]
        return join_explanation_lines(
            'Чтобы найти расстояние, нужно скорость умножить на время',
            f'{speed} × {time_value} = {distance}',
            f'Ответ: {with_unit(distance, distance_unit)}',
            'Совет: в движении пользуйся правилом S = v × t',
        )

    match = re.search(r'за\s*(\d+)\s*(ч|час\w*|мин\w*|сек\w*).*?(?:проехал|прош[её]л|проплыл|пролетел|пробежал)\w*\s*(\d+)\s*(км|м)', lower)
    if match and any(fragment in lower for fragment in ('с какой скорост', 'какова скорость', 'чему равна скорость')):
        time_value, time_unit_text, distance, distance_unit = match.groups()
        time_value = int(time_value)
        distance = int(distance)
        if time_value == 0 or distance % time_value != 0:
            return None
        speed = distance // time_value
        return join_explanation_lines(
            'Чтобы найти скорость, нужно расстояние разделить на время',
            f'{distance} : {time_value} = {speed}',
            f'Ответ: {with_unit(speed, speed_unit(distance_unit, time_unit_text))}',
            'Совет: в движении пользуйся правилом v = S : t',
        )

    match = re.search(r'скорост\w*\s*(\d+)\s*(км/ч|м/мин|м/с).*?(?:прош[её]л|проехал|проплыл|пролетел)\w*\s*(\d+)\s*(км|м)', lower)
    if not match:
        match = re.search(r'(?:прош[её]л|проехал|проплыл|пролетел)\w*\s*(\d+)\s*(км|м).*?скорост\w*\s*(\d+)\s*(км/ч|м/мин|м/с)', lower)
        if match and ('сколько часов' in lower or 'какое время' in lower or 'сколько минут' in lower or 'сколько времени' in lower):
            distance, distance_unit, speed, speed_unit_text = match.groups()
            distance = int(distance)
            speed = int(speed)
            if speed == 0 or distance % speed != 0:
                return None
            time_value = distance // speed
            return join_explanation_lines(
                'Чтобы найти время, нужно расстояние разделить на скорость',
                f'{distance} : {speed} = {time_value}',
                f'Ответ: {with_unit(time_value, time_symbol(speed_unit_text.split("/")[1]))}',
                'Совет: в движении пользуйся правилом t = S : v',
            )
    if match and ('сколько часов' in lower or 'какое время' in lower or 'сколько минут' in lower or 'сколько времени' in lower):
        speed, speed_unit_text, distance, distance_unit = match.groups()
        speed = int(speed)
        distance = int(distance)
        if speed == 0 or distance % speed != 0:
            return None
        time_value = distance // speed
        return join_explanation_lines(
            'Чтобы найти время, нужно расстояние разделить на скорость',
            f'{distance} : {speed} = {time_value}',
            f'Ответ: {with_unit(time_value, time_symbol(speed_unit_text.split("/")[1]))}',
            'Совет: в движении пользуйся правилом t = S : v',
        )

    match = re.search(r'навстречу.*?скорост\w*\s*(\d+)\s*км/ч.*?(\d+)\s*км/ч.*?через\s*(\d+)\s*ч', lower)
    if match:
        v1, v2, time_hours = map(int, match.groups())
        closing_speed = v1 + v2
        distance = closing_speed * time_hours
        return join_explanation_lines(
            'Сначала найдём скорость сближения',
            f'{v1} + {v2} = {closing_speed}',
            f'Потом найдём расстояние: {closing_speed} × {time_hours} = {distance}',
            f'Ответ: {with_unit(distance, "км")}',
            'Совет: при встречном движении скорости складывают',
        )

    match = re.search(r'в противоположных направлениях.*?скорост\w*\s*(\d+)\s*км/ч.*?(\d+)\s*км/ч.*?через\s*(\d+)\s*ч', lower)
    if match:
        v1, v2, time_hours = map(int, match.groups())
        removal_speed = v1 + v2
        distance = removal_speed * time_hours
        return join_explanation_lines(
            'Сначала найдём скорость удаления',
            f'{v1} + {v2} = {removal_speed}',
            f'Потом найдём расстояние между ними: {removal_speed} × {time_hours} = {distance}',
            f'Ответ: {with_unit(distance, "км")}',
            'Совет: при движении в противоположных направлениях скорости тоже складывают',
        )

    match = re.search(r'за\s*(\d+)\s*ч.*?проехал\s*(\d+)\s*км.*?следующ\w*\s*(\d+)\s*ч.*?на\s*(\d+)\s*км/ч\s+меньше', lower)
    if match:
        time1, distance1, time2, delta = map(int, match.groups())
        if time1 == 0 or distance1 % time1 != 0:
            return None
        speed1 = distance1 // time1
        speed2 = speed1 - delta
        if speed2 < 0:
            return None
        distance2 = speed2 * time2
        total = distance1 + distance2
        return join_explanation_lines(
            'Можем ли мы сразу ответить? Нет',
            f'Сначала узнаем первую скорость: {distance1} : {time1} = {speed1}',
            f'Потом узнаем вторую скорость: {speed1} - {delta} = {speed2}',
            f'Найдём второе расстояние: {speed2} × {time2} = {distance2}',
            f'Теперь найдём весь путь: {distance1} + {distance2} = {total}',
            f'Ответ: {with_unit(total, "км")}',
            'Совет: в составной задаче на движение сначала находи неизвестную скорость',
        )

    match = re.search(r'расстояние\s+между\s+ними\s*(\d+)\s*км.*?на\s*(\d+)\s*км/ч', lower)
    if match and 'догон' in lower:
        distance, diff_speed = map(int, match.groups())
        if diff_speed == 0:
            return None
        time_value = Fraction(distance, diff_speed)
        return join_explanation_lines(
            'При догонке используем скорость сближения',
            f'Она равна разности скоростей: {diff_speed} км/ч',
            f'{distance} : {diff_speed} = {format_fraction(time_value)}',
            f'Ответ: {format_fraction(time_value)} ч',
            'Совет: время догонки = расстояние : скорость сближения',
        )

    if 'половин' in lower and len(numbers) == 1 and asks_named_value:
        part_value = numbers[0]
        whole = part_value * 2
        unit = first_measure_unit(lower)
        return join_explanation_lines(
            'Половина — это одна вторая часть целого',
            f'Чтобы найти целое, {part_value} × 2 = {whole}',
            f'Ответ: {with_unit(whole, unit)}',
            'Совет: если известна половина, всё число получаем умножением на 2',
        )

    match = re.search(r'(\d+)\s*(км|м|л|кг|руб|см)?\s*\.?\s*это\s*(\d+)\s*/\s*(\d+)\s+всего', lower)
    if match and asks_named_value:
        part_value, unit, numerator, denominator = match.groups()
        part_value = int(part_value)
        numerator = int(numerator)
        denominator = int(denominator)
        if numerator == 0 or part_value % numerator != 0:
            return None
        one_share = part_value // numerator
        whole = one_share * denominator
        return join_explanation_lines(
            'Чтобы найти число по его части, нужно разделить эту часть на числитель и умножить на знаменатель',
            f'{part_value} : {numerator} × {denominator} = {whole}',
            f'Ответ: {with_unit(whole, unit or "")}',
            'Совет: сначала узнай одну долю, потом всё число',
        )

    match = re.search(r'(\d+)\s*(руб|км|л|м|кг|см)?\s*\.?\s*(\d+)\s*/\s*(\d+).*?(?:потрат|израсход)', lower)
    if match:
        total_value, unit, numerator, denominator = match.groups()
        total_value = int(total_value)
        numerator = int(numerator)
        denominator = int(denominator)
        spent = Fraction(total_value * numerator, denominator)
        remain = Fraction(total_value, 1) - spent
        spent_text = format_fraction(spent)
        remain_text = format_fraction(remain)
        answer_text = f'{remain_text}{(" " + unit) if unit else ""}'
        return join_explanation_lines(
            'Сначала найдём потраченную часть',
            f'{total_value} : {denominator} × {numerator} = {spent_text}',
            f'Потом найдём остаток: {total_value} - {spent_text} = {remain_text}',
            f'Ответ: {answer_text}',
            'Совет: чтобы найти часть от числа, дели на знаменатель и умножай на числитель',
        )

    fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', lower)
    if fraction_match and len(numbers) >= 3 and asks_plain_quantity:
        numerator = int(fraction_match.group(1))
        denominator = int(fraction_match.group(2))
        total_value = numbers[0]
        if denominator == 0:
            return None
        part_value = Fraction(total_value * numerator, denominator)
        part_text = format_fraction(part_value)
        unit = first_measure_unit(lower)
        answer_text = f'{part_text}{(" " + unit) if unit else ""}'
        return join_explanation_lines(
            'Чтобы найти часть от числа, нужно разделить число на знаменатель и умножить на числитель',
            f'{total_value} : {denominator} × {numerator} = {part_text}',
            f'Ответ: {answer_text}',
            'Совет: знаменатель показывает, на сколько равных частей делим целое',
        )

    match = re.search(r'собрали\s*(\d+)\s*кг.*?и\s*(\d+)\s*кг.*?на\s*(\d+)\s+мешк', lower)
    if match:
        first_mass, second_mass, bag_diff = map(int, match.groups())
        bigger_mass = max(first_mass, second_mass)
        smaller_mass = min(first_mass, second_mass)
        mass_diff = bigger_mass - smaller_mass
        if bag_diff == 0 or mass_diff % bag_diff != 0:
            return None
        one_bag = mass_diff // bag_diff
        if one_bag == 0 or first_mass % one_bag != 0 or second_mass % one_bag != 0:
            return None
        first_count = first_mass // one_bag
        second_count = second_mass // one_bag
        smaller_label = 'моркови' if first_mass <= second_mass else 'картофеля'
        bigger_label = 'картофеля' if first_mass <= second_mass else 'моркови'
        smaller_count = smaller_mass // one_bag
        bigger_count = bigger_mass // one_bag
        return join_explanation_lines(
            'Можем ли мы сразу ответить? Нет',
            f'Сначала узнаем, на сколько килограммов больше: {bigger_mass} - {smaller_mass} = {mass_diff}',
            f'Потом узнаем, сколько в одном мешке: {mass_diff} : {bag_diff} = {one_bag}',
            f'Теперь найдём количество мешков: {smaller_mass} : {one_bag} = {smaller_count} и {bigger_mass} : {one_bag} = {bigger_count}',
            f'Ответ: {smaller_label} — {smaller_count}, {bigger_label} — {bigger_count}',
            'Совет: в задачах на две разности сначала находят одну равную часть',
        )

    return None

async def build_explanation(user_text: str) -> dict:
    local_explanation = try_local_equation_explanation(user_text) or try_local_fraction_explanation(user_text) or try_local_expression_explanation(user_text) or try_local_methodical_geometry_explanation(user_text) or try_local_geometry_explanation(user_text) or try_local_methodical_story_explanation(user_text) or try_local_compound_word_problem_explanation(user_text) or try_local_word_problem_explanation(user_text)
    kind = infer_task_kind(user_text)
    if local_explanation:
        return {'result': shape_explanation(local_explanation, kind), 'source': 'local', 'validated': True}
    extra_instruction = ''
    if kind == 'word':
        extra_instruction = 'Это текстовая задача. Сначала скажи, что нужно найти и почему выбирается это действие. Потом выполни вычисление.\n\n'
    elif kind == 'geometry':
        extra_instruction = 'Это задача по геометрии. Сначала назови правило, потом подставь числа и выполни вычисление.\n\n'
    elif kind == 'expression':
        extra_instruction = 'Это обычный пример или выражение. Не пиши готовый ответ в первой строке. Если есть деление, объясняй ход последовательно и без строки Проверка.\n\n'
    elif kind == 'fraction':
        extra_instruction = 'Это задача с дробями. Сначала скажи, одинаковые ли знаменатели. Потом выполни вычисление.\n\n'
    payload = {'model': 'deepseek-chat', 'messages': [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f'Объясни решение так, чтобы ребёнок мог слушать текст и идти по нему глазами строка за строкой. Сначала объяснение, потом ответ, а не наоборот. Ответ дай строго в заданной структуре.\n\n{extra_instruction}{user_text}'}], 'max_tokens': 550, 'temperature': 0.05}
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get('error'):
        return llm_result
    shaped = shape_explanation(llm_result['result'], kind)
    return {'result': shaped, 'source': 'llm', 'validated': False}
