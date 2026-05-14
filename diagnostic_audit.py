from __future__ import annotations

from collections import defaultdict
from typing import Any

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
    {'category': 'geometry', 'name': 'area_rect', 'text': 'У прямоугольника длина 8 см, ширина 5 см. Найди площадь.', 'expected': ['40 кв. см']},
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
        'category': str(case.get('category') or 'custom'),
        'name': str(case.get('name') or f'case_{index + 1}'),
        'text': str(case.get('text') or ''),
        'expected': _case_expected_fragments(case),
        'expectedSource': case.get('expectedSource'),
    }


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
        if fragment and fragment.lower() not in result.lower():
            issues.append(f'missing expected fragment {fragment!r}')
    low_source = source.lower()
    if any(low_source.startswith(marker) for marker in FORBIDDEN_SOURCES):
        issues.append(f'forbidden source {source!r}')
    for marker in FORBIDDEN_RESULT_MARKERS:
        if marker.lower() in result.lower():
            issues.append(f'forbidden marker {marker!r}')
    if '\n1)\n' in result or '\n2)\n' in result or '\n3)\n' in result or '\n4)\n' in result:
        issues.append('split action number formatting')
    return {
        'ok': not issues,
        'issues': issues,
        'source': source,
        'resultPreview': result[:260],
    }


async def run_math_audit(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    raw_cases = cases if cases is not None else DEFAULT_AUDIT_CASES
    normalized = [_normalize_case(case, i) for i, case in enumerate(raw_cases)]
    results: list[dict[str, Any]] = []
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {'passed': 0, 'failed': 0, 'total': 0})
    for case in normalized:
        payload = await generate_explanation_response(case['text'])
        checked = _check_payload(case, payload)
        row = {
            'category': case['category'],
            'name': case['name'],
            'ok': checked['ok'],
            'issues': checked['issues'],
            'source': checked['source'],
            'expectedSource': case.get('expectedSource'),
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
        'passed': passed,
        'failed': failed,
        'total': len(results),
        'allPassed': failed == 0,
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
    add('external_geometry', 'rect_area', 'Прямоугольник имеет длину 9 см и ширину 4 см. Найди площадь прямоугольника.', '36 кв. см')
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
        'Сколько сантиметров в 2 дм 5 см?', '25 сантиметров', expected_numeric=25, expected_unit='сантиметров', expected_final='25 сантиметров')
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
        'expectedUnit': case.get('expectedUnit'),
        'expectedFinalAnswer': case.get('expectedFinalAnswer'),
        'expectedSource': case.get('expectedSource'),
        'expectedSourceFamily': case.get('expectedSourceFamily'),
        'shouldWarn': bool(case.get('shouldWarn')),
    }


def _check_payload(case: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    import re

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
    expected_source_family = case.get('expectedSourceFamily')
    if expected_source_family and not source.startswith(str(expected_source_family)):
        issues.append(f'expected source family {expected_source_family!r}, got {source!r}')

    low_source = source.lower()
    if any(low_source.startswith(marker) for marker in FORBIDDEN_SOURCES):
        issues.append(f'forbidden source {source!r}')
    if case.get('shouldWarn'):
        if source != 'guard-multi-task':
            issues.append(f'expected multi-task warning, got source {source!r}')
        if 'разделите задания' not in result.lower():
            issues.append('missing multi-task warning text')
    else:
        if source.startswith('guard-low-confidence'):
            issues.append('solvable task returned low confidence')

    for fragment in case.get('expected') or []:
        if fragment and fragment.lower() not in result.lower():
            issues.append(f'missing expected fragment {fragment!r}')

    expected_final = case.get('expectedFinalAnswer')
    if expected_final and str(expected_final).lower() not in result.lower():
        issues.append(f'missing expected final answer phrase {expected_final!r}')

    expected_unit = case.get('expectedUnit')
    if expected_unit and str(expected_unit).lower() not in result.lower():
        issues.append(f'missing expected unit {expected_unit!r}')

    expected_numeric = case.get('expectedNumericAnswer')
    if expected_numeric is not None and expected_numeric != '':
        target = str(expected_numeric).replace(',', '.')
        normalized_result = result.replace(',', '.')
        if ':' in target:
            if target not in normalized_result:
                issues.append(f'missing expected numeric answer {expected_numeric!r}')
        else:
            pattern = r'(?<![0-9])' + re.escape(target) + r'(?![0-9])'
            if re.search(pattern, normalized_result) is None:
                issues.append(f'missing expected numeric answer {expected_numeric!r}')

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
    }
