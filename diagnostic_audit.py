from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any
import re

from backend.service import APP_RELEASE, SOLVER_VERSION, generate_explanation_response

FORBIDDEN_RESULT_MARKERS = (
    'Применяем правило:',
    'Zad3',
    'deterministic regression',
    'answer map',
    'lookup',
)
FORBIDDEN_SOURCES = (
    'guard-low-confidence',
    'fallback',
    'legacy-ai',
)

DEFAULT_AUDIT_CASES: list[dict[str, Any]] = [
    # Basic word problems.
    {'category': 'basic_add_sub', 'name': 'add_apples', 'text': 'У Маши было 7 яблок, ей дали еще 5 яблок. Сколько яблок стало у Маши?', 'expected': ['12 яблок']},
    {'category': 'basic_add_sub', 'name': 'add_mushrooms', 'text': 'Маша нашла в лесу 2 белых гриба и 3 желтых гриба. Сколько Маша собрала грибов в лесу?', 'expected': ['5 гриб']},
    {'category': 'basic_add_sub', 'name': 'sub_pencils', 'text': 'У Пети было 20 карандашей. Он отдал 6 карандашей. Сколько карандашей осталось?', 'expected': ['14 карандаш']},
    {'category': 'basic_add_sub', 'name': 'sub_books', 'text': 'У Вани было 15 книг. Он подарил 4 книги. Сколько книг осталось у Вани?', 'expected': ['11 книг']},
    # Equal groups and division.
    {'category': 'equal_groups', 'name': 'boxes_candies_total', 'text': 'В 4 коробках по 6 конфет. Сколько конфет всего?', 'expected': ['24 конфет']},
    {'category': 'equal_groups', 'name': 'branches_cones_remaining', 'text': 'На 3 ветках по 9 шишек. Белка утащила 3 шишки. Сколько шишек осталось?', 'expected': ['24 шиш']},
    {'category': 'equal_groups', 'name': 'sets_pencils_remaining', 'text': 'Витя купил 2 набора по 8 карандашей в каждом. Он подарил 5 карандашей. Сколько карандашей осталось у Вити?', 'expected': ['11 карандаш']},
    {'category': 'division', 'name': 'sharing_candies', 'text': '24 конфеты разложили поровну в 6 коробок. Сколько конфет в каждой коробке?', 'expected': ['4 конфет']},
    {'category': 'division', 'name': 'containers_apples', 'text': 'В коробки кладут по 6 яблок. Сколько коробок понадобится для 25 яблок?', 'expected': ['5 короб']},
    {'category': 'division', 'name': 'containers_balls', 'text': 'В пакеты кладут по 8 шариков. Сколько пакетов понадобится для 33 шариков?', 'expected': ['5']},
    # Money.
    {'category': 'money', 'name': 'money_left', 'text': 'У Маши было 100 рублей. Она купила 3 тетради по 12 рублей. Сколько рублей осталось у Маши?', 'expected': ['64 руб']},
    {'category': 'money', 'name': 'money_cost', 'text': 'Петя купил 4 ручки по 9 рублей. Сколько рублей он заплатил?', 'expected': ['36 руб']},
    {'category': 'money', 'name': 'rub_kop', 'text': 'Сколько копеек в 3 рублях 50 копейках?', 'expected': ['350 коп']},
    # Motion.
    {'category': 'motion', 'name': 'distance_car', 'text': 'Автомобиль ехал 3 часа со скоростью 60 км/ч. Сколько километров он проехал?', 'expected': ['180 километр']},
    {'category': 'motion', 'name': 'speed_boat', 'text': 'Катер прошел 45 км за 3 часа. С какой скоростью шел катер?', 'expected': ['15 км/ч']},
    {'category': 'motion', 'name': 'remaining_bike', 'text': 'Велосипедист ехал 2 ч со скоростью 10 км/ч. После этого ему осталось проехать в 2 раза больше того, что он проехал. Сколько всего километров он должен проехать?', 'expected': ['60 километр']},
    # Joint work.
    {'category': 'joint_work', 'name': 'tractor_ares', 'text': 'Один трактор может вспахать поле площадью 240 аров за 3 часа, а другой трактор — за 6 часов. За сколько часов вспашут поле оба трактора, работая вместе?', 'expected': ['2 часа', '120 аров в час'], 'expectedSource': 'local:live-joint-work'},
    {'category': 'joint_work', 'name': 'tractor_acres', 'text': 'Один трактор может вспахать поле площадью 240 акров за 3 часа, а другой трактор — за 6 часов. За сколько часов вспашут поле оба трактора, работая вместе?', 'expected': ['2 часа', '120 акров в час'], 'expectedSource': 'local:live-joint-work'},
    {'category': 'joint_work', 'name': 'combine_days', 'text': 'Один комбайн убрал с поля 168 т пшеницы за 6 дней, а другой — столько же за 12 дней. За сколько дней уберут поле оба комбайна, работая вместе?', 'expected': ['4 дня'], 'expectedSource': 'local:live-joint-work'},
    {'category': 'joint_work', 'name': 'pipes_hours', 'text': 'Одна труба наполняет бассейн за 4 часа, а другая труба — за 6 часов. За сколько часов наполнят бассейн обе трубы вместе?', 'expected': ['2 часа 24 минуты'], 'expectedSource': 'local:live-joint-work'},
    # Equations and systems.
    {'category': 'equations', 'name': 'simple_equation', 'text': 'x + 5 = 12', 'expected': ['x = 7']},
    {'category': 'systems', 'name': 'system_comma', 'text': 'x + y = 10, y - x = 2', 'expected': ['x = 4, y = 6'], 'expectedSource': 'local:live-system-solver'},
    {'category': 'systems', 'name': 'system_newline', 'text': 'x + y = 10\ny - x = 2', 'expected': ['x = 4, y = 6'], 'expectedSource': 'local:live-system-solver'},
    {'category': 'systems', 'name': 'system_collapsed', 'text': 'x + y = 10 y - x = 2', 'expected': ['x = 4, y = 6'], 'expectedSource': 'local:live-system-solver'},
    # Fractions, units, geometry.
    {'category': 'fractions', 'name': 'third_part', 'text': 'Найди третью часть от 27.', 'expected': ['9']},
    {'category': 'fractions', 'name': 'fifth_part', 'text': 'Найди пятую часть от 45.', 'expected': ['9']},
    {'category': 'units', 'name': 'meters_cm', 'text': 'Сколько сантиметров в 3 м 20 см?', 'expected': ['320 сантиметр']},
    {'category': 'units', 'name': 'kg_g', 'text': 'Сколько граммов в 4 кг 250 г?', 'expected': ['4250']},
    {'category': 'geometry', 'name': 'perimeter_rect', 'text': 'У прямоугольника длина 8 см, ширина 5 см. Найди периметр.', 'expected': ['26 см']},
    {'category': 'geometry', 'name': 'area_rect', 'text': 'У прямоугольника длина 8 см, ширина 5 см. Найди площадь.', 'expected': ['40 см²']},
    # Expressions and compare.
    {'category': 'expressions', 'name': 'compare_equal', 'text': 'Сравни 2+2 и 5-1.', 'expected': ['равны']},
    {'category': 'expressions', 'name': 'compare_greater', 'text': 'Сравни 18-5 и 3+7.', 'expected': ['больше']},
    # Multi-task guard.
    {'category': 'input_guard', 'name': 'two_examples_newline', 'text': '2+2\n32-8', 'expected': ['Разделите задания'], 'expectedSource': 'guard-multi-task'},
]


def _case_expected_fragments(case: dict[str, Any]) -> list[str]:
    value = case.get('expected') or case.get('expectedFragments') or []
    if isinstance(value, str):
        return [value]
    return [str(x) for x in value]


def _normalize_case(case: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        'id': str(case.get('id') or case.get('name') or f'case_{index + 1}'),
        'grade': case.get('grade'),
        'category': str(case.get('category') or 'custom'),
        'name': str(case.get('name') or f'case_{index + 1}'),
        'text': str(case.get('text') or ''),
        'expected': _case_expected_fragments(case),
        'expectedSource': case.get('expectedSource'),
        'expectedNumericAnswer': case.get('expectedNumericAnswer'),
        'expectedUnit': case.get('expectedUnit'),
        'expectedFinalAnswer': case.get('expectedFinalAnswer'),
        'expectedSourceFamily': case.get('expectedSourceFamily'),
        'forbidden': list(case.get('forbidden') or []),
        'shouldWarn': bool(case.get('shouldWarn') or False),
        'ttsAudit': bool(case.get('ttsAudit') or False),
        'ttsSource': case.get('ttsSource'),
        'expectedTtsContains': list(case.get('expectedTtsContains') or []),
        'expectedTtsNotContains': list(case.get('expectedTtsNotContains') or case.get('expectedTtsForbidden') or []),
        'expectedTtsExact': case.get('expectedTtsExact'),
    }



def _loose_expected_phrase_present(expected: str, result: str) -> bool:
    exp = str(expected or '').lower().replace('ё', 'е').strip()
    res = str(result or '').lower().replace('ё', 'е')
    if not exp:
        return True
    if exp in res:
        return True
    # Accept punctuation/connector variants for tens-units answers:
    # "1 десяток и 2 единицы" vs "1 десяток, 2 единицы".
    def compact_units(value: str) -> str:
        value = value.replace(',', ' и ')
        value = re.sub(r'\s+', ' ', value)
        value = value.replace(' единицa', ' единица')
        return value.strip()
    return compact_units(exp) in compact_units(res)

def _check_payload(case: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    result = str(payload.get('result') or '')
    source = str(payload.get('source') or '')
    issues: list[str] = []
    if not result.strip():
        issues.append('empty result')
    if 'Ответ:' not in result:
        issues.append('missing Ответ: line')
    expected_source = case.get('expectedSource')
    if expected_source and source != expected_source:
        issues.append(f'expected source {expected_source!r}, got {source!r}')
    for fragment in case.get('expected') or []:
        if fragment and _audit_compare_text(fragment) not in result_for_compare:
            issues.append(f'missing expected fragment {fragment!r}')
    low_source = source.lower()
    if any(low_source.startswith(marker) for marker in FORBIDDEN_SOURCES):
        issues.append(f'forbidden source {source!r}')
    markers_to_check = tuple(dict.fromkeys(FORBIDDEN_RESULT_MARKERS + tuple(case.get('forbidden') or ())))
    for marker in markers_to_check:
        if marker and marker.lower() in result.lower():
            issues.append(f'forbidden marker {marker!r}')
    if '\n1)\n' in result or '\n2)\n' in result or '\n3)\n' in result or '\n4)\n' in result:
        issues.append('split action number formatting')
    return {
        'ok': not issues,
        'issues': issues,
        'source': source,
        'resultPreview': result[:260],
        **numeric_details,
    }


async def run_math_audit(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    raw_cases = cases if cases is not None else DEFAULT_AUDIT_CASES
    normalized = [_normalize_case(case, i) for i, case in enumerate(raw_cases)]
    results: list[dict[str, Any]] = []
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {'passed': 0, 'failed': 0, 'total': 0})
    for case in normalized:
        payload = await generate_explanation_response(case['text'], solver_mode='local_primary')
        checked = _check_payload(case, payload)
        row = {
            'id': case.get('id'),
            'grade': case.get('grade'),
            'category': case['category'],
            'name': case['name'],
            'ok': checked['ok'],
            'issues': checked['issues'],
            'source': checked['source'],
            'expectedSource': case.get('expectedSource'),
            'expectedSourceFamily': case.get('expectedSourceFamily'),
            'expectedNumericAnswer': case.get('expectedNumericAnswer'),
            'expectedUnit': case.get('expectedUnit'),
            'expectedFinalAnswer': case.get('expectedFinalAnswer'),
            'expected': case.get('expected'),
            'resultPreview': checked['resultPreview'],
        }
        results.append(row)
        bucket = by_category[case['category']]
        bucket['total'] += 1
        if row['ok']:
            bucket['passed'] += 1
        else:
            bucket['failed'] += 1
    passed = sum(1 for item in results if item['ok'])
    failed = len(results) - passed
    return {
        'release': APP_RELEASE,
        'backendBuild': APP_RELEASE,
        'frontendExpectedBackend': APP_RELEASE,
        'solverVersion': SOLVER_VERSION,
        'status': 'ok',
        'diagnostic': 'math-audit',
        'auditMode': 'LOCAL_VERIFIER_REGRESSION_NO_EXTERNAL_API',
        'passed': passed,
        'failed': failed,
        'total': len(results),
        'allPassed': failed == 0,
        'externalApiCalls': 0,
        'externalApiUsed': False,
        'byCategory': dict(sorted(by_category.items())),
        'failures': [item for item in results if not item['ok']],
        'results': results,
    }

# --- v279 external black-box audit expansion ---
# These cases are synthetic, but their categories were selected from external
# online task lists and lesson pages.  They are intentionally checked through
# generate_explanation_response(), not by calling internal handlers directly.

def _v279_external_audit_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    def add(category: str, name: str, text: str, expected: str | list[str], source: str | None = None):
        row: dict[str, Any] = {'category': category, 'name': name, 'text': text, 'expected': expected if isinstance(expected, list) else [expected]}
        if source:
            row['expectedSource'] = source
        cases.append(row)

    # Basic addition/subtraction, grade 1-2 style.
    add('external_basic_addition', 'add_oli_stickers', 'У Оли было 8 наклеек, мама дала ей ещё 7 наклеек. Сколько наклеек стало у Оли?', '15 наклеек')
    add('external_basic_addition', 'add_plate_plums', 'На тарелке лежало 9 слив. Положили ещё 6 слив. Сколько слив стало на тарелке?', '15 слив')
    add('external_basic_addition', 'add_pencils', 'У Димы было 11 карандашей, папа дал ему ещё 4 карандаша. Сколько карандашей стало у Димы?', '15 карандашей')
    add('external_basic_subtraction', 'sub_kolya_stamps', 'У Коли было 18 марок. Он подарил другу 5 марок. Сколько марок осталось у Коли?', '13 марок')
    add('external_basic_subtraction', 'sub_bus', 'В автобусе было 27 пассажиров. На остановке вышли 9 пассажиров. Сколько пассажиров осталось?', '18 пассажиров')
    add('external_basic_subtraction', 'sub_pencils', 'У Вани было 20 карандашей. Он отдал 6 карандашей. Сколько карандашей осталось у Вани?', '14 карандашей')

    # Equal groups and sharing.
    add('external_equal_groups', 'groups_packets_apples', 'В 6 пакетах по 4 яблока. Сколько яблок всего?', '24 яблока')
    add('external_equal_groups', 'groups_shelves_books', 'На 5 полках по 7 книг. Сколько книг на всех полках?', '35 книг')
    add('external_equal_groups', 'groups_boxes_pencils_remaining', 'В 4 коробках по 8 карандашей. 6 карандашей взяли. Сколько карандашей осталось?', '26 карандашей')
    add('external_equal_sharing', 'share_candies', '24 конфеты раздали поровну 6 детям. Сколько конфет получил каждый ребенок?', '4 конфеты')
    add('external_equal_sharing', 'share_apples', '36 яблок раздали поровну 9 детям. Сколько яблок получил каждый ребенок?', '4 яблока')

    # Cost / quantity / price and money.
    add('external_price_quantity_cost', 'cost_pens', 'Купили 6 ручек по 9 рублей. Сколько рублей заплатили за ручки?', '54 рубля')
    add('external_price_quantity_cost', 'quantity_notebooks', 'Сколько тетрадей можно купить на 72 рубля, если одна тетрадь стоит 8 рублей?', '9 тетрадей')
    add('external_price_quantity_cost', 'one_notebook_price', 'За 5 одинаковых блокнотов заплатили 60 рублей. Сколько рублей стоит один блокнот?', '12 рублей')
    add('external_price_quantity_cost', 'money_left_pencils', 'У Маши было 100 рублей. Она купила 3 карандаша по 12 рублей. Сколько рублей осталось у Маши?', '64 рубля')
    add('external_price_quantity_cost', 'money_conversion', 'Сколько копеек в 3 рублях 50 копейках?', '350 копеек')

    # Motion.
    add('external_motion', 'distance_pedestrian', 'Пешеход шел 4 часа со скоростью 5 км/ч. Какое расстояние он прошел?', '20 километров')
    add('external_motion', 'speed_bus', 'Автобус проехал 180 км за 3 часа. Найди скорость автобуса.', '60 км/ч')
    add('external_motion', 'time_train', 'Поезд ехал со скоростью 70 км/ч и прошел 210 км. Сколько часов ехал поезд?', '3 часа')
    add('external_motion', 'towards_cars', 'Из двух городов одновременно навстречу друг другу выехали два автомобиля. Скорость первого 60 км/ч, второго 50 км/ч. Через 2 часа они встретились. Какое расстояние между городами?', '220 километров')
    add('external_motion', 'remaining_tourist', 'Турист прошел 12 км. Ему осталось пройти в 2 раза меньше, чем он уже прошел. Сколько километров весь путь?', '18 километров')

    # Joint work.
    add('external_joint_work', 'brigades_days', 'Одна бригада может выполнить заказ за 8 дней, другая бригада — за 12 дней. За сколько дней выполнят заказ две бригады вместе?', '4,8 дня')
    add('external_joint_work', 'pipes_hours', 'Первая труба наполняет бассейн за 6 часов, вторая труба — за 3 часа. За сколько часов наполнят бассейн две трубы вместе?', '2 часа')
    add('external_joint_work', 'masters_details', 'Один мастер делает 120 деталей за 6 часов, другой мастер делает столько же за 4 часа. За сколько часов они сделают 120 деталей вместе?', '2 часа 24 минуты')
    add('external_joint_work', 'tractors_ars', 'Один трактор может вспахать поле площадью 240 аров за 3 часа, а другой трактор — за 6 часов. За сколько часов вспашут поле оба трактора, работая вместе?', '2 часа')

    # Units.
    add('external_units', 'm_cm_to_cm', 'Сколько сантиметров в 5 м 40 см?', '540 сантиметров')
    add('external_units', 'cm_to_m_cm', 'Сколько метров и сантиметров в 375 см?', '3 метра 75 сантиметров')
    add('external_units', 'kg_g_to_g', 'Сколько граммов в 2 кг 300 г?', '2300 граммов')
    add('external_units', 'hours_minutes_to_minutes', 'Сколько минут в 3 часах 15 минутах?', '195 минут')

    # Geometry.
    add('external_geometry', 'rect_perimeter', 'Прямоугольник имеет длину 9 см и ширину 4 см. Найди периметр прямоугольника.', '26 см')
    add('external_geometry', 'rect_area', 'Прямоугольник имеет длину 9 см и ширину 4 см. Найди площадь прямоугольника.', '36 см²')
    add('external_geometry', 'square_side', 'Периметр квадрата равен 28 см. Чему равна сторона квадрата?', '7 см')

    # Fractions.
    add('external_fractions', 'fourth_part', 'Найди четвертую часть от 36.', '9')
    add('external_fractions', 'whole_from_third', 'Треть числа равна 12. Найди всё число.', '36')
    add('external_fractions', 'compare_fractions', 'Сравни дроби 1/3 и 1/4.', '1/3 больше')

    # Equations and systems.
    add('external_equations', 'eq_add', 'x + 15 = 42. Найди x.', '27')
    add('external_equations', 'eq_sub', '56 - x = 19. Найди x.', '37')
    add('external_equations', 'eq_dividend', 'x : 7 = 6. Найди x.', '42')
    add('external_equations', 'eq_divisor', '72 : x = 8. Найди x.', '9')
    add('external_systems', 'system_15_3', 'x + y = 15, x - y = 3', 'x = 9, y = 6', 'local:live-system-solver')
    add('external_systems', 'system_newline_10_2', 'x + y = 10\ny - x = 2', 'x = 4, y = 6', 'local:live-system-solver')

    # Expressions, comparisons, remainders and data reading.
    add('external_expressions', 'expr_parentheses', 'Вычисли значение выражения (18 + 12) : 5.', '6')
    add('external_expressions', 'expr_order', 'Найди значение выражения 7 * 8 - 15.', '41')
    add('external_expressions', 'compare_equal', 'Сравни 6 * 7 и 50 - 8.', 'равны')
    add('external_division_remainder', 'apples_packets', '37 яблок разложили по 5 яблок в пакет. Сколько полных пакетов получилось и сколько яблок осталось?', ['7', '2 яблока'])
    add('external_division_remainder', 'books_boxes', 'В коробку помещается 8 книг. Сколько коробок нужно для 34 книг?', '5 коробок')
    add('external_data_reading', 'table_difference', 'В таблице: яблоки — 12, груши — 9, сливы — 15. На сколько слив больше, чем груш?', '6')

    # A few relation problems to catch more/less wording.
    add('external_relations', 'more_by', 'У Пети 12 марок, у Маши на 5 марок больше. Сколько марок у Маши?', '17 марок')
    add('external_relations', 'less_by', 'У Пети 12 марок, у Маши на 5 марок меньше. Сколько марок у Маши?', '7 марок')
    add('external_relations', 'times_more', 'У Пети 6 марок, у Маши в 3 раза больше. Сколько марок у Маши?', '18 марок')

    return cases


EXTERNAL_AUDIT_SOURCE_NOTES = [
    'external category mining: joint work / productivity',
    'external category mining: primary-school online tests and grade 1-4 topic lists',
    'external category mining: price-quantity-cost',
    'external category mining: units, perimeter/area, motion, equations',
]

DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v279_external_audit_cases()

# --- v280 external black-box audit wave 1: Grade 1-2 basics + route/input guard ---
# The tasks below are original synthetic variants.  Their category map was
# derived from external primary-school topic lists, but no textbook/web task is
# copied verbatim.  Expected answers are precomputed here and checked through the
# same generate_explanation_response() path used by the HTTP API.

_V280_FORBIDDEN_RESULT_MARKERS = tuple(dict.fromkeys(FORBIDDEN_RESULT_MARKERS + ('generic fallback',)))


def _v280_wave1_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    def add(
        category: str,
        case_id: str,
        grade: int,
        text: str,
        expected: str | list[str],
        *,
        expected_numeric: int | str | None = None,
        expected_unit: str | None = None,
        expected_final: str | None = None,
        expected_source_family: str | None = 'local:live',
        expected_source: str | None = None,
        should_warn: bool = False,
    ) -> None:
        row: dict[str, Any] = {
            'id': case_id,
            'grade': grade,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': expected if isinstance(expected, list) else [expected],
            'expectedNumericAnswer': expected_numeric,
            'expectedUnit': expected_unit,
            'expectedFinalAnswer': expected_final or (expected[0] if isinstance(expected, list) else expected),
            'expectedSourceFamily': expected_source_family,
            'shouldWarn': should_warn,
        }
        if expected_source:
            row['expectedSource'] = expected_source
        cases.append(row)

    add('v280_numbers_place_value', 'v280_g1_place_value_write_47', 1,
        'Запиши число, в котором 4 десятка и 7 единиц.', '47', expected_numeric=47, expected_final='Ответ: 47.')
    add('v280_numbers_place_value', 'v280_g1_place_value_read_58', 1,
        'В числе 58 сколько десятков и сколько единиц?', ['5 десятков', '8 единиц'], expected_numeric=5, expected_unit='десятков', expected_final='5 десятков и 8 единиц')
    add('v280_numbers_compare', 'v280_g1_compare_36_63', 1,
        'Сравни числа 36 и 63.', '36 < 63', expected_final='36 < 63')
    add('v280_numbers_compare', 'v280_g1_larger_89_98', 1,
        'Какое число больше: 89 или 98?', '98', expected_numeric=98, expected_final='98')
    add('v280_numbers_parity', 'v280_g1_even_24', 1,
        'Число 24 четное или нечетное?', 'чётное', expected_final='Число 24 чётное')
    add('v280_numbers_parity', 'v280_g1_odd_35', 1,
        'Число 35 четное или нечетное?', 'нечётное', expected_final='Число 35 нечётное')
    add('v280_units_length', 'v280_g1_dm_cm_to_cm', 1,
        'Сколько сантиметров в 2 дм 5 см?', '25 сантиметров', expected_numeric=25, expected_unit='сантиметр', expected_final='25 сантиметров')
    add('v280_units_money', 'v280_g2_rub_kop_to_kop', 2,
        'Сколько копеек в 4 рублях 20 копейках?', '420 копеек', expected_numeric=420, expected_unit='копеек', expected_final='420 копеек')
    add('v280_units_time', 'v280_g2_hour_min_to_min', 2,
        'Сколько минут в 1 часе 25 минутах?', '85 минут', expected_numeric=85, expected_unit='минут', expected_final='85 минут')
    add('v280_calendar', 'v280_g1_weeks_to_days', 1,
        'Сколько дней в 3 неделях?', '21 день', expected_numeric=21, expected_unit='день', expected_final='21 день')

    add('v280_arithmetic_direct', 'v280_g2_add_34_25', 2,
        'Вычисли 34 + 25.', '59', expected_numeric=59, expected_final='59')
    add('v280_arithmetic_direct', 'v280_g2_sub_70_28', 2,
        'Вычисли 70 - 28.', '42', expected_numeric=42, expected_final='42')
    add('v280_arithmetic_direct', 'v280_g2_mul_6_7', 2,
        'Вычисли 6 * 7.', '42', expected_numeric=42, expected_final='42')
    add('v280_arithmetic_direct', 'v280_g2_div_56_8', 2,
        'Вычисли 56 : 8.', '7', expected_numeric=7, expected_final='7')
    add('v280_order_of_operations', 'v280_g2_order_18_plus_3_times_4', 2,
        'Найди значение выражения 18 + 3 * 4.', '30', expected_numeric=30, expected_final='30')
    add('v280_order_of_operations', 'v280_g2_parentheses_18_6_div_3', 2,
        'Вычисли (18 + 6) : 3.', '8', expected_numeric=8, expected_final='8')
    add('v280_division_remainder', 'v280_g2_remainder_29_5', 2,
        'Выполни деление с остатком: 29 : 5.', ['5', 'остаток 4'], expected_numeric=5, expected_unit='остаток 4', expected_final='5, остаток 4')
    add('v280_number_transform', 'v280_g1_number_more_27_by_8', 1,
        'Какое число на 8 больше 27?', '35', expected_numeric=35, expected_final='35')
    add('v280_number_transform', 'v280_g1_number_less_41_by_6', 1,
        'Какое число на 6 меньше 41?', '35', expected_numeric=35, expected_final='35')
    add('v280_number_transform', 'v280_g2_increase_7_3_times', 2,
        'Увеличь 7 в 3 раза.', '21', expected_numeric=21, expected_final='21')
    add('v280_number_transform', 'v280_g2_decrease_36_4_times', 2,
        'Уменьши 36 в 4 раза.', '9', expected_numeric=9, expected_final='9')

    add('v280_text_simple_total', 'v280_g1_lena_cards_became', 1,
        'У Лены было 12 открыток, ей подарили ещё 8 открыток. Сколько открыток стало у Лены?', '20 открыток', expected_numeric=20, expected_unit='открыток', expected_final='20 открыток')
    add('v280_text_simple_remaining', 'v280_g1_parking_cars_left', 1,
        'На стоянке было 15 машин. Уехали 4 машины. Сколько машин осталось?', '11 машин', expected_numeric=11, expected_unit='машин', expected_final='11 машин')
    add('v280_text_simple_total', 'v280_g1_vase_roses_became', 1,
        'В вазе было 10 роз. Поставили ещё 7 роз. Сколько роз стало в вазе?', '17 роз', expected_numeric=17, expected_unit='роз', expected_final='17 роз')
    add('v280_text_relation_less', 'v280_g1_sasha_ira_less', 1,
        'У Саши 18 фишек, у Иры на 6 фишек меньше. Сколько фишек у Иры?', '12 фишек', expected_numeric=12, expected_unit='фишек', expected_final='12 фишек')
    add('v280_text_relation_times', 'v280_g2_nina_tanya_times_more', 2,
        'У Нины 9 наклеек, у Тани в 2 раза больше. Сколько наклеек у Тани?', '18 наклеек', expected_numeric=18, expected_unit='наклеек', expected_final='18 наклеек')
    add('v280_text_equal_groups_total', 'v280_g2_baskets_balls_total', 2,
        'В 5 корзинах по 3 мяча. Сколько мячей всего?', '15 мячей', expected_numeric=15, expected_unit='мячей', expected_final='15 мячей')
    add('v280_text_equal_sharing', 'v280_g2_cookies_on_plates', 2,
        '18 печений разложили поровну на 3 тарелки. Сколько печений на каждой тарелке?', '6 печений', expected_numeric=6, expected_unit='печений', expected_final='6 печений')
    add('v280_money_budget_change', 'v280_g2_peter_money_two_purchases_left', 2,
        'У Пети было 20 рублей. Он купил сок за 8 рублей и булочку за 7 рублей. Сколько рублей осталось?', '5 рублей', expected_numeric=5, expected_unit='рублей', expected_final='5 рублей')
    add('v280_text_composite_two_action', 'v280_g2_class_children_left', 2,
        'В классе 12 девочек и 9 мальчиков. 3 ученика ушли на кружок. Сколько учеников осталось в классе?', '18 учеников', expected_numeric=18, expected_unit='учеников', expected_final='18 учеников')
    add('v280_text_reverse_relation', 'v280_g2_vera_olya_less_from_more', 2,
        'У Веры было 14 карандашей. Это на 5 больше, чем у Оли. Сколько карандашей у Оли?', '9 карандашей', expected_numeric=9, expected_unit='карандашей', expected_final='9 карандашей')
    add('v280_text_composite_relation_total', 'v280_g2_misha_kostya_together', 2,
        'У Миши 6 машинок, у Кости на 4 машинки больше. Сколько машинок у них вместе?', '16 машинок', expected_numeric=16, expected_unit='машинок', expected_final='16 машинок')
    add('v280_text_equal_groups_total', 'v280_g1_packets_apples_total', 1,
        'В одном пакете 5 яблок. Сколько яблок в 4 таких пакетах?', '20 яблок', expected_numeric=20, expected_unit='яблок', expected_final='20 яблок')
    add('v280_text_equal_groups_division', 'v280_g2_pencils_boxes_exact', 2,
        '24 карандаша разложили в коробки по 6 карандашей. Сколько коробок получилось?', '4 коробки', expected_numeric=4, expected_unit='коробки', expected_final='4 коробки')
    add('v280_money_cost', 'v280_g2_notebooks_cost', 2,
        'Одна тетрадь стоит 7 рублей. Сколько стоят 5 таких тетрадей?', '35 рублей', expected_numeric=35, expected_unit='рублей', expected_final='35 рублей')
    add('v280_money_change', 'v280_g2_ruler_change', 2,
        'У Димы 50 рублей. Он купил линейку за 18 рублей. Сколько рублей сдачи получил Дима?', '32 рубля', expected_numeric=32, expected_unit='рубля', expected_final='32 рубля')
    add('v280_money_quantity', 'v280_g2_pencils_quantity_by_budget', 2,
        'Сколько карандашей можно купить на 45 рублей, если карандаш стоит 9 рублей?', '5 карандашей', expected_numeric=5, expected_unit='карандашей', expected_final='5 карандашей')

    add('v280_time_duration', 'v280_g1_lesson_duration', 1,
        'Урок начался в 9:00 и закончился в 9:45. Сколько минут длился урок?', '45 минут', expected_numeric=45, expected_unit='минут', expected_final='45 минут')
    add('v280_time_end', 'v280_g2_cartoon_end_time', 2,
        'Мультфильм начался в 16:20 и длился 30 минут. Во сколько он закончился?', '16:50', expected_numeric='16:50', expected_final='16:50')
    add('v280_time_duration', 'v280_g2_training_duration', 2,
        'Тренировка началась в 15:10 и закончилась в 15:55. Сколько минут длилась тренировка?', '45 минут', expected_numeric=45, expected_unit='минут', expected_final='45 минут')

    add('v280_route_wrappers', 'v280_g1_solve_task_answer_number', 1,
        'Реши задачу: У Оли было 9 шаров, ей подарили 4 шара. Сколько шаров стало? Ответ запиши числом.', '13 шаров', expected_numeric=13, expected_unit='шаров', expected_final='13 шаров')
    add('v280_input_guard_multi_task', 'v280_route_multi_task_newline_warning', 1,
        '2 + 2\n3 + 4', 'Разделите задания', expected_source_family='guard-multi-task', expected_source='guard-multi-task', should_warn=True, expected_final='Разделите задания')
    add('v280_input_guard_multi_task', 'v280_route_multi_task_collapsed_warning', 1,
        '12-5  6+7', 'Разделите задания', expected_source_family='guard-multi-task', expected_source='guard-multi-task', should_warn=True, expected_final='Разделите задания')
    add('v280_route_equation_cyrillic_x', 'v280_route_cyrillic_x_equation', 2,
        'х + 5 = 12', 'x = 7', expected_numeric=7, expected_final='x = 7')
    add('v280_route_unicode_minus', 'v280_route_unicode_minus_expr', 1,
        'Реши: 18 − 7', '11', expected_numeric=11, expected_final='11')
    add('v280_route_middle_dot', 'v280_route_middle_dot_expr', 2,
        'Вычисли: 6·4', '24', expected_numeric=24, expected_final='24')
    add('v280_route_ocr_noise', 'v280_route_ocr_noise_magazine', 1,
        'В мага3ине было 20 яблок, продали 7 яблок. Сколько яблок осталось?', '13 яблок', expected_numeric=13, expected_unit='яблок', expected_final='13 яблок')
    add('v280_route_wrappers', 'v280_route_answer_number_equal_groups', 2,
        'Ответ запиши числом: В 3 коробках по 6 кубиков. Сколько кубиков всего?', '18 кубиков', expected_numeric=18, expected_unit='кубиков', expected_final='18 кубиков')

    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v280_wave1_cases()


def _normalize_case(case: dict[str, Any], index: int) -> dict[str, Any]:
    # v280-compatible normalizer.  It preserves the old v279 fields and adds
    # explicit grade/id/unit/source-family metadata for external black-box cases.
    return {
        'id': str(case.get('id') or case.get('name') or f'case_{index + 1}'),
        'grade': case.get('grade'),
        'category': str(case.get('category') or 'custom'),
        'name': str(case.get('name') or case.get('id') or f'case_{index + 1}'),
        'text': str(case.get('text') or ''),
        'expected': _case_expected_fragments(case),
        'expectedNumericAnswer': case.get('expectedNumericAnswer'),
        'expectedRawAnswer': case.get('expectedRawAnswer'),
        'expectedComparisonMode': case.get('expectedComparisonMode'),
        'comparisonMode': case.get('comparisonMode'),
        'numericComparable': case.get('numericComparable'),
        'expectedAnswerFormat': case.get('expectedAnswerFormat'),
        'excelRowNumber': case.get('excelRowNumber'),
        'excelId': case.get('excelId'),
        'inputText': case.get('inputText') or case.get('text'),
        'expectedUnit': case.get('expectedUnit'),
        'expectedFinalAnswer': case.get('expectedFinalAnswer'),
        'expectedSource': case.get('expectedSource'),
        'expectedSourceFamily': case.get('expectedSourceFamily'),
        'shouldWarn': bool(case.get('shouldWarn')),
        'ttsAudit': bool(case.get('ttsAudit') or False),
        'ttsSource': case.get('ttsSource'),
        'expectedTtsContains': list(case.get('expectedTtsContains') or []),
        'expectedTtsNotContains': list(case.get('expectedTtsNotContains') or case.get('expectedTtsForbidden') or []),
        'expectedTtsExact': case.get('expectedTtsExact'),
    }



def _audit_compare_text(value: str) -> str:
    value = str(value or '').lower().replace('ё', 'е').replace(',', '.')
    value = re.sub(r'(?<!\d)(\d{1,2})\s*:\s*(\d{2})(?!\d)', lambda m: f'{int(m.group(1)):02d}:{m.group(2)}', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return value


_NUMERIC_TOKEN_RE = re.compile(
    r'(?<![A-Za-zА-Яа-яЁё0-9])[-+]?\d+(?:[\s\u00a0]?\d{3})*\s*/\s*[-+]?\d+(?:[,.]\d+)?'
    r'|(?<![A-Za-zА-Яа-яЁё0-9])[-+]?\d+(?:[\s\u00a0]?\d{3})*(?:[,.]\d+)?'
)


def _numeric_token_to_fraction(value: Any) -> Fraction | None:
    text = str(value or '').replace('\u00a0', ' ').replace(' ', '').replace(',', '.').strip()
    if not text:
        return None
    try:
        if '/' in text:
            numerator, denominator = text.split('/', 1)
            return Fraction(Decimal(numerator)) / Fraction(Decimal(denominator))
        return Fraction(Decimal(text))
    except (ArithmeticError, InvalidOperation, ValueError, ZeroDivisionError):
        return None


def _numeric_fraction_to_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f'{value.numerator}/{value.denominator}'


def _normalize_numeric_token(value: Any) -> str:
    frac = _numeric_token_to_fraction(value)
    if frac is not None:
        return _numeric_fraction_to_text(frac)
    text = str(value or '').replace('\u00a0', ' ').replace(' ', '').replace(',', '.').strip()
    return text


def _numeric_tokens_from_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (int, float, Decimal, Fraction)):
        return [_normalize_numeric_token(value)]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            out.extend(_numeric_tokens_from_text(item))
        return out
    text = str(value or '').replace('\u00a0', ' ')
    out: list[str] = []
    for match in _NUMERIC_TOKEN_RE.finditer(text):
        normalized = _normalize_numeric_token(match.group(0))
        if normalized:
            out.append(normalized)
    return out


def _numeric_values_equal(left: Any, right: Any) -> bool:
    lf = _numeric_token_to_fraction(left)
    rf = _numeric_token_to_fraction(right)
    if lf is None or rf is None:
        return False
    return lf == rf


def _ordered_numeric_subsequence(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return True
    pos = 0
    for token in actual:
        if _numeric_values_equal(token, expected[pos]):
            pos += 1
            if pos >= len(expected):
                return True
    return False


def _payload_structured_solution(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ('structured_solution', 'structuredSolution'):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _extract_answer_line(result: str) -> str:
    match = re.search(r'Ответ\s*:\s*(.+)', str(result or ''), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ''
    return match.group(1).splitlines()[0].strip().rstrip('.')


def _numeric_candidate_sources(payload: dict[str, Any], result: str) -> list[tuple[str, list[str]]]:
    structured = _payload_structured_solution(payload)
    sources: list[tuple[str, Any]] = [
        ('answer_number', payload.get('answer_number')),
        ('structured_answer_number', structured.get('answer_number')),
        ('final_answer', payload.get('final_answer')),
        ('structured_final_answer', structured.get('final_answer')),
        ('answer_line', _extract_answer_line(result)),
    ]
    out: list[tuple[str, list[str]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for name, value in sources:
        tokens = _numeric_tokens_from_text(value)
        key = (name, tuple(tokens))
        if tokens and key not in seen:
            out.append((name, tokens))
            seen.add(key)
    visible_tokens = _numeric_tokens_from_text(result)
    if len(visible_tokens) == 1:
        out.append(('visible_single_number_safe_fallback', visible_tokens))
    return out


def _compare_numeric_expected(case: dict[str, Any], payload: dict[str, Any], result: str) -> dict[str, Any]:
    expected_raw = case.get('expectedNumericAnswer')
    expected_tokens = _numeric_tokens_from_text(expected_raw)
    comparison_mode = str(case.get('comparisonMode') or case.get('expectedComparisonMode') or '').strip().lower()
    numeric_comparable = bool(case.get('numericComparable')) or (comparison_mode == 'numeric' and bool(expected_tokens))
    base: dict[str, Any] = {
        'expectedNumericAnswerNormalized': expected_tokens[0] if len(expected_tokens) == 1 else expected_tokens,
        'actualAnswerNumber': '',
        'actualAnswerNumberSource': '',
        'actualNumericTokens': [],
        'numericComparable': numeric_comparable,
        'numericPassed': None,
        'numericSkipped': False,
        'numericComparisonMode': 'numeric_list' if len(expected_tokens) > 1 else 'numeric_scalar',
        'numericComparisonTolerance': 'exact rational/decimal equality',
    }
    if not numeric_comparable:
        base.update({
            'numericComparisonMode': 'non_numeric_expected',
            'numericSkipped': True,
            'numericComparisonIssue': 'expected answer is not safely numeric-comparable',
        })
        return base
    if not expected_tokens:
        base.update({
            'numericPassed': False,
            'numericComparisonIssue': 'expected numeric answer could not be parsed',
        })
        return base
    candidates = _numeric_candidate_sources(payload, result)
    first_actual_tokens: list[str] = []
    first_source = ''
    for source_name, tokens in candidates:
        if not first_actual_tokens:
            first_actual_tokens = list(tokens)
            first_source = source_name
        if len(expected_tokens) == 1:
            selected = tokens[0] if tokens else ''
            if selected and _numeric_values_equal(selected, expected_tokens[0]):
                base.update({
                    'actualAnswerNumber': selected,
                    'actualAnswerNumberSource': source_name,
                    'actualNumericTokens': tokens,
                    'numericPassed': True,
                    'numericComparisonIssue': '',
                })
                return base
            # Safe fallback for full answer lines that put quantities before the main answer:
            # accept the last number only when it is inside the explicit Ответ line, not the whole solution.
            if source_name == 'answer_line' and len(tokens) > 1 and _numeric_values_equal(tokens[-1], expected_tokens[0]):
                base.update({
                    'actualAnswerNumber': tokens[-1],
                    'actualAnswerNumberSource': 'answer_line_last_number_safe_fallback',
                    'actualNumericTokens': tokens,
                    'numericPassed': True,
                    'numericComparisonIssue': '',
                })
                return base
        else:
            if _ordered_numeric_subsequence(expected_tokens, tokens):
                base.update({
                    'actualAnswerNumber': tokens[:],
                    'actualAnswerNumberSource': source_name,
                    'actualNumericTokens': tokens,
                    'numericPassed': True,
                    'numericComparisonIssue': '',
                })
                return base
    base.update({
        'actualAnswerNumber': first_actual_tokens[0] if len(expected_tokens) == 1 and first_actual_tokens else (first_actual_tokens if first_actual_tokens else ''),
        'actualAnswerNumberSource': first_source,
        'actualNumericTokens': first_actual_tokens,
        'numericPassed': False,
        'numericComparisonIssue': f'actual numeric answer does not match expected {expected_tokens!r}',
    })
    return base


def _looks_like_text_word_problem_for_full_answer(case: dict[str, Any]) -> bool:
    text = str(case.get('text') or '').lower().replace('ё', 'е')
    if str(case.get('category') or '') != 'excel_numeric_regression':
        return False
    if '?' not in text or len(text) < 35:
        return False
    return any(word in text for word in ('сколько', 'на сколько', 'во сколько', 'какой', 'какая', 'какое', 'чему равн', 'найдите', 'узнайте'))




def _calculation_unit_dash_issue(case: dict[str, Any], result: str) -> str:
    # V401.1 user rule: in text-problem calculations, the result of each
    # arithmetic action carries a unit in parentheses and an explanation after a dash.
    if str(case.get('category') or '') != 'excel_numeric_regression':
        return ''
    text = str(case.get('text') or '').lower().replace('ё', 'е')
    if '?' not in text and not any(word in text for word in ('сколько', 'каков', 'какая', 'какой', 'чему равн')):
        return ''
    in_solution = False
    for line in str(result or '').splitlines():
        clean = line.strip()
        low_clean = clean.lower()
        if not clean:
            continue
        if re.match(r'^решение\s*[.:]?$', low_clean):
            in_solution = True
            continue
        if low_clean.startswith('ответ:'):
            break
        if not in_solution or low_clean.startswith('задача'):
            continue
        if re.search(r'\d\s*(?:[+\-−×*·:/÷])\s*\d', clean):
            if not re.search(r'=\s*[-+]?\d+(?:[,.]\d+)?(?:\s*/\s*[-+]?\d+)?\s*\([^)]{1,40}\)', clean):
                return 'V401.1 formatting: calculation result must include unit in parentheses'
            if '—' not in clean and '–' not in clean and not re.search(r'\s-\s', clean):
                return 'V401.1 formatting: calculation line must include dash explanation'
    return ''

def _full_answer_phrase_issue(case: dict[str, Any], result: str) -> str:
    if not _looks_like_text_word_problem_for_full_answer(case):
        return ''
    answer = _extract_answer_line(result)
    if not answer:
        return ''
    answer_norm = _audit_compare_text(answer)
    raw_norm = _audit_compare_text(str(case.get('expectedRawAnswer') or ''))
    if raw_norm and answer_norm == raw_norm:
        return 'Excel numeric regression: visible Ответ line repeats short Excel answer instead of a full school phrase'
    # Too short means only a number/fraction plus at most 1-3 unit/word tokens, optionally with На/В/Через.
    short_pattern = r'^(?:на|в|через)?\s*[-+]?\d+(?:[,.]\d+)?(?:\s*/\s*[-+]?\d+)?(?:\s+[а-яёa-z.²³/-]+){0,3}$'
    if re.fullmatch(short_pattern, answer_norm, flags=re.IGNORECASE):
        return 'Excel numeric regression: visible Ответ line is too short for a text problem'
    return ''


def _loose_expected_phrase_present(expected: str, result: str) -> bool:
    exp = _audit_compare_text(expected)
    res = _audit_compare_text(result)
    if not exp:
        return True
    if exp in res:
        return True
    # Accept punctuation/connector variants for tens-units answers:
    # "1 десяток и 2 единицы" vs "1 десяток, 2 единицы".
    def compact_units(value: str) -> str:
        value = value.replace(',', ' и ')
        value = re.sub(r'\s+', ' ', value)
        value = value.replace(' единицa', ' единица')
        return value.strip()
    return compact_units(exp) in compact_units(res)

def _check_payload(case: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    import re

    result = str(payload.get('result') or '')
    result_for_compare = _audit_compare_text(result)
    source = str(payload.get('source') or '')
    issues: list[str] = []
    if not result.strip():
        issues.append('empty result')
    if 'Ответ:' not in result:
        issues.append('missing Ответ: line')

    expected_source = case.get('expectedSource')
    if expected_source and source != expected_source:
        issues.append(f'expected source {expected_source!r}, got {source!r}')
    expected_source_family = case.get('expectedSourceFamily')
    if expected_source_family and not source.startswith(str(expected_source_family)):
        compatible_source_families = {
            'local:live-v285': ('local:live-v297-g1-',),
        }
        compatible_prefixes = compatible_source_families.get(str(expected_source_family), ())
        if not any(source.startswith(prefix) for prefix in compatible_prefixes):
            issues.append(f'expected source family {expected_source_family!r}, got {source!r}')

    low_source = source.lower()
    allow_expected_guard_source = bool(expected_source) and low_source == str(expected_source).lower()
    if any(low_source.startswith(marker) for marker in FORBIDDEN_SOURCES) and not allow_expected_guard_source:
        issues.append(f'forbidden source {source!r}')
    if case.get('shouldWarn'):
        if source != 'guard-multi-task':
            issues.append(f'expected multi-task warning, got source {source!r}')
        if 'разделите задания' not in result.lower():
            issues.append('missing multi-task warning text')
    else:
        if source.startswith('guard-low-confidence') and str(expected_source or '') != 'guard-low-confidence':
            issues.append('solvable task returned low confidence')

    for fragment in case.get('expected') or []:
        if fragment and fragment.lower() not in result.lower():
            issues.append(f'missing expected fragment {fragment!r}')

    expected_final = case.get('expectedFinalAnswer')
    if expected_final and not _loose_expected_phrase_present(str(expected_final), result):
        issues.append(f'missing expected final answer phrase {expected_final!r}')

    expected_unit = case.get('expectedUnit')
    if expected_unit and _audit_compare_text(str(expected_unit)) not in result_for_compare:
        issues.append(f'missing expected unit {expected_unit!r}')

    numeric_details = _compare_numeric_expected(case, payload, result)
    expected_numeric = case.get('expectedNumericAnswer')
    if numeric_details.get('numericComparable') and not numeric_details.get('numericPassed'):
        issues.append(str(numeric_details.get('numericComparisonIssue') or f'missing expected numeric answer {expected_numeric!r}'))

    full_answer_issue = _full_answer_phrase_issue(case, result)
    if full_answer_issue:
        issues.append(full_answer_issue)

    calculation_format_issue = _calculation_unit_dash_issue(case, result)
    if calculation_format_issue:
        issues.append(calculation_format_issue)

    for marker in _V280_FORBIDDEN_RESULT_MARKERS:
        if marker.lower() in result.lower():
            issues.append(f'forbidden marker {marker!r}')
    if '\n1)\n' in result or '\n2)\n' in result or '\n3)\n' in result or '\n4)\n' in result:
        issues.append('split action number formatting')
    return {
        'ok': not issues,
        'issues': issues,
        'source': source,
        'resultPreview': result[:260],
        **numeric_details,
    }


# --- v281 external black-box audit wave 2: Grade 3-4 core ---
# Synthetic cases inspired by external curriculum/task-family sources; not copied from them.
def _v281_wave2_cases() -> list[dict[str, Any]]:
    return [{'id': 'v281_g3_place_value_write_384',
  'name': 'v281_g3_place_value_write_384',
  'grade': 3,
  'category': 'v281_numbers_place_value',
  'text': 'Запиши число, в котором 3 сотни 8 десятков и 4 единицы.',
  'expected': ['384'],
  'expectedFinalAnswer': '384',
  'expectedNumericAnswer': '384'},
 {'id': 'v281_g3_place_value_read_706',
  'name': 'v281_g3_place_value_read_706',
  'grade': 3,
  'category': 'v281_numbers_place_value',
  'text': 'В числе 706 сколько сотен, десятков и единиц?',
  'expected': ['7 сотен', '0 десятков', '6 единиц'],
  'expectedFinalAnswer': '7 сотен',
  'expectedNumericAnswer': '7',
  'expectedUnit': 'сотен'},
 {'id': 'v281_g4_place_value_write_245316',
  'name': 'v281_g4_place_value_write_245316',
  'grade': 4,
  'category': 'v281_numbers_place_value',
  'text': 'Запиши число, в котором 2 сотни тысяч 4 десятка тысяч 5 тысяч 3 сотни 1 десяток и 6 единиц.',
  'expected': ['245316'],
  'expectedFinalAnswer': '245316',
  'expectedNumericAnswer': '245316'},
 {'id': 'v281_g3_compare_5384_5834',
  'name': 'v281_g3_compare_5384_5834',
  'grade': 3,
  'category': 'v281_numbers_compare',
  'text': 'Сравни числа 5384 и 5834.',
  'expected': ['5384 < 5834'],
  'expectedFinalAnswer': '5384 < 5834',
  'expectedNumericAnswer': '5384'},
 {'id': 'v281_g3_round_367_tens',
  'name': 'v281_g3_round_367_tens',
  'grade': 3,
  'category': 'v281_numbers_rounding',
  'text': 'Округли 367 до десятков.',
  'expected': ['370'],
  'expectedFinalAnswer': '370',
  'expectedNumericAnswer': '370'},
 {'id': 'v281_g4_round_1249_hundreds',
  'name': 'v281_g4_round_1249_hundreds',
  'grade': 4,
  'category': 'v281_numbers_rounding',
  'text': 'Округли 1249 до сотен.',
  'expected': ['1200'],
  'expectedFinalAnswer': '1200',
  'expectedNumericAnswer': '1200'},
 {'id': 'v281_g3_even_138',
  'name': 'v281_g3_even_138',
  'grade': 3,
  'category': 'v281_numbers_parity',
  'text': 'Число 138 четное или нечетное?',
  'expected': ['чётное'],
  'expectedFinalAnswer': 'чётное'},
 {'id': 'v281_g3_km_m_to_m',
  'name': 'v281_g3_km_m_to_m',
  'grade': 3,
  'category': 'v281_units_length',
  'text': 'Сколько метров в 7 км 250 м?',
  'expected': ['7250 метров'],
  'expectedFinalAnswer': '7250 метров',
  'expectedNumericAnswer': '7250',
  'expectedUnit': 'метров'},
 {'id': 'v281_g3_g_to_kg_g',
  'name': 'v281_g3_g_to_kg_g',
  'grade': 3,
  'category': 'v281_units_mass',
  'text': 'Сколько килограммов и граммов в 3250 г?',
  'expected': ['3 килограмма 250 граммов'],
  'expectedFinalAnswer': '3 килограмма 250 граммов',
  'expectedNumericAnswer': '3',
  'expectedUnit': 'килограмма 250 граммов'},
 {'id': 'v281_g3_min_sec_to_sec',
  'name': 'v281_g3_min_sec_to_sec',
  'grade': 3,
  'category': 'v281_units_time',
  'text': 'Сколько секунд в 4 мин 20 с?',
  'expected': ['260 секунд'],
  'expectedFinalAnswer': '260 секунд',
  'expectedNumericAnswer': '260',
  'expectedUnit': 'секунд'},
 {'id': 'v281_g3_weeks_days_to_days',
  'name': 'v281_g3_weeks_days_to_days',
  'grade': 3,
  'category': 'v281_calendar',
  'text': 'Сколько дней в 3 неделях 5 днях?',
  'expected': ['26 дней'],
  'expectedFinalAnswer': '26 дней',
  'expectedNumericAnswer': '26',
  'expectedUnit': 'дней'},
 {'id': 'v281_g3_hours_to_days',
  'name': 'v281_g3_hours_to_days',
  'grade': 3,
  'category': 'v281_calendar',
  'text': 'Сколько дней в 96 часах?',
  'expected': ['4 дня'],
  'expectedFinalAnswer': '4 дня',
  'expectedNumericAnswer': '4',
  'expectedUnit': 'дня'},
 {'id': 'v281_g3_add_348_276',
  'name': 'v281_g3_add_348_276',
  'grade': 3,
  'category': 'v281_arithmetic_direct',
  'text': 'Вычисли 348 + 276.',
  'expected': ['624'],
  'expectedFinalAnswer': '624',
  'expectedNumericAnswer': '624'},
 {'id': 'v281_g3_sub_902_458',
  'name': 'v281_g3_sub_902_458',
  'grade': 3,
  'category': 'v281_arithmetic_direct',
  'text': 'Вычисли 902 - 458.',
  'expected': ['444'],
  'expectedFinalAnswer': '444',
  'expectedNumericAnswer': '444'},
 {'id': 'v281_g3_mul_37_6',
  'name': 'v281_g3_mul_37_6',
  'grade': 3,
  'category': 'v281_arithmetic_direct',
  'text': 'Вычисли 37 * 6.',
  'expected': ['222'],
  'expectedFinalAnswer': '222',
  'expectedNumericAnswer': '222'},
 {'id': 'v281_g3_div_936_9',
  'name': 'v281_g3_div_936_9',
  'grade': 3,
  'category': 'v281_arithmetic_direct',
  'text': 'Вычисли 936 : 9.',
  'expected': ['104'],
  'expectedFinalAnswer': '104',
  'expectedNumericAnswer': '104'},
 {'id': 'v281_g4_expr_parentheses_420',
  'name': 'v281_g4_expr_parentheses_420',
  'grade': 4,
  'category': 'v281_order_of_operations',
  'text': 'Найди значение выражения 420 : (7 + 8) + 36.',
  'expected': ['64'],
  'expectedFinalAnswer': '64',
  'expectedNumericAnswer': '64'},
 {'id': 'v281_g4_expr_order_125',
  'name': 'v281_g4_expr_order_125',
  'grade': 4,
  'category': 'v281_order_of_operations',
  'text': 'Найди значение выражения 125 + 75 : 3 * 4.',
  'expected': ['225'],
  'expectedFinalAnswer': '225',
  'expectedNumericAnswer': '225'},
 {'id': 'v281_g3_rem_86_9',
  'name': 'v281_g3_rem_86_9',
  'grade': 3,
  'category': 'v281_division_remainder',
  'text': 'Выполни деление с остатком: 86 : 9.',
  'expected': ['9', 'остаток 5'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': '9'},
 {'id': 'v281_g4_rem_157_12',
  'name': 'v281_g4_rem_157_12',
  'grade': 4,
  'category': 'v281_division_remainder',
  'text': '157 : 12 с остатком.',
  'expected': ['13', 'остаток 1'],
  'expectedFinalAnswer': '13',
  'expectedNumericAnswer': '13'},
 {'id': 'v281_g3_compare_expr_equal',
  'name': 'v281_g3_compare_expr_equal',
  'grade': 3,
  'category': 'v281_expressions_compare',
  'text': 'Сравни 64 : 8 + 7 и 3 * 5.',
  'expected': ['равны'],
  'expectedFinalAnswer': 'равны'},
 {'id': 'v281_g4_letter_a_8_15',
  'name': 'v281_g4_letter_a_8_15',
  'grade': 4,
  'category': 'v281_letter_expressions',
  'text': 'Найди значение выражения a * 8 + 15, если a = 7.',
  'expected': ['71'],
  'expectedFinalAnswer': '71',
  'expectedNumericAnswer': '71'},
 {'id': 'v281_g4_letter_b_div_6_minus_9',
  'name': 'v281_g4_letter_b_div_6_minus_9',
  'grade': 4,
  'category': 'v281_letter_expressions',
  'text': 'Найди значение выражения b : 6 - 9, если b = 90.',
  'expected': ['6'],
  'expectedFinalAnswer': '6',
  'expectedNumericAnswer': '6'},
 {'id': 'v281_g3_expr_two_parentheses',
  'name': 'v281_g3_expr_two_parentheses',
  'grade': 3,
  'category': 'v281_order_of_operations',
  'text': 'Вычисли (96 - 36) : (5 + 5).',
  'expected': ['6'],
  'expectedFinalAnswer': '6',
  'expectedNumericAnswer': '6'},
 {'id': 'v281_g3_library_boxes',
  'name': 'v281_g3_library_boxes',
  'grade': 3,
  'category': 'v281_text_composite',
  'text': 'В библиотеку привезли 4 коробки по 25 книг и 3 коробки по 18 книг. Сколько книг привезли всего?',
  'expected': ['154 книги'],
  'expectedFinalAnswer': '154 книги',
  'expectedNumericAnswer': '154',
  'expectedUnit': 'книги'},
 {'id': 'v281_g3_garden_rows',
  'name': 'v281_g3_garden_rows',
  'grade': 3,
  'category': 'v281_text_composite',
  'text': 'В саду посадили 5 рядов по 12 яблонь и 4 ряда по 15 груш. Сколько всего деревьев посадили?',
  'expected': ['120 деревьев'],
  'expectedFinalAnswer': '120 деревьев',
  'expectedNumericAnswer': '120',
  'expectedUnit': 'деревьев'},
 {'id': 'v281_g3_warehouse_notebooks_left',
  'name': 'v281_g3_warehouse_notebooks_left',
  'grade': 3,
  'category': 'v281_text_composite',
  'text': 'На складе было 360 тетрадей. В 4 класса раздали по 35 тетрадей. Сколько тетрадей осталось?',
  'expected': ['220 тетрадей'],
  'expectedFinalAnswer': '220 тетрадей',
  'expectedNumericAnswer': '220',
  'expectedUnit': 'тетрадей'},
 {'id': 'v281_g4_potatoes_two_days_left',
  'name': 'v281_g4_potatoes_two_days_left',
  'grade': 4,
  'category': 'v281_text_composite',
  'text': 'В магазине было 240 кг картофеля. В первый день продали 85 кг, во второй день продали на 18 кг больше. Сколько кг осталось?',
  'expected': ['52 килограмма'],
  'expectedFinalAnswer': '52 килограмма',
  'expectedNumericAnswer': '52',
  'expectedUnit': 'килограмма'},
 {'id': 'v281_g3_book_extra_data',
  'name': 'v281_g3_book_extra_data',
  'grade': 3,
  'category': 'v281_text_extra_data',
  'text': 'В книге 96 страниц. В понедельник Миша прочитал 28 страниц, во вторник прочитал 31 страницу. Книга стоит 150 рублей. Сколько '
          'страниц осталось прочитать?',
  'expected': ['37 страниц'],
  'expectedFinalAnswer': '37 страниц',
  'expectedNumericAnswer': '37',
  'expectedUnit': 'страниц'},
 {'id': 'v281_g3_vera_dima_times',
  'name': 'v281_g3_vera_dima_times',
  'grade': 3,
  'category': 'v281_text_reverse_relation',
  'text': 'У Веры было 72 марки. Это в 3 раза больше, чем у Димы. Сколько марок у Димы?',
  'expected': ['24 марки'],
  'expectedFinalAnswer': '24 марки',
  'expectedNumericAnswer': '24',
  'expectedUnit': 'марки'},
 {'id': 'v281_g3_kolya_misha_less',
  'name': 'v281_g3_kolya_misha_less',
  'grade': 3,
  'category': 'v281_text_reverse_relation',
  'text': 'У Коли 48 наклеек. Это на 12 наклеек меньше, чем у Миши. Сколько наклеек у Миши?',
  'expected': ['60 наклеек'],
  'expectedFinalAnswer': '60 наклеек',
  'expectedNumericAnswer': '60',
  'expectedUnit': 'наклеек'},
 {'id': 'v281_g3_two_classes_left',
  'name': 'v281_g3_two_classes_left',
  'grade': 3,
  'category': 'v281_text_composite',
  'text': 'В двух классах было 24 и 26 учеников. 18 учеников ушли в актовый зал. Сколько учеников осталось?',
  'expected': ['32 ученика'],
  'expectedFinalAnswer': '32 ученика',
  'expectedNumericAnswer': '32',
  'expectedUnit': 'ученика'},
 {'id': 'v281_g4_bus_free_seats',
  'name': 'v281_g4_bus_free_seats',
  'grade': 4,
  'category': 'v281_text_composite',
  'text': 'На экскурсию поехали 243 ученика. Было 6 автобусов по 45 мест. Сколько мест осталось свободными?',
  'expected': ['27 мест'],
  'expectedFinalAnswer': '27 мест',
  'expectedNumericAnswer': '27',
  'expectedUnit': 'мест'},
 {'id': 'v281_g3_boxes_sold_left',
  'name': 'v281_g3_boxes_sold_left',
  'grade': 3,
  'category': 'v281_text_composite',
  'text': 'В 8 ящиках было по 15 яблок. Продали 47 яблок. Сколько яблок осталось?',
  'expected': ['73 яблока'],
  'expectedFinalAnswer': '73 яблока',
  'expectedNumericAnswer': '73',
  'expectedUnit': 'яблока'},
 {'id': 'v281_g3_screws_boxes',
  'name': 'v281_g3_screws_boxes',
  'grade': 3,
  'category': 'v281_equal_sharing',
  'text': '144 винта разложили поровну в 6 коробок. Сколько винтов в каждой коробке?',
  'expected': ['24 винта'],
  'expectedFinalAnswer': '24 винта',
  'expectedNumericAnswer': '24',
  'expectedUnit': 'винта'},
 {'id': 'v281_g3_carrot_onion_difference',
  'name': 'v281_g3_carrot_onion_difference',
  'grade': 3,
  'category': 'v281_text_comparison',
  'text': 'Моркови было 96 кг, а лука в 3 раза меньше. На сколько килограммов моркови больше, чем лука?',
  'expected': ['64 килограмма'],
  'expectedFinalAnswer': '64 килограмма',
  'expectedNumericAnswer': '64',
  'expectedUnit': 'килограмма'},
 {'id': 'v281_g3_olya_ira_total',
  'name': 'v281_g3_olya_ira_total',
  'grade': 3,
  'category': 'v281_text_part_whole',
  'text': 'У Оли и Иры 58 наклеек. У Оли 25 наклеек. Сколько наклеек у Иры?',
  'expected': ['33 наклейки'],
  'expectedFinalAnswer': '33 наклейки',
  'expectedNumericAnswer': '33',
  'expectedUnit': 'наклейки'},
 {'id': 'v281_g3_albums_paints_total',
  'name': 'v281_g3_albums_paints_total',
  'grade': 3,
  'category': 'v281_money_total',
  'text': 'Купили 3 альбома по 48 рублей и краски за 96 рублей. Сколько рублей заплатили?',
  'expected': ['240 рублей'],
  'expectedFinalAnswer': '240 рублей',
  'expectedNumericAnswer': '240',
  'expectedUnit': 'рублей'},
 {'id': 'v281_g3_notebooks_change',
  'name': 'v281_g3_notebooks_change',
  'grade': 3,
  'category': 'v281_money_change',
  'text': 'С 500 рублей купили 6 блокнотов по 45 рублей. Сколько рублей сдачи получили?',
  'expected': ['230 рублей'],
  'expectedFinalAnswer': '230 рублей',
  'expectedNumericAnswer': '230',
  'expectedUnit': 'рублей'},
 {'id': 'v281_g3_apple_kg_price',
  'name': 'v281_g3_apple_kg_price',
  'grade': 3,
  'category': 'v281_money_price',
  'text': 'За 4 кг яблок заплатили 320 рублей. Сколько рублей стоит 1 кг яблок?',
  'expected': ['80 рублей'],
  'expectedFinalAnswer': '80 рублей',
  'expectedNumericAnswer': '80',
  'expectedUnit': 'рублей'},
 {'id': 'v281_g4_tickets_budget',
  'name': 'v281_g4_tickets_budget',
  'grade': 4,
  'category': 'v281_money_quantity',
  'text': 'Один билет стоит 85 рублей. Сколько билетов можно купить на 500 рублей?',
  'expected': ['5 билетов'],
  'expectedFinalAnswer': '5 билетов',
  'expectedNumericAnswer': '5',
  'expectedUnit': 'билетов'},
 {'id': 'v281_g3_rub_kop_add',
  'name': 'v281_g3_rub_kop_add',
  'grade': 3,
  'category': 'v281_money_mixed',
  'text': '2 рубля 80 копеек + 3 рубля 45 копеек. Сколько получится?',
  'expected': ['6 рублей 25 копеек'],
  'expectedFinalAnswer': '6 рублей 25 копеек',
  'expectedNumericAnswer': '6',
  'expectedUnit': 'рублей 25 копеек'},
 {'id': 'v281_g4_two_items_budget',
  'name': 'v281_g4_two_items_budget',
  'grade': 4,
  'category': 'v281_money_change',
  'text': 'С 150 рублей купили 4 карандаша по 17 рублей и 2 ластика по 13 рублей. Сколько рублей осталось?',
  'expected': ['56 рублей'],
  'expectedFinalAnswer': '56 рублей',
  'expectedNumericAnswer': '56',
  'expectedUnit': 'рублей'},
 {'id': 'v281_g3_price_qty_cost',
  'name': 'v281_g3_price_qty_cost',
  'grade': 3,
  'category': 'v281_money_cost',
  'text': 'Одна книга стоит 125 рублей. Сколько стоят 4 такие книги?',
  'expected': ['500 рублей'],
  'expectedFinalAnswer': '500 рублей',
  'expectedNumericAnswer': '500',
  'expectedUnit': 'рублей'},
 {'id': 'v281_g4_price_from_total',
  'name': 'v281_g4_price_from_total',
  'grade': 4,
  'category': 'v281_money_price',
  'text': 'За 6 одинаковых наборов заплатили 720 рублей. Сколько рублей стоит один набор?',
  'expected': ['120 рублей'],
  'expectedFinalAnswer': '120 рублей',
  'expectedNumericAnswer': '120',
  'expectedUnit': 'рублей'},
 {'id': 'v281_g3_lesson_845_1010',
  'name': 'v281_g3_lesson_845_1010',
  'grade': 3,
  'category': 'v281_time_duration',
  'text': 'Урок начался в 8:45 и закончился в 10:10. Сколько минут длился урок?',
  'expected': ['1 час 25 минут'],
  'expectedFinalAnswer': '1 час 25 минут',
  'expectedNumericAnswer': '1',
  'expectedUnit': 'час 25 минут'},
 {'id': 'v281_g3_film_end',
  'name': 'v281_g3_film_end',
  'grade': 3,
  'category': 'v281_time_end',
  'text': 'Фильм начался в 14:20 и длился 1 ч 35 мин. Во сколько он закончился?',
  'expected': ['15:55'],
  'expectedFinalAnswer': '15:55',
  'expectedNumericAnswer': '15:55'},
 {'id': 'v281_g4_train_cross_midnight',
  'name': 'v281_g4_train_cross_midnight',
  'grade': 4,
  'category': 'v281_time_duration',
  'text': 'Поезд отправился в 22:40 и прибыл в 01:10. Сколько времени поезд был в пути?',
  'expected': ['2 часа 30 минут'],
  'expectedFinalAnswer': '2 часа 30 минут',
  'expectedNumericAnswer': '2',
  'expectedUnit': 'часа 30 минут'},
 {'id': 'v281_g3_95_min_to_h_m',
  'name': 'v281_g3_95_min_to_h_m',
  'grade': 3,
  'category': 'v281_time_conversion',
  'text': '95 минут - это сколько часов и минут?',
  'expected': ['1 час 35 минут'],
  'expectedFinalAnswer': '1 час 35 минут',
  'expectedNumericAnswer': '1',
  'expectedUnit': 'час 35 минут'},
 {'id': 'v281_g3_weeks_days',
  'name': 'v281_g3_weeks_days',
  'grade': 3,
  'category': 'v281_calendar',
  'text': 'Сколько дней в 4 неделях 2 днях?',
  'expected': ['30 дней'],
  'expectedFinalAnswer': '30 дней',
  'expectedNumericAnswer': '30',
  'expectedUnit': 'дней'},
 {'id': 'v281_g3_bus_arrival',
  'name': 'v281_g3_bus_arrival',
  'grade': 3,
  'category': 'v281_time_end',
  'text': 'Автобус отправился в 12:15 и ехал 2 ч 25 мин. Во сколько он прибыл?',
  'expected': ['14:40'],
  'expectedFinalAnswer': '14:40',
  'expectedNumericAnswer': '14:40'},
 {'id': 'v281_g3_training_1305_1350',
  'name': 'v281_g3_training_1305_1350',
  'grade': 3,
  'category': 'v281_time_duration',
  'text': 'Тренировка началась в 13:05 и закончилась в 13:50. Сколько минут длилась тренировка?',
  'expected': ['45 минут'],
  'expectedFinalAnswer': '45 минут',
  'expectedNumericAnswer': '45',
  'expectedUnit': 'минут'},
 {'id': 'v281_g3_truck_distance',
  'name': 'v281_g3_truck_distance',
  'grade': 3,
  'category': 'v281_motion_distance',
  'text': 'Грузовик ехал 4 часа со скоростью 65 км/ч. Сколько километров он проехал?',
  'expected': ['260 километров'],
  'expectedFinalAnswer': '260 километров',
  'expectedNumericAnswer': '260',
  'expectedUnit': 'километров'},
 {'id': 'v281_g3_tourist_speed',
  'name': 'v281_g3_tourist_speed',
  'grade': 3,
  'category': 'v281_motion_speed',
  'text': 'Турист прошел 36 км за 3 часа. С какой скоростью шел турист?',
  'expected': ['12 км/ч'],
  'expectedFinalAnswer': '12 км/ч',
  'expectedNumericAnswer': '12',
  'expectedUnit': 'км/ч'},
 {'id': 'v281_g3_bus_time',
  'name': 'v281_g3_bus_time',
  'grade': 3,
  'category': 'v281_motion_time',
  'text': 'Автобус ехал со скоростью 60 км/ч и проехал 180 км. Сколько часов ехал автобус?',
  'expected': ['3 часа'],
  'expectedFinalAnswer': '3 часа',
  'expectedNumericAnswer': '3',
  'expectedUnit': 'часа'},
 {'id': 'v281_g4_two_cars_towards',
  'name': 'v281_g4_two_cars_towards',
  'grade': 4,
  'category': 'v281_motion_towards',
  'text': 'Из двух городов одновременно навстречу друг другу выехали два автомобиля. Скорость первого 70 км/ч, скорость второго 80 км/ч. '
          'Через 3 часа они встретились. Какое расстояние между городами?',
  'expected': ['450 километров'],
  'expectedFinalAnswer': '450 километров',
  'expectedNumericAnswer': '450',
  'expectedUnit': 'километров'},
 {'id': 'v281_g4_car_two_leg',
  'name': 'v281_g4_car_two_leg',
  'grade': 4,
  'category': 'v281_motion_two_leg',
  'text': 'Автомобиль ехал 3 ч со скоростью 70 км/ч. Потом еще 2 ч со скоростью 60 км/ч. Какое расстояние он проехал?',
  'expected': ['330 километров'],
  'expectedFinalAnswer': '330 километров',
  'expectedNumericAnswer': '330',
  'expectedUnit': 'километров'},
 {'id': 'v281_g4_cyclist_remaining_times',
  'name': 'v281_g4_cyclist_remaining_times',
  'grade': 4,
  'category': 'v281_motion_remaining',
  'text': 'Велосипедист проехал 42 км. Ему осталось проехать в 2 раза больше. Каков весь путь?',
  'expected': ['126 километров'],
  'expectedFinalAnswer': '126 километров',
  'expectedNumericAnswer': '126',
  'expectedUnit': 'километров'},
 {'id': 'v281_g4_train_remaining_less',
  'name': 'v281_g4_train_remaining_less',
  'grade': 4,
  'category': 'v281_motion_remaining',
  'text': 'Поезд ехал 4 ч со скоростью 65 км/ч. Осталось проехать на 80 км меньше. Каков весь путь?',
  'expected': ['440 километров'],
  'expectedFinalAnswer': '440 километров',
  'expectedNumericAnswer': '440',
  'expectedUnit': 'километров'},
 {'id': 'v281_g4_towards_remaining',
  'name': 'v281_g4_towards_remaining',
  'grade': 4,
  'category': 'v281_motion_remaining_distance',
  'text': 'Расстояние между городами 300 км. Скорость первого автомобиля 65 км/ч, скорость второго 55 км/ч. Они едут навстречу. Сколько км '
          'останется между ними через 2 часа?',
  'expected': ['60 километров'],
  'expectedFinalAnswer': '60 километров',
  'expectedNumericAnswer': '60',
  'expectedUnit': 'километров'},
 {'id': 'v281_g4_pipes_5_10',
  'name': 'v281_g4_pipes_5_10',
  'grade': 4,
  'category': 'v281_joint_work',
  'text': 'Одна труба наполняет бассейн за 5 часов, другая труба — за 10 часов. За сколько часов наполнят бассейн обе трубы вместе?',
  'expected': ['3 часа 20 минут'],
  'expectedFinalAnswer': '3 часа 20 минут',
  'expectedNumericAnswer': '3',
  'expectedUnit': 'часа 20 минут'},
 {'id': 'v281_g4_printers_pages',
  'name': 'v281_g4_printers_pages',
  'grade': 4,
  'category': 'v281_joint_work',
  'text': 'Один принтер печатает 180 страниц за 6 часов, другой принтер — столько же за 9 часов. За сколько часов они напечатают 180 '
          'страниц вместе?',
  'expected': ['3 часа 36 минут'],
  'expectedFinalAnswer': '3 часа 36 минут',
  'expectedNumericAnswer': '3',
  'expectedUnit': 'часа 36 минут'},
 {'id': 'v281_g4_tractors_360',
  'name': 'v281_g4_tractors_360',
  'grade': 4,
  'category': 'v281_joint_work',
  'text': 'Один трактор может вспахать поле площадью 360 аров за 4 часа, а другой трактор — за 6 часов. За сколько часов вспашут поле оба '
          'трактора, работая вместе?',
  'expected': ['2 часа 24 минуты'],
  'expectedFinalAnswer': '2 часа 24 минуты',
  'expectedNumericAnswer': '2',
  'expectedUnit': 'часа 24 минуты'},
 {'id': 'v281_g4_brigades_12_6',
  'name': 'v281_g4_brigades_12_6',
  'grade': 4,
  'category': 'v281_joint_work',
  'text': 'Одна бригада может выполнить заказ за 12 дней, другая бригада — за 6 дней. За сколько дней выполнят заказ две бригады вместе?',
  'expected': ['4 дня'],
  'expectedFinalAnswer': '4 дня',
  'expectedNumericAnswer': '4',
  'expectedUnit': 'дня'},
 {'id': 'v281_g4_machines_details',
  'name': 'v281_g4_machines_details',
  'grade': 4,
  'category': 'v281_joint_work',
  'text': 'Один станок делает 240 деталей за 8 часов, другой станок — столько же за 12 часов. За сколько часов они сделают 240 деталей '
          'вместе?',
  'expected': ['4 часа 48 минут'],
  'expectedFinalAnswer': '4 часа 48 минут',
  'expectedNumericAnswer': '4',
  'expectedUnit': 'часа 48 минут'},
 {'id': 'v281_g4_pumps_minutes',
  'name': 'v281_g4_pumps_minutes',
  'grade': 4,
  'category': 'v281_joint_work',
  'text': 'Один насос перекачивает 240 литров за 8 минут, другой насос — столько же за 12 минут. За сколько минут они перекачают 240 '
          'литров вместе?',
  'expected': ['4,8 минуты'],
  'expectedFinalAnswer': '4,8 минуты',
  'expectedNumericAnswer': '4,8',
  'expectedUnit': 'минуты'},
 {'id': 'v281_g4_three_fourths_80',
  'name': 'v281_g4_three_fourths_80',
  'grade': 4,
  'category': 'v281_fractions_part',
  'text': 'Найди 3/4 от 80.',
  'expected': ['60'],
  'expectedFinalAnswer': '60',
  'expectedNumericAnswer': '60'},
 {'id': 'v281_g4_two_fifths_45',
  'name': 'v281_g4_two_fifths_45',
  'grade': 4,
  'category': 'v281_fractions_part',
  'text': 'Найди 2/5 от 45.',
  'expected': ['18'],
  'expectedFinalAnswer': '18',
  'expectedNumericAnswer': '18'},
 {'id': 'v281_g3_fourth_part_64',
  'name': 'v281_g3_fourth_part_64',
  'grade': 3,
  'category': 'v281_fractions_part',
  'text': 'Найди четвертую часть от 64.',
  'expected': ['16'],
  'expectedFinalAnswer': '16',
  'expectedNumericAnswer': '16'},
 {'id': 'v281_g3_third_whole_15',
  'name': 'v281_g3_third_whole_15',
  'grade': 3,
  'category': 'v281_fractions_whole',
  'text': 'Треть числа равна 15. Найди всё число.',
  'expected': ['45'],
  'expectedFinalAnswer': '45',
  'expectedNumericAnswer': '45'},
 {'id': 'v281_g4_two_thirds_whole_18',
  'name': 'v281_g4_two_thirds_whole_18',
  'grade': 4,
  'category': 'v281_fractions_whole',
  'text': '2/3 числа равны 18. Найди всё число.',
  'expected': ['27'],
  'expectedFinalAnswer': '27',
  'expectedNumericAnswer': '27'},
 {'id': 'v281_g4_compare_3_5_4_7',
  'name': 'v281_g4_compare_3_5_4_7',
  'grade': 4,
  'category': 'v281_fractions_compare',
  'text': 'Сравни дроби 3/5 и 4/7.',
  'expected': ['3/5 больше'],
  'expectedFinalAnswer': '3/5 больше',
  'expectedNumericAnswer': '3',
  'expectedUnit': '/5 больше'},
 {'id': 'v281_g3_quarter_hour',
  'name': 'v281_g3_quarter_hour',
  'grade': 3,
  'category': 'v281_fractions_time',
  'text': 'Сколько минут в четверти часа?',
  'expected': ['15 минут'],
  'expectedFinalAnswer': '15 минут',
  'expectedNumericAnswer': '15',
  'expectedUnit': 'минут'},
 {'id': 'v281_g4_one_sixth_3m',
  'name': 'v281_g4_one_sixth_3m',
  'grade': 4,
  'category': 'v281_fractions_length',
  'text': 'Найди 1/6 от 3 м.',
  'expected': ['50 сантиметров'],
  'expectedFinalAnswer': '50 сантиметров',
  'expectedNumericAnswer': '50',
  'expectedUnit': 'сантиметр'},
 {'id': 'v281_g3_rect_perimeter_14_6',
  'name': 'v281_g3_rect_perimeter_14_6',
  'grade': 3,
  'category': 'v281_geometry',
  'text': 'У прямоугольника длина 14 см, ширина 6 см. Найди периметр.',
  'expected': ['40 см'],
  'expectedFinalAnswer': '40 см',
  'expectedNumericAnswer': '40',
  'expectedUnit': 'см'},
 {'id': 'v281_g3_rect_area_14_6',
  'name': 'v281_g3_rect_area_14_6',
  'grade': 3,
  'category': 'v281_geometry',
  'text': 'У прямоугольника длина 14 см, ширина 6 см. Найди площадь.',
  'expected': ['84 см²'],
  'expectedFinalAnswer': '84 см²',
  'expectedNumericAnswer': '84',
  'expectedUnit': 'см²'},
 {'id': 'v281_g3_rect_width_less_area',
  'name': 'v281_g3_rect_width_less_area',
  'grade': 3,
  'category': 'v281_geometry',
  'text': 'Длина прямоугольника 12 см, ширина на 5 см меньше. Найди площадь.',
  'expected': ['84 см²'],
  'expectedFinalAnswer': '84 см²',
  'expectedNumericAnswer': '84',
  'expectedUnit': 'см²'},
 {'id': 'v281_g4_rect_unknown_length',
  'name': 'v281_g4_rect_unknown_length',
  'grade': 4,
  'category': 'v281_geometry',
  'text': 'Площадь прямоугольника 96 кв. см, ширина 8 см. Найди длину.',
  'expected': ['12 см'],
  'expectedFinalAnswer': '12 см',
  'expectedNumericAnswer': '12',
  'expectedUnit': 'см'},
 {'id': 'v281_g4_square_area_from_perimeter',
  'name': 'v281_g4_square_area_from_perimeter',
  'grade': 4,
  'category': 'v281_geometry',
  'text': 'Периметр квадрата равен 36 см. Найди площадь квадрата.',
  'expected': ['81 см²'],
  'expectedFinalAnswer': '81 см²',
  'expectedNumericAnswer': '81',
  'expectedUnit': 'см²'},
 {'id': 'v281_g3_square_side_perimeter',
  'name': 'v281_g3_square_side_perimeter',
  'grade': 3,
  'category': 'v281_geometry',
  'text': 'Сторона квадрата 7 см. Найди периметр квадрата.',
  'expected': ['28 см'],
  'expectedFinalAnswer': '28 см',
  'expectedNumericAnswer': '28',
  'expectedUnit': 'см'},
 {'id': 'v281_g4_composite_cut_square',
  'name': 'v281_g4_composite_cut_square',
  'grade': 4,
  'category': 'v281_geometry',
  'text': 'Из прямоугольника 10 см на 6 см вырезали квадрат 3 см на 3 см. Найди площадь оставшейся фигуры.',
  'expected': ['51 см²'],
  'expectedFinalAnswer': '51 см²',
  'expectedNumericAnswer': '51',
  'expectedUnit': 'см²'},
 {'id': 'v281_g3_grid_rectangle',
  'name': 'v281_g3_grid_rectangle',
  'grade': 3,
  'category': 'v281_geometry_grid',
  'text': 'На клетчатой бумаге прямоугольник занимает 5 клеток в длину и 4 клетки в ширину. Найди площадь.',
  'expected': ['20 клеток'],
  'expectedFinalAnswer': '20 клеток',
  'expectedNumericAnswer': '20',
  'expectedUnit': 'клеток'},
 {'id': 'v281_g4_coordinate_route',
  'name': 'v281_g4_coordinate_route',
  'grade': 4,
  'category': 'v281_geometry_route',
  'text': 'Из точки (1; 1) прошли 3 клетки вправо и 2 клетки вверх. В какой точке оказались?',
  'expected': ['(4; 3)'],
  'expectedFinalAnswer': '(4; 3)'},
 {'id': 'v281_g3_pentagon_sides_vertices',
  'name': 'v281_g3_pentagon_sides_vertices',
  'grade': 3,
  'category': 'v281_geometry_shapes',
  'text': 'У пятиугольника сколько сторон и вершин?',
  'expected': ['5 сторон и 5 вершин'],
  'expectedFinalAnswer': '5 сторон и 5 вершин',
  'expectedNumericAnswer': '5',
  'expectedUnit': 'сторон и 5 вершин'},
 {'id': 'v281_g3_table_total_visitors',
  'name': 'v281_g3_table_total_visitors',
  'grade': 3,
  'category': 'v281_data_table',
  'text': 'В таблице: понедельник — 18, вторник — 24, среда — 21. Сколько всего за три дня?',
  'expected': ['63'],
  'expectedFinalAnswer': '63',
  'expectedNumericAnswer': '63'},
 {'id': 'v281_g3_table_difference',
  'name': 'v281_g3_table_difference',
  'grade': 3,
  'category': 'v281_data_table',
  'text': 'В таблице: музей — 34, театр — 19, парк — 28. На сколько музей больше, чем театр?',
  'expected': ['15'],
  'expectedFinalAnswer': '15',
  'expectedNumericAnswer': '15'},
 {'id': 'v281_g3_diagram_times',
  'name': 'v281_g3_diagram_times',
  'grade': 3,
  'category': 'v281_data_diagram',
  'text': 'На диаграмме: кошки — 12, собаки — 6. Во сколько раз кошки больше, чем собаки?',
  'expected': ['2 раза'],
  'expectedFinalAnswer': '2 раза',
  'expectedNumericAnswer': '2',
  'expectedUnit': 'раза'},
 {'id': 'v281_g3_pictogram_books',
  'name': 'v281_g3_pictogram_books',
  'grade': 3,
  'category': 'v281_data_pictogram',
  'text': 'Пиктограмма: 1 значок = 5 книг. У класса 7 значков. Сколько книг?',
  'expected': ['35 книг'],
  'expectedFinalAnswer': '35 книг',
  'expectedNumericAnswer': '35',
  'expectedUnit': 'книг'},
 {'id': 'v281_g4_schedule_difference',
  'name': 'v281_g4_schedule_difference',
  'grade': 4,
  'category': 'v281_data_table',
  'text': 'В таблице: поезд А — 45 минут, поезд Б — 30 минут. На сколько поезд А дольше, чем поезд Б?',
  'expected': ['15'],
  'expectedFinalAnswer': '15',
  'expectedNumericAnswer': '15'},
 {'id': 'v281_g4_choose_data',
  'name': 'v281_g4_choose_data',
  'grade': 4,
  'category': 'v281_data_table',
  'text': 'В таблице: математика — 32, русский — 28, чтение — 24. Сколько всего заданий по математике и русскому?',
  'expected': ['60'],
  'expectedFinalAnswer': '60',
  'expectedNumericAnswer': '60'},
 {'id': 'v281_route_solve_text_wrapper',
  'name': 'v281_route_solve_text_wrapper',
  'grade': 3,
  'category': 'v281_route_wrappers',
  'text': 'Реши задачу: В библиотеку привезли 2 коробки по 30 книг и 4 коробки по 15 книг. Сколько книг привезли всего? Ответ запиши '
          'числом.',
  'expected': ['120 книг'],
  'expectedFinalAnswer': '120 книг',
  'expectedNumericAnswer': '120',
  'expectedUnit': 'книг'},
 {'id': 'v281_route_unicode_div_mul',
  'name': 'v281_route_unicode_div_mul',
  'grade': 3,
  'category': 'v281_route_unicode',
  'text': 'Вычисли 48 ÷ 6 + 7 · 3.',
  'expected': ['29'],
  'expectedFinalAnswer': '29',
  'expectedNumericAnswer': '29'},
 {'id': 'v281_route_cyrillic_x_linear',
  'name': 'v281_route_cyrillic_x_linear',
  'grade': 4,
  'category': 'v281_route_cyrillic_x',
  'text': '3 * х + 12 = 39. Найди х.',
  'expected': ['x = 9'],
  'expectedFinalAnswer': 'x = 9'},
 {'id': 'v281_system_newline_18_4',
  'name': 'v281_system_newline_18_4',
  'grade': 4,
  'category': 'v281_systems',
  'text': 'x + y = 18\ny - x = 4',
  'expected': ['x = 7, y = 11'],
  'expectedFinalAnswer': 'x = 7, y = 11'},
 {'id': 'v281_multi_task_semicolon_warning',
  'name': 'v281_multi_task_semicolon_warning',
  'grade': 3,
  'category': 'v281_input_guard',
  'text': '48 : 6; 7 * 8',
  'expected': ['Разделите задания'],
  'expectedFinalAnswer': 'Разделите задания',
  'shouldWarn': True,
  'expectedSource': 'guard-multi-task',
  'expectedSourceFamily': 'guard-multi-task'}]

DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v281_wave2_cases()


# --- v283 external black-box audit wave 3: edge wording + frontend/TTS polish ---
# Synthetic cases inspired by external curriculum/task-family sources; not copied verbatim.
def _v283_wave3_cases() -> list[dict[str, Any]]:
    return [{'id': 'books_154',
  'name': 'books_154',
  'grade': 3,
  'category': 'v283_unit_agreement_books',
  'text': 'В библиотеку привезли 4 коробки по 25 книг и 3 коробки по 18 книг. Сколько книг привезли всего?',
  'expected': ['154 книги'],
  'expectedFinalAnswer': '154 книги',
  'expectedNumericAnswer': '154',
  'expectedUnit': 'книги'},
 {'id': 'students_132',
  'name': 'students_132',
  'grade': 3,
  'category': 'v283_unit_agreement_students',
  'text': 'На олимпиаду пришли 4 класса по 28 учеников и еще 20 учеников. Сколько учеников пришло всего?',
  'expected': ['132 ученика'],
  'expectedFinalAnswer': '132 ученика',
  'expectedNumericAnswer': '132',
  'expectedUnit': 'ученика'},
 {'id': 'places_24',
  'name': 'places_24',
  'grade': 3,
  'category': 'v283_unit_agreement_places',
  'text': 'В зале 9 рядов по 12 мест. Заняли 84 места. Сколько мест осталось свободными?',
  'expected': ['24 места'],
  'expectedFinalAnswer': '24 места',
  'expectedNumericAnswer': '24',
  'expectedUnit': 'места'},
 {'id': 'pages_104',
  'name': 'pages_104',
  'grade': 3,
  'category': 'v283_unit_agreement_pages',
  'text': 'В книге 240 страниц. Миша прочитал 68 страниц и потом еще 68 страниц. Сколько страниц осталось?',
  'expected': ['104 страницы'],
  'expectedFinalAnswer': '104 страницы',
  'expectedNumericAnswer': '104',
  'expectedUnit': 'страницы'},
 {'id': 'balls_22',
  'name': 'balls_22',
  'grade': 2,
  'category': 'v283_unit_agreement_balls',
  'text': 'В 6 коробках по 5 мячей. 8 мячей взяли. Сколько мячей осталось?',
  'expected': ['22 мяча'],
  'expectedFinalAnswer': '22 мяча',
  'expectedNumericAnswer': '22',
  'expectedUnit': 'мяча'},
 {'id': 'pencils_34',
  'name': 'pencils_34',
  'grade': 2,
  'category': 'v283_unit_agreement_pencils',
  'text': 'В 5 наборах по 8 карандашей. 6 карандашей подарили. Сколько карандашей осталось?',
  'expected': ['34 карандаша'],
  'expectedFinalAnswer': '34 карандаша',
  'expectedNumericAnswer': '34',
  'expectedUnit': 'карандаша'},
 {'id': 'kg_64',
  'name': 'kg_64',
  'grade': 4,
  'category': 'v283_unit_agreement_kg',
  'text': 'На складе было 180 кг муки. В первый день взяли 58 кг, во второй день взяли на 6 кг больше. Сколько кг муки '
          'осталось?',
  'expected': ['58 килограммов'],
  'expectedFinalAnswer': '58 килограммов',
  'expectedNumericAnswer': '58',
  'expectedUnit': 'килограммов'},
 {'id': 'minutes_44',
  'name': 'minutes_44',
  'grade': 3,
  'category': 'v283_unit_agreement_minutes',
  'text': 'Фильм начался в 18:35 и закончился в 19:19. Сколько минут длился фильм?',
  'expected': ['44 минуты'],
  'expectedFinalAnswer': '44 минуты',
  'expectedNumericAnswer': '44',
  'expectedUnit': 'минуты'},
 {'id': 'hours_22',
  'name': 'hours_22',
  'grade': 3,
  'category': 'v283_unit_agreement_hours',
  'text': 'Сколько часов в 1320 минутах?',
  'expected': ['22 часа'],
  'expectedFinalAnswer': '22 часа',
  'expectedNumericAnswer': '22',
  'expectedUnit': 'часа'},
 {'id': 'place_value_6084',
  'name': 'place_value_6084',
  'grade': 3,
  'category': 'v283_numbers',
  'text': 'Запиши число, в котором 6 тысяч 8 десятков и 4 единицы.',
  'expected': ['6084'],
  'expectedFinalAnswer': '6084',
  'expectedNumericAnswer': '6084'},
 {'id': 'place_value_read_3409',
  'name': 'place_value_read_3409',
  'grade': 3,
  'category': 'v283_numbers',
  'text': 'В числе 3409 сколько тысяч, сотен, десятков и единиц?',
  'expected': ['3 тысячи', '4 сотни', '0 десятков', '9 единиц'],
  'expectedFinalAnswer': '3 тысячи',
  'expectedNumericAnswer': '3',
  'expectedUnit': 'тысячи'},
 {'id': 'round_to_thousands',
  'name': 'round_to_thousands',
  'grade': 4,
  'category': 'v283_numbers',
  'text': 'Округли 24 681 до тысяч.',
  'expected': ['25000'],
  'expectedFinalAnswer': '25000',
  'expectedNumericAnswer': '25000'},
 {'id': 'compare_big',
  'name': 'compare_big',
  'grade': 4,
  'category': 'v283_numbers',
  'text': 'Сравни числа 60408 и 64008.',
  'expected': ['60408 < 64008'],
  'expectedFinalAnswer': '60408 < 64008',
  'expectedNumericAnswer': '60408',
  'expectedUnit': '< 64008'},
 {'id': 'odd_1001',
  'name': 'odd_1001',
  'grade': 3,
  'category': 'v283_numbers',
  'text': 'Число 1001 четное или нечетное?',
  'expected': ['нечётное'],
  'expectedFinalAnswer': 'нечётное'},
 {'id': 'meters_to_km_m',
  'name': 'meters_to_km_m',
  'grade': 4,
  'category': 'v283_units',
  'text': 'Сколько километров и метров в 5608 м?',
  'expected': ['5 километров 608 метров'],
  'expectedFinalAnswer': '5 километров 608 метров',
  'expectedNumericAnswer': '5',
  'expectedUnit': 'километров 608 метров'},
 {'id': 'tons_kg_to_kg',
  'name': 'tons_kg_to_kg',
  'grade': 4,
  'category': 'v283_units',
  'text': 'Сколько килограммов в 3 т 450 кг?',
  'expected': ['3450 килограммов'],
  'expectedFinalAnswer': '3450 килограммов',
  'expectedNumericAnswer': '3450',
  'expectedUnit': 'килограммов'},
 {'id': 'rub_kop_sub',
  'name': 'rub_kop_sub',
  'grade': 3,
  'category': 'v283_units',
  'text': '5 рублей 10 копеек - 2 рубля 35 копеек. Сколько получится?',
  'expected': ['2 рубля 75 копеек'],
  'expectedFinalAnswer': '2 рубля 75 копеек',
  'expectedNumericAnswer': '2',
  'expectedUnit': 'рубля 75 копеек'},
 {'id': 'seconds_to_min_sec',
  'name': 'seconds_to_min_sec',
  'grade': 3,
  'category': 'v283_units',
  'text': '135 секунд - это сколько минут и секунд?',
  'expected': ['2 минуты 15 секунд'],
  'expectedFinalAnswer': '2 минуты 15 секунд',
  'expectedNumericAnswer': '2',
  'expectedUnit': 'минуты 15 секунд'},
 {'id': 'months_to_year_month',
  'name': 'months_to_year_month',
  'grade': 4,
  'category': 'v283_units',
  'text': '26 месяцев - это сколько лет и месяцев?',
  'expected': ['2 года 2 месяца'],
  'expectedFinalAnswer': '2 года 2 месяца',
  'expectedNumericAnswer': '2',
  'expectedUnit': 'года 2 месяца'},
 {'id': 'expr_multi_parentheses',
  'name': 'expr_multi_parentheses',
  'grade': 4,
  'category': 'v283_arithmetic',
  'text': 'Найди значение выражения (250 - 70) : 6 + 18 * 3.',
  'expected': ['84'],
  'expectedFinalAnswer': '84',
  'expectedNumericAnswer': '84'},
 {'id': 'expr_unicode',
  'name': 'expr_unicode',
  'grade': 3,
  'category': 'v283_arithmetic',
  'text': 'Вычисли 96 ÷ 8 + 7 · 5.',
  'expected': ['47'],
  'expectedFinalAnswer': '47',
  'expectedNumericAnswer': '47'},
 {'id': 'remainder_context',
  'name': 'remainder_context',
  'grade': 3,
  'category': 'v283_arithmetic',
  'text': '97 конфет разложили по 12 конфет в коробку. Сколько полных коробок получилось и сколько конфет осталось?',
  'expected': ['8 полных', '1 конфет'],
  'expectedFinalAnswer': '8 полных',
  'expectedNumericAnswer': '8',
  'expectedUnit': 'полных'},
 {'id': 'eq_x_minus',
  'name': 'eq_x_minus',
  'grade': 3,
  'category': 'v283_equations',
  'text': 'x - 48 = 125. Найди x.',
  'expected': ['x = 173'],
  'expectedFinalAnswer': 'x = 173',
  'expectedNumericAnswer': '173'},
 {'id': 'eq_a_minus_x',
  'name': 'eq_a_minus_x',
  'grade': 3,
  'category': 'v283_equations',
  'text': '300 - x = 76. Найди x.',
  'expected': ['x = 224'],
  'expectedFinalAnswer': 'x = 224',
  'expectedNumericAnswer': '224'},
 {'id': 'eq_mul_add',
  'name': 'eq_mul_add',
  'grade': 4,
  'category': 'v283_equations',
  'text': '5 * x + 17 = 82. Найди x.',
  'expected': ['x = 13'],
  'expectedFinalAnswer': 'x = 13',
  'expectedNumericAnswer': '13'},
 {'id': 'eq_divisor',
  'name': 'eq_divisor',
  'grade': 4,
  'category': 'v283_equations',
  'text': '144 : x = 12. Найди x.',
  'expected': ['x = 12'],
  'expectedFinalAnswer': 'x = 12',
  'expectedNumericAnswer': '12'},
 {'id': 'letter_expr_two_vars',
  'name': 'letter_expr_two_vars',
  'grade': 4,
  'category': 'v283_expressions',
  'text': 'Найди значение выражения a * b - 18, если a = 9, b = 7.',
  'expected': ['45'],
  'expectedFinalAnswer': '45',
  'expectedNumericAnswer': '45'},
 {'id': 'compare_expr_greater',
  'name': 'compare_expr_greater',
  'grade': 3,
  'category': 'v283_expressions',
  'text': 'Сравни 96 : 8 + 12 и 4 * 5.',
  'expected': ['больше'],
  'expectedFinalAnswer': 'больше'},
 {'id': 'two_purchases_items',
  'name': 'two_purchases_items',
  'grade': 4,
  'category': 'v283_text_composite',
  'text': 'В магазин привезли 6 ящиков по 24 яблока и 5 ящиков по 18 груш. Сколько фруктов привезли всего?',
  'expected': ['234 фрукта'],
  'expectedFinalAnswer': '234 фрукта',
  'expectedNumericAnswer': '234',
  'expectedUnit': 'фрукта'},
 {'id': 'three_actions_left',
  'name': 'three_actions_left',
  'grade': 4,
  'category': 'v283_text_composite',
  'text': 'В школе было 420 тетрадей. В 3 класса раздали по 45 тетрадей, а в кружок отдали еще 28 тетрадей. Сколько '
          'тетрадей осталось?',
  'expected': ['257 тетрадей'],
  'expectedFinalAnswer': '257 тетрадей',
  'expectedNumericAnswer': '257',
  'expectedUnit': 'тетрадей'},
 {'id': 'extra_data_money',
  'name': 'extra_data_money',
  'grade': 4,
  'category': 'v283_text_composite',
  'text': 'В книге 180 страниц. В понедельник прочитали 45 страниц, во вторник на 12 страниц больше. Закладка стоит 30 '
          'рублей. Сколько страниц осталось прочитать?',
  'expected': ['78 страниц'],
  'expectedFinalAnswer': '78 страниц',
  'expectedNumericAnswer': '78',
  'expectedUnit': 'страниц'},
 {'id': 'reverse_times_total',
  'name': 'reverse_times_total',
  'grade': 3,
  'category': 'v283_text_composite',
  'text': 'У Вити 18 марок. Это в 3 раза меньше, чем у Саши. Сколько марок у них вместе?',
  'expected': ['72 марки'],
  'expectedFinalAnswer': '72 марки',
  'expectedNumericAnswer': '72',
  'expectedUnit': 'марки'},
 {'id': 'difference_times_more',
  'name': 'difference_times_more',
  'grade': 3,
  'category': 'v283_text_composite',
  'text': 'У первого класса 24 рисунка, у второго в 2 раза больше. На сколько рисунков у второго класса больше?',
  'expected': ['24 рисунка'],
  'expectedFinalAnswer': '24 рисунка',
  'expectedNumericAnswer': '24',
  'expectedUnit': 'рисунка'},
 {'id': 'whole_by_part',
  'name': 'whole_by_part',
  'grade': 4,
  'category': 'v283_text_composite',
  'text': 'В коробке 72 детали. 1/4 деталей использовали. Сколько деталей осталось?',
  'expected': ['54 детали'],
  'expectedFinalAnswer': '54 детали',
  'expectedNumericAnswer': '54',
  'expectedUnit': 'детали'},
 {'id': 'part_then_more',
  'name': 'part_then_more',
  'grade': 3,
  'category': 'v283_text_composite',
  'text': 'В саду 36 яблонь, а груш на 12 меньше. Сколько яблонь и груш вместе?',
  'expected': ['60 деревьев'],
  'expectedFinalAnswer': '60 деревьев',
  'expectedNumericAnswer': '60',
  'expectedUnit': 'деревьев'},
 {'id': 'equal_groups_divide_left',
  'name': 'equal_groups_divide_left',
  'grade': 3,
  'category': 'v283_text_composite',
  'text': '96 карандашей разложили поровну в 8 коробок. Из одной коробки взяли 5 карандашей. Сколько карандашей '
          'осталось в этой коробке?',
  'expected': ['7 карандашей'],
  'expectedFinalAnswer': '7 карандашей',
  'expectedNumericAnswer': '7',
  'expectedUnit': 'карандашей'},
 {'id': 'price_total_two_types',
  'name': 'price_total_two_types',
  'grade': 4,
  'category': 'v283_money',
  'text': 'Купили 4 альбома по 65 рублей и 3 кисточки по 38 рублей. Сколько рублей заплатили?',
  'expected': ['374 рубля'],
  'expectedFinalAnswer': '374 рубля',
  'expectedNumericAnswer': '374',
  'expectedUnit': 'рубля'},
 {'id': 'budget_two_types_change',
  'name': 'budget_two_types_change',
  'grade': 4,
  'category': 'v283_money',
  'text': 'У Ани было 1000 рублей. Она купила 3 книги по 180 рублей и пенал за 235 рублей. Сколько рублей осталось?',
  'expected': ['225 рублей'],
  'expectedFinalAnswer': '225 рублей',
  'expectedNumericAnswer': '225',
  'expectedUnit': 'рублей'},
 {'id': 'unit_price_items',
  'name': 'unit_price_items',
  'grade': 4,
  'category': 'v283_money',
  'text': 'За 8 одинаковых ручек заплатили 136 рублей. Сколько рублей стоят 3 такие ручки?',
  'expected': ['51 рубль'],
  'expectedFinalAnswer': '51 рубль',
  'expectedNumericAnswer': '51',
  'expectedUnit': 'рубль'},
 {'id': 'quantity_with_remainder',
  'name': 'quantity_with_remainder',
  'grade': 3,
  'category': 'v283_money',
  'text': 'Одна открытка стоит 14 рублей. Сколько открыток можно купить на 100 рублей и сколько рублей останется?',
  'expected': ['7 открыток', '2 рубля'],
  'expectedFinalAnswer': '7 открыток',
  'expectedNumericAnswer': '7',
  'expectedUnit': 'открыток'},
 {'id': 'kop_borrow_sub',
  'name': 'kop_borrow_sub',
  'grade': 4,
  'category': 'v283_money',
  'text': '7 рублей 05 копеек - 3 рубля 40 копеек. Сколько получится?',
  'expected': ['3 рубля 65 копеек'],
  'expectedFinalAnswer': '3 рубля 65 копеек',
  'expectedNumericAnswer': '3',
  'expectedUnit': 'рубля 65 копеек'},
 {'id': 'kopecks_to_rub_kop',
  'name': 'kopecks_to_rub_kop',
  'grade': 3,
  'category': 'v283_money',
  'text': '875 копеек - это сколько рублей и копеек?',
  'expected': ['8 рублей 75 копеек'],
  'expectedFinalAnswer': '8 рублей 75 копеек',
  'expectedNumericAnswer': '8',
  'expectedUnit': 'рублей 75 копеек'},
 {'id': 'time_range_direct',
  'name': 'time_range_direct',
  'grade': 3,
  'category': 'v283_time',
  'text': 'Сколько времени прошло с 13:25 до 14:10?',
  'expected': ['45 минут'],
  'expectedFinalAnswer': '45 минут',
  'expectedNumericAnswer': '45',
  'expectedUnit': 'минут'},
 {'id': 'cross_midnight_short',
  'name': 'cross_midnight_short',
  'grade': 4,
  'category': 'v283_time',
  'text': 'Сколько времени прошло с 23:50 до 00:25?',
  'expected': ['35 минут'],
  'expectedFinalAnswer': '35 минут',
  'expectedNumericAnswer': '35',
  'expectedUnit': 'минут'},
 {'id': 'start_by_end_duration',
  'name': 'start_by_end_duration',
  'grade': 4,
  'category': 'v283_time',
  'text': 'Спектакль закончился в 18:20 и длился 1 ч 45 мин. Во сколько он начался?',
  'expected': ['16:35'],
  'expectedFinalAnswer': '16:35',
  'expectedNumericAnswer': '16:35'},
 {'id': 'schedule_wait',
  'name': 'schedule_wait',
  'grade': 3,
  'category': 'v283_time',
  'text': 'Автобус пришел в 8:12, следующий пришел в 8:37. Сколько минут ждали следующий автобус?',
  'expected': ['25 минут'],
  'expectedFinalAnswer': '25 минут',
  'expectedNumericAnswer': '25',
  'expectedUnit': 'минут'},
 {'id': 'days_hours_to_hours',
  'name': 'days_hours_to_hours',
  'grade': 4,
  'category': 'v283_time',
  'text': 'Сколько часов в 2 сутках 5 часах?',
  'expected': ['53 часа'],
  'expectedFinalAnswer': '53 часа',
  'expectedNumericAnswer': '53',
  'expectedUnit': 'часа'},
 {'id': 'date_interval_simple',
  'name': 'date_interval_simple',
  'grade': 3,
  'category': 'v283_time',
  'text': 'Каникулы длились 2 недели и 3 дня. Сколько это дней?',
  'expected': ['17 дней'],
  'expectedFinalAnswer': '17 дней',
  'expectedNumericAnswer': '17',
  'expectedUnit': 'дней'},
 {'id': 'opposite_directions',
  'name': 'opposite_directions',
  'grade': 4,
  'category': 'v283_motion',
  'text': 'От станции одновременно в противоположных направлениях вышли два поезда. Скорость первого 60 км/ч, второго '
          '75 км/ч. Какое расстояние будет между ними через 4 часа?',
  'expected': ['540 километров'],
  'expectedFinalAnswer': '540 километров',
  'expectedNumericAnswer': '540',
  'expectedUnit': 'километров'},
 {'id': 'catch_up',
  'name': 'catch_up',
  'grade': 4,
  'category': 'v283_motion',
  'text': 'Из одного города одновременно выехали велосипедист со скоростью 12 км/ч и мотоциклист со скоростью 36 км/ч. '
          'На сколько километров мотоциклист будет впереди через 3 часа?',
  'expected': ['72 километра'],
  'expectedFinalAnswer': '72 километра',
  'expectedNumericAnswer': '72',
  'expectedUnit': 'километра'},
 {'id': 'downstream_simple',
  'name': 'downstream_simple',
  'grade': 4,
  'category': 'v283_motion',
  'text': 'Катер прошел 84 км за 3 часа. Найди скорость катера.',
  'expected': ['28 км/ч'],
  'expectedFinalAnswer': '28 км/ч',
  'expectedNumericAnswer': '28',
  'expectedUnit': 'км/ч'},
 {'id': 'remaining_after_two_legs',
  'name': 'remaining_after_two_legs',
  'grade': 3,
  'category': 'v283_motion',
  'text': 'Турист прошел 5 км утром и 7 км днем. Весь маршрут 20 км. Сколько километров осталось пройти?',
  'expected': ['8 километров'],
  'expectedFinalAnswer': '8 километров',
  'expectedNumericAnswer': '8',
  'expectedUnit': 'километров'},
 {'id': 'time_minutes_speed',
  'name': 'time_minutes_speed',
  'grade': 4,
  'category': 'v283_motion',
  'text': 'Самокат ехал 30 минут со скоростью 12 км/ч. Сколько километров он проехал?',
  'expected': ['6 километров'],
  'expectedFinalAnswer': '6 километров',
  'expectedNumericAnswer': '6',
  'expectedUnit': 'километров'},
 {'id': 'towards_not_meet',
  'name': 'towards_not_meet',
  'grade': 4,
  'category': 'v283_motion',
  'text': 'Расстояние между селами 90 км. Два велосипедиста выехали навстречу: 14 км/ч и 16 км/ч. Сколько километров '
          'останется между ними через 2 часа?',
  'expected': ['30 километров'],
  'expectedFinalAnswer': '30 километров',
  'expectedNumericAnswer': '30',
  'expectedUnit': 'километров'},
 {'id': 'distance_by_speed_time_min',
  'name': 'distance_by_speed_time_min',
  'grade': 4,
  'category': 'v283_motion',
  'text': 'Поезд ехал 2 ч 30 мин со скоростью 80 км/ч. Сколько километров он проехал?',
  'expected': ['200 километров'],
  'expectedFinalAnswer': '200 километров',
  'expectedNumericAnswer': '200',
  'expectedUnit': 'километров'},
 {'id': 'workers_units',
  'name': 'workers_units',
  'grade': 4,
  'category': 'v283_joint_work',
  'text': 'Один рабочий делает 96 деталей за 8 часов, второй рабочий делает столько же за 12 часов. Сколько деталей '
          'они сделают вместе за 2 часа?',
  'expected': ['40 деталей'],
  'expectedFinalAnswer': '40 деталей',
  'expectedNumericAnswer': '40',
  'expectedUnit': 'деталей'},
 {'id': 'two_pipes_liters',
  'name': 'two_pipes_liters',
  'grade': 4,
  'category': 'v283_joint_work',
  'text': 'Один насос перекачивает 300 л за 10 минут, другой насос 300 л за 15 минут. Сколько литров они перекачают '
          'вместе за 3 минуты?',
  'expected': ['150 литров'],
  'expectedFinalAnswer': '150 литров',
  'expectedNumericAnswer': '150',
  'expectedUnit': 'литров'},
 {'id': 'fraction_work_done',
  'name': 'fraction_work_done',
  'grade': 4,
  'category': 'v283_joint_work',
  'text': 'Первая бригада делает 1/6 работы за день, вторая бригада делает 1/3 работы за день. Какую часть работы они '
          'выполнят вместе за день?',
  'expected': ['1/2'],
  'expectedFinalAnswer': '1/2',
  'expectedNumericAnswer': '1'},
 {'id': 'time_with_rates',
  'name': 'time_with_rates',
  'grade': 4,
  'category': 'v283_joint_work',
  'text': 'Первый станок делает 20 деталей в час, второй станок 30 деталей в час. За сколько часов они сделают 200 '
          'деталей?',
  'expected': ['4 часа'],
  'expectedFinalAnswer': '4 часа',
  'expectedNumericAnswer': '4',
  'expectedUnit': 'часа'},
 {'id': 'fraction_of_money',
  'name': 'fraction_of_money',
  'grade': 4,
  'category': 'v283_fractions',
  'text': 'Найди 3/5 от 250 рублей.',
  'expected': ['150 рублей'],
  'expectedFinalAnswer': '150 рублей',
  'expectedNumericAnswer': '150',
  'expectedUnit': 'рублей'},
 {'id': 'fraction_of_time',
  'name': 'fraction_of_time',
  'grade': 4,
  'category': 'v283_fractions',
  'text': 'Найди 2/3 часа в минутах.',
  'expected': ['40 минут'],
  'expectedFinalAnswer': '40 минут',
  'expectedNumericAnswer': '40',
  'expectedUnit': 'минут'},
 {'id': 'whole_by_fraction',
  'name': 'whole_by_fraction',
  'grade': 4,
  'category': 'v283_fractions',
  'text': '3/4 числа равны 60. Найди число.',
  'expected': ['80'],
  'expectedFinalAnswer': '80',
  'expectedNumericAnswer': '80'},
 {'id': 'compare_same_den',
  'name': 'compare_same_den',
  'grade': 4,
  'category': 'v283_fractions',
  'text': 'Сравни дроби 5/8 и 3/8.',
  'expected': ['5/8 больше'],
  'expectedFinalAnswer': '5/8 больше',
  'expectedNumericAnswer': '5'},
 {'id': 'left_after_fraction',
  'name': 'left_after_fraction',
  'grade': 4,
  'category': 'v283_fractions',
  'text': 'От ленты длиной 48 см отрезали 1/3. Сколько сантиметров ленты осталось?',
  'expected': ['32 сантиметра'],
  'expectedFinalAnswer': '32 сантиметра',
  'expectedNumericAnswer': '32',
  'expectedUnit': 'сантиметра'},
 {'id': 'fraction_unit_kg',
  'name': 'fraction_unit_kg',
  'grade': 4,
  'category': 'v283_fractions',
  'text': 'Найди 1/4 от 2 кг.',
  'expected': ['500 граммов'],
  'expectedFinalAnswer': '500 граммов',
  'expectedNumericAnswer': '500',
  'expectedUnit': 'граммов'},
 {'id': 'perimeter_unknown_width',
  'name': 'perimeter_unknown_width',
  'grade': 4,
  'category': 'v283_geometry',
  'text': 'Периметр прямоугольника 54 см, длина 15 см. Найди ширину.',
  'expected': ['12 см'],
  'expectedFinalAnswer': '12 см',
  'expectedNumericAnswer': '12',
  'expectedUnit': 'см'},
 {'id': 'area_two_rectangles',
  'name': 'area_two_rectangles',
  'grade': 4,
  'category': 'v283_geometry',
  'text': 'Фигура состоит из прямоугольника 8 см на 5 см и прямоугольника 6 см на 4 см. Найди площадь фигуры.',
  'expected': ['64 см²'],
  'expectedFinalAnswer': '64 см²',
  'expectedNumericAnswer': '64',
  'expectedUnit': 'см²'},
 {'id': 'border_length_square',
  'name': 'border_length_square',
  'grade': 3,
  'category': 'v283_geometry',
  'text': 'Сторона квадрата 12 см. Найди площадь и периметр квадрата.',
  'expected': ['144 см²', '48 см'],
  'expectedFinalAnswer': '144 см²',
  'expectedNumericAnswer': '144',
  'expectedUnit': 'см²'},
 {'id': 'grid_l_shape',
  'name': 'grid_l_shape',
  'grade': 3,
  'category': 'v283_geometry',
  'text': 'Фигура на клетчатой бумаге состоит из 18 клеток, из нее убрали 5 клеток. Найди площадь оставшейся фигуры.',
  'expected': ['13 клеток'],
  'expectedFinalAnswer': '13 клеток',
  'expectedNumericAnswer': '13',
  'expectedUnit': 'клеток'},
 {'id': 'route_left_down',
  'name': 'route_left_down',
  'grade': 4,
  'category': 'v283_geometry',
  'text': 'Из точки (6; 5) прошли 2 клетки влево и 4 клетки вниз. В какой точке оказались?',
  'expected': ['(4; 1)'],
  'expectedFinalAnswer': '(4; 1)',
  'expectedNumericAnswer': '4'},
 {'id': 'symmetry_square',
  'name': 'symmetry_square',
  'grade': 4,
  'category': 'v283_geometry',
  'text': 'Сколько осей симметрии у квадрата?',
  'expected': ['4 оси'],
  'expectedFinalAnswer': '4 оси',
  'expectedNumericAnswer': '4',
  'expectedUnit': 'оси'},
 {'id': 'triangle_vertices',
  'name': 'triangle_vertices',
  'grade': 2,
  'category': 'v283_geometry',
  'text': 'У треугольника сколько сторон и вершин?',
  'expected': ['3 стороны и 3 вершины'],
  'expectedFinalAnswer': '3 стороны и 3 вершины',
  'expectedNumericAnswer': '3',
  'expectedUnit': 'стороны и 3 вершины'},
 {'id': 'table_total_two',
  'name': 'table_total_two',
  'grade': 3,
  'category': 'v283_data',
  'text': 'В таблице: хлеб - 28, молоко - 36, сыр - 19. Сколько всего хлеба и молока?',
  'expected': ['64'],
  'expectedFinalAnswer': '64',
  'expectedNumericAnswer': '64'},
 {'id': 'table_less',
  'name': 'table_less',
  'grade': 3,
  'category': 'v283_data',
  'text': 'В таблице: синие - 45, красные - 32. На сколько красных меньше, чем синих?',
  'expected': ['13'],
  'expectedFinalAnswer': '13',
  'expectedNumericAnswer': '13'},
 {'id': 'bar_chart_total',
  'name': 'bar_chart_total',
  'grade': 3,
  'category': 'v283_data',
  'text': 'На диаграмме: понедельник - 18, вторник - 22, среда - 20. Сколько всего за эти дни?',
  'expected': ['60'],
  'expectedFinalAnswer': '60',
  'expectedNumericAnswer': '60'},
 {'id': 'pictogram_left',
  'name': 'pictogram_left',
  'grade': 3,
  'category': 'v283_data',
  'text': 'Пиктограмма: 1 значок = 4 ученика. У команды 9 значков. Сколько учеников в команде?',
  'expected': ['36 учеников'],
  'expectedFinalAnswer': '36 учеников',
  'expectedNumericAnswer': '36',
  'expectedUnit': 'учеников'},
 {'id': 'schedule_duration',
  'name': 'schedule_duration',
  'grade': 3,
  'category': 'v283_data',
  'text': 'В расписании: кружок начался в 16:15, закончился в 17:05. Сколько минут длился кружок?',
  'expected': ['50 минут'],
  'expectedFinalAnswer': '50 минут',
  'expectedNumericAnswer': '50',
  'expectedUnit': 'минут'},
 {'id': 'multi_task_numbers_semicolon',
  'name': 'multi_task_numbers_semicolon',
  'grade': 4,
  'category': 'v283_input_guard',
  'text': '125 + 75; 360 : 9',
  'expected': ['Разделите задания'],
  'expectedFinalAnswer': 'Разделите задания',
  'expectedSource': 'guard-multi-task',
  'expectedSourceFamily': 'guard-multi-task'},
 {'id': 'multi_task_words_newline',
  'name': 'multi_task_words_newline',
  'grade': 4,
  'category': 'v283_input_guard',
  'text': 'Найди 3/4 от 80\nВычисли 25 * 4',
  'expected': ['Разделите задания'],
  'expectedFinalAnswer': 'Разделите задания',
  'expectedSource': 'guard-multi-task',
  'expectedSourceFamily': 'guard-multi-task'},
 {'id': 'system_true_enter',
  'name': 'system_true_enter',
  'grade': 4,
  'category': 'v283_input_guard',
  'text': 'x + y = 24\ny - x = 6',
  'expected': ['x = 9, y = 15'],
  'expectedFinalAnswer': 'x = 9, y = 15',
  'expectedSource': 'local:live-system-solver',
  'expectedSourceFamily': 'local:live-system-solver',
  'expectedNumericAnswer': '9'},
 {'id': 'cyrillic_x_equation',
  'name': 'cyrillic_x_equation',
  'grade': 4,
  'category': 'v283_input_route',
  'text': '4 * х - 15 = 45. Найди х.',
  'expected': ['x = 15'],
  'expectedFinalAnswer': 'x = 15',
  'expectedNumericAnswer': '15'},
 {'id': 'ocr_noise_shop',
  'name': 'ocr_noise_shop',
  'grade': 2,
  'category': 'v283_input_route',
  'text': 'В магаз1не было 45 ручек, продали 18 ручек. Сколько ручек осталось?',
  'expected': ['27 ручек'],
  'expectedFinalAnswer': '27 ручек',
  'expectedNumericAnswer': '27',
  'expectedUnit': 'ручек'},
 {'id': 'wrapper_answer_number',
  'name': 'wrapper_answer_number',
  'grade': 2,
  'category': 'v283_input_route',
  'text': 'Ответ запиши числом: На 7 полках по 9 книг. Сколько книг всего?',
  'expected': ['63 книги'],
  'expectedFinalAnswer': '63 книги',
  'expectedNumericAnswer': '63',
  'expectedUnit': 'книги'}]

DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v283_wave3_cases()


# --- v284 external black-box audit wave 4: hardening edge cases ---
# Synthetic variants based on external topic maps. They are checked through
# generate_explanation_response(), the same path used by HTTP API requests.

def _v284_wave4_cases() -> list[dict[str, Any]]:
    return [{'id': 'write_629', 'name': 'write_629', 'grade': 3, 'category': 'v284_numbers', 'text': 'Запиши число, в котором 6 сотен 2 десятка и 9 единиц.', 'expected': ['629'], 'expectedFinalAnswer': '629', 'expectedNumericAnswer': '629', 'expectedSourceFamily': 'local:live'}, {'id': 'read_805', 'name': 'read_805', 'grade': 3, 'category': 'v284_numbers', 'text': 'В числе 805 сколько сотен, десятков и единиц?', 'expected': ['8 сотен', '0 десятков', '5 единиц'], 'expectedFinalAnswer': '8 сотен', 'expectedNumericAnswer': '8', 'expectedSourceFamily': 'local:live'}, {'id': 'write_316204', 'name': 'write_316204', 'grade': 4, 'category': 'v284_numbers', 'text': 'Запиши число, в котором 3 сотни тысяч 1 десяток тысяч 6 тысяч 2 сотни 0 десятков и 4 единицы.', 'expected': ['316204'], 'expectedFinalAnswer': '316204', 'expectedNumericAnswer': '316204', 'expectedSourceFamily': 'local:live'}, {'id': 'compare_7305_7350', 'name': 'compare_7305_7350', 'grade': 3, 'category': 'v284_numbers', 'text': 'Сравни числа 7305 и 7350.', 'expected': ['7305 < 7350'], 'expectedFinalAnswer': '7305 < 7350', 'expectedNumericAnswer': '7305', 'expectedSourceFamily': 'local:live'}, {'id': 'larger_12009_11999', 'name': 'larger_12009_11999', 'grade': 4, 'category': 'v284_numbers', 'text': 'Какое число больше: 12009 или 11999?', 'expected': ['12009'], 'expectedFinalAnswer': '12009', 'expectedNumericAnswer': '12009', 'expectedSourceFamily': 'local:live'}, {'id': 'round_452_tens', 'name': 'round_452_tens', 'grade': 3, 'category': 'v284_numbers', 'text': 'Округли 452 до десятков.', 'expected': ['450'], 'expectedFinalAnswer': '450', 'expectedNumericAnswer': '450', 'expectedSourceFamily': 'local:live'}, {'id': 'round_458_hundreds', 'name': 'round_458_hundreds', 'grade': 3, 'category': 'v284_numbers', 'text': 'Округли 458 до сотен.', 'expected': ['500'], 'expectedFinalAnswer': '500', 'expectedNumericAnswer': '500', 'expectedSourceFamily': 'local:live'}, {'id': 'round_38649_thousands', 'name': 'round_38649_thousands', 'grade': 4, 'category': 'v284_numbers', 'text': 'Округли 38 649 до тысяч.', 'expected': ['39000'], 'expectedFinalAnswer': '39000', 'expectedNumericAnswer': '39000', 'expectedSourceFamily': 'local:live'}, {'id': 'odd_7021', 'name': 'odd_7021', 'grade': 3, 'category': 'v284_numbers', 'text': 'Число 7021 четное или нечетное?', 'expected': ['нечётное'], 'expectedFinalAnswer': 'нечётное', 'expectedNumericAnswer': None, 'expectedSourceFamily': 'local:live'}, {'id': 'even_6408', 'name': 'even_6408', 'grade': 3, 'category': 'v284_numbers', 'text': 'Число 6408 четное или нечетное?', 'expected': ['чётное'], 'expectedFinalAnswer': 'чётное', 'expectedNumericAnswer': None, 'expectedSourceFamily': 'local:live'}, {'id': 'km_m_to_m', 'name': 'km_m_to_m', 'grade': 3, 'category': 'v284_units', 'text': 'Сколько метров в 8 км 75 м?', 'expected': ['8075 метров'], 'expectedFinalAnswer': '8075 метров', 'expectedNumericAnswer': '8075', 'expectedSourceFamily': 'local:live'}, {'id': 'm_to_km_m', 'name': 'm_to_km_m', 'grade': 4, 'category': 'v284_units', 'text': 'Сколько километров и метров в 6420 м?', 'expected': ['6 километров 420 метров'], 'expectedFinalAnswer': '6 километров 420 метров', 'expectedNumericAnswer': '6', 'expectedSourceFamily': 'local:live'}, {'id': 'kg_g_to_g', 'name': 'kg_g_to_g', 'grade': 3, 'category': 'v284_units', 'text': 'Сколько граммов в 6 кг 45 г?', 'expected': ['6045 граммов'], 'expectedFinalAnswer': '6045 граммов', 'expectedNumericAnswer': '6045', 'expectedSourceFamily': 'local:live'}, {'id': 'g_to_kg_g', 'name': 'g_to_kg_g', 'grade': 3, 'category': 'v284_units', 'text': 'Сколько килограммов и граммов в 5075 г?', 'expected': ['5 килограммов 75 граммов'], 'expectedFinalAnswer': '5 килограммов 75 граммов', 'expectedNumericAnswer': '5', 'expectedSourceFamily': 'local:live'}, {'id': 'min_sec_to_sec', 'name': 'min_sec_to_sec', 'grade': 3, 'category': 'v284_units', 'text': 'Сколько секунд в 7 мин 8 с?', 'expected': ['428 секунд'], 'expectedFinalAnswer': '428 секунд', 'expectedNumericAnswer': '428', 'expectedSourceFamily': 'local:live'}, {'id': 'sec_to_min_sec', 'name': 'sec_to_min_sec', 'grade': 3, 'category': 'v284_units', 'text': '245 секунд - это сколько минут и секунд?', 'expected': ['4 минуты 5 секунд'], 'expectedFinalAnswer': '4 минуты 5 секунд', 'expectedNumericAnswer': '4', 'expectedSourceFamily': 'local:live'}, {'id': 'rub_kop_to_kop', 'name': 'rub_kop_to_kop', 'grade': 2, 'category': 'v284_units', 'text': 'Сколько копеек в 9 рублях 8 копейках?', 'expected': ['908 копеек'], 'expectedFinalAnswer': '908 копеек', 'expectedNumericAnswer': '908', 'expectedSourceFamily': 'local:live'}, {'id': 'kop_to_rub_kop', 'name': 'kop_to_rub_kop', 'grade': 3, 'category': 'v284_units', 'text': '1234 копеек - это сколько рублей и копеек?', 'expected': ['12 рублей 34 копейки'], 'expectedFinalAnswer': '12 рублей 34 копейки', 'expectedNumericAnswer': '12', 'expectedSourceFamily': 'local:live'}, {'id': 'add_4digit', 'name': 'add_4digit', 'grade': 4, 'category': 'v284_arithmetic', 'text': 'Вычисли 2345 + 678.', 'expected': ['3023'], 'expectedFinalAnswer': '3023', 'expectedNumericAnswer': '3023', 'expectedSourceFamily': 'local:live'}, {'id': 'sub_4digit', 'name': 'sub_4digit', 'grade': 4, 'category': 'v284_arithmetic', 'text': 'Вычисли 5000 - 2376.', 'expected': ['2624'], 'expectedFinalAnswer': '2624', 'expectedNumericAnswer': '2624', 'expectedSourceFamily': 'local:live'}, {'id': 'mul_3digit', 'name': 'mul_3digit', 'grade': 4, 'category': 'v284_arithmetic', 'text': 'Вычисли 128 * 7.', 'expected': ['896'], 'expectedFinalAnswer': '896', 'expectedNumericAnswer': '896', 'expectedSourceFamily': 'local:live'}, {'id': 'div_4digit', 'name': 'div_4digit', 'grade': 4, 'category': 'v284_arithmetic', 'text': 'Вычисли 1350 : 6.', 'expected': ['225'], 'expectedFinalAnswer': '225', 'expectedNumericAnswer': '225', 'expectedSourceFamily': 'local:live'}, {'id': 'order_complex', 'name': 'order_complex', 'grade': 4, 'category': 'v284_arithmetic', 'text': 'Найди значение выражения 360 : (12 + 6) + 7 * 8.', 'expected': ['76'], 'expectedFinalAnswer': '76', 'expectedNumericAnswer': '76', 'expectedSourceFamily': 'local:live'}, {'id': 'unicode_expr', 'name': 'unicode_expr', 'grade': 3, 'category': 'v284_arithmetic', 'text': 'Вычисли 84 ÷ 7 + 6 · 9.', 'expected': ['66'], 'expectedFinalAnswer': '66', 'expectedNumericAnswer': '66', 'expectedSourceFamily': 'local:live'}, {'id': 'remainder', 'name': 'remainder', 'grade': 3, 'category': 'v284_arithmetic', 'text': 'Выполни деление с остатком: 125 : 9.', 'expected': ['13', 'остаток 8'], 'expectedFinalAnswer': '13', 'expectedNumericAnswer': '13', 'expectedSourceFamily': 'local:live'}, {'id': 'x_plus', 'name': 'x_plus', 'grade': 3, 'category': 'v284_equations', 'text': 'x + 28 = 73. Найди x.', 'expected': ['x = 45'], 'expectedFinalAnswer': 'x = 45', 'expectedNumericAnswer': '45', 'expectedSourceFamily': 'local:live'}, {'id': 'x_minus', 'name': 'x_minus', 'grade': 3, 'category': 'v284_equations', 'text': 'x - 39 = 84. Найди x.', 'expected': ['x = 123'], 'expectedFinalAnswer': 'x = 123', 'expectedNumericAnswer': '123', 'expectedSourceFamily': 'local:live'}, {'id': 'a_minus_x', 'name': 'a_minus_x', 'grade': 3, 'category': 'v284_equations', 'text': '260 - x = 95. Найди x.', 'expected': ['x = 165'], 'expectedFinalAnswer': 'x = 165', 'expectedNumericAnswer': '165', 'expectedSourceFamily': 'local:live'}, {'id': 'mul_x_plus', 'name': 'mul_x_plus', 'grade': 4, 'category': 'v284_equations', 'text': '6 * x + 14 = 68. Найди x.', 'expected': ['x = 9'], 'expectedFinalAnswer': 'x = 9', 'expectedNumericAnswer': '9', 'expectedSourceFamily': 'local:live'}, {'id': 'divisor', 'name': 'divisor', 'grade': 4, 'category': 'v284_equations', 'text': '168 : x = 14. Найди x.', 'expected': ['x = 12'], 'expectedFinalAnswer': 'x = 12', 'expectedNumericAnswer': '12', 'expectedSourceFamily': 'local:live'}, {'id': 'letter_expr', 'name': 'letter_expr', 'grade': 4, 'category': 'v284_equations', 'text': 'Найди значение выражения a * b - 27, если a = 8, b = 9.', 'expected': ['45'], 'expectedFinalAnswer': '45', 'expectedNumericAnswer': '45', 'expectedSourceFamily': 'local:live'}, {'id': 'two_group_total_books', 'name': 'two_group_total_books', 'grade': 3, 'category': 'v284_text', 'text': 'В библиотеку привезли 5 коробок по 18 книг и 4 коробки по 22 книги. Сколько книг привезли всего?', 'expected': ['178 книг'], 'expectedFinalAnswer': '178 книг', 'expectedNumericAnswer': '178', 'expectedSourceFamily': 'local:live'}, {'id': 'distributed_left', 'name': 'distributed_left', 'grade': 4, 'category': 'v284_text', 'text': 'На складе было 520 тетрадей. В 6 классов раздали по 48 тетрадей. Сколько тетрадей осталось?', 'expected': ['232 тетради'], 'expectedFinalAnswer': '232 тетради', 'expectedNumericAnswer': '232', 'expectedSourceFamily': 'local:live'}, {'id': 'two_day_left', 'name': 'two_day_left', 'grade': 4, 'category': 'v284_text', 'text': 'В магазине было 300 кг сахара. В первый день продали 96 кг, во второй день продали на 24 кг больше. Сколько кг осталось?', 'expected': ['84 килограмма'], 'expectedFinalAnswer': '84 килограмма', 'expectedNumericAnswer': '84', 'expectedSourceFamily': 'local:live'}, {'id': 'extra_data_pages', 'name': 'extra_data_pages', 'grade': 3, 'category': 'v284_text', 'text': 'В книге 150 страниц. В понедельник прочитали 47 страниц, во вторник 38 страниц. Обложка синяя. Сколько страниц осталось прочитать?', 'expected': ['65 страниц'], 'expectedFinalAnswer': '65 страниц', 'expectedNumericAnswer': '65', 'expectedSourceFamily': 'local:live'}, {'id': 'reverse_times_less', 'name': 'reverse_times_less', 'grade': 3, 'category': 'v284_text', 'text': 'У Кати 28 открыток. Это в 4 раза меньше, чем у Вики. Сколько открыток у Вики?', 'expected': ['112 открыток'], 'expectedFinalAnswer': '112 открыток', 'expectedNumericAnswer': '112', 'expectedSourceFamily': 'local:live'}, {'id': 'reverse_times_more', 'name': 'reverse_times_more', 'grade': 3, 'category': 'v284_text', 'text': 'У Веры 81 марка. Это в 3 раза больше, чем у Димы. Сколько марок у Димы?', 'expected': ['27 марок'], 'expectedFinalAnswer': '27 марок', 'expectedNumericAnswer': '27', 'expectedSourceFamily': 'local:live'}, {'id': 'comparison_times_less', 'name': 'comparison_times_less', 'grade': 3, 'category': 'v284_text', 'text': 'В первой коробке 90 деталей, во второй в 3 раза меньше. На сколько деталей в первой коробке больше?', 'expected': ['60 деталей'], 'expectedFinalAnswer': '60 деталей', 'expectedNumericAnswer': '60', 'expectedSourceFamily': 'local:live'}, {'id': 'part_of_box_left', 'name': 'part_of_box_left', 'grade': 4, 'category': 'v284_text', 'text': 'В коробке 96 деталей. 1/3 деталей использовали. Сколько деталей осталось?', 'expected': ['64 детали'], 'expectedFinalAnswer': '64 детали', 'expectedNumericAnswer': '64', 'expectedSourceFamily': 'local:live'}, {'id': 'total_by_difference', 'name': 'total_by_difference', 'grade': 2, 'category': 'v284_text', 'text': 'У Миши 14 машинок, у Кости на 9 машинок больше. Сколько машинок у них вместе?', 'expected': ['37 машинок'], 'expectedFinalAnswer': '37 машинок', 'expectedNumericAnswer': '37', 'expectedSourceFamily': 'local:live'}, {'id': 'equal_groups_remaining', 'name': 'equal_groups_remaining', 'grade': 3, 'category': 'v284_text', 'text': 'В 7 ящиках по 16 яблок. Продали 39 яблок. Сколько яблок осталось?', 'expected': ['73 яблока'], 'expectedFinalAnswer': '73 яблока', 'expectedNumericAnswer': '73', 'expectedSourceFamily': 'local:live'}, {'id': 'cost_two_items', 'name': 'cost_two_items', 'grade': 4, 'category': 'v284_money', 'text': 'Купили 5 альбомов по 72 рубля и краски за 180 рублей. Сколько рублей заплатили?', 'expected': ['540 рублей'], 'expectedFinalAnswer': '540 рублей', 'expectedNumericAnswer': '540', 'expectedSourceFamily': 'local:live'}, {'id': 'change_two_types', 'name': 'change_two_types', 'grade': 4, 'category': 'v284_money', 'text': 'С 1000 рублей купили 4 книги по 160 рублей и 3 ручки по 25 рублей. Сколько рублей осталось?', 'expected': ['285 рублей'], 'expectedFinalAnswer': '285 рублей', 'expectedNumericAnswer': '285', 'expectedSourceFamily': 'local:live'}, {'id': 'unit_price', 'name': 'unit_price', 'grade': 3, 'category': 'v284_money', 'text': 'За 9 одинаковых блокнотов заплатили 315 рублей. Сколько рублей стоит один блокнот?', 'expected': ['35 рублей'], 'expectedFinalAnswer': '35 рублей', 'expectedNumericAnswer': '35', 'expectedSourceFamily': 'local:live'}, {'id': 'how_many_can_buy', 'name': 'how_many_can_buy', 'grade': 4, 'category': 'v284_money', 'text': 'Один билет стоит 120 рублей. Сколько билетов можно купить на 750 рублей?', 'expected': ['6 билетов'], 'expectedFinalAnswer': '6 билетов', 'expectedNumericAnswer': '6', 'expectedSourceFamily': 'local:live'}, {'id': 'quantity_remainder', 'name': 'quantity_remainder', 'grade': 3, 'category': 'v284_money', 'text': 'Одна открытка стоит 16 рублей. Сколько открыток можно купить на 100 рублей и сколько рублей останется?', 'expected': ['6 открыток', '4 рубля'], 'expectedFinalAnswer': '6 открыток', 'expectedNumericAnswer': '6', 'expectedSourceFamily': 'local:live'}, {'id': 'rub_kop_add', 'name': 'rub_kop_add', 'grade': 3, 'category': 'v284_money', 'text': '4 рубля 65 копеек + 2 рубля 70 копеек. Сколько получится?', 'expected': ['7 рублей 35 копеек'], 'expectedFinalAnswer': '7 рублей 35 копеек', 'expectedNumericAnswer': '7', 'expectedSourceFamily': 'local:live'}, {'id': 'rub_kop_sub', 'name': 'rub_kop_sub', 'grade': 4, 'category': 'v284_money', 'text': '8 рублей 00 копеек - 3 рубля 75 копеек. Сколько получится?', 'expected': ['4 рубля 25 копеек'], 'expectedFinalAnswer': '4 рубля 25 копеек', 'expectedNumericAnswer': '4', 'expectedSourceFamily': 'local:live'}, {'id': 'duration', 'name': 'duration', 'grade': 3, 'category': 'v284_time', 'text': 'Занятие началось в 11:35 и закончилось в 12:20. Сколько минут длилось занятие?', 'expected': ['45 минут'], 'expectedFinalAnswer': '45 минут', 'expectedNumericAnswer': '45', 'expectedSourceFamily': 'local:live'}, {'id': 'duration_cross_midnight', 'name': 'duration_cross_midnight', 'grade': 4, 'category': 'v284_time', 'text': 'Поезд отправился в 23:40 и прибыл в 01:05. Сколько времени поезд был в пути?', 'expected': ['1 час 25 минут'], 'expectedFinalAnswer': '1 час 25 минут', 'expectedNumericAnswer': '1', 'expectedSourceFamily': 'local:live'}, {'id': 'end_time', 'name': 'end_time', 'grade': 4, 'category': 'v284_time', 'text': 'Экскурсия началась в 10:15 и длилась 2 ч 40 мин. Во сколько она закончилась?', 'expected': ['12:55'], 'expectedFinalAnswer': '12:55', 'expectedNumericAnswer': '12:55', 'expectedSourceFamily': 'local:live'}, {'id': 'start_time', 'name': 'start_time', 'grade': 4, 'category': 'v284_time', 'text': 'Спектакль закончился в 19:30 и длился 1 ч 20 мин. Во сколько он начался?', 'expected': ['18:10'], 'expectedFinalAnswer': '18:10', 'expectedNumericAnswer': '18:10', 'expectedSourceFamily': 'local:live'}, {'id': 'min_to_hm', 'name': 'min_to_hm', 'grade': 3, 'category': 'v284_time', 'text': '145 минут - это сколько часов и минут?', 'expected': ['2 часа 25 минут'], 'expectedFinalAnswer': '2 часа 25 минут', 'expectedNumericAnswer': '2', 'expectedSourceFamily': 'local:live'}, {'id': 'weeks_days', 'name': 'weeks_days', 'grade': 3, 'category': 'v284_time', 'text': 'Сколько дней в 5 неделях 4 днях?', 'expected': ['39 дней'], 'expectedFinalAnswer': '39 дней', 'expectedNumericAnswer': '39', 'expectedSourceFamily': 'local:live'}, {'id': 'months_years', 'name': 'months_years', 'grade': 4, 'category': 'v284_time', 'text': '29 месяцев - это сколько лет и месяцев?', 'expected': ['2 года 5 месяцев'], 'expectedFinalAnswer': '2 года 5 месяцев', 'expectedNumericAnswer': '2', 'expectedSourceFamily': 'local:live'}, {'id': 'distance', 'name': 'distance', 'grade': 4, 'category': 'v284_motion', 'text': 'Автомобиль ехал 5 часов со скоростью 72 км/ч. Сколько километров он проехал?', 'expected': ['360 километров'], 'expectedFinalAnswer': '360 километров', 'expectedNumericAnswer': '360', 'expectedSourceFamily': 'local:live'}, {'id': 'speed', 'name': 'speed', 'grade': 4, 'category': 'v284_motion', 'text': 'Катер прошел 96 км за 4 часа. С какой скоростью шел катер?', 'expected': ['24 км/ч'], 'expectedFinalAnswer': '24 км/ч', 'expectedNumericAnswer': '24', 'expectedSourceFamily': 'local:live'}, {'id': 'time', 'name': 'time', 'grade': 4, 'category': 'v284_motion', 'text': 'Автобус ехал со скоростью 75 км/ч и проехал 300 км. Сколько часов ехал автобус?', 'expected': ['4 часа'], 'expectedFinalAnswer': '4 часа', 'expectedNumericAnswer': '4', 'expectedSourceFamily': 'local:live'}, {'id': 'towards', 'name': 'towards', 'grade': 4, 'category': 'v284_motion', 'text': 'Из двух городов одновременно навстречу друг другу выехали два автомобиля. Скорость первого 85 км/ч, скорость второго 65 км/ч. Через 2 часа они встретились. Какое расстояние между городами?', 'expected': ['300 километров'], 'expectedFinalAnswer': '300 километров', 'expectedNumericAnswer': '300', 'expectedSourceFamily': 'local:live'}, {'id': 'remaining_times', 'name': 'remaining_times', 'grade': 4, 'category': 'v284_motion', 'text': 'Турист прошел 18 км. Ему осталось пройти в 2 раза больше, чем он уже прошел. Сколько километров весь путь?', 'expected': ['54 километра'], 'expectedFinalAnswer': '54 километра', 'expectedNumericAnswer': '54', 'expectedSourceFamily': 'local:live'}, {'id': 'remaining_less_by', 'name': 'remaining_less_by', 'grade': 4, 'category': 'v284_motion', 'text': 'Поезд ехал 3 ч со скоростью 80 км/ч. Осталось проехать на 60 км меньше. Каков весь путь?', 'expected': ['420 километров'], 'expectedFinalAnswer': '420 километров', 'expectedNumericAnswer': '420', 'expectedSourceFamily': 'local:live'}, {'id': 'two_leg', 'name': 'two_leg', 'grade': 4, 'category': 'v284_motion', 'text': 'Автомобиль ехал 2 ч со скоростью 90 км/ч. Потом еще 3 ч со скоростью 70 км/ч. Какое расстояние он проехал?', 'expected': ['390 километров'], 'expectedFinalAnswer': '390 километров', 'expectedNumericAnswer': '390', 'expectedSourceFamily': 'local:live'}, {'id': 'towards_remaining', 'name': 'towards_remaining', 'grade': 4, 'category': 'v284_motion', 'text': 'Расстояние между городами 420 км. Скорость первого автомобиля 70 км/ч, скорость второго 60 км/ч. Они едут навстречу. Сколько км останется между ними через 3 часа?', 'expected': ['30 километров'], 'expectedFinalAnswer': '30 километров', 'expectedNumericAnswer': '30', 'expectedSourceFamily': 'local:live'}, {'id': 'pipes', 'name': 'pipes', 'grade': 4, 'category': 'v284_joint_work', 'text': 'Одна труба наполняет бассейн за 6 часов, другая труба — за 12 часов. За сколько часов наполнят бассейн обе трубы вместе?', 'expected': ['4 часа'], 'expectedFinalAnswer': '4 часа', 'expectedNumericAnswer': '4', 'expectedSourceFamily': 'local:live'}, {'id': 'tractors', 'name': 'tractors', 'grade': 4, 'category': 'v284_joint_work', 'text': 'Один трактор может вспахать поле площадью 480 аров за 6 часов, а другой трактор — за 8 часов. За сколько часов вспашут поле оба трактора, работая вместе?', 'expected': ['3 часа 26 минут'], 'expectedFinalAnswer': '3 часа 26 минут', 'expectedNumericAnswer': '3', 'expectedSourceFamily': 'local:live'}, {'id': 'printers_time', 'name': 'printers_time', 'grade': 4, 'category': 'v284_joint_work', 'text': 'Один принтер печатает 240 страниц за 8 часов, другой принтер - столько же за 12 часов. За сколько часов они напечатают 240 страниц вместе?', 'expected': ['4 часа 48 минут'], 'expectedFinalAnswer': '4 часа 48 минут', 'expectedNumericAnswer': '4', 'expectedSourceFamily': 'local:live'}, {'id': 'details_together_for_time', 'name': 'details_together_for_time', 'grade': 4, 'category': 'v284_joint_work', 'text': 'Один рабочий делает 120 деталей за 6 часов, второй рабочий делает столько же за 10 часов. Сколько деталей они сделают вместе за 3 часа?', 'expected': ['96 деталей'], 'expectedFinalAnswer': '96 деталей', 'expectedNumericAnswer': '96', 'expectedSourceFamily': 'local:live'}, {'id': 'part_3_8', 'name': 'part_3_8', 'grade': 4, 'category': 'v284_fractions', 'text': 'Найди 3/8 от 96.', 'expected': ['36'], 'expectedFinalAnswer': '36', 'expectedNumericAnswer': '36', 'expectedSourceFamily': 'local:live'}, {'id': 'whole_2_5', 'name': 'whole_2_5', 'grade': 4, 'category': 'v284_fractions', 'text': '2/5 числа равны 28. Найди все число.', 'expected': ['70'], 'expectedFinalAnswer': '70', 'expectedNumericAnswer': '70', 'expectedSourceFamily': 'local:live'}, {'id': 'compare', 'name': 'compare', 'grade': 4, 'category': 'v284_fractions', 'text': 'Сравни дроби 5/6 и 3/4.', 'expected': ['5/6 больше'], 'expectedFinalAnswer': '5/6 больше', 'expectedNumericAnswer': '5', 'expectedSourceFamily': 'local:live'}, {'id': 'quarter_hour', 'name': 'quarter_hour', 'grade': 3, 'category': 'v284_fractions', 'text': 'Сколько минут в четверти часа?', 'expected': ['15 минут'], 'expectedFinalAnswer': '15 минут', 'expectedNumericAnswer': '15', 'expectedSourceFamily': 'local:live'}, {'id': 'length', 'name': 'length', 'grade': 4, 'category': 'v284_fractions', 'text': 'Найди 1/5 от 4 м.', 'expected': ['80 сантиметров'], 'expectedFinalAnswer': '80 сантиметров', 'expectedNumericAnswer': '80', 'expectedSourceFamily': 'local:live'}, {'id': 'money_fraction', 'name': 'money_fraction', 'grade': 4, 'category': 'v284_fractions', 'text': 'Найди 2/5 от 300 рублей.', 'expected': ['120 рублей'], 'expectedFinalAnswer': '120 рублей', 'expectedNumericAnswer': '120', 'expectedSourceFamily': 'local:live'}, {'id': 'rect_perimeter', 'name': 'rect_perimeter', 'grade': 3, 'category': 'v284_geometry', 'text': 'У прямоугольника длина 18 см, ширина 7 см. Найди периметр.', 'expected': ['50 см'], 'expectedFinalAnswer': '50 см', 'expectedNumericAnswer': '50', 'expectedSourceFamily': 'local:live'}, {'id': 'rect_area', 'name': 'rect_area', 'grade': 3, 'category': 'v284_geometry', 'text': 'У прямоугольника длина 18 см, ширина 7 см. Найди площадь.', 'expected': ['126 см²'], 'expectedFinalAnswer': '126 см²', 'expectedNumericAnswer': '126', 'expectedSourceFamily': 'local:live'}, {'id': 'width_by_area', 'name': 'width_by_area', 'grade': 4, 'category': 'v284_geometry', 'text': 'Площадь прямоугольника 144 кв. см, длина 16 см. Найди ширину.', 'expected': ['9 см'], 'expectedFinalAnswer': '9 см', 'expectedNumericAnswer': '9', 'expectedSourceFamily': 'local:live'}, {'id': 'square_area_from_perim', 'name': 'square_area_from_perim', 'grade': 4, 'category': 'v284_geometry', 'text': 'Периметр квадрата равен 44 см. Найди площадь квадрата.', 'expected': ['121 см²'], 'expectedFinalAnswer': '121 см²', 'expectedNumericAnswer': '121', 'expectedSourceFamily': 'local:live'}, {'id': 'composite_cut', 'name': 'composite_cut', 'grade': 4, 'category': 'v284_geometry', 'text': 'Из прямоугольника 12 см на 8 см вырезали квадрат 4 см на 4 см. Найди площадь оставшейся фигуры.', 'expected': ['80 см²'], 'expectedFinalAnswer': '80 см²', 'expectedNumericAnswer': '80', 'expectedSourceFamily': 'local:live'}, {'id': 'grid', 'name': 'grid', 'grade': 3, 'category': 'v284_geometry', 'text': 'На клетчатой бумаге прямоугольник занимает 6 клеток в длину и 5 клеток в ширину. Найди площадь.', 'expected': ['30 клеток'], 'expectedFinalAnswer': '30 клеток', 'expectedNumericAnswer': '30', 'expectedSourceFamily': 'local:live'}, {'id': 'coordinate', 'name': 'coordinate', 'grade': 4, 'category': 'v284_geometry', 'text': 'Из точки (2; 4) прошли 5 клетки вправо и 3 клетки вниз. В какой точке оказались?', 'expected': ['(7; 1)'], 'expectedFinalAnswer': '(7; 1)', 'expectedNumericAnswer': '7', 'expectedSourceFamily': 'local:live'}, {'id': 'pentagon', 'name': 'pentagon', 'grade': 2, 'category': 'v284_geometry', 'text': 'У шестиугольника сколько сторон и вершин?', 'expected': ['6 сторон и 6 вершин'], 'expectedFinalAnswer': '6 сторон и 6 вершин', 'expectedNumericAnswer': '6', 'expectedSourceFamily': 'local:live'}, {'id': 'table_total', 'name': 'table_total', 'grade': 3, 'category': 'v284_data', 'text': 'В таблице: математика - 37, русский - 29, чтение - 18. Сколько всего заданий по математике и русскому?', 'expected': ['66 заданий'], 'expectedFinalAnswer': '66 заданий', 'expectedNumericAnswer': '66', 'expectedSourceFamily': 'local:live'}, {'id': 'table_difference', 'name': 'table_difference', 'grade': 3, 'category': 'v284_data', 'text': 'В таблице: яблоки - 46, груши - 28, сливы - 35. На сколько яблок больше, чем груш?', 'expected': ['18'], 'expectedFinalAnswer': '18', 'expectedNumericAnswer': '18', 'expectedSourceFamily': 'local:live'}, {'id': 'diagram_times', 'name': 'diagram_times', 'grade': 3, 'category': 'v284_data', 'text': 'На диаграмме: кошки - 18, собаки - 6. Во сколько раз кошки больше, чем собаки?', 'expected': ['3 раза'], 'expectedFinalAnswer': '3 раза', 'expectedNumericAnswer': '3', 'expectedSourceFamily': 'local:live'}, {'id': 'pictogram', 'name': 'pictogram', 'grade': 3, 'category': 'v284_data', 'text': 'Пиктограмма: 1 значок = 6 книг. У класса 8 значков. Сколько книг?', 'expected': ['48 книг'], 'expectedFinalAnswer': '48 книг', 'expectedNumericAnswer': '48', 'expectedSourceFamily': 'local:live'}, {'id': 'schedule', 'name': 'schedule', 'grade': 3, 'category': 'v284_data', 'text': 'В расписании: кружок начался в 15:25, закончился в 16:10. Сколько минут длился кружок?', 'expected': ['45 минут'], 'expectedFinalAnswer': '45 минут', 'expectedNumericAnswer': '45', 'expectedSourceFamily': 'local:live'}, {'id': 'multi_newline', 'name': 'multi_newline', 'grade': 4, 'category': 'v284_input', 'text': 'Вычисли 45 + 18\nНайди 1/3 от 30', 'expected': ['Разделите задания'], 'expectedFinalAnswer': 'Разделите задания', 'expectedNumericAnswer': None, 'expectedSourceFamily': 'guard-multi-task', 'expectedSource': 'guard-multi-task', 'shouldWarn': True}, {'id': 'multi_semicolon', 'name': 'multi_semicolon', 'grade': 4, 'category': 'v284_input', 'text': '48 : 6; 17 + 9', 'expected': ['Разделите задания'], 'expectedFinalAnswer': 'Разделите задания', 'expectedNumericAnswer': None, 'expectedSourceFamily': 'guard-multi-task', 'expectedSource': 'guard-multi-task', 'shouldWarn': True}, {'id': 'system_enter', 'name': 'system_enter', 'grade': 4, 'category': 'v284_input', 'text': 'x + y = 30\ny - x = 8', 'expected': ['x = 11, y = 19'], 'expectedFinalAnswer': 'x = 11, y = 19', 'expectedNumericAnswer': '11', 'expectedSourceFamily': 'local:live-system-solver', 'expectedSource': 'local:live-system-solver', 'shouldWarn': False}, {'id': 'cyrillic_x', 'name': 'cyrillic_x', 'grade': 4, 'category': 'v284_input', 'text': '5 * х + 20 = 70. Найди х.', 'expected': ['x = 10'], 'expectedFinalAnswer': 'x = 10', 'expectedNumericAnswer': '10', 'expectedSourceFamily': 'local:live'}, {'id': 'ocr_noise', 'name': 'ocr_noise', 'grade': 2, 'category': 'v284_input', 'text': 'В магаз1не было 60 ручек, продали 25 ручек. Сколько ручек осталось?', 'expected': ['35 ручек'], 'expectedFinalAnswer': '35 ручек', 'expectedNumericAnswer': '35', 'expectedSourceFamily': 'local:live'}]

DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v284_wave4_cases()


# --- v285 sequential programmatic audit: 1 класс, раздел 1 — Числа и величины ---
# Cases are original synthetic variants; coverage follows the federal program
# topics for Grade 1 numbers/quantities (0-20, count, compare, neighbours,
# increase/decrease by units, elementary length in cm/dm).
def _v285_g1_numbers_values_cases() -> list[dict[str, Any]]:
    return [{'category': 'v285_g1_numbers_write',
  'expected': ['0'],
  'expectedFinalAnswer': '0',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_0',
  'name': 'write_0',
  'text': 'Запиши цифрой число ноль.'},
 {'category': 'v285_g1_numbers_write',
  'expected': ['5'],
  'expectedFinalAnswer': '5',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_5',
  'name': 'write_5',
  'text': 'Запиши цифрой число пять.'},
 {'category': 'v285_g1_numbers_write',
  'expected': ['7'],
  'expectedFinalAnswer': '7',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_7',
  'name': 'write_7',
  'text': 'Запиши цифрой число семь.'},
 {'category': 'v285_g1_numbers_write',
  'expected': ['9'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_9',
  'name': 'write_9',
  'text': 'Запиши цифрой число девять.'},
 {'category': 'v285_g1_numbers_write',
  'expected': ['10'],
  'expectedFinalAnswer': '10',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_10',
  'name': 'write_10',
  'text': 'Запиши цифрой число десять.'},
 {'category': 'v285_g1_numbers_write',
  'expected': ['11'],
  'expectedFinalAnswer': '11',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_11',
  'name': 'write_11',
  'text': 'Запиши цифрой число одиннадцать.'},
 {'category': 'v285_g1_numbers_write',
  'expected': ['14'],
  'expectedFinalAnswer': '14',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_14',
  'name': 'write_14',
  'text': 'Запиши цифрой число четырнадцать.'},
 {'category': 'v285_g1_numbers_write',
  'expected': ['17'],
  'expectedFinalAnswer': '17',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_17',
  'name': 'write_17',
  'text': 'Запиши цифрой число семнадцать.'},
 {'category': 'v285_g1_numbers_write',
  'expected': ['20'],
  'expectedFinalAnswer': '20',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'write_20',
  'name': 'write_20',
  'text': 'Запиши цифрой число двадцать.'},
 {'category': 'v285_g1_numbers_read',
  'expected': ['ноль'],
  'expectedFinalAnswer': 'ноль',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_0',
  'name': 'read_0',
  'text': 'Как читается число 0?'},
 {'category': 'v285_g1_numbers_read',
  'expected': ['три'],
  'expectedFinalAnswer': 'три',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_3',
  'name': 'read_3',
  'text': 'Как читается число 3?'},
 {'category': 'v285_g1_numbers_read',
  'expected': ['восемь'],
  'expectedFinalAnswer': 'восемь',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_8',
  'name': 'read_8',
  'text': 'Как читается число 8?'},
 {'category': 'v285_g1_numbers_read',
  'expected': ['десять'],
  'expectedFinalAnswer': 'десять',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_10',
  'name': 'read_10',
  'text': 'Как читается число 10?'},
 {'category': 'v285_g1_numbers_read',
  'expected': ['двенадцать'],
  'expectedFinalAnswer': 'двенадцать',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_12',
  'name': 'read_12',
  'text': 'Как читается число 12?'},
 {'category': 'v285_g1_numbers_read',
  'expected': ['шестнадцать'],
  'expectedFinalAnswer': 'шестнадцать',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_16',
  'name': 'read_16',
  'text': 'Как читается число 16?'},
 {'category': 'v285_g1_numbers_read',
  'expected': ['девятнадцать'],
  'expectedFinalAnswer': 'девятнадцать',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_19',
  'name': 'read_19',
  'text': 'Как читается число 19?'},
 {'category': 'v285_g1_tens_units',
  'expected': ['11'],
  'expectedFinalAnswer': '11',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'make_1d_1',
  'name': 'make_1d_1',
  'text': 'Запиши число, в котором 1 десяток и 1 единиц.'},
 {'category': 'v285_g1_tens_units',
  'expected': ['13'],
  'expectedFinalAnswer': '13',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'make_1d_3',
  'name': 'make_1d_3',
  'text': 'Запиши число, в котором 1 десяток и 3 единиц.'},
 {'category': 'v285_g1_tens_units',
  'expected': ['15'],
  'expectedFinalAnswer': '15',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'make_1d_5',
  'name': 'make_1d_5',
  'text': 'Запиши число, в котором 1 десяток и 5 единиц.'},
 {'category': 'v285_g1_tens_units',
  'expected': ['17'],
  'expectedFinalAnswer': '17',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'make_1d_7',
  'name': 'make_1d_7',
  'text': 'Запиши число, в котором 1 десяток и 7 единиц.'},
 {'category': 'v285_g1_tens_units',
  'expected': ['19'],
  'expectedFinalAnswer': '19',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'make_1d_9',
  'name': 'make_1d_9',
  'text': 'Запиши число, в котором 1 десяток и 9 единиц.'},
 {'category': 'v285_g1_tens_units',
  'expected': ['1 десят', '0 единиц'],
  'expectedFinalAnswer': '1 десят',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_10',
  'name': 'read_10',
  'text': 'В числе 10 сколько десятков и сколько единиц?'},
 {'category': 'v285_g1_tens_units',
  'expected': ['1 десят', '2 единиц'],
  'expectedFinalAnswer': '1 десят',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_12',
  'name': 'read_12',
  'text': 'В числе 12 сколько десятков и сколько единиц?'},
 {'category': 'v285_g1_tens_units',
  'expected': ['1 десят', '4 единиц'],
  'expectedFinalAnswer': '1 десят',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_14',
  'name': 'read_14',
  'text': 'В числе 14 сколько десятков и сколько единиц?'},
 {'category': 'v285_g1_tens_units',
  'expected': ['1 десят', '8 единиц'],
  'expectedFinalAnswer': '1 десят',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_18',
  'name': 'read_18',
  'text': 'В числе 18 сколько десятков и сколько единиц?'},
 {'category': 'v285_g1_tens_units',
  'expected': ['2 десят', '0 единиц'],
  'expectedFinalAnswer': '2 десят',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'read_20',
  'name': 'read_20',
  'text': 'В числе 20 сколько десятков и сколько единиц?'},
 {'category': 'v285_g1_compare',
  'expected': ['3 < 5'],
  'expectedFinalAnswer': '3 < 5',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_3_5',
  'name': 'cmp_3_5',
  'text': 'Сравни числа 3 и 5.'},
 {'category': 'v285_g1_compare',
  'expected': ['9 > 6'],
  'expectedFinalAnswer': '9 > 6',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_9_6',
  'name': 'cmp_9_6',
  'text': 'Сравни числа 9 и 6.'},
 {'category': 'v285_g1_compare',
  'expected': ['7 = 7'],
  'expectedFinalAnswer': '7 = 7',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_7_7',
  'name': 'cmp_7_7',
  'text': 'Сравни числа 7 и 7.'},
 {'category': 'v285_g1_compare',
  'expected': ['12 < 18'],
  'expectedFinalAnswer': '12 < 18',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_12_18',
  'name': 'cmp_12_18',
  'text': 'Сравни числа 12 и 18.'},
 {'category': 'v285_g1_compare',
  'expected': ['20 > 14'],
  'expectedFinalAnswer': '20 > 14',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_20_14',
  'name': 'cmp_20_14',
  'text': 'Сравни числа 20 и 14.'},
 {'category': 'v285_g1_compare',
  'expected': ['16 = 16'],
  'expectedFinalAnswer': '16 = 16',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_16_16',
  'name': 'cmp_16_16',
  'text': 'Сравни числа 16 и 16.'},
 {'category': 'v285_g1_compare',
  'expected': ['11 > 10'],
  'expectedFinalAnswer': '11 > 10',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_11_10',
  'name': 'cmp_11_10',
  'text': 'Сравни числа 11 и 10.'},
 {'category': 'v285_g1_compare',
  'expected': ['0 < 4'],
  'expectedFinalAnswer': '0 < 4',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_0_4',
  'name': 'cmp_0_4',
  'text': 'Сравни числа 0 и 4.'},
 {'category': 'v285_g1_compare',
  'expected': ['8 > 0'],
  'expectedFinalAnswer': '8 > 0',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_8_0',
  'name': 'cmp_8_0',
  'text': 'Сравни числа 8 и 0.'},
 {'category': 'v285_g1_compare',
  'expected': ['13 < 15'],
  'expectedFinalAnswer': '13 < 15',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cmp_13_15',
  'name': 'cmp_13_15',
  'text': 'Сравни числа 13 и 15.'},
 {'category': 'v285_g1_compare',
  'expected': ['8'],
  'expectedFinalAnswer': '8',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'larger_4_8',
  'name': 'larger_4_8',
  'text': 'Какое число больше: 4 или 8?'},
 {'category': 'v285_g1_compare',
  'expected': ['17'],
  'expectedFinalAnswer': '17',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'larger_17_12',
  'name': 'larger_17_12',
  'text': 'Какое число больше: 17 или 12?'},
 {'category': 'v285_g1_compare',
  'expected': ['9'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'larger_6_9',
  'name': 'larger_6_9',
  'text': 'Какое число больше: 6 или 9?'},
 {'category': 'v285_g1_compare',
  'expected': ['20'],
  'expectedFinalAnswer': '20',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'larger_15_20',
  'name': 'larger_15_20',
  'text': 'Какое число больше: 15 или 20?'},
 {'category': 'v285_g1_compare',
  'expected': ['11'],
  'expectedFinalAnswer': '11',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'larger_11_3',
  'name': 'larger_11_3',
  'text': 'Какое число больше: 11 или 3?'},
 {'category': 'v285_g1_compare',
  'expected': ['4'],
  'expectedFinalAnswer': '4',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'smaller_4_8',
  'name': 'smaller_4_8',
  'text': 'Какое число меньше: 4 или 8?'},
 {'category': 'v285_g1_compare',
  'expected': ['12'],
  'expectedFinalAnswer': '12',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'smaller_17_12',
  'name': 'smaller_17_12',
  'text': 'Какое число меньше: 17 или 12?'},
 {'category': 'v285_g1_compare',
  'expected': ['6'],
  'expectedFinalAnswer': '6',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'smaller_6_9',
  'name': 'smaller_6_9',
  'text': 'Какое число меньше: 6 или 9?'},
 {'category': 'v285_g1_compare',
  'expected': ['15'],
  'expectedFinalAnswer': '15',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'smaller_15_20',
  'name': 'smaller_15_20',
  'text': 'Какое число меньше: 15 или 20?'},
 {'category': 'v285_g1_compare',
  'expected': ['0'],
  'expectedFinalAnswer': '0',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'smaller_0_3',
  'name': 'smaller_0_3',
  'text': 'Какое число меньше: 0 или 3?'},
 {'category': 'v285_g1_sequence',
  'expected': ['1'],
  'expectedFinalAnswer': '1',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'after_0',
  'name': 'after_0',
  'text': 'Какое число идет после 0 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['2'],
  'expectedFinalAnswer': '2',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'after_1',
  'name': 'after_1',
  'text': 'Какое число идет после 1 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['6'],
  'expectedFinalAnswer': '6',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'after_5',
  'name': 'after_5',
  'text': 'Какое число идет после 5 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['9'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'after_8',
  'name': 'after_8',
  'text': 'Какое число идет после 8 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['14'],
  'expectedFinalAnswer': '14',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'after_13',
  'name': 'after_13',
  'text': 'Какое число идет после 13 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['20'],
  'expectedFinalAnswer': '20',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'after_19',
  'name': 'after_19',
  'text': 'Какое число идет после 19 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['0'],
  'expectedFinalAnswer': '0',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'before_1',
  'name': 'before_1',
  'text': 'Какое число идет перед 1 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['3'],
  'expectedFinalAnswer': '3',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'before_4',
  'name': 'before_4',
  'text': 'Какое число идет перед 4 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['9'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'before_10',
  'name': 'before_10',
  'text': 'Какое число идет перед 10 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['13'],
  'expectedFinalAnswer': '13',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'before_14',
  'name': 'before_14',
  'text': 'Какое число идет перед 14 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['19'],
  'expectedFinalAnswer': '19',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'before_20',
  'name': 'before_20',
  'text': 'Какое число идет перед 20 при счете?'},
 {'category': 'v285_g1_sequence',
  'expected': ['2', '4'],
  'expectedFinalAnswer': '2',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'neighbors_3',
  'name': 'neighbors_3',
  'text': 'Назови соседей числа 3.'},
 {'category': 'v285_g1_sequence',
  'expected': ['7', '9'],
  'expectedFinalAnswer': '7',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'neighbors_8',
  'name': 'neighbors_8',
  'text': 'Назови соседей числа 8.'},
 {'category': 'v285_g1_sequence',
  'expected': ['9', '11'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'neighbors_10',
  'name': 'neighbors_10',
  'text': 'Назови соседей числа 10.'},
 {'category': 'v285_g1_sequence',
  'expected': ['14', '16'],
  'expectedFinalAnswer': '14',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'neighbors_15',
  'name': 'neighbors_15',
  'text': 'Назови соседей числа 15.'},
 {'category': 'v285_g1_sequence',
  'expected': ['3'],
  'expectedFinalAnswer': '3',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'between_2_4',
  'name': 'between_2_4',
  'text': 'Какое число стоит между 2 и 4?'},
 {'category': 'v285_g1_sequence',
  'expected': ['7'],
  'expectedFinalAnswer': '7',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'between_6_8',
  'name': 'between_6_8',
  'text': 'Какое число стоит между 6 и 8?'},
 {'category': 'v285_g1_sequence',
  'expected': ['10'],
  'expectedFinalAnswer': '10',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'between_9_11',
  'name': 'between_9_11',
  'text': 'Какое число стоит между 9 и 11?'},
 {'category': 'v285_g1_sequence',
  'expected': ['15'],
  'expectedFinalAnswer': '15',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'between_14_16',
  'name': 'between_14_16',
  'text': 'Какое число стоит между 14 и 16?'},
 {'category': 'v285_g1_number_change',
  'expected': ['7'],
  'expectedFinalAnswer': '7',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'inc_5_2',
  'name': 'inc_5_2',
  'text': 'Увеличь число 5 на 2.'},
 {'category': 'v285_g1_number_change',
  'expected': ['8'],
  'expectedFinalAnswer': '8',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'inc_7_1',
  'name': 'inc_7_1',
  'text': 'Увеличь число 7 на 1.'},
 {'category': 'v285_g1_number_change',
  'expected': ['15'],
  'expectedFinalAnswer': '15',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'inc_12_3',
  'name': 'inc_12_3',
  'text': 'Увеличь число 12 на 3.'},
 {'category': 'v285_g1_number_change',
  'expected': ['20'],
  'expectedFinalAnswer': '20',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'inc_16_4',
  'name': 'inc_16_4',
  'text': 'Увеличь число 16 на 4.'},
 {'category': 'v285_g1_number_change',
  'expected': ['6'],
  'expectedFinalAnswer': '6',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'inc_0_6',
  'name': 'inc_0_6',
  'text': 'Увеличь число 0 на 6.'},
 {'category': 'v285_g1_number_change',
  'expected': ['7'],
  'expectedFinalAnswer': '7',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dec_9_2',
  'name': 'dec_9_2',
  'text': 'Уменьши число 9 на 2.'},
 {'category': 'v285_g1_number_change',
  'expected': ['5'],
  'expectedFinalAnswer': '5',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dec_10_5',
  'name': 'dec_10_5',
  'text': 'Уменьши число 10 на 5.'},
 {'category': 'v285_g1_number_change',
  'expected': ['12'],
  'expectedFinalAnswer': '12',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dec_18_6',
  'name': 'dec_18_6',
  'text': 'Уменьши число 18 на 6.'},
 {'category': 'v285_g1_number_change',
  'expected': ['5'],
  'expectedFinalAnswer': '5',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dec_6_1',
  'name': 'dec_6_1',
  'text': 'Уменьши число 6 на 1.'},
 {'category': 'v285_g1_number_change',
  'expected': ['10'],
  'expectedFinalAnswer': '10',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dec_14_4',
  'name': 'dec_14_4',
  'text': 'Уменьши число 14 на 4.'},
 {'category': 'v285_g1_difference',
  'expected': ['3'],
  'expectedFinalAnswer': '3',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'more_diff_8_5',
  'name': 'more_diff_8_5',
  'text': 'На сколько 8 больше 5?'},
 {'category': 'v285_g1_difference',
  'expected': ['5'],
  'expectedFinalAnswer': '5',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'more_diff_12_7',
  'name': 'more_diff_12_7',
  'text': 'На сколько 12 больше 7?'},
 {'category': 'v285_g1_difference',
  'expected': ['7'],
  'expectedFinalAnswer': '7',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'more_diff_20_13',
  'name': 'more_diff_20_13',
  'text': 'На сколько 20 больше 13?'},
 {'category': 'v285_g1_difference',
  'expected': ['9'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'more_diff_9_0',
  'name': 'more_diff_9_0',
  'text': 'На сколько 9 больше 0?'},
 {'category': 'v285_g1_difference',
  'expected': ['0'],
  'expectedFinalAnswer': '0',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'more_diff_15_15',
  'name': 'more_diff_15_15',
  'text': 'На сколько 15 больше 15?'},
 {'category': 'v285_g1_difference',
  'expected': ['3'],
  'expectedFinalAnswer': '3',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'less_diff_5_8',
  'name': 'less_diff_5_8',
  'text': 'На сколько 5 меньше 8?'},
 {'category': 'v285_g1_difference',
  'expected': ['5'],
  'expectedFinalAnswer': '5',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'less_diff_7_12',
  'name': 'less_diff_7_12',
  'text': 'На сколько 7 меньше 12?'},
 {'category': 'v285_g1_difference',
  'expected': ['7'],
  'expectedFinalAnswer': '7',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'less_diff_13_20',
  'name': 'less_diff_13_20',
  'text': 'На сколько 13 меньше 20?'},
 {'category': 'v285_g1_difference',
  'expected': ['9'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'less_diff_0_9',
  'name': 'less_diff_0_9',
  'text': 'На сколько 0 меньше 9?'},
 {'category': 'v285_g1_difference',
  'expected': ['0'],
  'expectedFinalAnswer': '0',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'less_diff_15_15',
  'name': 'less_diff_15_15',
  'text': 'На сколько 15 меньше 15?'},
 {'category': 'v285_g1_order',
  'expected': ['3, 7, 9'],
  'expectedFinalAnswer': '3, 7, 9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'order_7_3_9',
  'name': 'order_7_3_9',
  'text': 'Расположи числа 7, 3, 9 в порядке возрастания.'},
 {'category': 'v285_g1_order',
  'expected': ['8, 5, 2'],
  'expectedFinalAnswer': '8, 5, 2',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'order_2_8_5',
  'name': 'order_2_8_5',
  'text': 'Расположи числа 2, 8, 5 в порядке убывания.'},
 {'category': 'v285_g1_order',
  'expected': ['11, 14, 18'],
  'expectedFinalAnswer': '11, 14, 18',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'order_14_11_18',
  'name': 'order_14_11_18',
  'text': 'Расположи числа 14, 11, 18 в порядке возрастания.'},
 {'category': 'v285_g1_order',
  'expected': ['4, 2, 0'],
  'expectedFinalAnswer': '4, 2, 0',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'order_0_4_2',
  'name': 'order_0_4_2',
  'text': 'Расположи числа 0, 4, 2 в порядке убывания.'},
 {'category': 'v285_g1_series',
  'expected': ['6'],
  'expectedFinalAnswer': '6',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'series_by_1',
  'name': 'series_by_1',
  'text': 'Продолжи ряд: 3, 4, 5, ...'},
 {'category': 'v285_g1_series',
  'expected': ['8'],
  'expectedFinalAnswer': '8',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'series_by_2',
  'name': 'series_by_2',
  'text': 'Продолжи ряд: 2, 4, 6, ...'},
 {'category': 'v285_g1_series',
  'expected': ['20'],
  'expectedFinalAnswer': '20',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'series_by_5',
  'name': 'series_by_5',
  'text': 'Продолжи ряд: 5, 10, 15, ...'},
 {'category': 'v285_g1_series',
  'expected': ['6'],
  'expectedFinalAnswer': '6',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'series_down',
  'name': 'series_down',
  'text': 'Продолжи ряд: 9, 8, 7, ...'},
 {'category': 'v285_g1_lengths',
  'expected': ['10 сантиметров'],
  'expectedFinalAnswer': '10 сантиметров',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dm_to_cm',
  'name': 'dm_to_cm',
  'text': 'Сколько сантиметров в 1 дм?'},
 {'category': 'v285_g1_lengths',
  'expected': ['15 сантиметров'],
  'expectedFinalAnswer': '15 сантиметров',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dm_cm_to_cm_15',
  'name': 'dm_cm_to_cm_15',
  'text': 'Сколько сантиметров в 1 дм 5 см?'},
 {'category': 'v285_g1_lengths',
  'expected': ['12 сантиметров'],
  'expectedFinalAnswer': '12 сантиметров',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dm_cm_to_cm_12',
  'name': 'dm_cm_to_cm_12',
  'text': 'Сколько сантиметров в 1 дм 2 см?'},
 {'category': 'v285_g1_lengths',
  'expected': ['1 дм', '2 см'],
  'expectedFinalAnswer': '1 дм',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cm_to_dm_cm_12',
  'name': 'cm_to_dm_cm_12',
  'text': '12 см - это сколько дециметров и сантиметров?'},
 {'category': 'v285_g1_lengths',
  'expected': ['1 дм', '9 см'],
  'expectedFinalAnswer': '1 дм',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'cm_to_dm_cm_19',
  'name': 'cm_to_dm_cm_19',
  'text': '19 см - это сколько дециметров и сантиметров?'},
 {'category': 'v285_g1_lengths',
  'expected': ['8 см > 6 см'],
  'expectedFinalAnswer': '8 см > 6 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'compare_len',
  'name': 'compare_len',
  'text': 'Сравни длины 8 см и 6 см.'},
 {'category': 'v285_g1_lengths',
  'expected': ['6 см'],
  'expectedFinalAnswer': '6 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'shorter',
  'name': 'shorter',
  'text': 'Какой отрезок короче: 6 см или 9 см?'},
 {'category': 'v285_g1_lengths',
  'expected': ['7 см'],
  'expectedFinalAnswer': '7 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'longer',
  'name': 'longer',
  'text': 'Какой отрезок длиннее: 7 см или 4 см?'},
 {'category': 'v285_g1_lengths',
  'expected': ['5 см'],
  'expectedFinalAnswer': '5 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'diff_len',
  'name': 'diff_len',
  'text': 'На сколько сантиметров 9 см длиннее 4 см?'},
 {'category': 'v285_g1_lengths',
  'expected': ['5 см'],
  'expectedFinalAnswer': '5 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'diff_len2',
  'name': 'diff_len2',
  'text': 'На сколько сантиметров 3 см короче 8 см?'},
 {'category': 'v285_g1_lengths',
  'expected': ['6 см'],
  'expectedFinalAnswer': '6 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'ruler_segment',
  'name': 'ruler_segment',
  'text': 'На линейке от 2 см до 8 см. Какой длины отрезок?'},
 {'category': 'v285_g1_lengths',
  'expected': ['6 см'],
  'expectedFinalAnswer': '6 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'ruler_segment2',
  'name': 'ruler_segment2',
  'text': 'Отметили точки на 5 см и 11 см. Какой длины отрезок между ними?'},
 {'category': 'v285_g1_lengths',
  'expected': ['7 см'],
  'expectedFinalAnswer': '7 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'ribbon_left',
  'name': 'ribbon_left',
  'text': 'Лента была длиной 10 см. Отрезали 3 см. Сколько сантиметров осталось?'},
 {'category': 'v285_g1_lengths',
  'expected': ['10 см'],
  'expectedFinalAnswer': '10 см',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'pencil_total',
  'name': 'pencil_total',
  'text': 'Карандаш был 8 см, его удлинили на 2 см. Какая стала длина?'},
 {'category': 'v285_g1_mixed_values',
  'expected': ['0'],
  'expectedFinalAnswer': '0',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'zero_sub',
  'name': 'zero_sub',
  'text': 'Сколько получится, если из 7 вычесть 7?'},
 {'category': 'v285_g1_mixed_values',
  'expected': ['6'],
  'expectedFinalAnswer': '6',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'zero_add',
  'name': 'zero_add',
  'text': 'Сколько получится, если к 0 прибавить 6?'},
 {'category': 'v285_g1_mixed_values',
  'expected': ['9'],
  'expectedFinalAnswer': '9',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'zero_sub0',
  'name': 'zero_sub0',
  'text': 'Сколько получится, если из 9 вычесть 0?'},
 {'category': 'v285_g1_mixed_values',
  'expected': ['7 фруктов'],
  'expectedFinalAnswer': '7 фруктов',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'count_fruits',
  'name': 'count_fruits',
  'text': 'На тарелке 4 яблока и 3 груши. Сколько всего фруктов?'},
 {'category': 'v285_g1_mixed_values',
  'expected': ['8 кубиков'],
  'expectedFinalAnswer': '8 кубиков',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'count_cubes',
  'name': 'count_cubes',
  'text': 'В коробке 6 красных кубиков и 2 синих кубика. Сколько всего кубиков?'},
 {'category': 'v285_g1_mixed_values',
  'expected': ['5 книг'],
  'expectedFinalAnswer': '5 книг',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'left_books',
  'name': 'left_books',
  'text': 'На полке было 9 книг, 4 книги убрали. Сколько книг осталось?'},
 {'category': 'v285_g1_mixed_values',
  'expected': ['3 наклейки'],
  'expectedFinalAnswer': '3 наклейки',
  'expectedNumericAnswer': None,
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3'],
  'grade': 1,
  'id': 'dash_sonya',
  'name': 'dash_sonya',
  'text': 'У Даши 5 наклеек, у Сони 8 наклеек. На сколько наклеек у Сони больше?'}]

DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v285_g1_numbers_values_cases()


# --- v287 sequential programmatic audit: 1 класс, раздел 2 — Арифметические действия ---

def _v287_g1_arithmetic_actions_cases() -> list[dict[str, Any]]:
    return [{'id': 'v287_add_2_3',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_2_3',
  'text': 'Вычисли 2 + 3.',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_4_5',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_4_5',
  'text': 'Вычисли 4 + 5.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_6_3',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_6_3',
  'text': 'Вычисли 6 + 3.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_7_2',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_7_2',
  'text': 'Вычисли 7 + 2.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_8_1',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_8_1',
  'text': 'Вычисли 8 + 1.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_5_5',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_5_5',
  'text': 'Вычисли 5 + 5.',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_9_4',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_9_4',
  'text': 'Вычисли 9 + 4.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_8_7',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_8_7',
  'text': 'Вычисли 8 + 7.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_6_8',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_6_8',
  'text': 'Вычисли 6 + 8.',
  'expected': ['Ответ: 14'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_7_6',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_7_6',
  'text': 'Вычисли 7 + 6.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_9_6',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_9_6',
  'text': 'Вычисли 9 + 6.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_3_8',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_3_8',
  'text': 'Вычисли 3 + 8.',
  'expected': ['Ответ: 11'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_4_9',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_4_9',
  'text': 'Вычисли 4 + 9.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_11_2',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_11_2',
  'text': 'Вычисли 11 + 2.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_12_3',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_12_3',
  'text': 'Вычисли 12 + 3.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_10_5',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_10_5',
  'text': 'Вычисли 10 + 5.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_13_4',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_13_4',
  'text': 'Вычисли 13 + 4.',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_14_5',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_14_5',
  'text': 'Вычисли 14 + 5.',
  'expected': ['Ответ: 19'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '19',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_15_2',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_15_2',
  'text': 'Вычисли 15 + 2.',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_add_16_3',
  'grade': 1,
  'category': 'v287_g1_direct_addition',
  'name': 'v287_add_16_3',
  'text': 'Вычисли 16 + 3.',
  'expected': ['Ответ: 19'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '19',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_5_2',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_5_2',
  'text': 'Вычисли 5 - 2.',
  'expected': ['Ответ: 3'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '3',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_7_4',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_7_4',
  'text': 'Вычисли 7 - 4.',
  'expected': ['Ответ: 3'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '3',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_9_3',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_9_3',
  'text': 'Вычисли 9 - 3.',
  'expected': ['Ответ: 6'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '6',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_10_6',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_10_6',
  'text': 'Вычисли 10 - 6.',
  'expected': ['Ответ: 4'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '4',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_12_5',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_12_5',
  'text': 'Вычисли 12 - 5.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_14_7',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_14_7',
  'text': 'Вычисли 14 - 7.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_15_8',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_15_8',
  'text': 'Вычисли 15 - 8.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_16_9',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_16_9',
  'text': 'Вычисли 16 - 9.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_18_6',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_18_6',
  'text': 'Вычисли 18 - 6.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_20_11',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_20_11',
  'text': 'Вычисли 20 - 11.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_13_3',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_13_3',
  'text': 'Вычисли 13 - 3.',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_17_5',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_17_5',
  'text': 'Вычисли 17 - 5.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_19_4',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_19_4',
  'text': 'Вычисли 19 - 4.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_11_9',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_11_9',
  'text': 'Вычисли 11 - 9.',
  'expected': ['Ответ: 2'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '2',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_8_8',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_8_8',
  'text': 'Вычисли 8 - 8.',
  'expected': ['Ответ: 0'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '0',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_20_0',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_20_0',
  'text': 'Вычисли 20 - 0.',
  'expected': ['Ответ: 20'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '20',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_12_0',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_12_0',
  'text': 'Вычисли 12 - 0.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_10_10',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_10_10',
  'text': 'Вычисли 10 - 10.',
  'expected': ['Ответ: 0'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '0',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_18_9',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_18_9',
  'text': 'Вычисли 18 - 9.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sub_16_7',
  'grade': 1,
  'category': 'v287_g1_direct_subtraction',
  'name': 'v287_sub_16_7',
  'text': 'Вычисли 16 - 7.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_add_7_5',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_add_7_5',
  'text': 'К 7 прибавь 5.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_add_9_2',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_add_9_2',
  'text': 'К 9 прибавь 2.',
  'expected': ['Ответ: 11'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_add_4_8',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_add_4_8',
  'text': 'К 4 прибавь 8.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_add_6_6',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_add_6_6',
  'text': 'К 6 прибавь 6.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_add_12_4',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_add_12_4',
  'text': 'К 12 прибавь 4.',
  'expected': ['Ответ: 16'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '16',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_sub_13_5',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_sub_13_5',
  'text': 'Из 13 вычти 5.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_sub_17_8',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_sub_17_8',
  'text': 'Из 17 вычти 8.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_sub_19_7',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_sub_19_7',
  'text': 'Из 19 вычти 7.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_sub_10_3',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_sub_10_3',
  'text': 'Из 10 вычти 3.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_verbal_sub_16_4',
  'grade': 1,
  'category': 'v287_g1_verbal_actions',
  'name': 'v287_verbal_sub_16_4',
  'text': 'Из 16 вычти 4.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sum_6_4',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_sum_6_4',
  'text': 'Найди сумму чисел 6 и 4.',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sum_8_7',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_sum_8_7',
  'text': 'Найди сумму чисел 8 и 7.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sum_9_5',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_sum_9_5',
  'text': 'Найди сумму чисел 9 и 5.',
  'expected': ['Ответ: 14'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sum_11_6',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_sum_11_6',
  'text': 'Найди сумму чисел 11 и 6.',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sum_13_5',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_sum_13_5',
  'text': 'Найди сумму чисел 13 и 5.',
  'expected': ['Ответ: 18'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '18',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_sum_14_4',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_sum_14_4',
  'text': 'Найди сумму чисел 14 и 4.',
  'expected': ['Ответ: 18'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '18',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_diff_12_5',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_diff_12_5',
  'text': 'Найди разность чисел 12 и 5.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_diff_15_6',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_diff_15_6',
  'text': 'Найди разность чисел 15 и 6.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_diff_18_9',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_diff_18_9',
  'text': 'Найди разность чисел 18 и 9.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_diff_14_8',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_diff_14_8',
  'text': 'Найди разность чисел 14 и 8.',
  'expected': ['Ответ: 6'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '6',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_diff_19_7',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_diff_19_7',
  'text': 'Найди разность чисел 19 и 7.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_diff_16_4',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_diff_16_4',
  'text': 'Найди разность чисел 16 и 4.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_add_6_5',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_add_6_5',
  'text': 'Первое слагаемое 6, второе слагаемое 5. Найди сумму.',
  'expected': ['Ответ: 11'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_add_7_8',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_add_7_8',
  'text': 'Первое слагаемое 7, второе слагаемое 8. Найди сумму.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_add_9_4',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_add_9_4',
  'text': 'Первое слагаемое 9, второе слагаемое 4. Найди сумму.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_add_3_12',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_add_3_12',
  'text': 'Первое слагаемое 3, второе слагаемое 12. Найди сумму.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_add_10_6',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_add_10_6',
  'text': 'Первое слагаемое 10, второе слагаемое 6. Найди сумму.',
  'expected': ['Ответ: 16'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '16',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_sub_14_6',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_sub_14_6',
  'text': 'Уменьшаемое 14, вычитаемое 6. Найди разность.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_sub_17_8',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_sub_17_8',
  'text': 'Уменьшаемое 17, вычитаемое 8. Найди разность.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_sub_20_9',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_sub_20_9',
  'text': 'Уменьшаемое 20, вычитаемое 9. Найди разность.',
  'expected': ['Ответ: 11'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_sub_15_7',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_sub_15_7',
  'text': 'Уменьшаемое 15, вычитаемое 7. Найди разность.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_terms_sub_12_4',
  'grade': 1,
  'category': 'v287_g1_components',
  'name': 'v287_terms_sub_12_4',
  'text': 'Уменьшаемое 12, вычитаемое 4. Найди разность.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_result_plus_name',
  'grade': 1,
  'category': 'v287_g1_component_names',
  'name': 'v287_result_plus_name',
  'text': 'Как называется результат действия 6 + 4?',
  'expected': ['сумма'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'сумма',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_result_minus_name',
  'grade': 1,
  'category': 'v287_g1_component_names',
  'name': 'v287_result_minus_name',
  'text': 'Как называется результат действия 13 - 5?',
  'expected': ['разность'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'разность',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_check_subtraction_action',
  'grade': 1,
  'category': 'v287_g1_component_names',
  'name': 'v287_check_subtraction_action',
  'text': 'Каким действием проверяют вычитание?',
  'expected': ['сложением'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'сложением',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_add_6_to_13',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_add_6_to_13',
  'text': 'Какое число надо прибавить к 6, чтобы получить 13?',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_add_8_to_15',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_add_8_to_15',
  'text': 'Какое число надо прибавить к 8, чтобы получить 15?',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_add_9_to_17',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_add_9_to_17',
  'text': 'Какое число надо прибавить к 9, чтобы получить 17?',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_add_4_to_12',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_add_4_to_12',
  'text': 'Какое число надо прибавить к 4, чтобы получить 12?',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_add_7_to_16',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_add_7_to_16',
  'text': 'Какое число надо прибавить к 7, чтобы получить 16?',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_sub_from_14_to_9',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_sub_from_14_to_9',
  'text': 'Какое число надо вычесть из 14, чтобы получить 9?',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_sub_from_16_to_7',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_sub_from_16_to_7',
  'text': 'Какое число надо вычесть из 16, чтобы получить 7?',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_sub_from_18_to_8',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_sub_from_18_to_8',
  'text': 'Какое число надо вычесть из 18, чтобы получить 8?',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_sub_from_13_to_5',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_sub_from_13_to_5',
  'text': 'Какое число надо вычесть из 13, чтобы получить 5?',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_sub_from_20_to_11',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_sub_from_20_to_11',
  'text': 'Какое число надо вычесть из 20, чтобы получить 11?',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_minuend_4_9',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_minuend_4_9',
  'text': 'Из какого числа вычли 4 и получили 9?',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_minuend_7_8',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_minuend_7_8',
  'text': 'Из какого числа вычли 7 и получили 8?',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_minuend_5_12',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_minuend_5_12',
  'text': 'Из какого числа вычли 5 и получили 12?',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_minuend_6_6',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_minuend_6_6',
  'text': 'Из какого числа вычли 6 и получили 6?',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_missing_minuend_3_14',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_missing_minuend_3_14',
  'text': 'Из какого числа вычли 3 и получили 14?',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_unknown_added_5_12',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_unknown_added_5_12',
  'text': 'К 5 прибавили неизвестное число и получили 12. Найди неизвестное число.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_unknown_added_6_14',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_unknown_added_6_14',
  'text': 'К 6 прибавили неизвестное число и получили 14. Найди неизвестное число.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_unknown_added_8_17',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_unknown_added_8_17',
  'text': 'К 8 прибавили неизвестное число и получили 17. Найди неизвестное число.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_unknown_added_7_15',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_unknown_added_7_15',
  'text': 'К 7 прибавили неизвестное число и получили 15. Найди неизвестное число.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_unknown_added_9_18',
  'grade': 1,
  'category': 'v287_g1_missing_component',
  'name': 'v287_unknown_added_9_18',
  'text': 'К 9 прибавили неизвестное число и получили 18. Найди неизвестное число.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_x_plus_5_12',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_x_plus_5_12',
  'text': 'x + 5 = 12. Найди x.',
  'expected': ['x = 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_x_plus_4_9',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_x_plus_4_9',
  'text': 'x + 4 = 9. Найди x.',
  'expected': ['x = 5'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 5',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_x_plus_7_15',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_x_plus_7_15',
  'text': 'x + 7 = 15. Найди x.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_x_plus_8_16',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_x_plus_8_16',
  'text': 'x + 8 = 16. Найди x.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_plus_x_6_13',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_plus_x_6_13',
  'text': '6 + x = 13. Найди x.',
  'expected': ['x = 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_plus_x_9_17',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_plus_x_9_17',
  'text': '9 + x = 17. Найди x.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_plus_x_5_14',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_plus_x_5_14',
  'text': '5 + x = 14. Найди x.',
  'expected': ['x = 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_plus_x_3_11',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_plus_x_3_11',
  'text': '3 + x = 11. Найди x.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_x_minus_3_8',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_x_minus_3_8',
  'text': 'x - 3 = 8. Найди x.',
  'expected': ['x = 11'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 11',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_x_minus_5_7',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_x_minus_5_7',
  'text': 'x - 5 = 7. Найди x.',
  'expected': ['x = 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_x_minus_6_9',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_x_minus_6_9',
  'text': 'x - 6 = 9. Найди x.',
  'expected': ['x = 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_x_minus_4_12',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_x_minus_4_12',
  'text': 'x - 4 = 12. Найди x.',
  'expected': ['x = 16'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 16',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_minus_x_15_7',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_minus_x_15_7',
  'text': '15 - x = 7. Найди x.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_minus_x_18_9',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_minus_x_18_9',
  'text': '18 - x = 9. Найди x.',
  'expected': ['x = 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_minus_x_12_5',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_minus_x_12_5',
  'text': '12 - x = 5. Найди x.',
  'expected': ['x = 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_eq_minus_x_20_11',
  'grade': 1,
  'category': 'v287_g1_equations',
  'name': 'v287_eq_minus_x_20_11',
  'text': '20 - x = 11. Найди x.',
  'expected': ['x = 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_1',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_1',
  'text': 'Сравни выражения 7 + 4 и 15 - 3.',
  'expected': ['7 + 4 < 15 - 3'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7 + 4 < 15 - 3',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_2',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_2',
  'text': 'Сравни выражения 8 + 5 и 14 - 1.',
  'expected': ['8 + 5 = 14 - 1'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8 + 5 = 14 - 1',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_3',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_3',
  'text': 'Сравни выражения 9 + 2 и 18 - 5.',
  'expected': ['9 + 2 < 18 - 5'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9 + 2 < 18 - 5',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_4',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_4',
  'text': 'Сравни выражения 6 + 6 и 17 - 4.',
  'expected': ['6 + 6 < 17 - 4'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '6 + 6 < 17 - 4',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_5',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_5',
  'text': 'Сравни выражения 5 + 9 и 20 - 6.',
  'expected': ['5 + 9 = 20 - 6'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '5 + 9 = 20 - 6',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_6',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_6',
  'text': 'Сравни выражения 12 - 4 и 3 + 5.',
  'expected': ['12 - 4 = 3 + 5'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12 - 4 = 3 + 5',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_7',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_7',
  'text': 'Сравни выражения 16 - 7 и 2 + 8.',
  'expected': ['16 - 7 < 2 + 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '16 - 7 < 2 + 8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_8',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_8',
  'text': 'Сравни выражения 11 + 3 и 18 - 4.',
  'expected': ['11 + 3 = 18 - 4'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '11 + 3 = 18 - 4',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_9',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_9',
  'text': 'Сравни выражения 4 + 7 и 13 - 1.',
  'expected': ['4 + 7 < 13 - 1'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '4 + 7 < 13 - 1',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_compare_expr_10',
  'grade': 1,
  'category': 'v287_g1_expression_compare',
  'name': 'v287_compare_expr_10',
  'text': 'Сравни выражения 19 - 8 и 5 + 6.',
  'expected': ['19 - 8 = 5 + 6'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '19 - 8 = 5 + 6',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_1',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_1',
  'text': 'Вычисли цепочку: 3 + 4 + 2.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_2',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_2',
  'text': 'Вычисли цепочку: 10 - 3 + 5.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_3',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_3',
  'text': 'Вычисли цепочку: 8 + 2 - 6.',
  'expected': ['Ответ: 4'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '4',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_4',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_4',
  'text': 'Вычисли цепочку: 6 + 5 + 4.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_5',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_5',
  'text': 'Вычисли цепочку: 15 - 5 - 3.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_6',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_6',
  'text': 'Вычисли цепочку: 12 + 3 - 4.',
  'expected': ['Ответ: 11'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_7',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_7',
  'text': 'Вычисли цепочку: 7 + 6 - 5.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_8',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_8',
  'text': 'Вычисли цепочку: 20 - 8 + 2.',
  'expected': ['Ответ: 14'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_9',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_9',
  'text': 'Вычисли цепочку: 9 + 1 + 7.',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_chain_10',
  'grade': 1,
  'category': 'v287_g1_chains',
  'name': 'v287_chain_10',
  'text': 'Вычисли цепочку: 18 - 4 - 6.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_1',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_1',
  'text': 'Вычисли 8 + 0.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_2',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_2',
  'text': 'Вычисли 0 + 7.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_3',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_3',
  'text': 'Вычисли 12 - 0.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_4',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_4',
  'text': 'Вычисли 9 - 9.',
  'expected': ['Ответ: 0'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '0',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_5',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_5',
  'text': 'Вычисли 1 + 6.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_6',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_6',
  'text': 'Вычисли 14 - 1.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_7',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_7',
  'text': 'Вычисли 0 + 0.',
  'expected': ['Ответ: 0'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '0',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_8',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_8',
  'text': 'Вычисли 1 + 1.',
  'expected': ['Ответ: 2'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '2',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_9',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_9',
  'text': 'Вычисли 10 - 1.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_zero_one_10',
  'grade': 1,
  'category': 'v287_g1_zero_one',
  'name': 'v287_zero_one_10',
  'text': 'Вычисли 11 + 0.',
  'expected': ['Ответ: 11'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_true_false_1',
  'grade': 1,
  'category': 'v287_g1_true_false',
  'name': 'v287_true_false_1',
  'text': 'Верно ли: 8 + 5 = 13?',
  'expected': ['верно'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'верно',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_true_false_2',
  'grade': 1,
  'category': 'v287_g1_true_false',
  'name': 'v287_true_false_2',
  'text': 'Верно ли: 7 + 6 = 14?',
  'expected': ['неверно'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'неверно',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_true_false_3',
  'grade': 1,
  'category': 'v287_g1_true_false',
  'name': 'v287_true_false_3',
  'text': 'Верно ли: 15 - 7 = 8?',
  'expected': ['верно'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'верно',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_true_false_4',
  'grade': 1,
  'category': 'v287_g1_true_false',
  'name': 'v287_true_false_4',
  'text': 'Верно ли: 12 - 4 = 9?',
  'expected': ['неверно'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'неверно',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v287_true_false_5',
  'grade': 1,
  'category': 'v287_g1_true_false',
  'name': 'v287_true_false_5',
  'text': 'Верно ли: 9 + 9 = 18?',
  'expected': ['верно'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'верно',
  'expectedSourceFamily': 'local:live-v287',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']}]

DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v287_g1_arithmetic_actions_cases()


# --- v289 sequential programmatic live DeepSeek audit: 1 класс, раздел 1 — Числа и величины ---
def _v289_g1_numbers_values_live_deepseek_cases() -> list[dict[str, Any]]:
    return [{'id': 'v289_write_digit_0',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_0',
  'text': 'Запиши цифрой число ноль.',
  'expected': ['Ответ: 0'],
  'expectedNumericAnswer': 0,
  'expectedUnit': None,
  'expectedFinalAnswer': '0',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_1',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_1',
  'text': 'Запиши цифрой число один.',
  'expected': ['Ответ: 1'],
  'expectedNumericAnswer': 1,
  'expectedUnit': None,
  'expectedFinalAnswer': '1',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_2',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_2',
  'text': 'Запиши цифрой число два.',
  'expected': ['Ответ: 2'],
  'expectedNumericAnswer': 2,
  'expectedUnit': None,
  'expectedFinalAnswer': '2',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_3',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_3',
  'text': 'Запиши цифрой число три.',
  'expected': ['Ответ: 3'],
  'expectedNumericAnswer': 3,
  'expectedUnit': None,
  'expectedFinalAnswer': '3',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_4',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_4',
  'text': 'Запиши цифрой число четыре.',
  'expected': ['Ответ: 4'],
  'expectedNumericAnswer': 4,
  'expectedUnit': None,
  'expectedFinalAnswer': '4',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_5',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_5',
  'text': 'Запиши цифрой число пять.',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_6',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_6',
  'text': 'Запиши цифрой число шесть.',
  'expected': ['Ответ: 6'],
  'expectedNumericAnswer': 6,
  'expectedUnit': None,
  'expectedFinalAnswer': '6',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_7',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_7',
  'text': 'Запиши цифрой число семь.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_8',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_8',
  'text': 'Запиши цифрой число восемь.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_9',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_9',
  'text': 'Запиши цифрой число девять.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_12',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_12',
  'text': 'Запиши цифрой число двенадцать.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': 12,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_write_digit_20',
  'grade': 1,
  'category': 'v289_g1_numbers_write',
  'name': 'v289_write_digit_20',
  'text': 'Запиши цифрой число двадцать.',
  'expected': ['Ответ: 20'],
  'expectedNumericAnswer': 20,
  'expectedUnit': None,
  'expectedFinalAnswer': '20',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_read_number_0',
  'grade': 1,
  'category': 'v289_g1_numbers_read',
  'name': 'v289_read_number_0',
  'text': 'Как читается число 0?',
  'expected': ['ноль'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'ноль',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_read_number_3',
  'grade': 1,
  'category': 'v289_g1_numbers_read',
  'name': 'v289_read_number_3',
  'text': 'Как читается число 3?',
  'expected': ['три'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'три',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_read_number_5',
  'grade': 1,
  'category': 'v289_g1_numbers_read',
  'name': 'v289_read_number_5',
  'text': 'Как читается число 5?',
  'expected': ['пять'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'пять',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_read_number_8',
  'grade': 1,
  'category': 'v289_g1_numbers_read',
  'name': 'v289_read_number_8',
  'text': 'Как читается число 8?',
  'expected': ['восемь'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'восемь',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_read_number_10',
  'grade': 1,
  'category': 'v289_g1_numbers_read',
  'name': 'v289_read_number_10',
  'text': 'Как читается число 10?',
  'expected': ['десять'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'десять',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_read_number_11',
  'grade': 1,
  'category': 'v289_g1_numbers_read',
  'name': 'v289_read_number_11',
  'text': 'Как читается число 11?',
  'expected': ['одиннадцать'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'одиннадцать',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_read_number_14',
  'grade': 1,
  'category': 'v289_g1_numbers_read',
  'name': 'v289_read_number_14',
  'text': 'Как читается число 14?',
  'expected': ['четырнадцать'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'четырнадцать',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_read_number_19',
  'grade': 1,
  'category': 'v289_g1_numbers_read',
  'name': 'v289_read_number_19',
  'text': 'Как читается число 19?',
  'expected': ['девятнадцать'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'девятнадцать',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_write_10',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_write_10',
  'text': 'Запиши число, в котором 1 десяток и 0 единиц.',
  'expected': ['10'],
  'expectedNumericAnswer': 10,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_write_11',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_write_11',
  'text': 'Запиши число, в котором 1 десяток и 1 единиц.',
  'expected': ['11'],
  'expectedNumericAnswer': 11,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_write_12',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_write_12',
  'text': 'Запиши число, в котором 1 десяток и 2 единиц.',
  'expected': ['12'],
  'expectedNumericAnswer': 12,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_write_13',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_write_13',
  'text': 'Запиши число, в котором 1 десяток и 3 единиц.',
  'expected': ['13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_write_14',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_write_14',
  'text': 'Запиши число, в котором 1 десяток и 4 единиц.',
  'expected': ['14'],
  'expectedNumericAnswer': 14,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_write_15',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_write_15',
  'text': 'Запиши число, в котором 1 десяток и 5 единиц.',
  'expected': ['15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_write_16',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_write_16',
  'text': 'Запиши число, в котором 1 десяток и 6 единиц.',
  'expected': ['16'],
  'expectedNumericAnswer': 16,
  'expectedUnit': None,
  'expectedFinalAnswer': '16',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_write_17',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_write_17',
  'text': 'Запиши число, в котором 1 десяток и 7 единиц.',
  'expected': ['17'],
  'expectedNumericAnswer': 17,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_read_10',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_read_10',
  'text': 'В числе 10 сколько десятков и сколько единиц?',
  'expected': ['1 десят', '0'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 десяток и 0 единиц',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_read_11',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_read_11',
  'text': 'В числе 11 сколько десятков и сколько единиц?',
  'expected': ['1 десят', '1'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 десяток и 1 единица',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_read_12',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_read_12',
  'text': 'В числе 12 сколько десятков и сколько единиц?',
  'expected': ['1 десят', '2'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 десяток и 2 единицы',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_read_13',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_read_13',
  'text': 'В числе 13 сколько десятков и сколько единиц?',
  'expected': ['1 десят', '3'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 десяток и 3 единицы',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_read_14',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_read_14',
  'text': 'В числе 14 сколько десятков и сколько единиц?',
  'expected': ['1 десят', '4'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 десяток и 4 единицы',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_read_15',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_read_15',
  'text': 'В числе 15 сколько десятков и сколько единиц?',
  'expected': ['1 десят', '5'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 десяток и 5 единиц',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_read_16',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_read_16',
  'text': 'В числе 16 сколько десятков и сколько единиц?',
  'expected': ['1 десят', '6'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 десяток и 6 единиц',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_tens_units_read_18',
  'grade': 1,
  'category': 'v289_g1_tens_units',
  'name': 'v289_tens_units_read_18',
  'text': 'В числе 18 сколько десятков и сколько единиц?',
  'expected': ['1 десят', '8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 десяток и 8 единиц',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_3_7',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_3_7',
  'text': 'Сравни числа 3 и 7.',
  'expected': ['3 < 7'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '3 < 7',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_12_15',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_12_15',
  'text': 'Сравни числа 12 и 15.',
  'expected': ['12 < 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12 < 15',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_18_11',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_18_11',
  'text': 'Сравни числа 18 и 11.',
  'expected': ['18 > 11'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '18 > 11',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_9_9',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_9_9',
  'text': 'Сравни числа 9 и 9.',
  'expected': ['9 = 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9 = 9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_20_19',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_20_19',
  'text': 'Сравни числа 20 и 19.',
  'expected': ['20 > 19'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '20 > 19',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_14_17',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_14_17',
  'text': 'Сравни числа 14 и 17.',
  'expected': ['14 < 17'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '14 < 17',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_6_2',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_6_2',
  'text': 'Сравни числа 6 и 2.',
  'expected': ['6 > 2'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '6 > 2',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_10_13',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_10_13',
  'text': 'Сравни числа 10 и 13.',
  'expected': ['10 < 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '10 < 13',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_16_16',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_16_16',
  'text': 'Сравни числа 16 и 16.',
  'expected': ['16 = 16'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '16 = 16',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_8_5',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_8_5',
  'text': 'Сравни числа 8 и 5.',
  'expected': ['8 > 5'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8 > 5',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_1_4',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_1_4',
  'text': 'Сравни числа 1 и 4.',
  'expected': ['1 < 4'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 < 4',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_19_20',
  'grade': 1,
  'category': 'v289_g1_compare',
  'name': 'v289_compare_19_20',
  'text': 'Сравни числа 19 и 20.',
  'expected': ['19 < 20'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '19 < 20',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_choose_больше_4_9',
  'grade': 1,
  'category': 'v289_g1_compare_choice',
  'name': 'v289_choose_больше_4_9',
  'text': 'Какое число больше: 4 или 9?',
  'expected': ['9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_choose_меньше_4_9',
  'grade': 1,
  'category': 'v289_g1_compare_choice',
  'name': 'v289_choose_меньше_4_9',
  'text': 'Какое число меньше: 4 или 9?',
  'expected': ['4'],
  'expectedNumericAnswer': 4,
  'expectedUnit': None,
  'expectedFinalAnswer': '4',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_choose_больше_12_18',
  'grade': 1,
  'category': 'v289_g1_compare_choice',
  'name': 'v289_choose_больше_12_18',
  'text': 'Какое число больше: 12 или 18?',
  'expected': ['18'],
  'expectedNumericAnswer': 18,
  'expectedUnit': None,
  'expectedFinalAnswer': '18',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_choose_меньше_12_18',
  'grade': 1,
  'category': 'v289_g1_compare_choice',
  'name': 'v289_choose_меньше_12_18',
  'text': 'Какое число меньше: 12 или 18?',
  'expected': ['12'],
  'expectedNumericAnswer': 12,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_choose_больше_20_17',
  'grade': 1,
  'category': 'v289_g1_compare_choice',
  'name': 'v289_choose_больше_20_17',
  'text': 'Какое число больше: 20 или 17?',
  'expected': ['20'],
  'expectedNumericAnswer': 20,
  'expectedUnit': None,
  'expectedFinalAnswer': '20',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_choose_меньше_1_6',
  'grade': 1,
  'category': 'v289_g1_compare_choice',
  'name': 'v289_choose_меньше_1_6',
  'text': 'Какое число меньше: 1 или 6?',
  'expected': ['1'],
  'expectedNumericAnswer': 1,
  'expectedUnit': None,
  'expectedFinalAnswer': '1',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_after_5',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_after_5',
  'text': 'Какое число идет после 5?',
  'expected': ['6'],
  'expectedNumericAnswer': 6,
  'expectedUnit': None,
  'expectedFinalAnswer': '6',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_after_8',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_after_8',
  'text': 'Какое число идет после 8?',
  'expected': ['9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_after_12',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_after_12',
  'text': 'Какое число идет после 12?',
  'expected': ['13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_after_17',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_after_17',
  'text': 'Какое число идет после 17?',
  'expected': ['18'],
  'expectedNumericAnswer': 18,
  'expectedUnit': None,
  'expectedFinalAnswer': '18',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_before_6',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_before_6',
  'text': 'Какое число стоит перед 6?',
  'expected': ['5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_before_10',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_before_10',
  'text': 'Какое число стоит перед 10?',
  'expected': ['9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_before_15',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_before_15',
  'text': 'Какое число стоит перед 15?',
  'expected': ['14'],
  'expectedNumericAnswer': 14,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_before_20',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_before_20',
  'text': 'Какое число стоит перед 20?',
  'expected': ['19'],
  'expectedNumericAnswer': 19,
  'expectedUnit': None,
  'expectedFinalAnswer': '19',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_neighbors_5',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_neighbors_5',
  'text': 'Назови соседей числа 5.',
  'expected': ['4 и 6'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '4 и 6',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_neighbors_8',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_neighbors_8',
  'text': 'Назови соседей числа 8.',
  'expected': ['7 и 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7 и 9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_neighbors_14',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_neighbors_14',
  'text': 'Назови соседей числа 14.',
  'expected': ['13 и 15'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '13 и 15',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_between_2_4',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_between_2_4',
  'text': 'Какое число стоит между 2 и 4?',
  'expected': ['3'],
  'expectedNumericAnswer': 3,
  'expectedUnit': None,
  'expectedFinalAnswer': '3',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_between_7_9',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_between_7_9',
  'text': 'Какое число стоит между 7 и 9?',
  'expected': ['8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_between_13_15',
  'grade': 1,
  'category': 'v289_g1_sequence',
  'name': 'v289_between_13_15',
  'text': 'Какое число стоит между 13 и 15?',
  'expected': ['14'],
  'expectedNumericAnswer': 14,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_increase_4_3',
  'grade': 1,
  'category': 'v289_g1_number_change',
  'name': 'v289_increase_4_3',
  'text': 'Увеличь число 4 на 3.',
  'expected': ['7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_increase_8_5',
  'grade': 1,
  'category': 'v289_g1_number_change',
  'name': 'v289_increase_8_5',
  'text': 'Увеличь число 8 на 5.',
  'expected': ['13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_increase_12_4',
  'grade': 1,
  'category': 'v289_g1_number_change',
  'name': 'v289_increase_12_4',
  'text': 'Увеличь число 12 на 4.',
  'expected': ['16'],
  'expectedNumericAnswer': 16,
  'expectedUnit': None,
  'expectedFinalAnswer': '16',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_increase_15_2',
  'grade': 1,
  'category': 'v289_g1_number_change',
  'name': 'v289_increase_15_2',
  'text': 'Увеличь число 15 на 2.',
  'expected': ['17'],
  'expectedNumericAnswer': 17,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_decrease_9_4',
  'grade': 1,
  'category': 'v289_g1_number_change',
  'name': 'v289_decrease_9_4',
  'text': 'Уменьши число 9 на 4.',
  'expected': ['5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_decrease_14_3',
  'grade': 1,
  'category': 'v289_g1_number_change',
  'name': 'v289_decrease_14_3',
  'text': 'Уменьши число 14 на 3.',
  'expected': ['11'],
  'expectedNumericAnswer': 11,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_decrease_18_6',
  'grade': 1,
  'category': 'v289_g1_number_change',
  'name': 'v289_decrease_18_6',
  'text': 'Уменьши число 18 на 6.',
  'expected': ['12'],
  'expectedNumericAnswer': 12,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_decrease_20_5',
  'grade': 1,
  'category': 'v289_g1_number_change',
  'name': 'v289_decrease_20_5',
  'text': 'Уменьши число 20 на 5.',
  'expected': ['15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_more_by_12_7',
  'grade': 1,
  'category': 'v289_g1_difference',
  'name': 'v289_more_by_12_7',
  'text': 'На сколько 12 больше 7?',
  'expected': ['5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_more_by_18_9',
  'grade': 1,
  'category': 'v289_g1_difference',
  'name': 'v289_more_by_18_9',
  'text': 'На сколько 18 больше 9?',
  'expected': ['9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_less_by_6_15',
  'grade': 1,
  'category': 'v289_g1_difference',
  'name': 'v289_less_by_6_15',
  'text': 'На сколько 6 меньше 15?',
  'expected': ['9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_less_by_8_20',
  'grade': 1,
  'category': 'v289_g1_difference',
  'name': 'v289_less_by_8_20',
  'text': 'На сколько 8 меньше 20?',
  'expected': ['12'],
  'expectedNumericAnswer': 12,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_order_14_11_18_воз',
  'grade': 1,
  'category': 'v289_g1_order',
  'name': 'v289_order_14_11_18_воз',
  'text': 'Расположи числа 14, 11, 18 в порядке возрастания.',
  'expected': ['11, 14, 18'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '11, 14, 18',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_order_7_3_9_воз',
  'grade': 1,
  'category': 'v289_g1_order',
  'name': 'v289_order_7_3_9_воз',
  'text': 'Расположи числа 7, 3, 9 в порядке возрастания.',
  'expected': ['3, 7, 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '3, 7, 9',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_order_20_15_18_воз',
  'grade': 1,
  'category': 'v289_g1_order',
  'name': 'v289_order_20_15_18_воз',
  'text': 'Расположи числа 20, 15, 18 в порядке возрастания.',
  'expected': ['15, 18, 20'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '15, 18, 20',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_order_5_12_8_убы',
  'grade': 1,
  'category': 'v289_g1_order',
  'name': 'v289_order_5_12_8_убы',
  'text': 'Расположи числа 5, 12, 8 в порядке убывания.',
  'expected': ['12, 8, 5'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '12, 8, 5',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_order_13_19_16_убы',
  'grade': 1,
  'category': 'v289_g1_order',
  'name': 'v289_order_13_19_16_убы',
  'text': 'Расположи числа 13, 19, 16 в порядке убывания.',
  'expected': ['19, 16, 13'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '19, 16, 13',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_series_2_4_6',
  'grade': 1,
  'category': 'v289_g1_series',
  'name': 'v289_series_2_4_6',
  'text': 'Продолжи ряд: 2, 4, 6, ...',
  'expected': ['8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_series_5_10_15',
  'grade': 1,
  'category': 'v289_g1_series',
  'name': 'v289_series_5_10_15',
  'text': 'Продолжи ряд: 5, 10, 15, ...',
  'expected': ['20'],
  'expectedNumericAnswer': 20,
  'expectedUnit': None,
  'expectedFinalAnswer': '20',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_series_1_3_5',
  'grade': 1,
  'category': 'v289_g1_series',
  'name': 'v289_series_1_3_5',
  'text': 'Продолжи ряд: 1, 3, 5, ...',
  'expected': ['7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_series_4_8_12',
  'grade': 1,
  'category': 'v289_g1_series',
  'name': 'v289_series_4_8_12',
  'text': 'Продолжи ряд: 4, 8, 12, ...',
  'expected': ['16'],
  'expectedNumericAnswer': 16,
  'expectedUnit': None,
  'expectedFinalAnswer': '16',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_series_20_18_16',
  'grade': 1,
  'category': 'v289_g1_series',
  'name': 'v289_series_20_18_16',
  'text': 'Продолжи ряд: 20, 18, 16, ...',
  'expected': ['14'],
  'expectedNumericAnswer': 14,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_dm_cm_1_1',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_dm_cm_1_1',
  'text': 'Сколько сантиметров в 1 дм 1 см?',
  'expected': ['11', 'см'],
  'expectedNumericAnswer': 11,
  'expectedUnit': 'сантиметр',
  'expectedFinalAnswer': '11 сантиметров',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_dm_cm_1_2',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_dm_cm_1_2',
  'text': 'Сколько сантиметров в 1 дм 2 см?',
  'expected': ['12', 'см'],
  'expectedNumericAnswer': 12,
  'expectedUnit': 'сантиметр',
  'expectedFinalAnswer': '12 сантиметров',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_dm_cm_1_5',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_dm_cm_1_5',
  'text': 'Сколько сантиметров в 1 дм 5 см?',
  'expected': ['15', 'см'],
  'expectedNumericAnswer': 15,
  'expectedUnit': 'сантиметр',
  'expectedFinalAnswer': '15 сантиметров',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_dm_to_cm',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_dm_to_cm',
  'text': 'Сколько сантиметров в 1 дм?',
  'expected': ['10', 'см'],
  'expectedNumericAnswer': 10,
  'expectedUnit': 'сантиметр',
  'expectedFinalAnswer': '10 сантиметров',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_cm_to_dm_cm_14',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_cm_to_dm_cm_14',
  'text': '14 см - это сколько дециметров и сантиметров?',
  'expected': ['1 дм', '4 см'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 дм 4 см',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_cm_to_dm_cm_18',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_cm_to_dm_cm_18',
  'text': '18 см - это сколько дециметров и сантиметров?',
  'expected': ['1 дм', '8 см'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '1 дм 8 см',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_len_8_6',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_compare_len_8_6',
  'text': 'Сравни длины 8 см и 6 см.',
  'expected': ['8 см > 6 см'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '8 см > 6 см',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_compare_len_7_7',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_compare_len_7_7',
  'text': 'Сравни длины 7 см и 7 см.',
  'expected': ['7 см = 7 см'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7 см = 7 см',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_segment_longer_5_9',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_segment_longer_5_9',
  'text': 'Какой отрезок длиннее: 5 см или 9 см?',
  'expected': ['9 см'],
  'expectedNumericAnswer': 9,
  'expectedUnit': 'см',
  'expectedFinalAnswer': '9 см',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']},
 {'id': 'v289_ruler_2_8',
  'grade': 1,
  'category': 'v289_g1_lengths',
  'name': 'v289_ruler_2_8',
  'text': 'На линейке от 2 см до 8 см отметили отрезок. Какой он длины?',
  'expected': ['6 см'],
  'expectedNumericAnswer': 6,
  'expectedUnit': 'см',
  'expectedFinalAnswer': '6 см',
  'expectedSourceFamily': 'local:live-v285',
  'forbidden': ['Применяем правило:', 'lookup', 'answer map', 'generic fallback', 'deterministic regression', 'Zad3']}]

DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v289_g1_numbers_values_live_deepseek_cases()


# --- v296 live DeepSeek audit: 1 класс, раздел 2 — Арифметические действия ---

def _v296_g1_arithmetic_actions_live_deepseek_cases() -> list[dict[str, Any]]:
    return [{'id': 'v296_add10_2_3',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_2_3',
  'text': 'Вычисли 2 + 3.',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_4_5',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_4_5',
  'text': 'Вычисли 4 + 5.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_6_3',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_6_3',
  'text': 'Вычисли 6 + 3.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_7_2',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_7_2',
  'text': 'Вычисли 7 + 2.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_8_1',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_8_1',
  'text': 'Вычисли 8 + 1.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_5_5',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_5_5',
  'text': 'Вычисли 5 + 5.',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': 10,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_3_4',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_3_4',
  'text': 'Вычисли 3 + 4.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_2_6',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_2_6',
  'text': 'Вычисли 2 + 6.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_1_8',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_1_8',
  'text': 'Вычисли 1 + 8.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add10_4_4',
  'grade': 1,
  'category': 'v296_g1_direct_addition_10',
  'name': 'v296_add10_4_4',
  'text': 'Вычисли 4 + 4.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_9_4',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_9_4',
  'text': 'Вычисли 9 - 4.',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_8_3',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_8_3',
  'text': 'Вычисли 8 - 3.',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_7_2',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_7_2',
  'text': 'Вычисли 7 - 2.',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_6_6',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_6_6',
  'text': 'Вычисли 6 - 6.',
  'expected': ['Ответ: 0'],
  'expectedNumericAnswer': 0,
  'expectedUnit': None,
  'expectedFinalAnswer': '0',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_10_7',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_10_7',
  'text': 'Вычисли 10 - 7.',
  'expected': ['Ответ: 3'],
  'expectedNumericAnswer': 3,
  'expectedUnit': None,
  'expectedFinalAnswer': '3',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_5_2',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_5_2',
  'text': 'Вычисли 5 - 2.',
  'expected': ['Ответ: 3'],
  'expectedNumericAnswer': 3,
  'expectedUnit': None,
  'expectedFinalAnswer': '3',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_4_1',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_4_1',
  'text': 'Вычисли 4 - 1.',
  'expected': ['Ответ: 3'],
  'expectedNumericAnswer': 3,
  'expectedUnit': None,
  'expectedFinalAnswer': '3',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_9_8',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_9_8',
  'text': 'Вычисли 9 - 8.',
  'expected': ['Ответ: 1'],
  'expectedNumericAnswer': 1,
  'expectedUnit': None,
  'expectedFinalAnswer': '1',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_10_5',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_10_5',
  'text': 'Вычисли 10 - 5.',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub10_6_4',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_10',
  'name': 'v296_sub10_6_4',
  'text': 'Вычисли 6 - 4.',
  'expected': ['Ответ: 2'],
  'expectedNumericAnswer': 2,
  'expectedUnit': None,
  'expectedFinalAnswer': '2',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_9_4',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_9_4',
  'text': 'Вычисли 9 + 4.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_8_7',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_8_7',
  'text': 'Вычисли 8 + 7.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_6_8',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_6_8',
  'text': 'Вычисли 6 + 8.',
  'expected': ['Ответ: 14'],
  'expectedNumericAnswer': 14,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_7_6',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_7_6',
  'text': 'Вычисли 7 + 6.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_9_6',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_9_6',
  'text': 'Вычисли 9 + 6.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_3_8',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_3_8',
  'text': 'Вычисли 3 + 8.',
  'expected': ['Ответ: 11'],
  'expectedNumericAnswer': 11,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_4_9',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_4_9',
  'text': 'Вычисли 4 + 9.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_11_2',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_11_2',
  'text': 'Вычисли 11 + 2.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_12_3',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_12_3',
  'text': 'Вычисли 12 + 3.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_10_5',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_10_5',
  'text': 'Вычисли 10 + 5.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_13_4',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_13_4',
  'text': 'Вычисли 13 + 4.',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': 17,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_add20_14_5',
  'grade': 1,
  'category': 'v296_g1_direct_addition_20',
  'name': 'v296_add20_14_5',
  'text': 'Вычисли 14 + 5.',
  'expected': ['Ответ: 19'],
  'expectedNumericAnswer': 19,
  'expectedUnit': None,
  'expectedFinalAnswer': '19',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_13_5',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_13_5',
  'text': 'Вычисли 13 - 5.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_15_7',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_15_7',
  'text': 'Вычисли 15 - 7.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_16_9',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_16_9',
  'text': 'Вычисли 16 - 9.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_18_8',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_18_8',
  'text': 'Вычисли 18 - 8.',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': 10,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_20_6',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_20_6',
  'text': 'Вычисли 20 - 6.',
  'expected': ['Ответ: 14'],
  'expectedNumericAnswer': 14,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_17_9',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_17_9',
  'text': 'Вычисли 17 - 9.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_12_4',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_12_4',
  'text': 'Вычисли 12 - 4.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_19_5',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_19_5',
  'text': 'Вычисли 19 - 5.',
  'expected': ['Ответ: 14'],
  'expectedNumericAnswer': 14,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_14_6',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_14_6',
  'text': 'Вычисли 14 - 6.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_11_3',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_11_3',
  'text': 'Вычисли 11 - 3.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_10_8',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_10_8',
  'text': 'Вычисли 10 - 8.',
  'expected': ['Ответ: 2'],
  'expectedNumericAnswer': 2,
  'expectedUnit': None,
  'expectedFinalAnswer': '2',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sub20_20_11',
  'grade': 1,
  'category': 'v296_g1_direct_subtraction_20',
  'name': 'v296_sub20_20_11',
  'text': 'Вычисли 20 - 11.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_zero_add_7_0',
  'grade': 1,
  'category': 'v296_g1_zero_one',
  'name': 'v296_zero_add_7_0',
  'text': 'Вычисли 7 + 0.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_zero_add_0_9',
  'grade': 1,
  'category': 'v296_g1_zero_one',
  'name': 'v296_zero_add_0_9',
  'text': 'Вычисли 0 + 9.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_zero_sub_12_0',
  'grade': 1,
  'category': 'v296_g1_zero_one',
  'name': 'v296_zero_sub_12_0',
  'text': 'Вычисли 12 - 0.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': 12,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_zero_sub_8_8',
  'grade': 1,
  'category': 'v296_g1_zero_one',
  'name': 'v296_zero_sub_8_8',
  'text': 'Вычисли 8 - 8.',
  'expected': ['Ответ: 0'],
  'expectedNumericAnswer': 0,
  'expectedUnit': None,
  'expectedFinalAnswer': '0',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_one_add_9_1',
  'grade': 1,
  'category': 'v296_g1_zero_one',
  'name': 'v296_one_add_9_1',
  'text': 'Вычисли 9 + 1.',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': 10,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_one_k8_plus_1',
  'grade': 1,
  'category': 'v296_g1_zero_one',
  'name': 'v296_one_k8_plus_1',
  'text': 'К 8 прибавь 1.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_one_sub_15_1',
  'grade': 1,
  'category': 'v296_g1_zero_one',
  'name': 'v296_one_sub_15_1',
  'text': 'Вычисли 15 - 1.',
  'expected': ['Ответ: 14'],
  'expectedNumericAnswer': 14,
  'expectedUnit': None,
  'expectedFinalAnswer': '14',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_one_add_1_0',
  'grade': 1,
  'category': 'v296_g1_zero_one',
  'name': 'v296_one_add_1_0',
  'text': 'Вычисли 1 + 0.',
  'expected': ['Ответ: 1'],
  'expectedNumericAnswer': 1,
  'expectedUnit': None,
  'expectedFinalAnswer': '1',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_k_6_plus_4',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_k_6_plus_4',
  'text': 'К 6 прибавь 4.',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': 10,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_15_minus_6',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_15_minus_6',
  'text': 'Из 15 вычти 6.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_increase_8_5',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_increase_8_5',
  'text': 'Увеличь 8 на 5.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_decrease_17_8',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_decrease_17_8',
  'text': 'Уменьши 17 на 8.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_plus_to_9',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_plus_to_9',
  'text': 'Прибавь 3 к 9.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': 12,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_sub_from_14',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_sub_from_14',
  'text': 'Вычти 5 из 14.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_added_10_7',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_added_10_7',
  'text': 'Найди результат: к 10 прибавили 7.',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': 17,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_taken_18_9',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_taken_18_9',
  'text': 'Найди результат: от 18 отняли 9.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_how_much_7_plus_6',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_how_much_7_plus_6',
  'text': 'Сколько будет, если к 7 прибавить 6?',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_verb_how_much_16_minus_7',
  'grade': 1,
  'category': 'v296_g1_verbal_actions',
  'name': 'v296_verb_how_much_16_minus_7',
  'text': 'Сколько будет, если из 16 вычесть 7?',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sum_7_8',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_sum_7_8',
  'text': 'Найди сумму чисел 7 и 8.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sum_9_6',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_sum_9_6',
  'text': 'Найди сумму 9 и 6.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_diff_16_9',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_diff_16_9',
  'text': 'Найди разность чисел 16 и 9.',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_diff_20_8',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_diff_20_8',
  'text': 'Найди разность 20 и 8.',
  'expected': ['Ответ: 12'],
  'expectedNumericAnswer': 12,
  'expectedUnit': None,
  'expectedFinalAnswer': '12',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_terms_add_11_6',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_terms_add_11_6',
  'text': 'Первое слагаемое 11, второе слагаемое 6. Найди сумму.',
  'expected': ['Ответ: 17'],
  'expectedNumericAnswer': 17,
  'expectedUnit': None,
  'expectedFinalAnswer': '17',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_terms_sub_18_7',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_terms_sub_18_7',
  'text': 'Уменьшаемое 18, вычитаемое 7. Найди разность.',
  'expected': ['Ответ: 11'],
  'expectedNumericAnswer': 11,
  'expectedUnit': None,
  'expectedFinalAnswer': '11',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_name_result_plus',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_name_result_plus',
  'text': 'Как называется результат действия 6 + 4?',
  'expected': ['сумма'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'сумма',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_name_result_minus',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_name_result_minus',
  'text': 'Как называется результат действия 13 - 5?',
  'expected': ['разность'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'разность',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_name_terms',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_name_terms',
  'text': 'Как называются числа, которые складывают?',
  'expected': ['слагаемые'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'слагаемые',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_name_minuend',
  'grade': 1,
  'category': 'v296_g1_components',
  'name': 'v296_name_minuend',
  'text': 'Как называется число, из которого вычитают?',
  'expected': ['уменьшаемое'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'уменьшаемое',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_missing_add_6_to_13',
  'grade': 1,
  'category': 'v296_g1_missing_component_words',
  'name': 'v296_missing_add_6_to_13',
  'text': 'Какое число надо прибавить к 6, чтобы получить 13?',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_missing_add_8_to_15',
  'grade': 1,
  'category': 'v296_g1_missing_component_words',
  'name': 'v296_missing_add_8_to_15',
  'text': 'Какое число надо прибавить к 8, чтобы получить 15?',
  'expected': ['Ответ: 7'],
  'expectedNumericAnswer': 7,
  'expectedUnit': None,
  'expectedFinalAnswer': '7',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_missing_added_unknown_5_14',
  'grade': 1,
  'category': 'v296_g1_missing_component_words',
  'name': 'v296_missing_added_unknown_5_14',
  'text': 'К 5 прибавили неизвестное число и получили 14. Найди неизвестное число.',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_missing_added_unknown_9_17',
  'grade': 1,
  'category': 'v296_g1_missing_component_words',
  'name': 'v296_missing_added_unknown_9_17',
  'text': 'К 9 прибавили неизвестное число и получили 17. Найди неизвестное число.',
  'expected': ['Ответ: 8'],
  'expectedNumericAnswer': 8,
  'expectedUnit': None,
  'expectedFinalAnswer': '8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_missing_sub_from_14_to_9',
  'grade': 1,
  'category': 'v296_g1_missing_component_words',
  'name': 'v296_missing_sub_from_14_to_9',
  'text': 'Какое число надо вычесть из 14, чтобы получить 9?',
  'expected': ['Ответ: 5'],
  'expectedNumericAnswer': 5,
  'expectedUnit': None,
  'expectedFinalAnswer': '5',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_missing_sub_from_16_to_7',
  'grade': 1,
  'category': 'v296_g1_missing_component_words',
  'name': 'v296_missing_sub_from_16_to_7',
  'text': 'Какое число надо вычесть из 16, чтобы получить 7?',
  'expected': ['Ответ: 9'],
  'expectedNumericAnswer': 9,
  'expectedUnit': None,
  'expectedFinalAnswer': '9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_missing_minuend_6_13',
  'grade': 1,
  'category': 'v296_g1_missing_component_words',
  'name': 'v296_missing_minuend_6_13',
  'text': 'Из какого числа вычли 6 и получили 13?',
  'expected': ['Ответ: 19'],
  'expectedNumericAnswer': 19,
  'expectedUnit': None,
  'expectedFinalAnswer': '19',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_missing_minuend_8_7',
  'grade': 1,
  'category': 'v296_g1_missing_component_words',
  'name': 'v296_missing_minuend_8_7',
  'text': 'Из какого числа вычли 8 и получили 7?',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_eq_x_plus_5_13',
  'grade': 1,
  'category': 'v296_g1_simple_equations',
  'name': 'v296_eq_x_plus_5_13',
  'text': 'Реши уравнение: x + 5 = 13.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_eq_x_plus_7_16',
  'grade': 1,
  'category': 'v296_g1_simple_equations',
  'name': 'v296_eq_x_plus_7_16',
  'text': 'x + 7 = 16. Найди x.',
  'expected': ['x = 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_eq_6_plus_x_14',
  'grade': 1,
  'category': 'v296_g1_simple_equations',
  'name': 'v296_eq_6_plus_x_14',
  'text': 'Реши уравнение: 6 + x = 14.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_eq_9_plus_x_17',
  'grade': 1,
  'category': 'v296_g1_simple_equations',
  'name': 'v296_eq_9_plus_x_17',
  'text': '9 + x = 17. Найди x.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_eq_x_minus_4_8',
  'grade': 1,
  'category': 'v296_g1_simple_equations',
  'name': 'v296_eq_x_minus_4_8',
  'text': 'Реши уравнение: x - 4 = 8.',
  'expected': ['x = 12'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 12',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_eq_x_minus_7_9',
  'grade': 1,
  'category': 'v296_g1_simple_equations',
  'name': 'v296_eq_x_minus_7_9',
  'text': 'x - 7 = 9. Найди x.',
  'expected': ['x = 16'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 16',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_eq_15_minus_x_6',
  'grade': 1,
  'category': 'v296_g1_simple_equations',
  'name': 'v296_eq_15_minus_x_6',
  'text': 'Реши уравнение: 15 - x = 6.',
  'expected': ['x = 9'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 9',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_eq_18_minus_x_10',
  'grade': 1,
  'category': 'v296_g1_simple_equations',
  'name': 'v296_eq_18_minus_x_10',
  'text': '18 - x = 10. Найди x.',
  'expected': ['x = 8'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'x = 8',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_cmp_7p5_8p3',
  'grade': 1,
  'category': 'v296_g1_expression_compare',
  'name': 'v296_cmp_7p5_8p3',
  'text': 'Сравни выражения 7 + 5 и 8 + 3.',
  'expected': ['7 + 5 > 8 + 3'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '7 + 5 > 8 + 3',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_cmp_9p2_15m4',
  'grade': 1,
  'category': 'v296_g1_expression_compare',
  'name': 'v296_cmp_9p2_15m4',
  'text': 'Сравни выражения 9 + 2 и 15 - 4.',
  'expected': ['9 + 2 = 15 - 4'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '9 + 2 = 15 - 4',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_cmp_14m6_3p6',
  'grade': 1,
  'category': 'v296_g1_expression_compare',
  'name': 'v296_cmp_14m6_3p6',
  'text': 'Сравни выражения 14 - 6 и 3 + 6.',
  'expected': ['14 - 6 < 3 + 6'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '14 - 6 < 3 + 6',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_cmp_10p7_20m2',
  'grade': 1,
  'category': 'v296_g1_expression_compare',
  'name': 'v296_cmp_10p7_20m2',
  'text': 'Сравни выражения 10 + 7 и 20 - 2.',
  'expected': ['10 + 7 < 20 - 2'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '10 + 7 < 20 - 2',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sign_6p8_17m4',
  'grade': 1,
  'category': 'v296_g1_expression_compare',
  'name': 'v296_sign_6p8_17m4',
  'text': 'Поставь знак: 6 + 8 ? 17 - 4.',
  'expected': ['>'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '>',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_sign_12m5_2p5',
  'grade': 1,
  'category': 'v296_g1_expression_compare',
  'name': 'v296_sign_12m5_2p5',
  'text': 'Поставь знак: 12 - 5 ? 2 + 5.',
  'expected': ['='],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': '=',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_chain_3_4_2_5',
  'grade': 1,
  'category': 'v296_g1_calculation_chains',
  'name': 'v296_chain_3_4_2_5',
  'text': 'Вычисли цепочку: 3 + 4 - 2 + 5.',
  'expected': ['Ответ: 10'],
  'expectedNumericAnswer': 10,
  'expectedUnit': None,
  'expectedFinalAnswer': '10',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_chain_10_3_6',
  'grade': 1,
  'category': 'v296_g1_calculation_chains',
  'name': 'v296_chain_10_3_6',
  'text': 'Вычисли цепочку: 10 - 3 + 6.',
  'expected': ['Ответ: 13'],
  'expectedNumericAnswer': 13,
  'expectedUnit': None,
  'expectedFinalAnswer': '13',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_chain_12_5_2',
  'grade': 1,
  'category': 'v296_g1_calculation_chains',
  'name': 'v296_chain_12_5_2',
  'text': 'Пройди цепочку: 12 + 5 - 2.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_chain_20_8_3',
  'grade': 1,
  'category': 'v296_g1_calculation_chains',
  'name': 'v296_chain_20_8_3',
  'text': 'Пройди цепочку: 20 - 8 + 3.',
  'expected': ['Ответ: 15'],
  'expectedNumericAnswer': 15,
  'expectedUnit': None,
  'expectedFinalAnswer': '15',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_true_8p5_13',
  'grade': 1,
  'category': 'v296_g1_true_false',
  'name': 'v296_true_8p5_13',
  'text': 'Верно ли: 8 + 5 = 13?',
  'expected': ['верно'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'верно',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']},
 {'id': 'v296_false_14m6_7',
  'grade': 1,
  'category': 'v296_g1_true_false',
  'name': 'v296_false_14m6_7',
  'text': 'Верно ли: 14 - 6 = 7?',
  'expected': ['неверно'],
  'expectedNumericAnswer': None,
  'expectedUnit': None,
  'expectedFinalAnswer': 'неверно',
  'expectedSourceFamily': None,
  'forbidden': ['Применяем правило:',
                'lookup',
                'answer map',
                'generic fallback',
                'deterministic regression',
                'Zad3',
                '```',
                '<html',
                '<!doctype',
                '</']}]

DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v296_g1_arithmetic_actions_live_deepseek_cases()


_V297_NAME_CASE_MAP = {
    'маши': 'Маши', 'оли': 'Оли', 'пети': 'Пети', 'вани': 'Вани', 'иры': 'Иры', 'светы': 'Светы',
    'лены': 'Лены', 'юли': 'Юли', 'веры': 'Веры', 'зои': 'Зои', 'ромы': 'Ромы', 'димы': 'Димы',
    'нины': 'Нины', 'лизы': 'Лизы', 'дани': 'Дани', 'бори': 'Бори', 'максима': 'Максима', 'артема': 'Артема',
    'кати': 'Кати', 'саши': 'Саши'
}


def _style_v297_case_text(text: str) -> str:
    styled = str(text or '')
    for low, cap in _V297_NAME_CASE_MAP.items():
        styled = re.sub(rf'\b{low}\b', cap, styled, flags=re.IGNORECASE)
    return styled


def _v297_g1_text_problems_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:',
        'lookup',
        'answer map',
        'generic fallback',
        'deterministic regression',
        'Zad3',
        '```',
        '<html',
        '<!doctype',
        '</',
    ]
    forms = {
        'яблоко': ('яблоко', 'яблока', 'яблок'),
        'гриб': ('гриб', 'гриба', 'грибов'),
        'карандаш': ('карандаш', 'карандаша', 'карандашей'),
        'тетрадь': ('тетрадь', 'тетради', 'тетрадей'),
        'конфета': ('конфета', 'конфеты', 'конфет'),
        'книга': ('книга', 'книги', 'книг'),
        'марка': ('марка', 'марки', 'марок'),
        'шар': ('шар', 'шара', 'шаров'),
        'кукла': ('кукла', 'куклы', 'кукол'),
        'мяч': ('мяч', 'мяча', 'мячей'),
    }
    item_genders = {
        'яблоко': 'n',
        'гриб': 'm',
        'карандаш': 'm',
        'тетрадь': 'f',
        'конфета': 'f',
        'книга': 'f',
        'марка': 'f',
        'шар': 'm',
        'кукла': 'f',
        'мяч': 'm',
    }

    def word(n: int, item: str) -> str:
        one, few, many = forms[item]
        n = abs(int(n)) % 100
        if 11 <= n <= 14:
            return many
        tail = n % 10
        if tail == 1:
            return one
        if 2 <= tail <= 4:
            return few
        return many

    def count(n: int, item: str) -> str:
        return f'{int(n)} {word(int(n), item)}'

    object_forms_one = {
        'яблоко': 'яблоко',
        'гриб': 'гриб',
        'карандаш': 'карандаш',
        'тетрадь': 'тетрадь',
        'конфета': 'конфету',
        'книга': 'книгу',
        'марка': 'марку',
        'шар': 'шар',
        'кукла': 'куклу',
        'мяч': 'мяч',
    }

    def count_object(n: int, item: str) -> str:
        if int(n) == 1:
            return f'1 {object_forms_one[item]}'
        return count(n, item)

    def had_sentence(name: str, n: int, item: str) -> str:
        item_text = count(n, item)
        if int(n) == 1:
            gender = item_genders[item]
            verb = 'был' if gender == 'm' else 'была' if gender == 'f' else 'было'
            return f'У {name} {verb} {item_text}.'
        return f'У {name} было {item_text}.'

    def make_case(
        case_id: str,
        category: str,
        text: str,
        final_answer: str,
        *,
        number: int | None = None,
        unit: str | None = None,
        expected_source: str | None = None,
        should_warn: bool = False,
    ) -> dict[str, Any]:
        expected = [f'Ответ: {final_answer}']
        return {
            'id': case_id,
            'grade': 1,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': expected,
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final_answer,
            'expectedSource': expected_source,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': should_warn,
        }

    cases: list[dict[str, Any]] = []

    add_data = [
        ('v297_add_story_01', 'маши', 5, 'яблоко', 3),
        ('v297_add_story_02', 'оли', 4, 'конфета', 2),
        ('v297_add_story_03', 'пети', 6, 'карандаш', 3),
        ('v297_add_story_04', 'иры', 7, 'книга', 2),
        ('v297_add_story_05', 'лены', 8, 'тетрадь', 1),
        ('v297_add_story_06', 'вани', 3, 'мяч', 4),
        ('v297_add_story_07', 'кати', 2, 'кукла', 5),
        ('v297_add_story_08', 'саши', 9, 'марка', 1),
        ('v297_add_story_09', 'нины', 1, 'шар', 8),
        ('v297_add_story_10', 'димы', 5, 'гриб', 4),
        ('v297_add_story_11', 'веры', 10, 'яблоко', 2),
        ('v297_add_story_12', 'ромы', 6, 'мяч', 5),
        ('v297_add_story_13', 'лизы', 4, 'книга', 6),
        ('v297_add_story_14', 'артема', 7, 'карандаш', 5),
        ('v297_add_story_15', 'юли', 3, 'конфета', 7),
        ('v297_add_story_16', 'дани', 2, 'марка', 9),
        ('v297_add_story_17', 'светы', 8, 'тетрадь', 4),
        ('v297_add_story_18', 'бори', 5, 'шар', 6),
        ('v297_add_story_19', 'зои', 9, 'кукла', 2),
        ('v297_add_story_20', 'максима', 6, 'гриб', 7),
    ]
    add_verbs = [
        'Дали ещё {delta} {item}.',
        'Мама купила ещё {delta} {item}.',
        'Друг подарил {delta} {item}.',
        'Принесли ещё {delta} {item}.',
        'Добавили ещё {delta} {item}.',
    ]
    for idx, (case_id, name, base_n, item, delta_n) in enumerate(add_data):
        verb = add_verbs[idx % len(add_verbs)].format(delta=delta_n, item=count_object(delta_n, item).split(' ', 1)[1])
        text = f'{had_sentence(name, base_n, item)} {verb} Сколько {forms[item][2]} стало у {name}?'
        total = base_n + delta_n
        final = f'У {name[:1].upper() + name[1:]} стало {count(total, item)}'
        cases.append(make_case(case_id, 'v297_g1_text_addition_story', text, final, number=total, unit=forms[item][2]))

    sub_data = [
        ('v297_sub_story_01', 'пети', 9, 'карандаш', 4),
        ('v297_sub_story_02', 'маши', 8, 'яблоко', 3),
        ('v297_sub_story_03', 'оли', 7, 'конфета', 2),
        ('v297_sub_story_04', 'кати', 10, 'книга', 5),
        ('v297_sub_story_05', 'вани', 6, 'мяч', 1),
        ('v297_sub_story_06', 'иры', 12, 'тетрадь', 4),
        ('v297_sub_story_07', 'саши', 11, 'марка', 3),
        ('v297_sub_story_08', 'зои', 5, 'кукла', 2),
        ('v297_sub_story_09', 'димы', 13, 'шар', 6),
        ('v297_sub_story_10', 'веры', 9, 'гриб', 4),
        ('v297_sub_story_11', 'юли', 14, 'яблоко', 5),
        ('v297_sub_story_12', 'ромы', 15, 'карандаш', 7),
        ('v297_sub_story_13', 'лизы', 8, 'книга', 6),
        ('v297_sub_story_14', 'дани', 16, 'тетрадь', 8),
        ('v297_sub_story_15', 'бори', 17, 'марка', 9),
        ('v297_sub_story_16', 'нины', 10, 'кукла', 7),
        ('v297_sub_story_17', 'светы', 18, 'шар', 8),
        ('v297_sub_story_18', 'максима', 19, 'мяч', 9),
        ('v297_sub_story_19', 'артема', 11, 'гриб', 5),
        ('v297_sub_story_20', 'лены', 20, 'конфета', 10),
    ]
    sub_verbs = [
        'Отдали другу {delta} {item}.',
        'Подарили {delta} {item}.',
        'Убрали {delta} {item}.',
        'Взяли {delta} {item}.',
        'Забрали {delta} {item}.',
    ]
    for idx, (case_id, name, base_n, item, delta_n) in enumerate(sub_data):
        verb = sub_verbs[idx % len(sub_verbs)].format(delta=delta_n, item=count_object(delta_n, item).split(' ', 1)[1])
        text = f'У {name} было {count(base_n, item)}. {verb} Сколько {forms[item][2]} осталось у {name}?'
        left = base_n - delta_n
        final = f'У {name[:1].upper() + name[1:]} осталось {count(left, item)}'
        cases.append(make_case(case_id, 'v297_g1_text_subtraction_story', text, final, number=left, unit=forms[item][2]))

    diff_data = [
        ('v297_diff_story_01', 'оли', 8, 'кати', 5, 'марка', 'больше'),
        ('v297_diff_story_02', 'иры', 6, 'светы', 9, 'книга', 'меньше'),
        ('v297_diff_story_03', 'маши', 10, 'оли', 7, 'яблоко', 'больше'),
        ('v297_diff_story_04', 'пети', 4, 'вани', 11, 'карандаш', 'меньше'),
        ('v297_diff_story_05', 'лены', 12, 'юли', 9, 'тетрадь', 'больше'),
        ('v297_diff_story_06', 'веры', 3, 'зои', 8, 'кукла', 'меньше'),
        ('v297_diff_story_07', 'димы', 13, 'ромы', 6, 'мяч', 'больше'),
        ('v297_diff_story_08', 'нины', 5, 'лизы', 14, 'конфета', 'меньше'),
        ('v297_diff_story_09', 'дани', 7, 'бори', 2, 'шар', 'больше'),
        ('v297_diff_story_10', 'максима', 4, 'артема', 10, 'гриб', 'меньше'),
        ('v297_diff_story_11', 'саши', 15, 'пети', 6, 'марка', 'больше'),
        ('v297_diff_story_12', 'оли', 11, 'маши', 16, 'шар', 'меньше'),
        ('v297_diff_story_13', 'юли', 18, 'лены', 8, 'яблоко', 'больше'),
        ('v297_diff_story_14', 'зои', 9, 'веры', 12, 'конфета', 'меньше'),
        ('v297_diff_story_15', 'ромы', 17, 'димы', 13, 'мяч', 'больше'),
        ('v297_diff_story_16', 'лизы', 10, 'нины', 3, 'книга', 'больше'),
        ('v297_diff_story_17', 'бори', 6, 'дани', 15, 'гриб', 'меньше'),
        ('v297_diff_story_18', 'артема', 14, 'максима', 5, 'карандаш', 'больше'),
        ('v297_diff_story_19', 'кати', 7, 'иры', 11, 'тетрадь', 'меньше'),
        ('v297_diff_story_20', 'светы', 12, 'оли', 4, 'кукла', 'больше'),
    ]
    for case_id, name1, first, name2, second, item, kind in diff_data:
        text = f'У {name1} {count(first, item)}, у {name2} {count(second, item)}. На сколько {forms[item][2]} у {name1} {kind}, чем у {name2}?'
        diff = abs(first - second)
        final = f'У {name1[:1].upper() + name1[1:]} на {count(diff, item)} {kind}, чем у {name2[:1].upper() + name2[1:]}'
        cases.append(make_case(case_id, 'v297_g1_text_difference_compare', text, final, number=diff, unit=forms[item][2]))

    rel_data = [
        ('v297_relation_01', 'веры', 6, 'димы', 2, 'конфета', 'меньше'),
        ('v297_relation_02', 'оли', 8, 'кати', 3, 'яблоко', 'больше'),
        ('v297_relation_03', 'пети', 5, 'вани', 4, 'карандаш', 'меньше'),
        ('v297_relation_04', 'иры', 7, 'светы', 2, 'книга', 'больше'),
        ('v297_relation_05', 'лены', 9, 'юли', 5, 'тетрадь', 'меньше'),
        ('v297_relation_06', 'зои', 4, 'веры', 3, 'кукла', 'больше'),
        ('v297_relation_07', 'ромы', 10, 'димы', 6, 'мяч', 'меньше'),
        ('v297_relation_08', 'нины', 3, 'лизы', 7, 'конфета', 'больше'),
        ('v297_relation_09', 'дани', 11, 'бори', 2, 'шар', 'меньше'),
        ('v297_relation_10', 'максима', 5, 'артема', 4, 'гриб', 'больше'),
    ]
    for case_id, name1, base_n, name2, delta_n, item, kind in rel_data:
        text = f'У {name1} {count(base_n, item)}, у {name2} на {count(delta_n, item)} {kind}. Сколько {forms[item][2]} у {name2}?'
        value = base_n + delta_n if kind == 'больше' else base_n - delta_n
        final = f'У {name2[:1].upper() + name2[1:]} {count(value, item)}'
        cases.append(make_case(case_id, 'v297_g1_text_relation_story', text, final, number=value, unit=forms[item][2]))

    total_data = [
        ('v297_total_01', 'маши', 5, 'оли', 2, 'яблоко'),
        ('v297_total_02', 'пети', 4, 'вани', 3, 'карандаш'),
        ('v297_total_03', 'иры', 6, 'светы', 1, 'книга'),
        ('v297_total_04', 'лены', 7, 'юли', 5, 'тетрадь'),
        ('v297_total_05', 'веры', 8, 'зои', 4, 'конфета'),
        ('v297_total_06', 'ромы', 2, 'димы', 9, 'мяч'),
        ('v297_total_07', 'нины', 3, 'лизы', 8, 'шар'),
        ('v297_total_08', 'дани', 10, 'бори', 6, 'марка'),
        ('v297_total_09', 'максима', 1, 'артема', 7, 'гриб'),
        ('v297_total_10', 'кати', 9, 'оли', 5, 'кукла'),
    ]
    for case_id, name1, first, name2, second, item in total_data:
        text = f'У {name1} {count(first, item)}, у {name2} {count(second, item)}. Сколько всего {forms[item][2]}?'
        total = first + second
        final = f'Всего {count(total, item)}'
        cases.append(make_case(case_id, 'v297_g1_text_total_two_subjects', text, final, number=total, unit=forms[item][2]))

    extra_data = [
        ('v297_extra_01', 'У маши было 5 яблок. Кошка спала на окне. Ей дали ещё 3 яблока. Сколько яблок стало у маши?', 'У Маши стало 8 яблок', 8, 'яблок'),
        ('v297_extra_02', 'У пети было 9 карандашей. На улице шёл дождь. Он отдал другу 4 карандаша. Сколько карандашей осталось у пети?', 'У Пети осталось 5 карандашей', 5, 'карандашей'),
        ('v297_extra_03', 'У Оли 8 марок, у Кати 5 марок. Девочки рисовали. На сколько марок у Оли больше, чем у Кати?', 'У Оли на 3 марки больше, чем у Кати', 3, 'марок'),
        ('v297_extra_04', 'У Веры 6 конфет, у Димы на 2 конфеты меньше. На столе лежала книга. Сколько конфет у Димы?', 'У Димы 4 конфеты', 4, 'конфет'),
        ('v297_extra_05', 'У Маши 5 яблок, у Оли 2 яблока. За окном снег. Сколько всего яблок?', 'Всего 7 яблок', 7, 'яблок'),
        ('v297_extra_06', 'У Иры было 7 книг. В комнате тихо. Друг подарил 2 книги. Сколько книг стало у Иры?', 'У Иры стало 9 книг', 9, 'книг'),
        ('v297_extra_07', 'У Юли было 8 тетрадей. На стене часы. Она подарила 3 тетради. Сколько тетрадей осталось у Юли?', 'У Юли осталось 5 тетрадей', 5, 'тетрадей'),
        ('v297_extra_08', 'У Ромы 10 мячей, у Димы 6 мячей. Мальчики гуляли. На сколько мячей у Ромы больше, чем у Димы?', 'У Ромы на 4 мяча больше, чем у Димы', 4, 'мячей'),
        ('v297_extra_09', 'У Нины 3 шара, у Лизы 8 шаров. Птица сидела на ветке. Сколько всего шаров?', 'Всего 11 шаров', 11, 'шаров'),
        ('v297_extra_10', 'У Максима было 6 грибов. В корзине лежал лист. Мама купила ещё 7 грибов. Сколько грибов стало у Максима?', 'У Максима стало 13 грибов', 13, 'грибов'),
    ]
    for case_id, text, final, number, unit in extra_data:
        cases.append(make_case(case_id, 'v297_g1_text_extra_text', text, final, number=number, unit=unit))

    guard_cases = [
        ('v297_guard_incomplete_01', 'У Лены было 7 тетрадей. Мама купила ещё тетради. Сколько тетрадей стало у Лены?', 'guard-low-confidence'),
        ('v297_guard_incomplete_02', 'У Пети было несколько карандашей. Он отдал 2 карандаша. Сколько карандашей осталось у Пети?', 'guard-low-confidence'),
        ('v297_guard_incomplete_03', 'У Оли было 5 яблок. Ей дали ещё яблоки. Сколько яблок стало у Оли?', 'guard-low-confidence'),
        ('v297_guard_incomplete_04', 'У Иры было 9 книг. Подруга подарила ещё книги. Сколько книг стало у Иры?', 'guard-low-confidence'),
        ('v297_guard_incomplete_05', 'У Вани было 8 мячей. Он отдал мячи. Сколько мячей осталось у Вани?', 'guard-low-confidence'),
        ('v297_guard_no_question_01', 'У Маши было 5 яблок. Ей дали ещё 3 яблока.', 'guard-low-confidence'),
        ('v297_guard_no_question_02', 'У Пети было 9 карандашей. Он отдал другу 4 карандаша.', 'guard-low-confidence'),
        ('v297_guard_no_question_03', 'У Оли было 8 марок, у Кати было 5 марок.', 'guard-low-confidence'),
        ('v297_guard_multi_01', 'У Маши было 5 яблок. Ей дали ещё 3 яблока. Сколько яблок стало у Маши?\nУ Пети было 9 карандашей. Он отдал 4 карандаша. Сколько карандашей осталось у Пети?', 'guard-multi-task'),
        ('v297_guard_multi_02', 'Вычисли 2 + 3.\nУ Маши было 5 яблок. Ей дали ещё 3 яблока. Сколько яблок стало у Маши?', 'guard-multi-task'),
    ]
    for case_id, text, source in guard_cases:
        if source == 'guard-multi-task':
            final = 'Разделите задания и отправьте их по отдельности'
        else:
            final = 'нужно уточнить условие задачи'
        cases.append(make_case(
            case_id,
            'v297_g1_text_problem_guards',
            text,
            final,
            expected_source=source,
            should_warn=(source == 'guard-multi-task'),
        ))

    for case in cases:
        if case.get('category', '').startswith('v297_') or case.get('id', '').startswith('v297_'):
            case['text'] = _style_v297_case_text(case.get('text', ''))

    quality_problems: list[str] = []
    female_names = 'Маши|Оли|Иры|Лены|Кати|Юли|Веры|Зои|Нины|Лизы|Светы'
    male_names = 'Пети|Вани|Саши|Димы|Ромы|Дани|Бори|Максима|Артема'
    for case in cases:
        if case.get('category') != 'v297_g1_text_addition_story':
            continue
        rendered = str(case.get('text', ''))
        if re.search(rf'У ({female_names}) .*?\bЕму\b', rendered):
            quality_problems.append(f"{case.get('id')}: feminine story uses masculine pronoun")
        if re.search(rf'У ({male_names}) .*?\bЕй\b', rendered):
            quality_problems.append(f"{case.get('id')}: masculine story uses feminine pronoun")
        if re.search(r'\bбыло 1 (шар|карандаш|мяч|гриб)\b', rendered, flags=re.IGNORECASE):
            quality_problems.append(f"{case.get('id')}: masculine singular should use был")
        if re.search(r'\bбыло 1 (книга|тетрадь|конфета|марка|кукла)\b', rendered, flags=re.IGNORECASE):
            quality_problems.append(f"{case.get('id')}: feminine singular should use была")
    if quality_problems:
        raise AssertionError('V297 text case quality errors: ' + '; '.join(quality_problems[:10]))

    lower_name_markers = ['У маши', 'У оли', 'У пети', 'У вани', 'У иры', 'У светы', 'У лены', 'У юли', 'У веры', 'У зои', 'У ромы', 'У димы', 'У нины', 'У лизы', 'У дани', 'У бори', 'У максима', 'У артема', 'У кати', 'У саши']
    for case in cases:
        case_text = str(case.get('text') or '')
        for marker in lower_name_markers:
            if marker in case_text:
                raise AssertionError(f"V297 case text capitalization error: {marker} in {case.get('id')}")

    bad_case_phrases = [
        'Она отдал ',
        'Он отдала ',
        'Он подарила ',
        'Она подарил ',
        'Он взяла ',
        'Она взял ',
        'Он забрала ',
        'Она забрал ',
    ]
    object_case_bad_pattern = re.compile(
        r'(?:Дали ещё|Мама купила ещё|Друг подарил|Принесли ещё|Добавили ещё|Отдали другу|Подарили|Убрали|Взяли|Забрали) 1 (марка|книга|конфета|кукла)\.',
        flags=re.IGNORECASE,
    )
    for case in cases:
        case_text = str(case.get('text') or '')
        for bad in bad_case_phrases:
            if bad in case_text:
                raise AssertionError(f'V297 case text quality error: {bad} in {case.get("id")}')
        if object_case_bad_pattern.search(case_text):
            raise AssertionError(f'V297 feminine singular object form error in {case.get("id")}')

    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v297_g1_text_problems_live_ui_cases()



# --- v298 live UI audit: 1 класс, раздел 4 — Геометрия и пространственные отношения ---

def _v298_g1_geometry_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:',
        'lookup',
        'answer map',
        'generic fallback',
        'deterministic regression',
        'Zad3',
        '```',
        '<html',
        '<!doctype',
        '</',
    ]

    def make_case(
        case_id: str,
        category: str,
        text: str,
        final_answer: str,
        *,
        number: int | None = None,
        unit: str | None = None,
    ) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 1,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final_answer}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final_answer,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    def row_line(figures: list[str]) -> str:
        return 'Слева направо стоят ' + ', '.join(figures) + '.'

    def col_line(figures: list[str]) -> str:
        return 'Сверху вниз расположены ' + ', '.join(figures) + '.'

    figure_genitive = {
        'круг': 'круга',
        'квадрат': 'квадрата',
        'треугольник': 'треугольника',
        'прямоугольник': 'прямоугольника',
        'отрезок': 'отрезка',
    }
    figure_instrumental = {
        'круг': 'кругом',
        'квадрат': 'квадратом',
        'треугольник': 'треугольником',
        'прямоугольник': 'прямоугольником',
        'отрезок': 'отрезком',
    }

    def fig_genitive(name: str) -> str:
        return figure_genitive.get(name, name)

    def fig_instrumental(name: str) -> str:
        return figure_instrumental.get(name, name)

    cases: list[dict[str, Any]] = []

    row_cases = [
        ('v298_spatial_row_01', ['круг', 'квадрат', 'треугольник'], 'between', 'круг', 'треугольник', 'квадрат'),
        ('v298_spatial_row_02', ['квадрат', 'круг', 'прямоугольник'], 'right', 'круг', None, 'прямоугольник'),
        ('v298_spatial_row_03', ['треугольник', 'прямоугольник', 'круг'], 'left', 'прямоугольник', None, 'треугольник'),
        ('v298_spatial_row_04', ['круг', 'прямоугольник', 'квадрат', 'треугольник'], 'between', 'прямоугольник', 'треугольник', 'квадрат'),
        ('v298_spatial_row_05', ['квадрат', 'треугольник', 'круг', 'прямоугольник'], 'between', 'квадрат', 'круг', 'треугольник'),
        ('v298_spatial_row_06', ['треугольник', 'круг', 'квадрат', 'прямоугольник'], 'right', 'квадрат', None, 'прямоугольник'),
        ('v298_spatial_row_07', ['прямоугольник', 'круг', 'треугольник', 'квадрат'], 'left', 'круг', None, 'прямоугольник'),
        ('v298_spatial_row_08', ['квадрат', 'прямоугольник', 'круг', 'треугольник'], 'between', 'квадрат', 'круг', 'прямоугольник'),
        ('v298_spatial_row_09', ['круг', 'квадрат', 'прямоугольник', 'треугольник'], 'right', 'прямоугольник', None, 'треугольник'),
        ('v298_spatial_row_10', ['треугольник', 'квадрат', 'круг', 'прямоугольник'], 'left', 'круг', None, 'квадрат'),
        ('v298_spatial_row_11', ['прямоугольник', 'треугольник', 'круг'], 'between', 'прямоугольник', 'круг', 'треугольник'),
        ('v298_spatial_row_12', ['круг', 'треугольник', 'квадрат'], 'right', 'круг', None, 'треугольник'),
        ('v298_spatial_row_13', ['квадрат', 'круг', 'треугольник'], 'left', 'треугольник', None, 'круг'),
        ('v298_spatial_row_14', ['треугольник', 'прямоугольник', 'квадрат'], 'between', 'треугольник', 'квадрат', 'прямоугольник'),
        ('v298_spatial_row_15', ['круг', 'прямоугольник', 'треугольник'], 'left', 'треугольник', None, 'прямоугольник'),
    ]
    for case_id, figures, kind, ref1, ref2, answer in row_cases:
        if kind == 'between':
            text = f"{row_line(figures)} Какая фигура между {fig_instrumental(ref1)} и {fig_instrumental(ref2)}?"
        elif kind == 'left':
            text = f"{row_line(figures)} Какая фигура слева от {fig_genitive(ref1)}?"
        else:
            text = f"{row_line(figures)} Какая фигура справа от {fig_genitive(ref1)}?"
        cases.append(make_case(case_id, 'v298_g1_spatial_row', text, answer))

    column_cases = [
        ('v298_spatial_col_01', ['круг', 'квадрат', 'треугольник'], 'above', 'квадрат', 'круг'),
        ('v298_spatial_col_02', ['прямоугольник', 'круг', 'квадрат'], 'below', 'круг', 'квадрат'),
        ('v298_spatial_col_03', ['треугольник', 'прямоугольник', 'круг', 'квадрат'], 'above', 'круг', 'прямоугольник'),
        ('v298_spatial_col_04', ['квадрат', 'круг', 'прямоугольник', 'треугольник'], 'below', 'квадрат', 'круг'),
        ('v298_spatial_col_05', ['круг', 'треугольник', 'квадрат', 'прямоугольник'], 'below', 'квадрат', 'прямоугольник'),
        ('v298_spatial_col_06', ['прямоугольник', 'квадрат', 'круг'], 'below', 'квадрат', 'круг'),
        ('v298_spatial_col_07', ['треугольник', 'круг', 'прямоугольник'], 'above', 'прямоугольник', 'круг'),
        ('v298_spatial_col_08', ['квадрат', 'прямоугольник', 'треугольник'], 'above', 'треугольник', 'прямоугольник'),
        ('v298_spatial_col_09', ['круг', 'прямоугольник', 'треугольник'], 'below', 'круг', 'прямоугольник'),
        ('v298_spatial_col_10', ['треугольник', 'квадрат', 'круг', 'прямоугольник'], 'above', 'круг', 'квадрат'),
    ]
    for case_id, figures, kind, ref, answer in column_cases:
        if kind == 'above':
            text = f"{col_line(figures)} Какая фигура выше {fig_genitive(ref)}?"
        else:
            text = f"{col_line(figures)} Какая фигура ниже {fig_genitive(ref)}?"
        cases.append(make_case(case_id, 'v298_g1_spatial_column', text, answer))

    inside_cases = [
        ('v298_inside_01', 'Внутри квадрата круг, а вне квадрата треугольник. Какая фигура внутри квадрата?', 'круг'),
        ('v298_inside_02', 'Внутри круга квадрат, а вне круга прямоугольник. Какая фигура вне круга?', 'прямоугольник'),
        ('v298_inside_03', 'Внутри прямоугольника треугольник, а вне прямоугольника круг. Какая фигура внутри прямоугольника?', 'треугольник'),
        ('v298_inside_04', 'Внутри квадрата прямоугольник, а вне квадрата круг. Какая фигура вне квадрата?', 'круг'),
        ('v298_inside_05', 'Внутри круга треугольник, а вне круга квадрат. Какая фигура внутри круга?', 'треугольник'),
        ('v298_inside_06', 'Внутри прямоугольника круг, а вне прямоугольника треугольник. Какая фигура вне прямоугольника?', 'треугольник'),
        ('v298_inside_07', 'Внутри квадрата треугольник, а вне квадрата прямоугольник. Какая фигура внутри квадрата?', 'треугольник'),
        ('v298_inside_08', 'Внутри круга прямоугольник, а вне круга треугольник. Какая фигура вне круга?', 'треугольник'),
        ('v298_inside_09', 'Внутри прямоугольника квадрат, а вне прямоугольника круг. Какая фигура внутри прямоугольника?', 'квадрат'),
        ('v298_inside_10', 'Внутри квадрата круг, а вне квадрата прямоугольник. Какая фигура вне квадрата?', 'прямоугольник'),
    ]
    for case_id, text, answer in inside_cases:
        cases.append(make_case(case_id, 'v298_g1_spatial_inside_outside', text, answer))

    property_cases = [
        ('v298_shape_01', 'Какая фигура без углов: круг, квадрат или треугольник?', 'круг', None, None),
        ('v298_shape_02', 'Какая фигура имеет 3 угла: круг, треугольник или квадрат?', 'треугольник', None, None),
        ('v298_shape_03', 'Какая фигура имеет 4 угла и 4 равные стороны: квадрат или прямоугольник?', 'квадрат', None, None),
        ('v298_shape_04', 'Как называется часть прямой с двумя концами?', 'отрезок', None, None),
        ('v298_shape_05', 'Какая фигура имеет 3 стороны: квадрат, треугольник или круг?', 'треугольник', None, None),
        ('v298_shape_06', 'Какая фигура имеет две длинные и две короткие стороны: квадрат или прямоугольник?', 'прямоугольник', None, None),
        ('v298_shape_07', 'Сколько углов у треугольника?', '3', 3, None),
        ('v298_shape_08', 'Сколько углов у квадрата?', '4', 4, None),
        ('v298_shape_09', 'Сколько сторон у прямоугольника?', '4', 4, None),
        ('v298_shape_10', 'Сколько углов у круга?', '0', 0, None),
        ('v298_shape_11', 'Сколько сторон у треугольника?', '3', 3, None),
        ('v298_shape_12', 'Какая фигура без углов: прямоугольник, квадрат или круг?', 'круг', None, None),
        ('v298_shape_13', 'Какая фигура имеет 4 угла и 4 равные стороны: прямоугольник, квадрат или треугольник?', 'квадрат', None, None),
        ('v298_shape_14', 'Назови часть прямой с двумя концами.', 'отрезок', None, None),
        ('v298_shape_15', 'Какая фигура имеет 3 угла: круг, прямоугольник или треугольник?', 'треугольник', None, None),
        ('v298_shape_16', 'Сколько сторон у квадрата?', '4', 4, None),
        ('v298_shape_17', 'Сколько концов у отрезка?', '2', 2, None),
        ('v298_shape_18', 'Сколько углов у прямоугольника?', '4', 4, None),
        ('v298_shape_19', 'Что называют частью прямой с двумя концами?', 'отрезок', None, None),
        ('v298_shape_20', 'Какая фигура имеет 4 одинаковые стороны и 4 угла: квадрат или прямоугольник?', 'квадрат', None, None),
    ]
    for case_id, text, answer, number, unit in property_cases:
        cases.append(make_case(case_id, 'v298_g1_shape_property', text, answer, number=number, unit=unit))

    segment_cases = [
        ('v298_segment_01', 'Длина отрезка AB 6 см. Какова длина отрезка AB?', '6 см', 6, 'см'),
        ('v298_segment_02', 'Длина отрезка CD 8 см. Какова длина отрезка CD?', '8 см', 8, 'см'),
        ('v298_segment_03', 'Длина отрезка AB 7 см, а длина отрезка CD 4 см. На сколько сантиметров отрезок AB длиннее отрезка CD?', '3 см', 3, 'см'),
        ('v298_segment_04', 'Длина отрезка EF 9 см, а длина отрезка GH 5 см. На сколько сантиметров отрезок EF длиннее отрезка GH?', '4 см', 4, 'см'),
        ('v298_segment_05', 'Длина отрезка 6 см. Его увеличили на 2 см. Какой стала длина отрезка?', '8 см', 8, 'см'),
        ('v298_segment_06', 'Длина отрезка 8 см. Его увеличили на 1 см. Какой стала длина отрезка?', '9 см', 9, 'см'),
        ('v298_segment_07', 'Длина отрезка 9 см. Его уменьшили на 4 см. Какой стала длина отрезка?', '5 см', 5, 'см'),
        ('v298_segment_08', 'Длина отрезка 7 см. Его уменьшили на 3 см. Какой стала длина отрезка?', '4 см', 4, 'см'),
        ('v298_segment_09', 'Длина отрезка MN 8 см, а длина отрезка PQ 5 см. На сколько сантиметров отрезок MN длиннее отрезка PQ?', '3 см', 3, 'см'),
        ('v298_segment_10', 'Длина отрезка RS 10 см, а длина отрезка TU 6 см. На сколько сантиметров отрезок RS длиннее отрезка TU?', '4 см', 4, 'см'),
        ('v298_segment_11', 'Длина отрезка KL 3 см, а длина отрезка XY 3 см. На сколько сантиметров отрезок KL длиннее отрезка XY?', '0 см', 0, 'см'),
        ('v298_segment_12', 'Длина отрезка 4 см. Его увеличили на 4 см. Какой стала длина отрезка?', '8 см', 8, 'см'),
        ('v298_segment_13', 'Длина отрезка 12 см. Его уменьшили на 5 см. Какой стала длина отрезка?', '7 см', 7, 'см'),
        ('v298_segment_14', 'Длина отрезка EF 11 см. Какова длина отрезка EF?', '11 см', 11, 'см'),
        ('v298_segment_15', 'Длина отрезка GH 13 см, а длина отрезка IJ 9 см. На сколько сантиметров отрезок GH длиннее отрезка IJ?', '4 см', 4, 'см'),
        ('v298_segment_16', 'Длина отрезка 2 см. Его увеличили на 5 см. Какой стала длина отрезка?', '7 см', 7, 'см'),
        ('v298_segment_17', 'Длина отрезка 14 см. Его уменьшили на 6 см. Какой стала длина отрезка?', '8 см', 8, 'см'),
        ('v298_segment_18', 'Длина отрезка WX 15 см, а длина отрезка YZ 10 см. На сколько сантиметров отрезок WX длиннее отрезка YZ?', '5 см', 5, 'см'),
        ('v298_segment_19', 'Длина отрезка 1 см. Его увеличили на 2 см. Какой стала длина отрезка?', '3 см', 3, 'см'),
        ('v298_segment_20', 'Длина отрезка 18 см. Его уменьшили на 9 см. Какой стала длина отрезка?', '9 см', 9, 'см'),
    ]
    for case_id, text, answer, number, unit in segment_cases:
        cases.append(make_case(case_id, 'v298_g1_segment_length', text, answer, number=number, unit=unit))

    route_cases = [
        ('v298_route_01', 'На клетчатом листе старт в клетке Б2. Сделай 1 клетку вправо. В какой клетке окажешься?', 'Б3'),
        ('v298_route_02', 'На клетчатом листе старт в клетке В3. Сделай 1 клетку влево. В какой клетке окажешься?', 'В2'),
        ('v298_route_03', 'На клетчатом листе старт в клетке Г2. Сделай 1 клетку вверх. В какой клетке окажешься?', 'В2'),
        ('v298_route_04', 'На клетчатом листе старт в клетке Б4. Сделай 1 клетку вниз. В какой клетке окажешься?', 'В4'),
        ('v298_route_05', 'На клетчатом листе старт в клетке В2. Сделай 2 клетки вправо. В какой клетке окажешься?', 'В4'),
        ('v298_route_06', 'На клетчатом листе старт в клетке Г4. Сделай 2 клетки влево. В какой клетке окажешься?', 'Г2'),
        ('v298_route_07', 'На клетчатом листе старт в клетке В3. Сделай 2 клетки вверх. В какой клетке окажешься?', 'А3'),
        ('v298_route_08', 'На клетчатом листе старт в клетке Б1. Сделай 2 клетки вниз. В какой клетке окажешься?', 'Г1'),
        ('v298_route_09', 'На клетчатом листе старт в клетке В2. Сделай 1 клетку вправо и 1 клетку вниз. В какой клетке окажешься?', 'Г3'),
        ('v298_route_10', 'На клетчатом листе старт в клетке Г3. Сделай 1 клетку влево и 1 клетку вверх. В какой клетке окажешься?', 'В2'),
        ('v298_route_11', 'На клетчатом листе старт в клетке Б3. Сделай 2 клетки вправо и 1 клетку вниз. В какой клетке окажешься?', 'В5'),
        ('v298_route_12', 'На клетчатом листе старт в клетке Г5. Сделай 2 клетки влево и 1 клетку вверх. В какой клетке окажешься?', 'В3'),
        ('v298_route_13', 'На клетчатом листе старт в клетке Д2. Сделай 1 клетку вверх и 1 клетку вправо. В какой клетке окажешься?', 'Г3'),
        ('v298_route_14', 'На клетчатом листе старт в клетке А4. Сделай 1 клетку вниз и 2 клетки влево. В какой клетке окажешься?', 'Б2'),
        ('v298_route_15', 'На клетчатом листе старт в клетке В1. Сделай 3 клетки вправо. В какой клетке окажешься?', 'В4'),
        ('v298_route_16', 'На клетчатом листе старт в клетке Б5. Сделай 2 клетки влево. В какой клетке окажешься?', 'Б3'),
        ('v298_route_17', 'На клетчатом листе старт в клетке Г1. Сделай 2 клетки вправо и 1 клетку вверх. В какой клетке окажешься?', 'В3'),
        ('v298_route_18', 'На клетчатом листе старт в клетке В4. Сделай 1 клетку влево и 2 клетки вниз. В какой клетке окажешься?', 'Д3'),
        ('v298_route_19', 'На клетчатом листе старт в клетке Б2. Сделай 1 клетку вверх и 1 клетку вправо. В какой клетке окажешься?', 'А3'),
        ('v298_route_20', 'На клетчатом листе старт в клетке Г4. Сделай 1 клетку вниз и 1 клетку влево. В какой клетке окажешься?', 'Д3'),
        ('v298_route_21', 'На клетчатом листе старт в клетке В3. Сделай 1 клетку вправо и 1 клетку вправо и 1 клетку вверх. В какой клетке окажешься?', 'Б5'),
        ('v298_route_22', 'На клетчатом листе старт в клетке Д4. Сделай 2 клетки вверх и 1 клетку влево. В какой клетке окажешься?', 'В3'),
        ('v298_route_23', 'На клетчатом листе старт в клетке А2. Сделай 2 клетки вниз и 2 клетки вправо. В какой клетке окажешься?', 'В4'),
        ('v298_route_24', 'На клетчатом листе старт в клетке Г2. Сделай 1 клетку вверх и 1 клетку вверх и 1 клетку вправо. В какой клетке окажешься?', 'Б3'),
        ('v298_route_25', 'На клетчатом листе старт в клетке В5. Сделай 1 клетку влево и 1 клетку вниз. В какой клетке окажешься?', 'Г4'),
    ]
    for case_id, text, answer in route_cases:
        cases.append(make_case(case_id, 'v298_g1_grid_route', text, answer))

    if len(cases) != 100:
        raise AssertionError(f'V298 cases expected 100, got {len(cases)}')
    seen_texts: set[str] = set()
    for case in cases:
        text_value = str(case.get('text') or '')
        if text_value in seen_texts:
            raise AssertionError(f'V298 duplicate case text: {text_value}')
        seen_texts.add(text_value)
        if '  ' in text_value:
            raise AssertionError(f'V298 case text has double spaces: {case.get("id")}')
        if not text_value[:1].isupper():
            raise AssertionError(f'V298 case text should start with uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v298_g1_geometry_live_ui_cases()


def _v299_g1_math_information_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:',
        'lookup',
        'answer map',
        'generic fallback',
        'deterministic regression',
        'Zad3',
        '```',
        '<html',
        '<!doctype',
        '</',
    ]
    item_forms = {
        'яблоко': ('яблоко', 'яблока', 'яблок'),
        'груша': ('груша', 'груши', 'груш'),
        'книга': ('книга', 'книги', 'книг'),
        'карандаш': ('карандаш', 'карандаша', 'карандашей'),
        'шар': ('шар', 'шара', 'шаров'),
        'гриб': ('гриб', 'гриба', 'грибов'),
        'конфета': ('конфета', 'конфеты', 'конфет'),
        'кубик': ('кубик', 'кубика', 'кубиков'),
        'флажок': ('флажок', 'флажка', 'флажков'),
        'машинка': ('машинка', 'машинки', 'машинок'),
        'звезда': ('звезда', 'звезды', 'звёзд'),
        'наклейка': ('наклейка', 'наклейки', 'наклеек'),
        'предмет': ('предмет', 'предмета', 'предметов'),
    }

    def word(n: int, item: str) -> str:
        one, few, many = item_forms[item]
        n = abs(int(n)) % 100
        if 11 <= n <= 14:
            return many
        tail = n % 10
        if tail == 1:
            return one
        if 2 <= tail <= 4:
            return few
        return many

    def count(n: int, item: str) -> str:
        return f'{int(n)} {word(int(n), item)}'

    def make_case(case_id: str, category: str, text: str, final_answer: str, *, number: int | None = None, unit: str | None = None, expected_source: str | None = None, should_warn: bool = False) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 1,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final_answer}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final_answer,
            'expectedSource': expected_source,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': should_warn,
        }

    cases: list[dict[str, Any]] = []

    table_text_rows = [
        ('v299_table_text_01', 'Таблица уроков', [('Урок 1', 'чтение'), ('Урок 2', 'математика'), ('Урок 3', 'музыка')], 'Урок 2'),
        ('v299_table_text_02', 'Таблица кружков', [('Строка А', 'конструктор'), ('Строка Б', 'мозаика'), ('Строка В', 'лепка')], 'Строка В'),
        ('v299_table_text_03', 'Таблица дел', [('Дело 1', 'полив'), ('Дело 2', 'уборка'), ('Дело 3', 'чтение')], 'Дело 1'),
        ('v299_table_text_04', 'Таблица дежурств', [('Парта 1', 'Аня'), ('Парта 2', 'Оля'), ('Парта 3', 'Дима')], 'Парта 3'),
        ('v299_table_text_05', 'Таблица занятий', [('Час 1', 'письмо'), ('Час 2', 'рисование'), ('Час 3', 'лепка')], 'Час 2'),
        ('v299_table_text_06', 'Таблица библиотеки', [('Полка А', 'сказки'), ('Полка Б', 'стихи'), ('Полка В', 'энциклопедия')], 'Полка Б'),
        ('v299_table_text_07', 'Таблица меню', [('Строка 1', 'суп'), ('Строка 2', 'каша'), ('Строка 3', 'компот')], 'Строка 1'),
        ('v299_table_text_08', 'Таблица кабинетов', [('Кабинет 1', 'шахматы'), ('Кабинет 2', 'рисование'), ('Кабинет 3', 'музыка')], 'Кабинет 2'),
        ('v299_table_text_09', 'Таблица игр', [('Игра 1', 'домино'), ('Игра 2', 'лото'), ('Игра 3', 'мемо')], 'Игра 3'),
        ('v299_table_text_10', 'Таблица станций', [('Станция А', 'лес'), ('Станция Б', 'луг'), ('Станция В', 'река')], 'Станция Б'),
    ]
    for case_id, title, rows, target in table_text_rows[:5]:
        block = '; '.join(f'{key} — {value}' for key, value in rows)
        text = f'{title}: {block}. Что записано напротив строки {target}?'
        value = dict(rows)[target]
        final = f'Напротив строки {target} — {value}'
        cases.append(make_case(case_id, 'v299_g1_table_lookup_text', text, final))

    table_num_rows = [
        ('v299_table_num_01', 'Таблица книг', [('Полка А', count(3, 'книга')), ('Полка Б', count(5, 'книга')), ('Полка В', count(2, 'книга'))], 'Полка Б', 5, 'книг'),
        ('v299_table_num_02', 'Таблица кубиков', [('Коробка 1', count(4, 'кубик')), ('Коробка 2', count(6, 'кубик')), ('Коробка 3', count(1, 'кубик'))], 'Коробка 2', 6, 'кубиков'),
        ('v299_table_num_03', 'Таблица флажков', [('Ряд 1', count(2, 'флажок')), ('Ряд 2', count(7, 'флажок')), ('Ряд 3', count(5, 'флажок'))], 'Ряд 1', 2, 'флажка'),
        ('v299_table_num_04', 'Таблица машинок', [('Полка 1', count(3, 'машинка')), ('Полка 2', count(4, 'машинка')), ('Полка 3', count(8, 'машинка'))], 'Полка 3', 8, 'машинок'),
        ('v299_table_num_05', 'Таблица звёзд', [('Строка А', count(9, 'звезда')), ('Строка Б', count(6, 'звезда')), ('Строка В', count(3, 'звезда'))], 'Строка В', 3, 'звезды'),
        ('v299_table_num_06', 'Таблица наклеек', [('Ряд А', count(5, 'наклейка')), ('Ряд Б', count(2, 'наклейка')), ('Ряд В', count(4, 'наклейка'))], 'Ряд А', 5, 'наклеек'),
        ('v299_table_num_07', 'Таблица карандашей', [('Пенал 1', count(7, 'карандаш')), ('Пенал 2', count(1, 'карандаш')), ('Пенал 3', count(6, 'карандаш'))], 'Пенал 2', 1, 'карандаш'),
        ('v299_table_num_08', 'Таблица яблок', [('Корзина А', count(8, 'яблоко')), ('Корзина Б', count(3, 'яблоко')), ('Корзина В', count(5, 'яблоко'))], 'Корзина В', 5, 'яблок'),
        ('v299_table_num_09', 'Таблица конфет', [('Пачка 1', count(4, 'конфета')), ('Пачка 2', count(9, 'конфета')), ('Пачка 3', count(6, 'конфета'))], 'Пачка 2', 9, 'конфет'),
        ('v299_table_num_10', 'Таблица шаров', [('Связка А', count(2, 'шар')), ('Связка Б', count(5, 'шар')), ('Связка В', count(7, 'шар'))], 'Связка А', 2, 'шара'),
    ]
    for case_id, title, rows, target, number, unit in table_num_rows:
        block = '; '.join(f'{key} — {value}' for key, value in rows)
        text = f'{title}: {block}. Что записано напротив строки {target}?'
        value = dict(rows)[target]
        final = f'Напротив строки {target} — {value}'
        cases.append(make_case(case_id, 'v299_g1_table_lookup_number', text, final, number=number, unit=unit))

    pict_single = [
        ('v299_pic_single_01', '★', 2, 'яблоко', 'Лены', 3),
        ('v299_pic_single_02', '●', 3, 'груша', 'Оли', 2),
        ('v299_pic_single_03', '■', 2, 'книга', 'Пети', 4),
        ('v299_pic_single_04', '▲', 1, 'карандаш', 'Иры', 5),
        ('v299_pic_single_05', '◆', 2, 'шар', 'Вани', 3),
        ('v299_pic_single_06', '★', 3, 'гриб', 'Димы', 2),
        ('v299_pic_single_07', '●', 2, 'конфета', 'Кати', 4),
        ('v299_pic_single_08', '■', 1, 'кубик', 'Зои', 6),
        ('v299_pic_single_09', '▲', 2, 'флажок', 'Ромы', 3),
        ('v299_pic_single_10', '◆', 1, 'машинка', 'Юли', 5),
    ]
    for case_id, symbol, mult, item, name, symbol_count in pict_single:
        signs = symbol * symbol_count
        total = mult * symbol_count
        text = f'Пиктограмма: {symbol} = {count(mult, item)}. У {name} {signs}. Сколько {item_forms[item][2]} у {name}?'
        final = f'У {name} {count(total, item)}'
        cases.append(make_case(case_id, 'v299_g1_pictogram_single', text, final, number=total, unit=item_forms[item][2]))

    pict_total = [
        ('v299_pic_total_01', '★', 2, 'яблоко', ('Лены', 2), ('Оли', 3)),
        ('v299_pic_total_02', '●', 3, 'груша', ('Пети', 1), ('Иры', 2)),
        ('v299_pic_total_03', '■', 2, 'книга', ('Вани', 4), ('Димы', 1)),
        ('v299_pic_total_04', '▲', 1, 'карандаш', ('Кати', 3), ('Юли', 5)),
        ('v299_pic_total_05', '◆', 2, 'шар', ('Ромы', 2), ('Зои', 2)),
        ('v299_pic_total_06', '★', 3, 'гриб', ('Нины', 1), ('Лизы', 2)),
        ('v299_pic_total_07', '●', 2, 'конфета', ('Саши', 3), ('Веры', 4)),
        ('v299_pic_total_08', '■', 1, 'кубик', ('Бори', 6), ('Дани', 1)),
        ('v299_pic_total_09', '▲', 2, 'флажок', ('Максима', 2), ('Артёма', 3)),
        ('v299_pic_total_10', '◆', 1, 'машинка', ('Светы', 4), ('Маши', 2)),
    ]
    for case_id, symbol, mult, item, first, second in pict_total:
        name1, c1 = first
        name2, c2 = second
        total = mult * (c1 + c2)
        text = f'Пиктограмма: {symbol} = {count(mult, item)}. У {name1} {symbol * c1}, у {name2} {symbol * c2}. Сколько {item_forms[item][2]} всего?'
        final = f'Всего {count(total, item)}'
        cases.append(make_case(case_id, 'v299_g1_pictogram_total', text, final, number=total, unit=item_forms[item][2]))

    picture_cases = [
        ('v299_picture_01', 'На рисунке 3 красных шарика и 2 синих шарика. Сколько предметов всего на рисунке?', 5),
        ('v299_picture_02', 'На рисунке 4 яблока и 1 груша. Сколько предметов всего на рисунке?', 5),
        ('v299_picture_03', 'На рисунке 2 книги и 3 карандаша. Сколько предметов всего на рисунке?', 5),
        ('v299_picture_04', 'На рисунке 5 грибов и 2 листа. Сколько предметов всего на рисунке?', 7),
        ('v299_picture_05', 'На рисунке 6 кубиков и 1 машинка. Сколько предметов всего на рисунке?', 7),
    ]
    for case_id, text, total in picture_cases:
        final = f'На рисунке {count(total, "предмет")}'
        cases.append(make_case(case_id, 'v299_g1_picture_count', text, final, number=total, unit='предметов'))

    number_patterns = [
        ('v299_pattern_num_01', [2, 4, 6, 8], 10),
        ('v299_pattern_num_02', [1, 3, 5, 7], 9),
        ('v299_pattern_num_03', [5, 10, 15, 20], 25),
        ('v299_pattern_num_04', [3, 6, 9, 12], 15),
        ('v299_pattern_num_05', [4, 8, 12, 16], 20),
        ('v299_pattern_num_06', [7, 9, 11, 13], 15),
        ('v299_pattern_num_07', [10, 12, 14, 16], 18),
        ('v299_pattern_num_08', [6, 9, 12, 15], 18),
        ('v299_pattern_num_09', [11, 13, 15, 17], 19),
        ('v299_pattern_num_10', [8, 11, 14, 17], 20),
        ('v299_pattern_num_11', [9, 12, 15, 18], 21),
        ('v299_pattern_num_12', [12, 14, 16, 18], 20),
        ('v299_pattern_num_13', [14, 16, 18, 20], 22),
        ('v299_pattern_num_14', [2, 5, 8, 11], 14),
        ('v299_pattern_num_15', [13, 15, 17, 19], 21),
    ]
    for case_id, seq, nxt in number_patterns:
        text = f'Продолжи закономерность: {", ".join(str(x) for x in seq)}. Какое число следующее?'
        final = f'Следующее число — {nxt}'
        cases.append(make_case(case_id, 'v299_g1_pattern_number', text, final, number=nxt))

    shape_patterns = [
        ('v299_pattern_shape_01', ['круг', 'квадрат', 'круг', 'квадрат'], 'круг'),
        ('v299_pattern_shape_02', ['треугольник', 'круг', 'треугольник', 'круг'], 'треугольник'),
        ('v299_pattern_shape_03', ['квадрат', 'прямоугольник', 'круг', 'квадрат', 'прямоугольник', 'круг'], 'квадрат'),
        ('v299_pattern_shape_04', ['круг', 'треугольник', 'квадрат', 'круг', 'треугольник', 'квадрат'], 'круг'),
        ('v299_pattern_shape_05', ['прямоугольник', 'квадрат', 'прямоугольник', 'квадрат'], 'прямоугольник'),
    ]
    for case_id, seq, nxt in shape_patterns:
        text = f'Продолжи закономерность: {", ".join(seq)}. Какая фигура следующая?'
        final = f'Следующая фигура — {nxt}'
        cases.append(make_case(case_id, 'v299_g1_pattern_shape', text, final))

    table_tf_cases = [
        ('v299_table_tf_01', 'Таблица книг', [('Полка А', count(3, 'книга')), ('Полка Б', count(5, 'книга')), ('Полка В', count(2, 'книга'))], 'Полка Б', count(5, 'книга'), 'верно'),
        ('v299_table_tf_02', 'Таблица уроков', [('Урок 1', 'чтение'), ('Урок 2', 'математика'), ('Урок 3', 'музыка')], 'Урок 3', 'музыка', 'верно'),
        ('v299_table_tf_03', 'Таблица кубиков', [('Коробка 1', count(4, 'кубик')), ('Коробка 2', count(6, 'кубик')), ('Коробка 3', count(1, 'кубик'))], 'Коробка 3', count(3, 'кубик'), 'неверно'),
        ('v299_table_tf_04', 'Таблица меню', [('Строка 1', 'суп'), ('Строка 2', 'каша'), ('Строка 3', 'компот')], 'Строка 2', 'каша', 'верно'),
        ('v299_table_tf_05', 'Таблица яблок', [('Корзина А', count(8, 'яблоко')), ('Корзина Б', count(3, 'яблоко')), ('Корзина В', count(5, 'яблоко'))], 'Корзина Б', count(4, 'яблоко'), 'неверно'),
        ('v299_table_tf_06', 'Таблица игр', [('Игра 1', 'домино'), ('Игра 2', 'лото'), ('Игра 3', 'мемо')], 'Игра 1', 'домино', 'верно'),
        ('v299_table_tf_07', 'Таблица флажков', [('Ряд 1', count(2, 'флажок')), ('Ряд 2', count(7, 'флажок')), ('Ряд 3', count(5, 'флажок'))], 'Ряд 1', count(1, 'флажок'), 'неверно'),
        ('v299_table_tf_08', 'Таблица станций', [('Станция А', 'лес'), ('Станция Б', 'луг'), ('Станция В', 'река')], 'Станция В', 'река', 'верно'),
        ('v299_table_tf_09', 'Таблица наклеек', [('Ряд А', count(5, 'наклейка')), ('Ряд Б', count(2, 'наклейка')), ('Ряд В', count(4, 'наклейка'))], 'Ряд В', count(4, 'наклейка'), 'верно'),
        ('v299_table_tf_10', 'Таблица дежурств', [('Парта 1', 'Аня'), ('Парта 2', 'Оля'), ('Парта 3', 'Дима')], 'Парта 2', 'Ира', 'неверно'),
    ]
    for case_id, title, rows, target, claim, verdict in table_tf_cases[:5]:
        block = '; '.join(f'{key} — {value}' for key, value in rows)
        text = f'{title}: {block}. Верно ли, что напротив строки {target} — {claim}?'
        cases.append(make_case(case_id, 'v299_g1_true_false_table', text, verdict))

    pict_tf_cases = [
        ('v299_pic_tf_01', '★', 2, 'яблоко', 'Лены', 3, 6, 'верно'),
        ('v299_pic_tf_02', '●', 3, 'груша', 'Оли', 2, 5, 'неверно'),
        ('v299_pic_tf_03', '■', 2, 'книга', 'Пети', 4, 8, 'верно'),
        ('v299_pic_tf_04', '▲', 1, 'карандаш', 'Иры', 5, 4, 'неверно'),
        ('v299_pic_tf_05', '◆', 2, 'шар', 'Вани', 3, 6, 'верно'),
        ('v299_pic_tf_06', '★', 3, 'гриб', 'Димы', 2, 9, 'неверно'),
        ('v299_pic_tf_07', '●', 2, 'конфета', 'Кати', 4, 8, 'верно'),
        ('v299_pic_tf_08', '■', 1, 'кубик', 'Зои', 6, 5, 'неверно'),
        ('v299_pic_tf_09', '▲', 2, 'флажок', 'Ромы', 3, 6, 'верно'),
        ('v299_pic_tf_10', '◆', 1, 'машинка', 'Юли', 5, 7, 'неверно'),
    ]
    for case_id, symbol, mult, item, name, symbol_count, claim, verdict in pict_tf_cases:
        text = f'Пиктограмма: {symbol} = {count(mult, item)}. У {name} {symbol * symbol_count}. Верно ли, что у {name} {claim} {word(claim, item)}?'
        cases.append(make_case(case_id, 'v299_g1_true_false_pictogram', text, verdict))

    instruction_cases = [
        ('v299_instruction_01', 4, [('прибавь', 3), ('вычти', 2)], 5),
        ('v299_instruction_02', 7, [('увеличь на', 2), ('вычти', 1)], 8),
        ('v299_instruction_03', 5, [('прибавь', 4), ('прибавь', 1)], 10),
        ('v299_instruction_04', 9, [('уменьши на', 3), ('прибавь', 2)], 8),
        ('v299_instruction_05', 6, [('вычти', 1), ('вычти', 2)], 3),
        ('v299_instruction_06', 3, [('увеличь на', 5), ('уменьши на', 4)], 4),
        ('v299_instruction_07', 8, [('прибавь', 2), ('прибавь', 3), ('вычти', 4)], 9),
        ('v299_instruction_08', 10, [('уменьши на', 5), ('прибавь', 1)], 6),
        ('v299_instruction_09', 2, [('прибавь', 6), ('вычти', 3)], 5),
        ('v299_instruction_10', 11, [('уменьши на', 2), ('уменьши на', 4)], 5),
        ('v299_instruction_11', 1, [('прибавь', 7), ('прибавь', 2)], 10),
        ('v299_instruction_12', 12, [('вычти', 5), ('прибавь', 4)], 11),
        ('v299_instruction_13', 15, [('уменьши на', 6), ('прибавь', 3)], 12),
        ('v299_instruction_14', 5, [('прибавь', 5), ('вычти', 5), ('прибавь', 4)], 9),
        ('v299_instruction_15', 14, [('уменьши на', 4), ('уменьши на', 3)], 7),
    ]
    for case_id, start, actions, result in instruction_cases:
        action_text = '; '.join(f'{verb} {value}' for verb, value in actions)
        text = f'Выполни инструкцию: начни с числа {start}; {action_text}. Какое число получилось?'
        final = f'Получилось {result}'
        cases.append(make_case(case_id, 'v299_g1_instruction_number', text, final, number=result))

    low_cases = [
        ('v299_guard_low_01', 'Таблица уроков: Урок 1 — чтение; Урок 2 — математика. Что записано напротив строки Урок 4?'),
        ('v299_guard_low_02', 'Пиктограмма: ★ = 2 яблока. У Лены ★★★. Сколько яблок у Оли?'),
        ('v299_guard_low_03', 'Выполни инструкцию: начни с числа 4; прибавь. Какое число получилось?'),
        ('v299_guard_low_04', 'Таблица книг: Полка А — 3 книги; Полка Б — ?; Полка В — 2 книги. Что записано напротив строки Полка Б?'),
        ('v299_guard_low_05', 'Пиктограмма: ● = 3 груши. У Пети ●●, у Оли . Сколько груш всего?'),
    ]
    for case_id, text in low_cases:
        cases.append(make_case(case_id, 'v299_g1_guard_low_confidence', text, 'нужно уточнить условие задачи', expected_source='guard-low-confidence'))

    multi_cases = [
        ('v299_guard_multi_01', 'Таблица уроков: Урок 1 — чтение; Урок 2 — математика. Что записано напротив строки Урок 2?\nПродолжи закономерность: 2, 4, 6. Какое число следующее?'),
        ('v299_guard_multi_02', 'Пиктограмма: ★ = 2 яблока. У Лены ★★★. Сколько яблок у Лены?\nВыполни инструкцию: начни с числа 4; прибавь 3. Какое число получилось?'),
        ('v299_guard_multi_03', 'На рисунке 3 яблока и 2 груши. Сколько предметов всего на рисунке?\nТаблица меню: Строка 1 — суп; Строка 2 — каша. Что записано напротив строки Строка 2?'),
        ('v299_guard_multi_04', 'Продолжи закономерность: круг, квадрат, круг, квадрат. Какая фигура следующая?\nПиктограмма: ● = 3 груши. У Пети ●●. Верно ли, что у Пети 6 груш?'),
        ('v299_guard_multi_05', 'Выполни инструкцию: начни с числа 7; вычти 2. Какое число получилось?\nТаблица книг: Полка А — 3 книги; Полка Б — 5 книг. Верно ли, что напротив строки Полка Б — 5 книг?'),
    ]
    for case_id, text in multi_cases:
        cases.append(make_case(case_id, 'v299_g1_guard_multi_task', text, 'Разделите задания и отправьте их по отдельности', expected_source='guard-multi-task', should_warn=True))

    if len(cases) != 100:
        raise AssertionError(f'V299 cases expected 100, got {len(cases)}')
    seen_texts: set[str] = set()
    for case in cases:
        text_value = str(case.get('text') or '')
        if text_value in seen_texts:
            raise AssertionError(f'V299 duplicate case text: {text_value}')
        seen_texts.add(text_value)
        if '  ' in text_value:
            raise AssertionError(f'V299 case text has double spaces: {case.get("id")}')
        if not text_value[:1].isupper():
            raise AssertionError(f'V299 case text should start with uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v299_g1_math_information_live_ui_cases()

# --- v300 live UI audit: 2 класс, раздел 1 — Числа и величины ---

def _v300_g2_numbers_quantities_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | None = None, unit: str | None = None) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 2,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    def sign(a: int, b: int) -> str:
        return '<' if a < b else '>' if a > b else '='

    cases: list[dict[str, Any]] = []

    def v300_word(number: int, one: str, two: str, five: str) -> str:
        n = abs(int(number)); last_two = n % 100; last = n % 10
        if 11 <= last_two <= 14:
            return five
        if last == 1:
            return one
        if 2 <= last <= 4:
            return two
        return five

    compose = [(4,7),(5,2),(6,0),(3,9),(8,1),(7,5),(9,0),(2,6),(1,8),(5,5),(6,4),(3,0),(8,9),(4,1),(7,2)]
    for idx, (tens, units) in enumerate(compose, 1):
        value = tens * 10 + units
        tens_text = f'{tens} {v300_word(tens, "десяток", "десятка", "десятков")}'
        units_text = f'{units} {v300_word(units, "единица", "единицы", "единиц")}'
        text = f'Какое число содержит {tens_text} и {units_text}?'
        cases.append(make_case(f'v300_place_compose_{idx:02d}', 'v300_g2_place_value_compose', text, str(value), number=value))

    decompose = [68, 47, 90, 35, 82, 76, 54, 29, 61, 99, 40, 73, 18, 57, 84]
    for idx, n in enumerate(decompose, 1):
        if idx <= 5:
            tens = n // 10
            final = f'{tens} ' + ('десяток' if tens == 1 else 'десятка' if 2 <= tens <= 4 else 'десятков')
            text = f'В числе {n} сколько десятков?'
            cases.append(make_case(f'v300_place_tens_{idx:02d}', 'v300_g2_place_value_tens', text, final, number=tens, unit='десятков'))
        elif idx <= 10:
            units = n % 10
            if units == 1:
                word = 'единица'
            elif 2 <= units <= 4:
                word = 'единицы'
            else:
                word = 'единиц'
            final = f'{units} {word}'
            text = f'В числе {n} сколько единиц?'
            cases.append(make_case(f'v300_place_units_{idx:02d}', 'v300_g2_place_value_units', text, final, number=units, unit=word))
        else:
            tens = (n // 10) * 10
            units = n % 10
            final = f'{tens} + {units}' if units else str(tens)
            text = f'Представь число {n} как сумму десятков и единиц.'
            cases.append(make_case(f'v300_place_sum_{idx:02d}', 'v300_g2_place_value_sum', text, final))

    compare_pairs = [(48,52),(73,37),(65,65),(19,91),(84,79),(50,49),(27,72),(90,89),(33,38),(56,56)]
    for idx, (a,b) in enumerate(compare_pairs, 1):
        final = f'{a} {sign(a,b)} {b}'
        text = f'Сравни числа {a} и {b}. Какой знак нужно поставить?'
        cases.append(make_case(f'v300_compare_{idx:02d}', 'v300_g2_compare_numbers', text, final))
    tf_items = [(37,'>',73),(68,'<',86),(54,'=',54),(92,'<',29),(45,'>',44)]
    for idx, (a, sym, b) in enumerate(tf_items, 1):
        final = 'верно' if sign(a,b) == sym else 'неверно'
        text = f'Верно ли: {a} {sym} {b}?'
        cases.append(make_case(f'v300_compare_tf_{idx:02d}', 'v300_g2_true_false_inequality', text, final))

    incdec = [
        ('Увеличь 36 на 4.', 40), ('Увеличь 58 на 10.', 68), ('Увеличь 47 на 30.', 77),
        ('Увеличь 29 на 6.', 35), ('Увеличь 63 на 20.', 83), ('Увеличь 15 на 40.', 55),
        ('Увеличь 72 на 8.', 80), ('Увеличь 44 на 5.', 49), ('Увеличь 51 на 9.', 60), ('Увеличь 28 на 12.', 40),
        ('Уменьши 63 на 30.', 33), ('Уменьши 80 на 7.', 73), ('Уменьши 95 на 20.', 75),
        ('Уменьши 42 на 8.', 34), ('Уменьши 70 на 10.', 60), ('Уменьши 56 на 6.', 50),
        ('Какое число на 10 больше, чем 58?', 68), ('Какое число на 20 меньше, чем 74?', 54),
        ('Какое число на 7 больше, чем 45?', 52), ('Какое число на 9 меньше, чем 63?', 54),
    ]
    for idx, (text, value) in enumerate(incdec, 1):
        cases.append(make_case(f'v300_incdec_{idx:02d}', 'v300_g2_increase_decrease', text, str(value), number=value))

    diff_items = [
        ('На сколько 74 больше 69?', 'на 5 больше', 5), ('На сколько 28 меньше 35?', 'на 7 меньше', 7),
        ('На сколько 90 больше 54?', 'на 36 больше', 36), ('На сколько 41 меньше 60?', 'на 19 меньше', 19),
        ('На сколько 83 больше 77?', 'на 6 больше', 6), ('На сколько 25 меньше 52?', 'на 27 меньше', 27),
        ('На сколько 64 больше 40?', 'на 24 больше', 24), ('На сколько 38 меньше 46?', 'на 8 меньше', 8),
        ('На сколько 99 больше 9?', 'на 90 больше', 90), ('На сколько 57 меньше 70?', 'на 13 меньше', 13),
    ]
    for idx, (text, final, number) in enumerate(diff_items, 1):
        cases.append(make_case(f'v300_diff_{idx:02d}', 'v300_g2_difference_comparison', text, final, number=number))

    length_items = [
        ('Сколько сантиметров в 4 дм 3 см?', '43 сантиметра', 43), ('Сколько сантиметров в 7 дм 5 см?', '75 сантиметров', 75),
        ('Сколько сантиметров в 2 м 8 см?', '208 сантиметров', 208), ('Сколько сантиметров в 1 м 25 см?', '125 сантиметров', 125),
        ('Сколько дециметров и сантиметров в 47 см?', '4 дм 7 см', None), ('Сколько дециметров и сантиметров в 86 см?', '8 дм 6 см', None),
        ('Сравни длины 6 дм и 55 см.', '6 дм > 55 см', None), ('Сравни длины 4 дм и 42 см.', '4 дм < 42 см', None),
        ('Сравни длины 8 дм и 80 см.', '8 дм = 80 см', None), ('Сколько сантиметров в 9 дм 0 см?', '90 сантиметров', 90),
    ]
    for idx, (text, final, number) in enumerate(length_items, 1):
        cases.append(make_case(f'v300_length_{idx:02d}', 'v300_g2_length', text, final, number=number, unit='см' if number is not None else None))

    mass_time_cost = [
        ('Сколько граммов в 2 кг 300 г?', '2300 граммов', 2300, 'г'), ('Сколько граммов в 4 кг 50 г?', '4050 граммов', 4050, 'г'),
        ('Сколько граммов в 1 кг 700 г?', '1700 граммов', 1700, 'г'), ('Сколько граммов в 5 кг 0 г?', '5000 граммов', 5000, 'г'),
        ('Сколько минут в 1 ч 35 мин?', '95 минут', 95, 'минут'), ('Сколько минут в 2 ч 10 мин?', '130 минут', 130, 'минут'),
        ('Сколько минут в 3 ч 0 мин?', '180 минут', 180, 'минут'), ('Сколько минут в 1 ч 5 мин?', '65 минут', 65, 'минут'),
        ('Тетрадь стоит 12 рублей. Сколько стоят 3 тетради?', '36 рублей', 36, 'рублей'),
        ('Карандаш стоит 7 рублей. Сколько стоят 5 карандашей?', '35 рублей', 35, 'рублей'),
        ('Наклейка стоит 4 рубля. Сколько стоят 8 наклеек?', '32 рубля', 32, 'рубля'),
        ('Тетрадь стоит 9 рублей. Сколько стоят 6 тетрадей?', '54 рубля', 54, 'рубля'),
        ('У Оли было 50 рублей. Ручка стоит 18 рублей. Сколько рублей осталось?', '32 рубля', 32, 'рубля'),
        ('У Пети было 80 рублей. Альбом стоит 35 рублей. Сколько рублей осталось?', '45 рублей', 45, 'рублей'),
        ('У Иры было 70 рублей. Книга стоит 42 рубля. Сколько рублей осталось?', '28 рублей', 28, 'рублей'),
    ]
    for idx, (text, final, number, unit) in enumerate(mass_time_cost, 1):
        cases.append(make_case(f'v300_quantity_{idx:02d}', 'v300_g2_mass_time_cost', text, final, number=number, unit=unit))

    if len(cases) != 100:
        raise AssertionError(f'V300 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V300 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V300 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V300 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v300_g2_numbers_quantities_live_ui_cases()



# --- v302 live UI audit: 2 класс, раздел 3 — Текстовые задачи ---

def _v302_g2_text_problems_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]
    forms = {
        'яблоко': ('яблоко', 'яблока', 'яблок'), 'груша': ('груша', 'груши', 'груш'),
        'книга': ('книга', 'книги', 'книг'), 'карандаш': ('карандаш', 'карандаша', 'карандашей'),
        'наклейка': ('наклейка', 'наклейки', 'наклеек'), 'марка': ('марка', 'марки', 'марок'),
        'конфета': ('конфета', 'конфеты', 'конфет'), 'тетрадь': ('тетрадь', 'тетради', 'тетрадей'),
        'мяч': ('мяч', 'мяча', 'мячей'), 'открытка': ('открытка', 'открытки', 'открыток'),
        'печенье': ('печенье', 'печенья', 'печений'), 'билет': ('билет', 'билета', 'билетов'),
        'ручка': ('ручка', 'ручки', 'ручек'), 'блокнот': ('блокнот', 'блокнота', 'блокнотов'),
        'альбом': ('альбом', 'альбома', 'альбомов'), 'рубль': ('рубль', 'рубля', 'рублей'),
        'задача': ('задача', 'задачи', 'задач'), 'пирожок': ('пирожок', 'пирожка', 'пирожков'),
        'значок': ('значок', 'значка', 'значков'), 'коробка': ('коробка', 'коробки', 'коробок'),
        'пакет': ('пакет', 'пакета', 'пакетов'), 'полка': ('полка', 'полки', 'полок'),
    }
    def word(n: int, unit: str) -> str:
        f = forms[unit]
        n_abs = abs(int(n)); last_two = n_abs % 100; last = n_abs % 10
        if 11 <= last_two <= 14:
            return f[2]
        if last == 1:
            return f[0]
        if 2 <= last <= 4:
            return f[1]
        return f[2]
    def count(n: int, unit: str) -> str:
        return f'{int(n)} {word(n, unit)}'
    def times(n: int) -> str:
        return f"в {int(n)} {'раз' if int(n) % 10 == 1 and int(n) % 100 != 11 else 'раза' if int(n) % 10 in (2, 3, 4) and int(n) % 100 not in (12, 13, 14) else 'раз'}"
    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | str | None = None, unit: str | None = None) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 2,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    cases: list[dict[str, Any]] = []

    one_step_addition = [
        ('У Лены было {a} {au}. Ей подарили {b} {bu}. Сколько {q} стало у Лены?', 24, 18, 'наклейка'),
        ('У Димы было {a} {au}. Ему дали {b} {bu}. Сколько {q} стало у Димы?', 35, 17, 'карандаш'),
        ('В вазе было {a} {au}. Положили {b} {bu}. Сколько {q} стало в вазе?', 16, 9, 'груша'),
        ('На полке было {a} {au}. Принесли {b} {bu}. Сколько {q} стало на полке?', 42, 18, 'книга'),
        ('В альбоме было {a} {au}. Добавили {b} {bu}. Сколько {q} стало в альбоме?', 28, 14, 'марка'),
        ('В коробке было {a} {au}. Положили {b} {bu}. Сколько {q} стало в коробке?', 19, 23, 'конфета'),
        ('У Оли было {a} {au}. Ей подарили {b} {bu}. Сколько {q} стало у Оли?', 27, 16, 'открытка'),
        ('На тарелке было {a} {au}. Положили {b} {bu}. Сколько {q} стало на тарелке?', 18, 24, 'печенье'),
        ('В портфеле было {a} {au}. Добавили {b} {bu}. Сколько {q} стало в портфеле?', 33, 12, 'тетрадь'),
        ('В корзине было {a} {au}. Принесли {b} {bu}. Сколько {q} стало в корзине?', 21, 29, 'яблоко'),
    ]
    for idx, (tpl, a, b, unit) in enumerate(one_step_addition, 1):
        text = tpl.format(a=a, au=count(a, unit).split(' ',1)[1], b=b, bu=count(b, unit).split(' ',1)[1], q=forms[unit][2])
        res = a + b
        cases.append(make_case(f'v302_add_story_{idx:02d}', 'v302_g2_one_step_addition', text, count(res, unit), number=res, unit=word(res, unit)))

    one_step_subtraction = [
        ('В коробке было {a} {au}. Из коробки взяли {b} {bu}. Сколько {q} осталось?', 45, 18, 'карандаш'),
        ('У Кати было {a} {au}. Она подарила {b} {bu}. Сколько {q} осталось у Кати?', 36, 12, 'марка'),
        ('В корзине было {a} {au}. Из корзины взяли {b} {bu}. Сколько {q} осталось?', 52, 27, 'яблоко'),
        ('На полке было {a} {au}. Выдали {b} {bu}. Сколько {q} осталось на полке?', 64, 29, 'книга'),
        ('У Пети было {a} {au}. Он отдал {b} {bu}. Сколько {q} осталось у Пети?', 31, 15, 'наклейка'),
        ('В пакете было {a} {au}. Съели {b} {bu}. Сколько {q} осталось?', 40, 16, 'печенье'),
        ('В кассе было {a} {au}. Продали {b} {bu}. Сколько {q} осталось?', 58, 24, 'билет'),
        ('В коробке было {a} {au}. Убрали {b} {bu}. Сколько {q} осталось?', 73, 38, 'мяч'),
        ('У Веры было {a} {au}. Она отдала {b} {bu}. Сколько {q} осталось у Веры?', 47, 19, 'тетрадь'),
        ('На столе было {a} {au}. Взяли {b} {bu}. Сколько {q} осталось?', 29, 11, 'конфета'),
    ]
    for idx, (tpl, a, b, unit) in enumerate(one_step_subtraction, 1):
        text = tpl.format(a=a, au=count(a, unit).split(' ',1)[1], b=b, bu=count(b, unit).split(' ',1)[1], q=forms[unit][2])
        res = a - b
        cases.append(make_case(f'v302_sub_story_{idx:02d}', 'v302_g2_one_step_subtraction', text, count(res, unit), number=res, unit=word(res, unit)))

    diff_items = [
        ('У Маши было {a} {au}, у Оли было {b} {bu}. На сколько {q} у Оли больше, чем у Маши?', 28, 35, 'марка', 'больше'),
        ('У Саши было {a} {au}, у Иры было {b} {bu}. На сколько {q} у Саши меньше, чем у Иры?', 19, 31, 'наклейка', 'меньше'),
        ('На первой полке {a} {au}, на второй полке {b} {bu}. На сколько {q} на первой полке больше?', 42, 27, 'книга', 'больше'),
        ('На первой тарелке {a} {au}, на второй тарелке {b} {bu}. На сколько {q} на первой тарелке меньше?', 18, 26, 'груша', 'меньше'),
        ('У Вани было {a} {au}, у Димы было {b} {bu}. На сколько {q} у Димы больше, чем у Вани?', 34, 49, 'карандаш', 'больше'),
        ('У Лизы было {a} {au}, у Нади было {b} {bu}. На сколько {q} у Лизы меньше, чем у Нади?', 25, 40, 'открытка', 'меньше'),
        ('На первой полке {a} {au}, на второй полке {b} {bu}. На сколько {q} на второй полке меньше?', 55, 38, 'тетрадь', 'меньше'),
        ('У Коли было {a} {au}, у Пети было {b} {bu}. На сколько {q} у Пети больше, чем у Коли?', 46, 63, 'значок', 'больше'),
        ('У Алёши было {a} {au}, у Ромы было {b} {bu}. На сколько {q} у Алёши меньше, чем у Ромы?', 32, 51, 'билет', 'меньше'),
        ('На первой тарелке {a} {au}, на второй тарелке {b} {bu}. На сколько {q} на второй тарелке больше?', 24, 37, 'пирожок', 'больше'),
    ]
    for idx, (tpl, a, b, unit, rel) in enumerate(diff_items, 1):
        text = tpl.format(a=a, au=count(a, unit).split(' ',1)[1], b=b, bu=count(b, unit).split(' ',1)[1], q=forms[unit][2])
        diff = abs(a - b)
        final = f'на {count(diff, unit)} {rel}'
        cases.append(make_case(f'v302_diff_{idx:02d}', 'v302_g2_difference_comparison', text, final, number=diff, unit=word(diff, unit)))

    two_step_items = [
        ('В корзине было {a} {au}. Положили {b} {bu}, потом взяли {c} {cu}. Сколько {q} стало в корзине?', 34, 12, 9, 'яблоко', '+-'),
        ('В коробке было {a} {au}. Добавили {b} {bu}, потом убрали {c} {cu}. Сколько {q} стало в коробке?', 48, 15, 22, 'карандаш', '+-'),
        ('В библиотеке было {a} {au}. Выдали {b} {bu}, потом вернули {c} {cu}. Сколько {q} стало в библиотеке?', 58, 23, 11, 'книга', '-+'),
        ('В пакете было {a} {au}. Съели {b} {bu}, потом положили {c} {cu}. Сколько {q} стало в пакете?', 42, 17, 8, 'конфета', '-+'),
        ('На одной полке {a} {au}, на другой полке {b} {bu}. Выдали {c} {cu}. Сколько {q} осталось?', 26, 18, 15, 'книга', 'sum-'),
        ('В одной коробке {a} {au}, в другой коробке {b} {bu}. Взяли {c} {cu}. Сколько {q} осталось?', 37, 24, 19, 'мяч', 'sum-'),
        ('В вазе было {a} {au}. Положили {b} {bu}, потом взяли {c} {cu}. Сколько {q} стало в вазе?', 29, 18, 14, 'груша', '+-'),
        ('В альбоме было {a} {au}. Добавили {b} {bu}, потом отдали {c} {cu}. Сколько {q} стало в альбоме?', 33, 21, 16, 'марка', '+-'),
        ('В классе было {a} {au}. Выдали {b} {bu}, потом принесли {c} {cu}. Сколько {q} стало в классе?', 72, 28, 14, 'тетрадь', '-+'),
        ('На складе было {a} {au}. Продали {b} {bu}, потом привезли {c} {cu}. Сколько {q} стало на складе?', 65, 19, 23, 'альбом', '-+'),
        ('На одной тарелке {a} {au}, на другой тарелке {b} {bu}. Съели {c} {cu}. Сколько {q} осталось?', 28, 17, 13, 'печенье', 'sum-'),
        ('В первом ящике {a} {au}, во втором ящике {b} {bu}. Взяли {c} {cu}. Сколько {q} осталось?', 44, 25, 31, 'яблоко', 'sum-'),
        ('В кружке было {a} {au}. Принесли {b} {bu}, потом выдали {c} {cu}. Сколько {q} стало в кружке?', 38, 27, 20, 'значок', '+-'),
        ('В магазине было {a} {au}. Продали {b} {bu}, потом привезли {c} {cu}. Сколько {q} стало в магазине?', 90, 34, 28, 'блокнот', '-+'),
        ('На выставке было {a} {au}. Добавили {b} {bu}, потом убрали {c} {cu}. Сколько {q} стало на выставке?', 57, 16, 25, 'открытка', '+-'),
    ]
    for idx, (tpl, a, b, c, unit, mode) in enumerate(two_step_items, 1):
        text = tpl.format(a=a, au=count(a, unit).split(' ',1)[1], b=b, bu=count(b, unit).split(' ',1)[1], c=c, cu=count(c, unit).split(' ',1)[1], q=forms[unit][2])
        if mode == '+-': res = a + b - c
        elif mode == '-+': res = a - b + c
        else: res = a + b - c
        cases.append(make_case(f'v302_two_step_{idx:02d}', 'v302_g2_two_step', text, count(res, unit), number=res, unit=word(res, unit)))

    equal_groups = [
        ('В {g} коробках по {e} {eu}. Сколько {q} всего?', 6, 4, 'карандаш'),
        ('В {g} пакетах по {e} {eu}. Сколько {q} всего?', 5, 7, 'яблоко'),
        ('На {g} полках по {e} {eu}. Сколько {q} на всех полках?', 4, 8, 'книга'),
        ('В {g} коробках по {e} {eu}. Сколько {q} всего?', 7, 6, 'мяч'),
        ('В {g} пакетах по {e} {eu}. Сколько {q} всего?', 8, 3, 'конфета'),
        ('На {g} полках по {e} {eu}. Сколько {q} на всех полках?', 6, 5, 'тетрадь'),
        ('В {g} коробках по {e} {eu}. Сколько {q} всего?', 9, 4, 'открытка'),
        ('В {g} пакетах по {e} {eu}. Сколько {q} всего?', 3, 9, 'печенье'),
        ('На {g} полках по {e} {eu}. Сколько {q} на всех полках?', 5, 6, 'альбом'),
        ('В {g} коробках по {e} {eu}. Сколько {q} всего?', 4, 7, 'блокнот'),
        ('В {g} пакетах по {e} {eu}. Сколько {q} всего?', 7, 5, 'груша'),
        ('На {g} полках по {e} {eu}. Сколько {q} на всех полках?', 8, 4, 'значок'),
        ('В {g} коробках по {e} {eu}. Сколько {q} всего?', 6, 8, 'марка'),
        ('В {g} пакетах по {e} {eu}. Сколько {q} всего?', 5, 9, 'пирожок'),
        ('На {g} полках по {e} {eu}. Сколько {q} на всех полках?', 3, 8, 'ручка'),
    ]
    for idx, (tpl, g, e, unit) in enumerate(equal_groups, 1):
        text = tpl.format(g=g, e=e, eu=count(e, unit).split(' ',1)[1], q=forms[unit][2])
        res = g * e
        cases.append(make_case(f'v302_groups_{idx:02d}', 'v302_g2_equal_groups', text, count(res, unit), number=res, unit=word(res, unit)))

    sharing = [
        ('Всего {total} {tu} раздали поровну {g} детям. Сколько {q} получил каждый ребёнок?', 24, 6, 'конфета'),
        ('Всего {total} {tu} раздали поровну {g} детям. Сколько {q} получил каждый ребёнок?', 36, 9, 'яблоко'),
        ('Всего {total} {tu} разложили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 28, 4, 'карандаш'),
        ('Всего {total} {tu} распределили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 45, 5, 'наклейка'),
        ('Всего {total} {tu} раздали поровну {g} детям. Сколько {q} получил каждый ребёнок?', 32, 8, 'мяч'),
        ('Всего {total} {tu} разложили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 42, 7, 'марка'),
        ('Всего {total} {tu} распределили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 54, 6, 'открытка'),
        ('Всего {total} {tu} раздали поровну {g} детям. Сколько {q} получил каждый ребёнок?', 40, 5, 'тетрадь'),
        ('Всего {total} {tu} разложили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 63, 9, 'значок'),
        ('Всего {total} {tu} распределили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 56, 8, 'билет'),
        ('Всего {total} {tu} раздали поровну {g} детям. Сколько {q} получил каждый ребёнок?', 30, 6, 'пирожок'),
        ('Всего {total} {tu} разложили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 48, 6, 'ручка'),
        ('Всего {total} {tu} распределили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 35, 5, 'груша'),
        ('Всего {total} {tu} раздали поровну {g} детям. Сколько {q} получил каждый ребёнок?', 72, 8, 'печенье'),
        ('Всего {total} {tu} разложили поровну {g} детям. Сколько {q} получил каждый ребёнок?', 27, 3, 'альбом'),
    ]
    for idx, (tpl, total, g, unit) in enumerate(sharing, 1):
        text = tpl.format(total=total, tu=count(total, unit).split(' ',1)[1], g=g, q=forms[unit][2])
        res = total // g
        cases.append(make_case(f'v302_share_{idx:02d}', 'v302_g2_sharing_division', text, count(res, unit), number=res, unit=word(res, unit)))

    price_items = [
        ('Блокнот стоит {p} рублей. Сколько стоят {q} блокнотов?', 9, 5),
        ('Тетрадь стоит {p} рублей. Сколько стоят {q} тетрадей?', 12, 4),
        ('Ручка стоит {p} рублей. Сколько стоят {q} ручек?', 8, 7),
        ('Альбом стоит {p} рублей. Сколько стоят {q} альбомов?', 15, 3),
        ('Пирожок стоит {p} рублей. Сколько стоят {q} пирожков?', 6, 8),
        ('Билет стоит {p} рублей. Сколько стоят {q} билетов?', 10, 6),
        ('Ручка стоит {p} рублей. Сколько ручек можно купить на {money} рублей?', 8, 5),
        ('Блокнот стоит {p} рублей. Сколько блокнотов можно купить на {money} рублей?', 7, 6),
        ('Тетрадь стоит {p} рублей. Сколько тетрадей можно купить на {money} рублей?', 9, 4),
        ('Альбом стоит {p} рублей. Сколько альбомов можно купить на {money} рублей?', 12, 5),
    ]
    for idx, item in enumerate(price_items, 1):
        tpl, price, qty = item
        money = price * qty
        text = tpl.format(p=price, q=qty, money=money)
        if 'можно купить' in text:
            unit = 'ручка' if 'ручек' in text else 'блокнот' if 'блокнотов' in text else 'тетрадь' if 'тетрадей' in text else 'альбом'
            final = count(qty, unit); number = qty; exp_unit = word(qty, unit)
        else:
            final = count(money, 'рубль'); number = money; exp_unit = word(money, 'рубль')
        cases.append(make_case(f'v302_price_{idx:02d}', 'v302_g2_price_quantity_cost', text, final, number=number, unit=exp_unit))

    times_items = [
        ('У Маши {a} открыток, у Оли {b} открыток. Во сколько раз у Оли больше открыток, чем у Маши?', 6, 18),
        ('У Вани {a} марок, у Пети {b} марок. Во сколько раз у Пети больше марок, чем у Вани?', 7, 28),
        ('У Иры {a} значков, у Кати {b} значков. Во сколько раз у Иры меньше значков, чем у Кати?', 5, 20),
        ('У Димы {a} мячей, у Саши {b} мячей. Во сколько раз у Димы меньше мячей, чем у Саши?', 4, 16),
        ('У Лены {a} наклеек, у Нины {b} наклеек. Во сколько раз у Нины больше наклеек, чем у Лены?', 8, 24),
        ('В первом ряду {a} стульев, во втором ряду {b} стульев. Во сколько раз во втором ряду больше стульев?', 9, 27),
        ('В первом ряду {a} книг, во втором ряду {b} книг. Во сколько раз в первом ряду больше книг?', 30, 10),
        ('В первом ряду {a} яблок, во втором ряду {b} яблок. Во сколько раз во втором ряду меньше яблок?', 32, 8),
        ('У Тани {a} конфет, у Веры {b} конфет. Во сколько раз у Веры больше конфет, чем у Тани?', 6, 30),
        ('У Ромы {a} билетов, у Ильи {b} билетов. Во сколько раз у Ромы меньше билетов, чем у Ильи?', 7, 21),
    ]
    for idx, (tpl, a, b) in enumerate(times_items, 1):
        text = tpl.format(a=a, b=b)
        ratio = max(a, b) // min(a, b)
        cases.append(make_case(f'v302_times_{idx:02d}', 'v302_g2_times_comparison', text, times(ratio), number=ratio, unit=None))

    inverse = [
        ('После того как к числу прибавили 16, получили 43. Какое число было сначала?', 27, ''),
        ('Из числа вычли 18 и получили 27. Какое число было сначала?', 45, ''),
        ('У Коли было 50 рублей. После покупки осталось 18 рублей. Сколько рублей он потратил?', 32, 'рубль'),
        ('В нескольких коробках по 6 мячей, всего 36 мячей. Сколько коробок?', 6, 'коробка'),
        ('За 7 одинаковых ручек заплатили 56 рублей. Сколько стоит одна ручка?', 8, 'рубль'),
    ]
    for idx, (text, value, unit) in enumerate(inverse, 1):
        final = str(value) if not unit else count(value, unit)
        cases.append(make_case(f'v302_inverse_{idx:02d}', 'v302_g2_inverse_tasks', text, final, number=value, unit=word(value, unit) if unit else None))

    if len(cases) != 100:
        raise AssertionError(f'V302 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V302 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V302 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V302 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v302_g2_text_problems_live_ui_cases()

# --- v303 live UI audit: 2 класс, раздел 4 — Геометрия ---

def _v303_g2_geometry_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | None = None, unit: str | None = None) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 2,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    def plural(n: int, one: str, two: str, five: str) -> str:
        n = abs(int(n)); last_two = n % 100; last = n % 10
        if 11 <= last_two <= 14:
            return five
        if last == 1:
            return one
        if 2 <= last <= 4:
            return two
        return five

    def count(n: int, unit: str) -> str:
        if unit in {'см', 'дм', 'м'}:
            return f'{n} {unit}'
        if unit == 'сантиметр':
            return f'{n} {plural(n, "сантиметр", "сантиметра", "сантиметров")}'
        if unit == 'клетка':
            return f'{n} {plural(n, "клетка", "клетки", "клеток")}'
        if unit == 'звено':
            return f'{n} {plural(n, "звено", "звена", "звеньев")}'
        return f'{n} {unit}'

    cases: list[dict[str, Any]] = []

    link_cases = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    for idx, links in enumerate(link_cases, 1):
        text = f'Ломаная состоит из {links} {plural(links, "звена", "звеньев", "звеньев")}. Сколько звеньев у ломаной?'
        cases.append(make_case(f'v303_polyline_links_{idx:02d}', 'v303_g2_polyline_links', text, count(links, 'звено'), number=links, unit=plural(links, 'звено', 'звена', 'звеньев')))
    point_cases = [4, 5, 6, 7, 8]
    for idx, points in enumerate(point_cases, 1):
        links = points - 1
        text = f'Ломаная соединяет {points} {plural(points, "точку", "точки", "точек")} по порядку. Сколько звеньев у такой ломаной?'
        cases.append(make_case(f'v303_polyline_points_{idx:02d}', 'v303_g2_polyline_links', text, count(links, 'звено'), number=links, unit=plural(links, 'звено', 'звена', 'звеньев')))

    poly_lengths = [
        (2, 3, 4), (5, 6, 7), (4, 4, 5), (7, 2, 6), (8, 3, 5),
        (9, 4, 4), (6, 6, 6), (3, 5, 8), (10, 2, 3), (7, 7, 2),
        (4, 9, 5), (8, 8, 1), (3, 3, 7), (5, 5, 5), (6, 2, 9),
    ]
    for idx, parts in enumerate(poly_lengths, 1):
        total = sum(parts)
        text = 'Звенья ломаной имеют длины ' + ', '.join(f'{x} см' for x in parts[:-1]) + f' и {parts[-1]} см. Найди длину ломаной.'
        cases.append(make_case(f'v303_polyline_length_{idx:02d}', 'v303_g2_polyline_length', text, count(total, 'см'), number=total, unit='см'))

    rectangles = [(8,3), (7,5), (9,4), (6,2), (10,6), (12,4), (5,5), (11,3), (14,2), (13,7), (16,5), (18,4), (20,6), (15,8), (17,9), (22,5), (24,3), (19,6), (21,7), (25,4)]
    for idx, (a, b) in enumerate(rectangles, 1):
        p = 2 * (a + b)
        if idx % 2:
            text = f'У прямоугольника длина {a} см, ширина {b} см. Найди периметр.'
        else:
            text = f'Прямоугольник со сторонами {a} см и {b} см. Чему равен периметр?'
        cases.append(make_case(f'v303_rect_perimeter_{idx:02d}', 'v303_g2_rectangle_perimeter', text, f'периметр прямоугольника равен {count(p, "см")}', number=p, unit='см'))

    squares = [3,4,5,6,7,8,9,10,11,12,13,14,15,16,18]
    for idx, side in enumerate(squares, 1):
        p = side * 4
        if idx % 2:
            text = f'Сторона квадрата {side} см. Найди периметр квадрата.'
        else:
            text = f'Квадрат со стороной {side} см. Чему равен его периметр?'
        cases.append(make_case(f'v303_square_perimeter_{idx:02d}', 'v303_g2_square_perimeter', text, f'периметр квадрата равен {count(p, "см")}', number=p, unit='см'))

    conversions = [
        ('Сколько сантиметров в 3 дм 5 см?', 35, 'сантиметр'),
        ('Сколько сантиметров в 6 дм 2 см?', 62, 'сантиметр'),
        ('Сколько сантиметров в 4 дм?', 40, 'сантиметр'),
        ('Сколько сантиметров в 1 м 2 дм?', 120, 'сантиметр'),
        ('Сколько сантиметров в 2 м 3 дм 4 см?', 234, 'сантиметр'),
        ('Сколько дециметров в 50 см?', 5, 'дм'),
        ('Сколько дециметров в 80 см?', 8, 'дм'),
        ('Сколько метров в 300 см?', 3, 'м'),
        ('Сколько сантиметров в 5 дм 9 см?', 59, 'сантиметр'),
        ('Сколько сантиметров в 2 м 5 см?', 205, 'сантиметр'),
        ('Сколько дециметров в 90 см?', 9, 'дм'),
        ('Сколько метров в 400 см?', 4, 'м'),
    ]
    for idx, (text, value, unit) in enumerate(conversions, 1):
        cases.append(make_case(f'v303_length_convert_{idx:02d}', 'v303_g2_length_conversion', text, count(value, unit), number=value, unit=unit))

    segments = [
        ('Начерти отрезок длиной 6 см. Какую длину нужно отложить на линейке?', 6),
        ('Построй отрезок длиной 9 см. Какую длину нужно отложить на линейке?', 9),
        ('Начерти отрезок длиной 12 см. Какую длину нужно отложить на линейке?', 12),
        ('Отрезок AB 5 см. Начерти отрезок CD на 3 см длиннее. Какой длины будет CD?', 8),
        ('Отрезок AB 11 см. Начерти отрезок CD на 4 см короче. Какой длины будет CD?', 7),
        ('Отрезок MN 7 см. Начерти отрезок PQ на 5 см длиннее. Какой длины будет PQ?', 12),
        ('Отрезок MN 14 см. Начерти отрезок PQ на 6 см короче. Какой длины будет PQ?', 8),
        ('Построй отрезок длиной 15 см. Какую длину нужно отложить на линейке?', 15),
        ('Отрезок RS 8 см. Начерти отрезок TU на 2 см длиннее. Какой длины будет TU?', 10),
        ('Отрезок RS 13 см. Начерти отрезок TU на 5 см короче. Какой длины будет TU?', 8),
        ('Начерти отрезок длиной 4 см. Какую длину нужно отложить на линейке?', 4),
        ('Построй отрезок длиной 10 см. Какую длину нужно отложить на линейке?', 10),
        ('Отрезок KL 9 см. Начерти отрезок XY на 4 см длиннее. Какой длины будет XY?', 13),
    ]
    for idx, (text, value) in enumerate(segments, 1):
        final = count(value, 'см')
        if 'длиннее' in text or 'короче' in text:
            final = f'длина отрезка будет {final}'
        cases.append(make_case(f'v303_segment_construct_{idx:02d}', 'v303_g2_segment_construction', text, final, number=value, unit='см'))

    grid_items = [
        ('На клетчатой бумаге отрезок занимает 6 клеток. Какова его длина в клетках?', 6),
        ('На клетчатой бумаге отрезок занимает 9 клеток. Какова его длина в клетках?', 9),
        ('На клетчатой бумаге путь идёт 3 клетки вправо и 2 клетки вверх. Сколько клеток в пути?', 5),
        ('На клетчатой бумаге путь идёт 4 клетки вправо и 5 клеток вниз. Сколько клеток в пути?', 9),
        ('На клетчатой бумаге путь идёт 6 клеток влево и 3 клетки вверх. Сколько клеток в пути?', 9),
        ('На клетчатой бумаге прямоугольник имеет 5 клеток в длину и 3 клетки в ширину. Найди периметр в клетках.', 16),
        ('На клетчатой бумаге прямоугольник имеет 4 клетки в длину и 2 клетки в ширину. Найди периметр в клетках.', 12),
        ('Сторона квадрата 5 клеток. Найди периметр квадрата в клетках.', 20),
        ('Сторона квадрата 7 клеток. Найди периметр квадрата в клетках.', 28),
        ('На клетчатой бумаге путь идёт 2 клетки вверх, 3 клетки вправо и 4 клетки вниз. Сколько клеток в пути?', 9),
    ]
    for idx, (text, value) in enumerate(grid_items, 1):
        cases.append(make_case(f'v303_grid_{idx:02d}', 'v303_g2_grid_paper', text, count(value, 'клетка'), number=value, unit=plural(value, 'клетка', 'клетки', 'клеток')))

    if len(cases) != 100:
        raise AssertionError(f'V303 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V303 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V303 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V303 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v303_g2_geometry_live_ui_cases()

# --- v301 live UI audit: 2 класс, раздел 2 — Арифметические действия ---

def _v301_g2_arithmetic_actions_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | str | None = None, unit: str | None = None) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 2,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    cases: list[dict[str, Any]] = []

    addition = [
        ('Вычисли 36 + 27.', 63), ('Вычисли 48 + 19.', 67), ('Вычисли 54 + 28.', 82),
        ('Вычисли 67 + 15.', 82), ('Вычисли 25 + 46.', 71), ('Вычисли 39 + 44.', 83),
        ('Вычисли 58 + 24.', 82), ('Вычисли 46 + 37.', 83), ('Вычисли 29 + 65.', 94),
        ('Вычисли 34 + 58.', 92), ('Найди сумму 43 и 28.', 71), ('Найди сумму 57 и 16.', 73),
        ('К 62 прибавь 19.', 81), ('К 75 прибавь 18.', 93), ('К 38 прибавь 47.', 85),
    ]
    for idx, (prompt, value) in enumerate(addition, 1):
        cases.append(make_case(f'v301_add_{idx:02d}', 'v301_g2_addition_100', prompt, str(value), number=value))

    subtraction = [
        ('Вычисли 72 - 38.', 34), ('Вычисли 91 - 47.', 44), ('Вычисли 80 - 26.', 54),
        ('Вычисли 63 - 29.', 34), ('Вычисли 54 - 18.', 36), ('Вычисли 97 - 59.', 38),
        ('Вычисли 70 - 45.', 25), ('Вычисли 86 - 27.', 59), ('Вычисли 100 - 64.', 36),
        ('Вычисли 52 - 36.', 16), ('Из 83 вычти 28.', 55), ('Из 95 вычти 37.', 58),
        ('Из 74 вычти 49.', 25), ('Найди разность 68 и 39.', 29), ('Найди разность 90 и 54.', 36),
    ]
    for idx, (prompt, value) in enumerate(subtraction, 1):
        cases.append(make_case(f'v301_sub_{idx:02d}', 'v301_g2_subtraction_100', prompt, str(value), number=value))

    table_addition = [
        ('По таблице сложения: 8 + 7.', 15), ('По таблице сложения: 9 + 6.', 15),
        ('По таблице сложения: 7 + 5.', 12), ('По таблице сложения: 6 + 8.', 14),
        ('По таблице сложения: 9 + 9.', 18), ('Дополни до 20: 13 + 7.', 20),
        ('Дополни до 20: 16 + 4.', 20), ('Сколько будет 8 + 9?', 17),
        ('Сколько будет 6 + 7?', 13), ('Сколько будет 5 + 8?', 13),
    ]
    for idx, (prompt, value) in enumerate(table_addition, 1):
        cases.append(make_case(f'v301_table_add_{idx:02d}', 'v301_g2_table_addition', prompt, str(value), number=value))

    multiplication = [
        ('Вычисли 6 · 7.', 42), ('Вычисли 8 · 5.', 40), ('Вычисли 9 · 4.', 36),
        ('Вычисли 7 · 3.', 21), ('Вычисли 5 · 6.', 30), ('Вычисли 4 · 8.', 32),
        ('Вычисли 9 · 7.', 63), ('Вычисли 6 · 6.', 36), ('Вычисли 3 · 9.', 27),
        ('Вычисли 8 · 8.', 64), ('Найди произведение 7 и 6.', 42), ('Найди произведение 9 и 5.', 45),
        ('По таблице умножения: 4 · 7.', 28), ('По таблице умножения: 8 · 3.', 24), ('По таблице умножения: 5 · 9.', 45),
    ]
    for idx, (prompt, value) in enumerate(multiplication, 1):
        cases.append(make_case(f'v301_mul_{idx:02d}', 'v301_g2_multiplication_table', prompt, str(value), number=value))

    division = [
        ('Вычисли 42 : 6.', 7), ('Вычисли 56 : 7.', 8), ('Вычисли 36 : 4.', 9),
        ('Вычисли 48 : 8.', 6), ('Вычисли 63 : 9.', 7), ('Вычисли 35 : 5.', 7),
        ('Вычисли 72 : 8.', 9), ('Вычисли 30 : 6.', 5), ('Вычисли 27 : 3.', 9),
        ('Вычисли 64 : 8.', 8), ('Найди частное 54 и 6.', 9), ('Найди частное 45 и 5.', 9),
        ('По таблице деления: 49 : 7.', 7), ('По таблице деления: 40 : 5.', 8), ('По таблице деления: 32 : 4.', 8),
    ]
    for idx, (prompt, value) in enumerate(division, 1):
        cases.append(make_case(f'v301_div_{idx:02d}', 'v301_g2_division_table', prompt, str(value), number=value))

    components = [
        ('Как называется результат умножения 6 · 4?', 'произведение'),
        ('Как называется число 6 в записи 6 · 4 = 24?', 'множитель'),
        ('Как называется число 4 в записи 6 · 4 = 24?', 'множитель'),
        ('Как называется результат деления 42 : 6?', 'частное'),
        ('Как называется число 42 в записи 42 : 6 = 7?', 'делимое'),
        ('Как называется число 6 в записи 42 : 6 = 7?', 'делитель'),
        ('Как называется результат сложения 35 + 27?', 'сумма'),
        ('Как называется результат вычитания 72 - 38?', 'разность'),
        ('Как называется число 72 в записи 72 - 38 = 34?', 'уменьшаемое'),
        ('Как называется число 38 в записи 72 - 38 = 34?', 'вычитаемое'),
    ]
    for idx, (prompt, final) in enumerate(components, 1):
        cases.append(make_case(f'v301_component_{idx:02d}', 'v301_g2_components', prompt, final))

    order_items = [
        ('Вычисли 6 + 4 · 3.', 18), ('Вычисли (6 + 4) · 3.', 30),
        ('Найди значение выражения 24 : 6 + 7.', 11), ('Найди значение выражения 30 - 4 · 5.', 10),
        ('Вычисли 18 : (3 + 3).', 3), ('Вычисли 40 - (12 + 8).', 20),
        ('Вычисли 7 · 3 - 5.', 16), ('Вычисли 5 · (9 - 4).', 25),
        ('Найди значение выражения 36 : 4 + 6 · 2.', 21), ('Найди значение выражения 50 - 18 : 3.', 44),
        ('Вычисли (45 - 21) : 6.', 4), ('Вычисли 27 + 6 · 5.', 57),
        ('Найди значение выражения (28 + 14) : 7.', 6), ('Вычисли 8 · 4 + 16.', 48),
        ('Вычисли 64 : 8 + 9.', 17), ('Вычисли 90 - 6 · 7.', 48),
        ('Найди значение выражения (16 + 24) : 5.', 8), ('Вычисли 3 · 9 + 4 · 5.', 47),
        ('Вычисли 72 : 9 + 6 · 4.', 32), ('Найди значение выражения 81 : 9 + (14 - 6).', 17),
    ]
    for idx, (prompt, value) in enumerate(order_items, 1):
        cases.append(make_case(f'v301_order_{idx:02d}', 'v301_g2_order_of_actions', prompt, str(value), number=value))

    if len(cases) != 100:
        raise AssertionError(f'V301 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V301 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V301 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V301 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v301_g2_arithmetic_actions_live_ui_cases()


# --- v305 live UI audit: 3 класс, раздел 1 — Числа и величины ---

def _v305_g3_numbers_quantities_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | str | None = None, unit: str | None = None) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 3,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    def plural(n: int, one: str, two: str, five: str) -> str:
        n = int(n); last = n % 10; last2 = n % 100
        if last == 1 and last2 != 11:
            return one
        if 2 <= last <= 4 and not (12 <= last2 <= 14):
            return two
        return five

    cases: list[dict[str, Any]] = []

    # 18 place-value and expanded-form cases.
    write_rows = [(4, 8, 3), (6, 2, 7), (3, 5, 9), (7, 0, 4), (9, 1, 6), (5, 4, 0)]
    for idx, (h, t, u) in enumerate(write_rows, 1):
        n = h * 100 + t * 10 + u
        cases.append(make_case(f'v305_place_write_{idx:02d}', 'v305_g3_place_value_write', f'Запиши число: {h} сотни, {t} десятков и {u} единиц.', str(n), number=n))

    digit_rows = [
        (736, 'сотен', 7, 'сотен'), (736, 'разрядных десятков', 3, 'десятка'), (736, 'разрядных единиц', 6, 'единиц'),
        (504, 'сотен', 5, 'сотен'), (504, 'разрядных десятков', 0, 'десятков'), (918, 'разрядных единиц', 8, 'единиц'),
    ]
    for idx, (n, kind, ans, unit) in enumerate(digit_rows, 1):
        cases.append(make_case(f'v305_place_digit_{idx:02d}', 'v305_g3_place_value_digit', f'Сколько {kind} в числе {n}?', f'{ans} {unit}', number=ans, unit=unit))

    expanded_rows = [584, 709, 930, 641, 805, 276]
    for idx, n in enumerate(expanded_rows, 1):
        h = (n // 100) * 100; t = ((n // 10) % 10) * 10; u = n % 10
        final = ' + '.join(str(x) for x in (h, t, u) if x)
        cases.append(make_case(f'v305_expanded_{idx:02d}', 'v305_g3_expanded_form', f'Разложи число {n} на разрядные слагаемые.', final))

    # 14 comparison cases.
    compare_rows = [(458,485),(672,627),(309,390),(800,799),(541,541),(936,963),(120,210),(705,750)]
    for idx, (a, b) in enumerate(compare_rows, 1):
        sign = '<' if a < b else ('>' if a > b else '=')
        cases.append(make_case(f'v305_compare_{idx:02d}', 'v305_g3_compare_numbers', f'Сравни числа {a} и {b}.', f'{a} {sign} {b}'))
    bigger_rows = [('больше', 672, 627, 672), ('меньше', 314, 341, 314), ('больше', 590, 905, 905), ('меньше', 808, 880, 808), ('больше', 456, 465, 465), ('меньше', 999, 990, 990)]
    for idx, (kind, a, b, ans) in enumerate(bigger_rows, 1):
        cases.append(make_case(f'v305_compare_choice_{idx:02d}', 'v305_g3_compare_choice', f'Какое число {kind}: {a} или {b}?', str(ans), number=ans))

    # 10 even/odd cases.
    even_rows = [428, 317, 600, 915, 734, 821, 990, 143, 256, 707]
    for idx, n in enumerate(even_rows, 1):
        final = 'чётное' if n % 2 == 0 else 'нечётное'
        cases.append(make_case(f'v305_even_odd_{idx:02d}', 'v305_g3_even_odd', f'Чётное или нечётное число {n}?', final))

    # 12 times increase/decrease cases.
    inc_rows = [(45,3,135),(84,2,168),(120,4,480),(205,3,615),(99,5,495),(250,2,500)]
    for idx, (a, b, ans) in enumerate(inc_rows, 1):
        cases.append(make_case(f'v305_times_increase_{idx:02d}', 'v305_g3_times_increase', f'Увеличь число {a} в {b} раза.', str(ans), number=ans))
    dec_rows = [(96,4,24),(144,3,48),(360,6,60),(420,7,60),(810,9,90),(560,8,70)]
    for idx, (a, b, ans) in enumerate(dec_rows, 1):
        cases.append(make_case(f'v305_times_decrease_{idx:02d}', 'v305_g3_times_decrease', f'Уменьши число {a} в {b} раза.', str(ans), number=ans))

    # 10 mass cases.
    mass_rows = [(3,250,3250),(4,75,4075),(2,500,2500),(6,5,6005),(1,900,1900),(7,0,7000)]
    for idx, (kg, g, total) in enumerate(mass_rows, 1):
        suffix = f' {g} г' if g else ''
        cases.append(make_case(f'v305_mass_grams_{idx:02d}', 'v305_g3_mass_grams', f'Сколько граммов в {kg} кг{suffix}?', f'{total} граммов', number=total, unit='граммов'))
    mass_compare = [(2,1900,'>'),(3,3000,'='),(5,5200,'<'),(4,3999,'>')]
    for idx, (kg, g, sign) in enumerate(mass_compare, 1):
        cases.append(make_case(f'v305_mass_compare_{idx:02d}', 'v305_g3_mass_compare', f'Сравни массы {kg} кг и {g} г.', f'{kg} кг {sign} {g} г'))

    # 10 length cases.
    mm_rows = [(6,60),(12,120),(25,250),(40,400)]
    for idx, (cm, mm) in enumerate(mm_rows, 1):
        cases.append(make_case(f'v305_length_mm_{idx:02d}', 'v305_g3_length_mm', f'Сколько миллиметров в {cm} см?', f'{mm} мм', number=mm, unit='мм'))
    m_rows = [(2,350,2350),(1,75,1075),(4,0,4000),(3,640,3640)]
    for idx, (km, m, total) in enumerate(m_rows, 1):
        suffix = f' {m} м' if m else ''
        cases.append(make_case(f'v305_length_meters_{idx:02d}', 'v305_g3_length_meters', f'Сколько метров в {km} км{suffix}?', f'{total} метров', number=total, unit='метров'))
    length_compare = [(2,1900,'>'),(3,3000,'=' )]
    for idx, (km, m, sign) in enumerate(length_compare, 1):
        cases.append(make_case(f'v305_length_compare_{idx:02d}', 'v305_g3_length_compare', f'Сравни длины {km} км и {m} м.', f'{km} км {sign} {m} м'))

    # 12 area cases.
    rect_rows = [(8,5,40),(12,4,48),(9,7,63),(15,6,90),(10,8,80),(13,3,39)]
    for idx, (a, b, area) in enumerate(rect_rows, 1):
        cases.append(make_case(f'v305_area_rect_{idx:02d}', 'v305_g3_area_rectangle', f'Найди площадь прямоугольника со сторонами {a} см и {b} см.', f'{area} см²', number=area, unit='см²'))
    sq_rows = [(7,49),(9,81),(12,144),(15,225)]
    for idx, (a, area) in enumerate(sq_rows, 1):
        cases.append(make_case(f'v305_area_square_{idx:02d}', 'v305_g3_area_square', f'Найди площадь квадрата со стороной {a} см.', f'площадь квадрата {area} см²', number=area, unit='см²'))

    # 24 time cases.
    end_rows = [
        ('Занятие', '09:15', 45, '10:00'), ('Урок', '10:05', 40, '10:45'), ('Поезд', '08:35', 50, '09:25'),
        ('Занятие', '13:20', 35, '13:55'), ('Урок', '14:10', 45, '14:55'), ('Поезд', '16:25', 30, '16:55'),
        ('Занятие', '11:40', 25, '12:05'), ('Урок', '12:30', 60, '13:30'),
    ]
    for idx, (subject, start, minutes, end) in enumerate(end_rows, 1):
        if subject == 'Поезд':
            text = f'Поезд отправился в {start} и ехал {minutes} минут. Во сколько прибыл поезд?'
        else:
            verb = 'началось' if subject == 'Занятие' else 'начался'
            pronoun = 'оно ' if subject == 'Занятие' else ''
            end_verb = 'закончилось' if subject == 'Занятие' else 'закончился'
            text = f'{subject} {verb} в {start} и длилось {minutes} минут. Во сколько {pronoun}{end_verb}?'
        cases.append(make_case(f'v305_time_end_{idx:02d}', 'v305_g3_time_end', text, end))

    duration_rows = [
        ('Тренировка', '14:20', '15:05', 45), ('Фильм', '16:10', '17:00', 50), ('Занятие', '08:30', '09:15', 45),
        ('Тренировка', '10:40', '11:25', 45), ('Фильм', '12:15', '13:05', 50), ('Занятие', '15:00', '15:35', 35),
        ('Тренировка', '17:30', '18:20', 50), ('Фильм', '09:05', '09:55', 50),
    ]
    for idx, (subject, start, end, minutes) in enumerate(duration_rows, 1):
        verb_start = 'началась' if subject in {'Тренировка'} else 'начался' if subject == 'Фильм' else 'началось'
        verb_end = 'закончилась' if subject in {'Тренировка'} else 'закончился' if subject == 'Фильм' else 'закончилось'
        verb_dur = 'длилась' if subject in {'Тренировка'} else 'длился' if subject == 'Фильм' else 'длилось'
        text = f'{subject} {verb_start} в {start} и {verb_end} в {end}. Сколько минут {verb_dur} {subject.lower()}?'
        unit = plural(minutes, 'минута', 'минуты', 'минут')
        cases.append(make_case(f'v305_time_duration_{idx:02d}', 'v305_g3_time_duration', text, f'{minutes} {unit}', number=minutes, unit=unit))

    if len(cases) != 100:
        raise AssertionError(f'V305 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V305 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V305 double spaces in {case.get("id")}')
        if text and not text[0].isupper():
            raise AssertionError(f'V305 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v305_g3_numbers_quantities_live_ui_cases()

# --- v306 live UI audit: 3 класс, раздел 2 — Арифметические действия ---

def _v306_g3_arithmetic_actions_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | str | None = None) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 3,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': '',
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    cases: list[dict[str, Any]] = []

    add_rows = [(478,236),(583,279),(604,198),(726,185),(349,467),(805,126),(129,678),(455,368),(697,208),(375,486),(540,389),(268,594)]
    for idx, (a, b) in enumerate(add_rows, 1):
        cases.append(make_case(f'v306_written_add_{idx:02d}', 'v306_g3_written_addition', f'Вычисли {a} + {b}.', str(a + b), number=a + b))

    sub_rows = [(812,376),(705,248),(930,457),(641,289),(1000,365),(824,596),(756,389),(902,417),(680,245),(534,278),(900,509),(721,364)]
    for idx, (a, b) in enumerate(sub_rows, 1):
        cases.append(make_case(f'v306_written_sub_{idx:02d}', 'v306_g3_written_subtraction', f'Вычисли {a} - {b}.', str(a - b), number=a - b))

    mul_one_rows = [(45,6),(78,4),(123,3),(206,4),(150,5),(234,2),(89,7),(305,3),(126,6),(407,2),(95,8),(318,3)]
    for idx, (a, b) in enumerate(mul_one_rows, 1):
        cases.append(make_case(f'v306_mul_one_digit_{idx:02d}', 'v306_g3_multiplication', f'Вычисли {a} · {b}.', str(a * b), number=a * b))

    mul_two_rows = [(24,15),(36,12),(42,18),(27,23),(58,14),(31,26),(64,11),(45,22)]
    for idx, (a, b) in enumerate(mul_two_rows, 1):
        cases.append(make_case(f'v306_mul_two_digit_{idx:02d}', 'v306_g3_multiplication', f'Вычисли {a} · {b}.', str(a * b), number=a * b))

    div_exact_rows = [(486,6),(672,8),(936,9),(728,7),(864,12),(624,6),(525,5),(952,14),(756,21),(900,15),(840,24),(960,32)]
    for idx, (a, b) in enumerate(div_exact_rows, 1):
        cases.append(make_case(f'v306_div_exact_{idx:02d}', 'v306_g3_division', f'Вычисли {a} : {b}.', str(a // b), number=a // b))

    div_rem_rows = [(783,6),(955,8),(742,9),(617,5),(859,7),(1000,12),(694,11),(875,16),(529,4),(998,13)]
    for idx, (a, b) in enumerate(div_rem_rows, 1):
        q, r = divmod(a, b)
        cases.append(make_case(f'v306_div_remainder_{idx:02d}', 'v306_g3_division_remainder', f'Выполни деление с остатком: {a} : {b}.', f'{q}, остаток {r}', number=q))

    order_rows = [
        ('360 - 45 · 3', 225), ('120 : 5 + 36', 60), ('84 + 16 · 4', 148), ('500 - 72 : 8', 491),
        ('35 · 6 - 80', 130), ('960 : 12 + 25', 105), ('700 - 48 · 9', 268), ('144 : 6 + 78', 102),
        ('250 + 18 · 5', 340), ('810 : 9 - 37', 53), ('64 · 7 + 52', 500), ('900 - 15 · 24', 540),
    ]
    for idx, (expr, ans) in enumerate(order_rows, 1):
        cases.append(make_case(f'v306_order_{idx:02d}', 'v306_g3_order_of_actions', f'Найди значение выражения {expr}.', str(ans), number=ans))

    paren_rows = [
        ('(360 - 120) : 6', 40), ('48 · (25 - 17)', 384), ('(720 : 9) + 56', 136), ('900 - (36 · 14)', 396),
        ('(125 + 175) : 5', 60), ('64 · (18 - 9)', 576), ('(840 - 120) : 8', 90), ('500 - (96 : 6)', 484),
        ('(45 + 35) · 7', 560), ('960 : (4 · 6)', 40), ('(700 - 448) : 7', 36), ('18 · (42 - 29)', 234),
    ]
    for idx, (expr, ans) in enumerate(paren_rows, 1):
        cases.append(make_case(f'v306_parentheses_{idx:02d}', 'v306_g3_expression_parentheses', f'Найди значение выражения {expr}.', str(ans), number=ans))

    letter_rows = [
        ('a + 238', 'a', 456, 694), ('b - 179', 'b', 640, 461), ('c · 7', 'c', 84, 588), ('x : 6', 'x', 726, 121),
        ('900 - y', 'y', 365, 535), ('a · 12', 'a', 43, 516), ('b + 407', 'b', 286, 693), ('x : 8', 'x', 984, 123),
        ('c - 248', 'c', 705, 457), ('y · 9', 'y', 67, 603),
    ]
    for idx, (expr, var, val, ans) in enumerate(letter_rows, 1):
        cases.append(make_case(f'v306_letter_expr_{idx:02d}', 'v306_g3_letter_expression', f'Найди значение выражения {expr}, если {var} = {val}.', str(ans), number=ans))

    if len(cases) != 100:
        raise AssertionError(f'V306 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V306 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V306 double spaces in {case.get("id")}')
        if text and not text[0].isupper():
            raise AssertionError(f'V306 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v306_g3_arithmetic_actions_live_ui_cases()


# --- v304 live UI audit: 2 класс, раздел 5 — Математическая информация ---

def _v304_g2_math_information_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | str | None = None, unit: str | None = None) -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 2,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    cases: list[dict[str, Any]] = []

    addition_rows = [
        ('8 + 7', 15, '9 + 6', 15, '6 + 5', 11, '9 + 6', 15),
        ('7 + 8', 15, '5 + 9', 14, '6 + 6', 12, '5 + 9', 14),
        ('9 + 4', 13, '8 + 8', 16, '7 + 6', 13, '8 + 8', 16),
        ('6 + 9', 15, '4 + 8', 12, '9 + 9', 18, '9 + 9', 18),
        ('5 + 7', 12, '8 + 6', 14, '9 + 5', 14, '5 + 7', 12),
        ('3 + 8', 11, '7 + 7', 14, '6 + 8', 14, '3 + 8', 11),
        ('9 + 7', 16, '8 + 5', 13, '4 + 9', 13, '9 + 7', 16),
        ('6 + 7', 13, '5 + 8', 13, '7 + 9', 16, '7 + 9', 16),
        ('8 + 9', 17, '6 + 4', 10, '7 + 5', 12, '8 + 9', 17),
        ('9 + 8', 17, '4 + 7', 11, '5 + 6', 11, '4 + 7', 11),
        ('8 + 4', 12, '9 + 3', 12, '7 + 4', 11, '9 + 3', 12),
        ('6 + 8', 14, '5 + 5', 10, '7 + 8', 15, '7 + 8', 15),
        ('9 + 2', 11, '8 + 3', 11, '6 + 9', 15, '6 + 9', 15),
        ('7 + 6', 13, '8 + 7', 15, '9 + 1', 10, '8 + 7', 15),
        ('5 + 9', 14, '6 + 6', 12, '8 + 8', 16, '8 + 8', 16),
    ]
    for idx, (e1, v1, e2, v2, e3, v3, target, ans) in enumerate(addition_rows, 1):
        text = f'Таблица сложения: {e1} = {v1}; {e2} = {v2}; {e3} = {v3}. Какой результат у {target}?'
        cases.append(make_case(f'v304_add_table_{idx:02d}', 'v304_g2_addition_table', text, str(ans), number=ans))

    multiplication_rows = [
        ('4 · 6', 24, '5 · 7', 35, '3 · 8', 24, '5 · 7', 35),
        ('6 · 6', 36, '7 · 4', 28, '8 · 3', 24, '6 · 6', 36),
        ('9 · 5', 45, '6 · 8', 48, '7 · 7', 49, '6 · 8', 48),
        ('3 · 9', 27, '4 · 8', 32, '5 · 6', 30, '4 · 8', 32),
        ('8 · 7', 56, '9 · 4', 36, '6 · 5', 30, '8 · 7', 56),
        ('2 · 9', 18, '3 · 7', 21, '4 · 9', 36, '4 · 9', 36),
        ('5 · 8', 40, '6 · 7', 42, '9 · 3', 27, '6 · 7', 42),
        ('7 · 5', 35, '8 · 4', 32, '9 · 6', 54, '9 · 6', 54),
        ('4 · 4', 16, '7 · 8', 56, '3 · 6', 18, '7 · 8', 56),
        ('9 · 7', 63, '8 · 8', 64, '6 · 4', 24, '8 · 8', 64),
        ('5 · 5', 25, '4 · 7', 28, '3 · 5', 15, '5 · 5', 25),
        ('6 · 9', 54, '7 · 3', 21, '8 · 6', 48, '8 · 6', 48),
        ('2 · 8', 16, '9 · 8', 72, '6 · 3', 18, '9 · 8', 72),
        ('7 · 6', 42, '5 · 4', 20, '8 · 2', 16, '7 · 6', 42),
        ('3 · 4', 12, '6 · 5', 30, '9 · 2', 18, '6 · 5', 30),
    ]
    for idx, (e1, v1, e2, v2, e3, v3, target, ans) in enumerate(multiplication_rows, 1):
        text = f'Таблица умножения: {e1} = {v1}; {e2} = {v2}; {e3} = {v3}. Какое произведение у {target}?'
        cases.append(make_case(f'v304_mul_table_{idx:02d}', 'v304_g2_multiplication_table_info', text, str(ans), number=ans))

    schedule_rows = [
        ('понедельник', '14:00', 'среда', '15:00', 'пятница', '16:00', 'среда', '15:00'),
        ('вторник', '13:30', 'четверг', '14:30', 'суббота', '10:00', 'суббота', '10:00'),
        ('понедельник', '12:00', 'вторник', '12:45', 'среда', '13:30', 'понедельник', '12:00'),
        ('среда', '16:15', 'пятница', '17:00', 'суббота', '11:30', 'пятница', '17:00'),
        ('вторник', '15:20', 'четверг', '16:20', 'воскресенье', '09:40', 'четверг', '16:20'),
        ('понедельник', '10:15', 'среда', '11:15', 'пятница', '12:15', 'пятница', '12:15'),
        ('вторник', '08:30', 'четверг', '09:30', 'суббота', '10:30', 'вторник', '08:30'),
        ('понедельник', '13:10', 'среда', '14:10', 'пятница', '15:10', 'среда', '14:10'),
        ('вторник', '17:45', 'четверг', '18:15', 'суббота', '12:45', 'четверг', '18:15'),
        ('понедельник', '09:20', 'среда', '10:20', 'пятница', '11:20', 'понедельник', '09:20'),
    ]
    for idx, (d1, t1, d2, t2, d3, t3, day, ans) in enumerate(schedule_rows, 1):
        text = f'Расписание кружка: {d1} — {t1}; {d2} — {t2}; {d3} — {t3}. Во сколько занятие в {day}?'
        cases.append(make_case(f'v304_schedule_lookup_{idx:02d}', 'v304_g2_schedule_lookup', text, ans))

    duration_rows = [
        ('09:00', '09:45', 45), ('10:10', '10:50', 40), ('12:15', '12:55', 40), ('13:20', '14:00', 40), ('08:30', '09:10', 40),
        ('11:05', '11:50', 45), ('14:15', '15:00', 45), ('15:10', '15:50', 40), ('16:20', '17:00', 40), ('09:25', '10:10', 45),
    ]
    for idx, (start, end, minutes) in enumerate(duration_rows, 1):
        text = f'По расписанию урок начинается в {start} и заканчивается в {end}. Сколько минут длится урок?'
        unit = 'минута' if minutes == 1 else ('минуты' if minutes % 10 in (2,3,4) and minutes % 100 not in (12,13,14) else 'минут')
        cases.append(make_case(f'v304_schedule_duration_{idx:02d}', 'v304_g2_schedule_duration', text, f'урок длится {minutes} {unit}', number=minutes, unit=unit))

    work_end_rows = [
        ('библиотека', '09:00-17:00', 'музей', '10:00-18:00', 'спортзал', '08:00-16:00', 'музей', '18:00'),
        ('аптека', '08:00-20:00', 'почта', '09:00-17:00', 'касса', '10:00-19:00', 'почта', '17:00'),
        ('магазин', '09:00-21:00', 'кафе', '10:00-22:00', 'киоск', '07:00-15:00', 'магазин', '21:00'),
        ('театр', '12:00-20:00', 'парк', '08:00-18:00', 'бассейн', '07:00-19:00', 'бассейн', '19:00'),
        ('читальня', '10:00-16:00', 'зал', '09:00-18:00', 'клуб', '11:00-19:00', 'клуб', '19:00'),
        ('центр', '08:00-14:00', 'секция', '15:00-20:00', 'студия', '12:00-18:00', 'секция', '20:00'),
        ('рынок', '07:00-13:00', 'ярмарка', '09:00-15:00', 'выставка', '10:00-17:00', 'выставка', '17:00'),
        ('каток', '10:00-18:00', 'прокат', '09:00-17:00', 'тир', '11:00-16:00', 'каток', '18:00'),
    ]
    for idx, (a, ta, b, tb, c, tc, target, ans) in enumerate(work_end_rows, 1):
        text = f'График работы: {a} — {ta}; {b} — {tb}; {c} — {tc}. До скольких работает {target}?'
        cases.append(make_case(f'v304_work_end_{idx:02d}', 'v304_g2_work_graph_end', text, ans))

    work_duration_rows = [
        ('библиотека', '09:00-17:00', 'музей', '10:00-18:00', 'спортзал', '08:00-16:00', 'библиотека', 8),
        ('аптека', '08:00-20:00', 'почта', '09:00-17:00', 'касса', '10:00-19:00', 'почта', 8),
        ('магазин', '09:00-21:00', 'кафе', '10:00-22:00', 'киоск', '07:00-15:00', 'киоск', 8),
        ('театр', '12:00-20:00', 'парк', '08:00-18:00', 'бассейн', '07:00-19:00', 'парк', 10),
        ('читальня', '10:00-16:00', 'зал', '09:00-18:00', 'клуб', '11:00-19:00', 'читальня', 6),
        ('центр', '08:00-14:00', 'секция', '15:00-20:00', 'студия', '12:00-18:00', 'студия', 6),
        ('рынок', '07:00-13:00', 'ярмарка', '09:00-15:00', 'выставка', '10:00-17:00', 'ярмарка', 6),
    ]
    for idx, (a, ta, b, tb, c, tc, target, hours) in enumerate(work_duration_rows, 1):
        text = f'График работы: {a} — {ta}; {b} — {tb}; {c} — {tc}. Сколько часов работает {target}?'
        unit = 'час' if hours == 1 else ('часа' if 2 <= hours <= 4 else 'часов')
        cases.append(make_case(f'v304_work_duration_{idx:02d}', 'v304_g2_work_graph_duration', text, f'{target} работает {hours} {unit}', number=hours, unit=unit))

    route_after_rows = [
        ('дом → школа → парк → библиотека', 'школы', 'парк'),
        ('класс → столовая → спортзал → двор', 'столовой', 'спортзал'),
        ('остановка → магазин → аптека → дом', 'магазина', 'аптека'),
        ('музей → площадь → театр → кафе', 'площади', 'театр'),
        ('дом → мост → парк → школа', 'моста', 'парк'),
        ('станция → сквер → почта → рынок', 'сквера', 'почта'),
    ]
    for idx, (route, target, ans) in enumerate(route_after_rows, 1):
        text = f'Схема маршрута: {route}. Что находится после {target}?'
        cases.append(make_case(f'v304_route_after_{idx:02d}', 'v304_g2_route_scheme_after', text, ans))

    route_between_rows = [
        ('дом → школа → парк → библиотека', 'домом', 'парком', 'школа'),
        ('класс → столовая → спортзал → двор', 'классом', 'спортзалом', 'столовая'),
        ('остановка → магазин → аптека → дом', 'магазином', 'домом', 'аптека'),
        ('музей → площадь → театр → кафе', 'музеем', 'театром', 'площадь'),
        ('дом → мост → парк → школа', 'домом', 'парком', 'мост'),
    ]
    for idx, (route, a, b, ans) in enumerate(route_between_rows, 1):
        text = f'Схема маршрута: {route}. Что находится между {a} и {b}?'
        cases.append(make_case(f'v304_route_between_{idx:02d}', 'v304_g2_route_scheme_between', text, ans))

    route_steps_rows = [
        ('дом → школа → парк → библиотека', 'дома', 'библиотеки', 3),
        ('класс → столовая → спортзал → двор', 'класса', 'двора', 3),
        ('остановка → магазин → аптека → дом', 'остановки', 'дома', 3),
        ('музей → площадь → театр → кафе', 'музея', 'кафе', 3),
        ('дом → мост → парк → школа', 'дома', 'школы', 3),
    ]
    for idx, (route, a, b, steps) in enumerate(route_steps_rows, 1):
        text = f'Схема маршрута: {route}. Сколько переходов от {a} до {b}?'
        unit = 'переход' if steps == 1 else ('перехода' if 2 <= steps <= 4 else 'переходов')
        cases.append(make_case(f'v304_route_steps_{idx:02d}', 'v304_g2_route_scheme_steps', text, f'{steps} {unit}', number=steps, unit=unit))

    select_single_rows = [
        ('тетрадь', 12, 'ручка', 8, 'альбом', 25, 'тетрадь', 12),
        ('карандаш', 6, 'линейка', 14, 'ластик', 5, 'линейка', 14),
        ('булочка', 18, 'сок', 32, 'яблоко', 9, 'сок', 32),
        ('наклейка', 7, 'открытка', 15, 'конверт', 4, 'открытка', 15),
        ('блокнот', 28, 'ручка', 9, 'папка', 35, 'папка', 35),
    ]
    for idx, (a, pa, b, pb, c, pc, target, ans) in enumerate(select_single_rows, 1):
        text = f'Данные для выбора: {a} — {pa} руб.; {b} — {pb} руб.; {c} — {pc} руб. Сколько рублей стоит {target}?'
        cases.append(make_case(f'v304_select_single_{idx:02d}', 'v304_g2_select_data_single', text, f'{ans} руб.', number=ans, unit='руб.'))

    select_total_rows = [
        ('тетрадь', 12, 'ручка', 8, 'альбом', 25, 3, 'тетради', 36),
        ('карандаш', 6, 'линейка', 14, 'ластик', 5, 4, 'карандаша', 24),
        ('булочка', 18, 'сок', 32, 'яблоко', 9, 2, 'булочки', 36),
        ('наклейка', 7, 'открытка', 15, 'конверт', 4, 5, 'наклеек', 35),
        ('блокнот', 28, 'ручка', 9, 'папка', 35, 2, 'блокнота', 56),
        ('тетрадь', 13, 'ручка', 11, 'альбом', 27, 4, 'ручки', 44),
        ('карандаш', 5, 'линейка', 16, 'ластик', 7, 3, 'ластика', 21),
        ('булочка', 19, 'сок', 30, 'яблоко', 8, 6, 'яблок', 48),
    ]
    for idx, (a, pa, b, pb, c, pc, qty, target, ans) in enumerate(select_total_rows, 1):
        text = f'Данные для выбора: {a} — {pa} руб.; {b} — {pb} руб.; {c} — {pc} руб. Сколько рублей стоят {qty} {target}?'
        cases.append(make_case(f'v304_select_total_{idx:02d}', 'v304_g2_select_data_total', text, f'{ans} руб.', number=ans, unit='руб.'))

    diagram_lookup_rows = [
        ('Аня', 6, 'Боря', 4, 'Вера', 8, 'наклеек', 'Веры', 8),
        ('Оля', 9, 'Коля', 5, 'Ира', 7, 'открыток', 'Оли', 9),
        ('Миша', 3, 'Даша', 8, 'Саша', 6, 'книг', 'Даши', 8),
        ('Лена', 10, 'Петя', 7, 'Юра', 4, 'значков', 'Пети', 7),
        ('Нина', 5, 'Толя', 9, 'Рита', 6, 'рисунков', 'Толи', 9),
    ]
    for idx, (a, va, b, vb, c, vc, item, target, ans) in enumerate(diagram_lookup_rows, 1):
        text = f'Диаграмма: {a} — {va}; {b} — {vb}; {c} — {vc}. Сколько {item} у {target}?'
        cases.append(make_case(f'v304_diagram_lookup_{idx:02d}', 'v304_g2_diagram_lookup', text, f'{ans} {item}', number=ans, unit=item))

    diagram_compare_rows = [
        ('Аня', 6, 'Боря', 4, 'Вера', 8, 'наклеек', 'Веры', 'Бори', 4),
    ]
    for idx, (a, va, b, vb, c, vc, item, first, second, ans) in enumerate(diagram_compare_rows, 1):
        text = f'Диаграмма: {a} — {va}; {b} — {vb}; {c} — {vc}. На сколько {item} у {first} больше, чем у {second}?'
        cases.append(make_case(f'v304_diagram_compare_{idx:02d}', 'v304_g2_diagram_compare', text, str(ans), number=ans))

    if len(cases) != 100:
        raise AssertionError(f'V304 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V304 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V304 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V304 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v304_g2_math_information_live_ui_cases()


# --- v307 live UI audit: 3 класс, раздел 3 — Текстовые задачи ---

def _v307_g3_text_problems_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def plural(n: int, one: str, two: str, five: str) -> str:
        n = abs(int(n)); last_two = n % 100; last = n % 10
        if 11 <= last_two <= 14:
            return five
        if last == 1:
            return one
        if 2 <= last <= 4:
            return two
        return five

    forms = {
        'книга': ('книга', 'книги', 'книг'),
        'коробка': ('коробка', 'коробки', 'коробок'),
        'карандаш': ('карандаш', 'карандаша', 'карандашей'),
        'тетрадь': ('тетрадь', 'тетради', 'тетрадей'),
        'деталь': ('деталь', 'детали', 'деталей'),
        'задача': ('задача', 'задачи', 'задач'),
        'марка': ('марка', 'марки', 'марок'),
        'альбом': ('альбом', 'альбома', 'альбомов'),
        'час': ('час', 'часа', 'часов'),
        'пачка': ('пачка', 'пачки', 'пачек'),
    }

    def count(n: int, unit: str) -> str:
        if unit in {'руб.', 'км', 'м'}:
            return f'{n} {unit}'
        f = forms[unit]
        return f'{n} {plural(n, *f)}'

    def answer_count(n: int, unit: str) -> str:
        if unit in {'руб.', 'руб', 'рубль', 'рубля', 'рублей'}:
            return f'{n} {plural(n, "рубль", "рубля", "рублей")}'
        return count(n, unit)

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | None = None, unit: str = '') -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 3,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    cases: list[dict[str, Any]] = []

    add_rows = [(128,47,35),(215,68,42),(340,125,75),(156,39,84),(420,57,63),(275,86,54),(198,47,92),(360,115,38),(249,73,61),(512,88,49)]
    for idx, (a, b, c) in enumerate(add_rows, 1):
        ans = a + b + c
        text = f'В библиотеке было {count(a, "книга")}. Привезли {count(b, "книга")}, а потом ещё {count(c, "книга")}. Сколько книг стало в библиотеке?'
        cases.append(make_case(f'v307_two_step_add_{idx:02d}', 'v307_g3_two_step_addition', text, f'в библиотеке стало {count(ans, "книга")}', number=ans, unit=plural(ans, *forms['книга'])))

    sub_rows = [(520,86,54),(430,115,75),(680,240,96),(395,87,48),(704,128,176),(560,95,135),(910,260,140),(478,126,83),(630,205,125),(845,315,130)]
    for idx, (a, b, c) in enumerate(sub_rows, 1):
        ans = a - b - c
        text = f'На складе было {count(a, "коробка")}. Утром отправили {count(b, "коробка")}, вечером отправили {count(c, "коробка")}. Сколько коробок осталось на складе?'
        cases.append(make_case(f'v307_two_step_sub_{idx:02d}', 'v307_g3_two_step_subtraction', text, f'на складе осталось {count(ans, "коробка")}', number=ans, unit=plural(ans, *forms['коробка'])))

    group_rows = [(6,24,38),(8,19,45),(7,32,64),(5,48,57),(9,18,71),(4,75,96),(6,37,82),(8,26,59),(7,45,113),(5,64,88)]
    for idx, (boxes, per, used) in enumerate(group_rows, 1):
        ans = boxes * per - used
        text = f'В {boxes} коробках лежало по {count(per, "карандаш")}. {count(used, "карандаш")} раздали. Сколько карандашей осталось?'
        cases.append(make_case(f'v307_equal_groups_{idx:02d}', 'v307_g3_equal_groups', text, f'осталось {count(ans, "карандаш")}', number=ans, unit=plural(ans, *forms['карандаш'])))

    share_rows = [(72,8,3),(96,6,4),(135,9,5),(84,7,6),(120,10,2),(144,12,3),(90,5,7),(108,9,4),(132,11,5),(160,8,6)]
    for idx, (total, packs, extra) in enumerate(share_rows, 1):
        ans = total // packs + extra
        text = f'Учитель разложил {count(total, "тетрадь")} поровну в {count(packs, "пачка")}. Потом в каждую пачку добавили {count(extra, "тетрадь")}. Сколько тетрадей стало в каждой пачке?'
        cases.append(make_case(f'v307_equal_sharing_{idx:02d}', 'v307_g3_equal_sharing', text, f'в каждой пачке стало {count(ans, "тетрадь")}', number=ans, unit=plural(ans, *forms['тетрадь'])))

    price_rows = [(5,36,18),(4,52,24),(6,28,35),(7,45,60),(3,84,27),(8,25,49),(5,64,32),(9,18,56),(4,75,40),(6,55,38)]
    for idx, (qty, price, extra) in enumerate(price_rows, 1):
        ans = qty * price + extra
        text = f'Купили {count(qty, "альбом")} по {price} руб. и кисть за {extra} руб. Сколько рублей заплатили?'
        cases.append(make_case(f'v307_price_total_{idx:02d}', 'v307_g3_price_quantity_cost', text, f'заплатили {answer_count(ans, "руб.")}', number=ans, unit=plural(ans, 'рубль', 'рубля', 'рублей')))

    move_rows = [(3,14,2,12),(4,16,3,11),(2,28,5,18),(5,13,2,21),(3,25,4,17),(6,12,3,15),(2,35,4,20),(4,18,2,24),(5,16,3,19),(3,22,5,14)]
    for idx, (t1, v1, t2, v2) in enumerate(move_rows, 1):
        ans = t1 * v1 + t2 * v2
        text = f'Пешеход шел {count(t1, "час")} со скоростью {v1} км/ч и {count(t2, "час")} со скоростью {v2} км/ч. Сколько километров он прошел?'
        cases.append(make_case(f'v307_movement_two_speeds_{idx:02d}', 'v307_g3_movement', text, f'пешеход прошёл {count(ans, "км")}', number=ans, unit='км'))

    prod_rows = [(18,4,3),(24,3,5),(15,6,2),(32,2,4),(21,5,3),(27,3,4),(16,7,2),(35,2,5),(28,4,2),(19,6,3)]
    for idx, (rate, t1, t2) in enumerate(prod_rows, 1):
        ans = rate * (t1 + t2)
        text = f'Мастер делает {count(rate, "деталь")} в час. Он работал {count(t1, "час")} утром и {count(t2, "час")} вечером. Сколько деталей сделал мастер?'
        cases.append(make_case(f'v307_productivity_{idx:02d}', 'v307_g3_productivity', text, f'мастер сделал {count(ans, "деталь")}', number=ans, unit=plural(ans, *forms['деталь'])))

    table_rows = [(24,31,18),(35,28,22),(42,19,27),(18,36,25),(50,47,21),(29,34,32),(41,26,38),(33,45,17),(27,52,16),(39,23,44)]
    for idx, (a, b, c) in enumerate(table_rows, 1):
        ans = a + b
        text = f'По таблице: понедельник — {count(a, "книга")}, вторник — {count(b, "книга")}, среда — {count(c, "книга")}. Сколько книг взяли в понедельник и вторник вместе?'
        cases.append(make_case(f'v307_table_total_{idx:02d}', 'v307_g3_table_model', text, count(ans, 'книга'), number=ans, unit=plural(ans, *forms['книга'])))

    diagram_rows = [(12,18,15),(24,31,28),(17,25,21),(36,44,39),(28,35,30),(19,27,22),(33,41,37),(26,34,29),(45,53,48),(21,32,27)]
    for idx, (a, b, c) in enumerate(diagram_rows, 1):
        diff = b - a
        text = f'На диаграмме: у Ани {count(a, "марка")}, у Бори {count(b, "марка")}, у Веры {count(c, "марка")}. На сколько марок у Бори больше, чем у Ани?'
        final = f'на {diff} {plural(diff, *forms["марка"])} больше'
        cases.append(make_case(f'v307_diagram_compare_{idx:02d}', 'v307_g3_diagram_model', text, final, number=diff, unit=plural(diff, *forms['марка'])))

    reverse_rows = [(5,18,110),(4,25,95),(6,14,86),(7,16,68),(3,42,74),(8,12,57),(5,24,123),(9,11,80),(6,21,99),(4,37,52)]
    for idx, (qty, price, left) in enumerate(reverse_rows, 1):
        ans = qty * price + left
        text = f'После покупки {count(qty, "тетрадь")} по {price} руб. у Димы осталось {left} руб. Сколько рублей было у Димы сначала?'
        cases.append(make_case(f'v307_reverse_cost_{idx:02d}', 'v307_g3_reverse_problem', text, f'у Димы было {answer_count(ans, "руб.")}', number=ans, unit=plural(ans, 'рубль', 'рубля', 'рублей')))

    if len(cases) != 100:
        raise AssertionError(f'V307 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V307 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V307 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V307 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v307_g3_text_problems_live_ui_cases()


# --- v308 live UI audit: 3 класс, раздел 4 — Геометрия ---

def _v308_g3_geometry_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | None = None, unit: str = '') -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 3,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    cases: list[dict[str, Any]] = []

    rect_area_rows = [(12, 7), (15, 6), (18, 5), (24, 4), (16, 8), (21, 3), (14, 9), (11, 10), (25, 5), (13, 6)]
    for idx, (a, b) in enumerate(rect_area_rows, 1):
        area = a * b
        text = f'У прямоугольника длина {a} см, ширина {b} см. Найди площадь прямоугольника.'
        cases.append(make_case(f'v308_rectangle_area_{idx:02d}', 'v308_g3_rectangle_area', text, f'площадь прямоугольника равна {area} см²', number=area, unit='см²'))

    rect_perimeter_rows = [(14, 6), (17, 8), (22, 5), (19, 7), (25, 9), (16, 11), (31, 4), (28, 6), (23, 12), (18, 10)]
    for idx, (a, b) in enumerate(rect_perimeter_rows, 1):
        p = 2 * (a + b)
        text = f'У прямоугольника длина {a} см, ширина {b} см. Найди периметр прямоугольника.'
        cases.append(make_case(f'v308_rectangle_perimeter_{idx:02d}', 'v308_g3_rectangle_perimeter', text, f'периметр прямоугольника равен {p} см', number=p, unit='см'))

    square_area_rows = [7, 8, 9, 11, 12, 13, 15, 16, 18, 20]
    for idx, side in enumerate(square_area_rows, 1):
        area = side * side
        text = f'Сторона квадрата {side} см. Найди площадь квадрата.'
        cases.append(make_case(f'v308_square_area_{idx:02d}', 'v308_g3_square_area', text, f'площадь квадрата {area} см²', number=area, unit='см²'))

    square_perimeter_rows = [9, 12, 14, 15, 18, 21, 24, 25, 27, 30]
    for idx, side in enumerate(square_perimeter_rows, 1):
        p = side * 4
        text = f'Сторона квадрата {side} см. Вычисли периметр квадрата.'
        cases.append(make_case(f'v308_square_perimeter_{idx:02d}', 'v308_g3_square_perimeter', text, f'периметр квадрата равен {p} см', number=p, unit='см'))

    width_by_area_rows = [(96, 12), (84, 14), (120, 15), (144, 18), (132, 11), (150, 25), (126, 14), (160, 20), (108, 12), (180, 15)]
    for idx, (area, length) in enumerate(width_by_area_rows, 1):
        width = area // length
        text = f'Площадь прямоугольника {area} кв. см, длина {length} см. Найди ширину.'
        cases.append(make_case(f'v308_width_by_area_{idx:02d}', 'v308_g3_side_by_area', text, f'ширина прямоугольника равна {width} см', number=width, unit='см'))

    width_by_perimeter_rows = [(50, 17), (64, 20), (78, 27), (90, 31), (72, 25), (84, 33), (58, 19), (96, 36), (88, 29), (70, 24)]
    for idx, (p, length) in enumerate(width_by_perimeter_rows, 1):
        width = p // 2 - length
        text = f'Периметр прямоугольника {p} см, длина {length} см. Найди ширину.'
        cases.append(make_case(f'v308_width_by_perimeter_{idx:02d}', 'v308_g3_side_by_perimeter', text, f'ширина прямоугольника равна {width} см', number=width, unit='см'))

    composite_sum_rows = [(8, 5, 6, 4), (12, 4, 7, 6), (9, 8, 5, 7), (14, 3, 10, 5), (11, 6, 8, 4), (15, 5, 6, 9), (13, 7, 4, 8), (16, 4, 9, 6), (18, 3, 7, 5), (10, 9, 12, 4)]
    for idx, (a, b, c, d) in enumerate(composite_sum_rows, 1):
        total = a * b + c * d
        text = f'Фигура составлена из двух прямоугольников: {a} см на {b} см и {c} см на {d} см. Найди площадь всей фигуры.'
        cases.append(make_case(f'v308_composite_area_sum_{idx:02d}', 'v308_g3_composite_area_sum', text, f'площадь всей фигуры равна {total} см²', number=total, unit='см²'))

    composite_diff_rows = [(15, 8, 4), (18, 9, 6), (20, 7, 5), (16, 10, 4), (22, 6, 3), (14, 12, 5), (24, 8, 6), (19, 11, 7), (21, 9, 4), (17, 13, 5)]
    for idx, (a, b, side) in enumerate(composite_diff_rows, 1):
        remain = a * b - side * side
        text = f'Из прямоугольника {a} см на {b} см вырезали квадрат со стороной {side} см. Найди площадь оставшейся фигуры.'
        cases.append(make_case(f'v308_composite_area_difference_{idx:02d}', 'v308_g3_composite_area_difference', text, f'площадь оставшейся фигуры равна {remain} см²', number=remain, unit='см²'))

    triangle_rows = [(7, 9, 11), (12, 8, 10), (15, 14, 13), (18, 7, 16), (20, 11, 9), (13, 17, 19), (21, 15, 12), (16, 16, 10), (23, 14, 18), (25, 20, 15)]
    for idx, (a, b, c) in enumerate(triangle_rows, 1):
        p = a + b + c
        text = f'У треугольника стороны {a} см, {b} см и {c} см. Найди периметр треугольника.'
        cases.append(make_case(f'v308_triangle_perimeter_{idx:02d}', 'v308_g3_triangle_perimeter', text, f'периметр треугольника равен {p} см', number=p, unit='см'))

    polyline_rows = [(14, 8, 12, 6), (9, 15, 7, 11), (18, 6, 10, 5), (13, 13, 8, 4), (20, 7, 9, 12), (16, 5, 14, 9), (11, 17, 6, 10), (22, 8, 5, 15), (19, 4, 16, 7), (12, 12, 12, 12)]
    for idx, (a, b, c, d) in enumerate(polyline_rows, 1):
        total = a + b + c + d
        text = f'Ломаная состоит из отрезков {a} см, {b} см, {c} см и {d} см. Найди длину ломаной.'
        cases.append(make_case(f'v308_polyline_length_{idx:02d}', 'v308_g3_polyline_length', text, f'длина ломаной равна {total} см', number=total, unit='см'))

    if len(cases) != 100:
        raise AssertionError(f'V308 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V308 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V308 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V308 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v308_g3_geometry_live_ui_cases()


# --- v309 live UI audit: 3 класс, раздел 5 — Математическая информация ---

def _v309_g3_math_information_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def plural(n: int, one: str, two: str, five: str) -> str:
        n = abs(int(n)); last_two = n % 100; last = n % 10
        if 11 <= last_two <= 14:
            return five
        if last == 1:
            return one
        if 2 <= last <= 4:
            return two
        return five

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | None = None, unit: str = '') -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 3,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    def visitors(n: int) -> str:
        return f'{n} {plural(n, "посетитель", "посетителя", "посетителей")}'

    def minutes(n: int) -> str:
        return f'{n} {plural(n, "минута", "минуты", "минут")}'

    cases: list[dict[str, Any]] = []

    attendance_rows = [(128,145,137),(96,118,104),(215,207,232),(174,189,166),(305,298,312),(142,156,149),(260,274,251),(119,135,128),(333,341,327),(188,176,195)]
    for idx, (mon, tue, wed) in enumerate(attendance_rows, 1):
        text = f'Таблица посещаемости: понедельник — {mon}; вторник — {tue}; среда — {wed}. Сколько посетителей было во вторник?'
        cases.append(make_case(f'v309_attendance_lookup_{idx:02d}', 'v309_g3_table_lookup', text, visitors(tue), number=tue, unit=plural(tue, 'посетитель', 'посетителя', 'посетителей')))

    order_rows = [(36,28,19),(54,47,25),(68,32,41),(75,59,23),(83,46,37),(92,64,58),(48,73,29),(66,55,44),(105,87,62),(124,96,81)]
    for idx, (pencils, pens, notebooks) in enumerate(order_rows, 1):
        total = pencils + notebooks
        text = f'Таблица заказов: карандаши — {pencils}; ручки — {pens}; тетради — {notebooks}. Сколько всего карандашей и тетрадей заказали?'
        cases.append(make_case(f'v309_order_total_{idx:02d}', 'v309_g3_table_total', text, f'{total} штук', number=total, unit='штук'))

    score_rows = [(48,63,57),(72,89,80),(95,117,102),(126,144,138),(158,181,169),(64,77,70),(205,236,221),(139,155,148),(88,106,99),(172,194,183)]
    for idx, (a, b, c) in enumerate(score_rows, 1):
        diff = b - a
        ball_unit = plural(diff, 'балл', 'балла', 'баллов')
        text = f'По таблице соревнований: 3А класс — {a} баллов; 3Б класс — {b} баллов; 3В класс — {c} баллов. На сколько баллов у 3Б класса больше, чем у 3А класса?'
        cases.append(make_case(f'v309_score_difference_{idx:02d}', 'v309_g3_table_difference', text, f'у 3Б класса на {diff} {ball_unit} больше, чем у 3А класса', number=diff, unit=ball_unit))

    max_rows = [(48,36,29,'яблоки'),(34,52,41,'груши'),(27,39,58,'сливы'),(65,44,51,'яблоки'),(49,73,66,'груши'),(81,77,94,'сливы'),(106,98,87,'яблоки'),(55,69,62,'груши'),(72,64,91,'сливы'),(120,104,116,'яблоки')]
    for idx, (apples, pears, plums, winner) in enumerate(max_rows, 1):
        text = f'Диаграмма урожая: яблоки — {apples} кг; груши — {pears} кг; сливы — {plums} кг. Какой показатель самый большой?'
        cases.append(make_case(f'v309_chart_max_{idx:02d}', 'v309_g3_diagram_max', text, f'самый большой показатель: {winner}'))

    chart_diff_rows = [(58,43,35),(76,52,61),(94,78,70),(125,96,104),(67,45,59),(83,64,71),(110,87,93),(139,118,121),(72,56,49),(101,74,88)]
    for idx, (apples, pears, plums) in enumerate(chart_diff_rows, 1):
        diff = apples - pears
        text = f'Диаграмма урожая: яблоки — {apples} кг; груши — {pears} кг; сливы — {plums} кг. На сколько килограммов яблок больше, чем груш?'
        cases.append(make_case(f'v309_chart_difference_{idx:02d}', 'v309_g3_diagram_difference', text, f'на {diff} кг яблок больше, чем груш', number=diff, unit='кг'))

    hike_rows = [('09:15','10:05','11:20',50),('08:30','09:10','10:45',40),('12:05','12:55','14:10',50),('13:20','14:00','15:35',40),('07:45','08:30','09:50',45),('10:10','10:55','12:05',45),('15:25','16:15','17:30',50),('11:40','12:20','13:45',40),('06:50','07:35','08:55',45),('14:05','14:55','16:10',50)]
    for idx, (start, rest, finish, mins) in enumerate(hike_rows, 1):
        text = f'Расписание похода: старт — {start}; привал — {rest}; финиш — {finish}. Сколько минут прошло от старта до привала?'
        cases.append(make_case(f'v309_schedule_duration_{idx:02d}', 'v309_g3_schedule_duration', text, minutes(mins), number=mins, unit=plural(mins, 'минута', 'минуты', 'минут')))

    lesson_rows = [
        ('математика','русский язык','чтение','2','русский язык'),('окружающий мир','математика','музыка','1','окружающий мир'),('литературное чтение','технология','математика','3','математика'),('русский язык','физкультура','изо','2','физкультура'),('математика','английский язык','окружающий мир','3','окружающий мир'),
        ('чтение','русский язык','математика','1','чтение'),('музыка','математика','труд','2','математика'),('окружающий мир','изо','русский язык','3','русский язык'),('математика','чтение','физкультура','1','математика'),('русский язык','математика','музыка','2','математика'),
    ]
    for idx, (s1, s2, s3, target, subject) in enumerate(lesson_rows, 1):
        text = f'Расписание уроков: 1 урок — {s1}; 2 урок — {s2}; 3 урок — {s3}. Какой предмет на {target} уроке?'
        cases.append(make_case(f'v309_lesson_lookup_{idx:02d}', 'v309_g3_schedule_lookup', text, f'на {target} уроке {subject}'))

    route_rows = [(250,180),(340,160),(125,275),(410,230),(360,145),(520,280),(195,305),(470,190),(285,215),(600,125)]
    for idx, (first, second) in enumerate(route_rows, 1):
        total = first + second
        text = f'Схема маршрута: дом — {first} м — парк — {second} м — школа. Сколько метров от дома до школы через парк?'
        cases.append(make_case(f'v309_route_distance_{idx:02d}', 'v309_g3_route_distance', text, f'{total} м', number=total, unit='м'))

    price_rows = [(80,25,40,2),(65,30,45,3),(120,35,50,2),(90,28,36,4),(75,22,31,3),(110,40,55,2),(95,33,48,3),(70,27,39,4),(130,45,60,2),(85,29,42,3)]
    for idx, (ticket, program, badge, qty) in enumerate(price_rows, 1):
        total = ticket * qty + program
        noun = plural(qty, 'билет', 'билета', 'билетов')
        text = f'Прайс-лист: билет — {ticket} руб.; программа — {program} руб.; значок — {badge} руб. Сколько рублей нужно заплатить за {qty} {noun} и 1 программу?'
        cases.append(make_case(f'v309_price_from_table_{idx:02d}', 'v309_g3_price_table', text, f'{total} {plural(total, 'рубль', 'рубля', 'рублей')}', number=total, unit=plural(total, 'рубль', 'рубля', 'рублей')))

    pictogram_rows = [(5,4,3),(4,6,5),(10,3,2),(6,5,4),(8,7,6),(3,9,8),(7,4,5),(9,5,3),(2,12,10),(5,8,7)]
    for idx, (scale, anya, borya) in enumerate(pictogram_rows, 1):
        total = scale * anya
        circle_word = plural(anya, 'кружок', 'кружка', 'кружков')
        b_circle_word = plural(borya, 'кружок', 'кружка', 'кружков')
        text = f'Пиктограмма: один кружок = {scale} книг. У Ани — {anya} {circle_word}, у Бори — {borya} {b_circle_word}. Сколько книг у Ани?'
        cases.append(make_case(f'v309_pictogram_scale_{idx:02d}', 'v309_g3_pictogram_scale', text, f'{total} книг', number=total, unit='книг'))

    if len(cases) != 100:
        raise AssertionError(f'V309 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V309 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V309 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V309 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v309_g3_math_information_live_ui_cases()

# --- v310 live UI audit: 4 класс, раздел 1 — Числа и величины ---

def _v310_g4_numbers_quantities_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def plural(n: int, one: str, two: str, five: str) -> str:
        n = abs(int(n)); last_two = n % 100; last = n % 10
        if 11 <= last_two <= 14:
            return five
        if last == 1:
            return one
        if 2 <= last <= 4:
            return two
        return five

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | str | None = None, unit: str = '') -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 4,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    cases: list[dict[str, Any]] = []

    write_rows = [(3,5,2,7,4,6),(4,0,8,2,9,1),(6,3,1,5,0,8),(2,7,9,0,6,4),(8,1,4,9,3,5),(5,6,0,4,2,7),(7,2,5,6,8,0),(9,4,3,1,7,2),(1,8,6,3,5,9),(6,9,7,8,0,4)]
    for idx, (hth, tth, th, h, t, u) in enumerate(write_rows, 1):
        n = hth * 100000 + tth * 10000 + th * 1000 + h * 100 + t * 10 + u
        text = f'Запиши число: {hth} сотен тысяч, {tth} десятков тысяч, {th} тысяч, {h} сотен, {t} десятков и {u} единиц.'
        cases.append(make_case(f'v310_place_value_write_{idx:02d}', 'v310_g4_place_value_write', text, str(n), number=n))

    expanded_rows = [583407, 406250, 720615, 901304, 654080, 238916, 870042, 315709, 492630, 760508]
    for idx, n in enumerate(expanded_rows, 1):
        digits = list(str(n)); length = len(digits); parts = []
        for pos, ch in enumerate(digits):
            dgt = int(ch); place = 10 ** (length - pos - 1)
            if dgt:
                parts.append(str(dgt * place))
        final = ' + '.join(parts)
        text = f'Разложи число {n} на разрядные слагаемые.'
        cases.append(make_case(f'v310_expanded_form_{idx:02d}', 'v310_g4_expanded_form', text, final, number=n))

    compare_rows = [(428560,428650),(905120,905102),(317845,317845),(760019,706019),(150300,150030),(99999,100000),(640700,640070),(812456,812465),(230001,229999),(555555,555550)]
    for idx, (a, b) in enumerate(compare_rows, 1):
        sign = '<' if a < b else ('>' if a > b else '=')
        final = f'{a} {sign} {b}'
        text = f'Сравни числа {a} и {b}.'
        cases.append(make_case(f'v310_compare_numbers_{idx:02d}', 'v310_g4_compare_numbers', text, final))

    round_rows = [(468732,'тысяч',469000),(123456,'тысяч',123000),(785500,'тысяч',786000),(904499,'тысяч',904000),(315750,'тысяч',316000),(468732,'десятков тысяч',470000),(123456,'десятков тысяч',120000),(785500,'десятков тысяч',790000),(904499,'десятков тысяч',900000),(315750,'десятков тысяч',320000)]
    for idx, (n, kind, ans) in enumerate(round_rows, 1):
        text = f'Округли число {n} до {kind}.'
        cases.append(make_case(f'v310_rounding_{idx:02d}', 'v310_g4_rounding', text, str(ans), number=ans))

    digit_rows = [(583407,'сотен тысяч',5,'сотен тысяч'),(583407,'десятков тысяч',8,'десятков тысяч'),(583407,'тысяч',3,'тысячи'),(406250,'сотен тысяч',4,'сотни тысяч'),(720615,'десятков тысяч',2,'десятка тысяч'),(901304,'тысяч',1,'тысяча'),(654080,'сотен тысяч',6,'сотен тысяч'),(238916,'десятков тысяч',3,'десятка тысяч'),(870042,'тысяч',0,'тысяч'),(315709,'сотен тысяч',3,'сотни тысяч')]
    for idx, (n, kind, digit, unit) in enumerate(digit_rows, 1):
        text = f'Сколько разрядных {kind} в числе {n}?'
        final = f'{digit} {unit}'
        cases.append(make_case(f'v310_digit_place_{idx:02d}', 'v310_g4_digit_place', text, final, number=digit, unit=unit))

    length_m_rows = [(4,320),(7,45),(12,608),(3,999),(15,250),(6,75),(20,5),(9,870),(11,410),(2,630)]
    for idx, (km, m) in enumerate(length_m_rows, 1):
        total = km * 1000 + m
        text = f'Сколько метров в {km} км {m} м?'
        cases.append(make_case(f'v310_length_meters_{idx:02d}', 'v310_g4_length_meters', text, f'{total} {plural(total, "метр", "метра", "метров")}', number=total, unit=plural(total, 'метр', 'метра', 'метров')))

    length_cm_rows = [(6,35),(8,4),(12,70),(3,99),(15,5),(9,48),(20,1),(7,60),(11,25),(4,88)]
    for idx, (m, cm) in enumerate(length_cm_rows, 1):
        total = m * 100 + cm
        text = f'Сколько сантиметров в {m} м {cm} см?'
        cases.append(make_case(f'v310_length_centimeters_{idx:02d}', 'v310_g4_length_centimeters', text, f'{total} см', number=total, unit='см'))

    mass_rows = [(3,250),(5,40),(12,600),(7,999),(9,5),(15,375),(20,80),(4,720),(11,110),(6,450)]
    for idx, (t, kg) in enumerate(mass_rows, 1):
        total = t * 1000 + kg
        text = f'Сколько килограммов в {t} т {kg} кг?'
        cases.append(make_case(f'v310_mass_kilograms_{idx:02d}', 'v310_g4_mass_kilograms', text, f'{total} {plural(total, "килограмм", "килограмма", "килограммов")}', number=total, unit=plural(total, 'килограмм', 'килограмма', 'килограммов')))

    time_rows = [(3,25),(5,40),(2,55),(7,10),(1,45),(4,5),(6,30),(8,15),(9,50),(12,0)]
    for idx, (h, minute) in enumerate(time_rows, 1):
        total = h * 60 + minute
        text = f'Сколько минут в {h} ч {minute} мин?'
        cases.append(make_case(f'v310_time_minutes_{idx:02d}', 'v310_g4_time_minutes', text, f'{total} {plural(total, "минута", "минуты", "минут")}', number=total, unit=plural(total, 'минута', 'минуты', 'минут')))

    area_rows = [('м²','дм²',6,600),('м²','дм²',12,1200),('м²','дм²',25,2500),('м²','дм²',40,4000),('м²','дм²',9,900),('дм²','см²',4,400),('дм²','см²',18,1800),('дм²','см²',35,3500),('дм²','см²',7,700),('дм²','см²',60,6000)]
    for idx, (src, dst, amount, total) in enumerate(area_rows, 1):
        if src == 'м²':
            text = f'Сколько квадратных дециметров в {amount} м²?'
        else:
            text = f'Сколько квадратных сантиметров в {amount} дм²?'
        cases.append(make_case(f'v310_area_conversion_{idx:02d}', 'v310_g4_area_conversion', text, f'{total} {dst}', number=total, unit=dst))

    if len(cases) != 100:
        raise AssertionError(f'V310 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V310 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V310 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V310 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v310_g4_numbers_quantities_live_ui_cases()



# --- v311 live UI audit: 4 класс, раздел 2 — Арифметические действия ---

def _v311_g4_arithmetic_actions_live_ui_cases() -> list[dict[str, Any]]:
    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]

    def make_case(case_id: str, category: str, text: str, final: str, *, number: int | str | None = None, unit: str = '') -> dict[str, Any]:
        return {
            'id': case_id,
            'grade': 4,
            'category': category,
            'name': case_id,
            'text': text,
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': number,
            'expectedUnit': unit,
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        }

    def eval_expr(expr: str) -> int:
        safe = expr.replace('·', '*').replace(':', '//')
        if not re.fullmatch(r'[0-9+\-*/() ]+', safe):
            raise AssertionError(f'Unsafe V311 expression: {expr}')
        return int(eval(safe, {'__builtins__': {}}, {}))

    cases: list[dict[str, Any]] = []

    addition_rows = [(478,236),(5827,3496),(20458,37905),(64509,2786),(99999,1),(120345,67890),(35678,42917),(76008,13992),(4506,8875),(70324,19876),(538210,46789),(306407,82593)]
    for idx, (a, b) in enumerate(addition_rows, 1):
        ans = a + b
        cases.append(make_case(f'v311_addition_{idx:02d}', 'v311_g4_addition', f'Вычисли: {a} + {b}.', str(ans), number=ans))

    subtraction_rows = [(910,456),(8205,3976),(70000,28456),(123456,7890),(100000,1),(654321,123456),(90008,45009),(50010,27895),(7304,1988),(210000,98765),(805600,406789),(432100,98765)]
    for idx, (a, b) in enumerate(subtraction_rows, 1):
        ans = a - b
        cases.append(make_case(f'v311_subtraction_{idx:02d}', 'v311_g4_subtraction', f'Вычисли: {a} - {b}.', str(ans), number=ans))

    multiplication_rows = [(345,6),(708,4),(1245,7),(3060,8),(523,9),(4812,5),(2304,6),(1907,3),(842,24),(315,18),(1206,15),(470,32),(2508,11),(136,47)]
    for idx, (a, b) in enumerate(multiplication_rows, 1):
        ans = a * b
        text = f'Вычисли произведение {a} и {b}.' if idx % 2 else f'Вычисли: {a} · {b}.'
        cases.append(make_case(f'v311_multiplication_{idx:02d}', 'v311_g4_multiplication', text, str(ans), number=ans))

    division_rows = [(864,6),(936,8),(1248,4),(2016,7),(4320,9),(1536,6),(2706,3),(3960,11),(8400,12),(5580,15),(7056,21),(4368,14),(10080,24),(12544,32)]
    for idx, (a, b) in enumerate(division_rows, 1):
        ans = a // b
        text = f'Вычисли частное {a} и {b}.' if idx % 2 else f'Вычисли: {a} : {b}.'
        cases.append(make_case(f'v311_division_{idx:02d}', 'v311_g4_division', text, str(ans), number=ans))

    remainder_rows = [(875,6),(943,7),(1250,9),(2045,8),(3671,5),(4900,13),(8057,12),(9999,14),(4567,25),(7088,31)]
    for idx, (a, b) in enumerate(remainder_rows, 1):
        q, r = divmod(a, b)
        final = f'{q}, остаток {r}'
        cases.append(make_case(f'v311_remainder_{idx:02d}', 'v311_g4_remainder_division', f'Выполни деление с остатком: {a} : {b}.', final, number=q))

    expression_rows = ['(480 + 360) : 7','720 - 45 · 8','(900 - 156) : 6','125 · 4 + 360','960 : (12 - 4)','(350 + 250) · 3','840 : 7 + 96','1000 - (375 + 268)','(72 + 48) : 6 + 19','540 : 9 · 8','(1200 - 300) : 15','86 · 7 - 235','(450 + 150) : 12','980 - 64 · 11','(705 + 195) : 9','320 + 840 : 12','(1500 - 420) : 18','48 · (36 - 29)']
    for idx, expr in enumerate(expression_rows, 1):
        ans = eval_expr(expr)
        cases.append(make_case(f'v311_expression_{idx:02d}', 'v311_g4_order_of_operations', f'Найди значение выражения {expr}.', str(ans), number=ans))

    equation_rows: list[tuple[str, int]] = []
    raw_equations = ['x + 285 = 740','350 + x = 920','x - 176 = 548','920 - x = 365','x · 7 = 1001','8 · x = 1872','x : 6 = 154','2016 : x = 12','x + 4096 = 9000','12000 - x = 3456','x - 2408 = 7592','x · 15 = 4500','24 · x = 7344','x : 18 = 320','9600 : x = 25','x + 67890 = 123456','500000 - x = 123456','x · 32 = 8192','x : 24 = 416','9990 : x = 27']
    for eq in raw_equations:
        m = re.match(r'^x \+ (\d+) = (\d+)$', eq)
        if m:
            a, b = map(int, m.groups()); val = b - a
        else:
            m = re.match(r'^(\d+) \+ x = (\d+)$', eq)
            if m:
                a, b = map(int, m.groups()); val = b - a
            else:
                m = re.match(r'^x - (\d+) = (\d+)$', eq)
                if m:
                    a, b = map(int, m.groups()); val = b + a
                else:
                    m = re.match(r'^(\d+) - x = (\d+)$', eq)
                    if m:
                        a, b = map(int, m.groups()); val = a - b
                    else:
                        m = re.match(r'^x · (\d+) = (\d+)$', eq)
                        if m:
                            a, b = map(int, m.groups()); val = b // a
                        else:
                            m = re.match(r'^(\d+) · x = (\d+)$', eq)
                            if m:
                                a, b = map(int, m.groups()); val = b // a
                            else:
                                m = re.match(r'^x : (\d+) = (\d+)$', eq)
                                if m:
                                    a, b = map(int, m.groups()); val = b * a
                                else:
                                    m = re.match(r'^(\d+) : x = (\d+)$', eq)
                                    if not m:
                                        raise AssertionError(eq)
                                    a, b = map(int, m.groups()); val = a // b
        equation_rows.append((eq, val))
    for idx, (eq, val) in enumerate(equation_rows, 1):
        final = f'x = {val}'
        cases.append(make_case(f'v311_equation_{idx:02d}', 'v311_g4_equation', f'Найди неизвестное число: {eq}.', final, number=val))

    if len(cases) != 100:
        raise AssertionError(f'V311 cases expected 100, got {len(cases)}')
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V311 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V311 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V311 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v311_g4_arithmetic_actions_live_ui_cases()


# --- v312 live UI audit: 4 класс, раздел 3 — Текстовые задачи ---

def _v312_g4_text_problems_live_ui_cases() -> list[dict[str, Any]]:
    """Build the accepted V312 text-problem audit cases from the service spec.

    The solver and the audit plan intentionally share the same deterministic
    case source so the browser UI proof checks rendering/transport, not a second
    hand-copied answer table.
    """
    from backend.service import _v312_case_specs  # local import avoids widening the public API

    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]
    category_blocks: list[tuple[str, str]] = [
        ('inventory_left', 'v312_g4_text_inventory_left'),
        ('third_container', 'v312_g4_text_third_container'),
        ('money_change', 'v312_g4_text_money_change'),
        ('price_from_total', 'v312_g4_text_price_from_total'),
        ('motion_two_leg', 'v312_g4_text_motion_two_leg'),
        ('motion_towards', 'v312_g4_text_motion_towards'),
        ('fraction_part', 'v312_g4_text_fraction_part'),
        ('fraction_whole', 'v312_g4_text_fraction_whole'),
        ('equal_groups_remaining', 'v312_g4_text_equal_groups_remaining'),
        ('time_end', 'v312_g4_text_time_end'),
    ]
    specs = list(_v312_case_specs().values())
    if len(specs) != 100:
        raise AssertionError(f'V312 service specs expected 100, got {len(specs)}')
    cases: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, 1):
        block_name, category = category_blocks[(index - 1) // 10]
        within = ((index - 1) % 10) + 1
        final = str(spec.get('final') or '').strip()
        case_id = f'v312_{block_name}_{within:02d}'
        cases.append({
            'id': case_id,
            'grade': 4,
            'category': category,
            'name': case_id,
            'text': str(spec.get('text') or '').strip(),
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': spec.get('number'),
            'expectedUnit': spec.get('unit') or '',
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        })
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V312 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V312 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V312 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v312_g4_text_problems_live_ui_cases()


# --- v313 live UI audit: 4 класс, раздел 4 — Геометрия ---

def _v313_g4_geometry_live_ui_cases() -> list[dict[str, Any]]:
    """Build V313.2 geometry audit cases from the service spec."""
    from backend.service import _v313_case_specs

    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]
    category_blocks: list[tuple[str, str]] = [
        ('rectangle_area', 'v313_g4_geometry_rectangle_area'),
        ('rectangle_perimeter', 'v313_g4_geometry_rectangle_perimeter'),
        ('square_area', 'v313_g4_geometry_square_area'),
        ('square_perimeter', 'v313_g4_geometry_square_perimeter'),
        ('side_by_area', 'v313_g4_geometry_side_by_area'),
        ('side_by_perimeter', 'v313_g4_geometry_side_by_perimeter'),
        ('composite_area_sum', 'v313_g4_geometry_composite_area_sum'),
        ('composite_area_difference', 'v313_g4_geometry_composite_area_difference'),
        ('cuboid_volume', 'v313_g4_geometry_cuboid_volume'),
        ('triangle_perimeter', 'v313_g4_geometry_triangle_perimeter'),
    ]
    specs = list(_v313_case_specs().values())
    if len(specs) != 100:
        raise AssertionError(f'V313.2 service specs expected 100, got {len(specs)}')
    cases: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, 1):
        block_name, category = category_blocks[(index - 1) // 10]
        within = ((index - 1) % 10) + 1
        final = str(spec.get('final') or '').strip()
        case_id = f'v313_{block_name}_{within:02d}'
        cases.append({
            'id': case_id,
            'grade': 4,
            'category': category,
            'name': case_id,
            'text': str(spec.get('text') or '').strip(),
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': spec.get('number'),
            'expectedUnit': spec.get('unit') or '',
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        })
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V313.2 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V313.2 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V313.2 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v313_g4_geometry_live_ui_cases()


# --- v314 live UI audit: 4 класс, раздел 5 — Математическая информация ---

def _v314_g4_math_information_live_ui_cases() -> list[dict[str, Any]]:
    """Build V314 mathematical-information audit cases from the service spec."""
    from backend.service import _v314_case_specs

    forbidden = [
        'Применяем правило:', 'lookup', 'answer map', 'generic fallback',
        'deterministic regression', 'Zad3', '```', '<html', '<!doctype', '</',
    ]
    category_blocks: list[tuple[str, str]] = [
        ('attendance_lookup', 'v314_g4_math_information_attendance_lookup'),
        ('order_total', 'v314_g4_math_information_order_total'),
        ('score_difference', 'v314_g4_math_information_score_difference'),
        ('diagram_max', 'v314_g4_math_information_diagram_max'),
        ('chart_difference', 'v314_g4_math_information_chart_difference'),
        ('schedule_duration', 'v314_g4_math_information_schedule_duration'),
        ('lesson_lookup', 'v314_g4_math_information_lesson_lookup'),
        ('route_distance', 'v314_g4_math_information_route_distance'),
        ('price_from_table', 'v314_g4_math_information_price_from_table'),
        ('pictogram_scale', 'v314_g4_math_information_pictogram_scale'),
    ]
    specs = list(_v314_case_specs().values())
    if len(specs) != 100:
        raise AssertionError(f'V317.1 service specs expected 100, got {len(specs)}')
    cases: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, 1):
        block_name, category = category_blocks[(index - 1) // 10]
        within = ((index - 1) % 10) + 1
        final = str(spec.get('final') or '').strip()
        case_id = f'v314_{block_name}_{within:02d}'
        cases.append({
            'id': case_id,
            'grade': 4,
            'category': category,
            'name': case_id,
            'text': str(spec.get('text') or '').strip(),
            'expected': [f'Ответ: {final}'],
            'expectedNumericAnswer': spec.get('number'),
            'expectedUnit': spec.get('unit') or '',
            'expectedFinalAnswer': final,
            'expectedSource': None,
            'expectedSourceFamily': None,
            'forbidden': list(forbidden),
            'shouldWarn': False,
        })
    seen: set[str] = set()
    for case in cases:
        text = str(case.get('text') or '')
        if text in seen:
            raise AssertionError(f'V317.1 duplicate case text: {text}')
        seen.add(text)
        if '  ' in text:
            raise AssertionError(f'V317.1 double spaces in {case.get("id")}')
        if not text[:1].isupper():
            raise AssertionError(f'V317.1 case text should start uppercase: {case.get("id")}')
    return cases


DEFAULT_AUDIT_CASES = DEFAULT_AUDIT_CASES + _v314_g4_math_information_live_ui_cases()
