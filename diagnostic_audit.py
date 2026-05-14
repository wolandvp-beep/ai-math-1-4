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
  'expectedUnit': 'сантиметров'},
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
  'expected': ['84 кв. см'],
  'expectedFinalAnswer': '84 кв. см',
  'expectedNumericAnswer': '84',
  'expectedUnit': 'кв. см'},
 {'id': 'v281_g3_rect_width_less_area',
  'name': 'v281_g3_rect_width_less_area',
  'grade': 3,
  'category': 'v281_geometry',
  'text': 'Длина прямоугольника 12 см, ширина на 5 см меньше. Найди площадь.',
  'expected': ['84 кв. см'],
  'expectedFinalAnswer': '84 кв. см',
  'expectedNumericAnswer': '84',
  'expectedUnit': 'кв. см'},
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
  'expected': ['81 кв. см'],
  'expectedFinalAnswer': '81 кв. см',
  'expectedNumericAnswer': '81',
  'expectedUnit': 'кв. см'},
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
  'expected': ['51 кв. см'],
  'expectedFinalAnswer': '51 кв. см',
  'expectedNumericAnswer': '51',
  'expectedUnit': 'кв. см'},
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
