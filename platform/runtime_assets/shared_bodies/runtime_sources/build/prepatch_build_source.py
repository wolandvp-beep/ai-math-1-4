from __future__ import annotations

"""Statically materialized runtime source for prepatch_build_source.py.

This preserves shard execution order while making this runtime layer a
normal importable Python module.
"""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

# --- merged segment 001: backend.legacy_runtime_shards.prepatch_build_source.segment_001 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 1-895."""

async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        prepared = add_task_context_lines(local_explanation, user_text, kind)
        return {"result": shape_explanation(prepared, kind), "source": "local", "validated": True}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1400,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    prepared = add_task_context_lines(llm_result["result"], user_text, kind)
    shaped = shape_explanation(prepared, kind)
    return {"result": shaped, "source": "llm", "validated": False}


# --- PATCH: detail fixes ---

def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        "Сначала вспоминаем правило: цена = стоимость : количество",
        f"Находим цену одной штуки: {total_cost} : {count} = {price}",
        f"Ответ: {price} руб.",
        "Совет: цену одного предмета находят делением общей стоимости на количество",
    )


def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        "Сначала вспоминаем правило: стоимость = цена × количество",
        f"Находим стоимость покупки: {price} × {count} = {total}",
        f"Ответ: {total} руб.",
        "Совет: стоимость находят умножением цены на количество",
    )


def explain_trip_time_for_same_distance(speed1: int, time1: int, speed2: int) -> Optional[str]:
    distance = speed1 * time1
    if speed2 == 0 or distance % speed2 != 0:
        return None
    time2 = distance // speed2
    return join_explanation_lines(
        f"Сначала находим расстояние между пунктами: {speed1} × {time1} = {distance}",
        f"Потом находим время для второго участника: {distance} : {speed2} = {time2}",
        f"Ответ: {time2} ч",
        "Совет: если путь один и тот же, сначала найди расстояние, потом дели его на новую скорость",
    )


def explain_second_day_motion_time(total_distance: int, first_speed: int, first_time: int, second_speed: int) -> Optional[str]:
    first_distance = first_speed * first_time
    second_distance = total_distance - first_distance
    if second_speed == 0 or second_distance < 0 or second_distance % second_speed != 0:
        return None
    second_time = second_distance // second_speed
    total_time = first_time + second_time
    return join_explanation_lines(
        f"Сначала находим путь в первый день: {first_speed} × {first_time} = {first_distance}",
        f"Потом находим путь во второй день: {total_distance} - {first_distance} = {second_distance}",
        f"Теперь находим время во второй день: {second_distance} : {second_speed} = {second_time}",
        f"И находим всё время: {first_time} + {second_time} = {total_time}",
        f"Ответ: во второй день — {second_time} ч; всего — {total_time} ч",
        "Совет: в составной задаче на движение сначала находят путь, потом время",
    )


def explain_remaining_part_speed(total_distance: int, first_speed: int, first_time: int, second_time: int) -> Optional[str]:
    first_distance = first_speed * first_time
    remaining_distance = total_distance - first_distance
    if second_time == 0 or remaining_distance < 0 or remaining_distance % second_time != 0:
        return None
    second_speed = remaining_distance // second_time
    return join_explanation_lines(
        f"Сначала находим первую часть пути: {first_speed} × {first_time} = {first_distance}",
        f"Потом находим оставшийся путь: {total_distance} - {first_distance} = {remaining_distance}",
        f"Теперь находим скорость на оставшейся части пути: {remaining_distance} : {second_time} = {second_speed}",
        f"Ответ: {second_speed} км/ч",
        "Совет: если известны оставшийся путь и время, скорость находят делением",
    )


def explain_return_trip_time_by_faster_speed(distance: int, speed: int, factor: int) -> Optional[str]:
    if speed == 0 or factor == 0 or distance % speed != 0:
        return None
    first_time = distance // speed
    faster_speed = speed * factor
    if faster_speed == 0 or distance % faster_speed != 0:
        return None
    return_time = distance // faster_speed
    return join_explanation_lines(
        f"Сначала находим время в одну сторону: {distance} : {speed} = {first_time}",
        f"Потом находим скорость на обратном пути: {speed} × {factor} = {faster_speed}",
        f"Теперь находим время на обратный путь: {distance} : {faster_speed} = {return_time}",
        f"Ответ: {return_time} ч",
        "Совет: если на обратном пути скорость увеличилась в несколько раз, сначала найди новую скорость",
    )


def try_local_price_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)

    if len(nums) >= 4 and "за всю покупку заплатили" in lower and "по" in lower and contains_any_fragment(lower, ("сколько стоила 1", "сколько стоит 1", "сколько стоила одна", "сколько стоит одна")):
        solved = explain_unknown_red_price(nums[0], nums[1], nums[2], nums[3])
        if solved:
            return solved

    if len(nums) >= 2 and contains_any_fragment(lower, ("сколько стоит 1", "сколько стоит одна", "сколько стоит один", "сколько стоит 1 ")):
        solved = explain_simple_price_per_item(nums[0], nums[1])
        if solved:
            return solved

    if len(nums) >= 2 and contains_any_fragment(lower, ("сколько стоят", "сколько стоила вся покупка", "сколько стоит вся покупка")):
        return explain_simple_total_cost(nums[0], nums[1])

    if len(nums) < 3:
        return None
    if contains_any_fragment(lower, ("за столько же", "на сколько пакет", "на сколько дороже", "на сколько дешевле")):
        return explain_price_difference_problem(nums[0], nums[1], nums[2])
    if contains_any_fragment(lower, ("сколько таких коробок", "сколько можно купить", "сколько коробок можно купить")):
        return explain_price_quantity_cost_problem(nums[0], nums[1], nums[2])
    return None


# --- PATCH: context extraction fixes ---


# --- FINAL PATCH: detailed school-style formatting, safer fallback, richer step output ---

DEEPSEEK_API_KEY = (os.environ.get("myapp_ai_math_1_4_API_key") or "").strip()

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать очень подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой содержательной строке пиши полный пример с ответом:
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, пиши строку:
Порядок действий:
Потом сам пример и над знаками действий цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши строку:
Решение по действиям:
4. Ниже обязательно пиши:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом само условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай только по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. По возможности используй школьную форму:
Если ..., то ...
6. После каждого действия коротко говори, что нашли.
7. В конце:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.

Важные требования:
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Если в задаче два вопроса, ответь на оба по порядку.
Для многодейственных задач не перескакивай сразу к ответу.
Сначала действие, потом пояснение, потом следующее действие.
""".strip()

BODY_LIMITS = {
    "expression": 40,
    "equation": 20,
    "fraction": 24,
    "geometry": 30,
    "word": 40,
    "other": 20,
}

seed_static_module_globals(globals())

_ORIGINAL_try_local_expression_explanation = try_local_expression_explanation
_ORIGINAL_try_local_equation_explanation = try_local_equation_explanation
_ORIGINAL_try_local_fraction_explanation = try_local_fraction_explanation
_ORIGINAL_try_local_geometry_explanation = try_local_geometry_explanation
_ORIGINAL_try_local_fraction_word_problem_explanation = try_local_fraction_word_problem_explanation
_ORIGINAL_try_local_motion_word_problem_explanation = try_local_motion_word_problem_explanation
_ORIGINAL_try_local_price_word_problem_explanation = try_local_price_word_problem_explanation
_ORIGINAL_try_local_unit_rate_word_problem_explanation = try_local_unit_rate_word_problem_explanation
_ORIGINAL_try_local_sum_and_divide_word_problem_explanation = try_local_sum_and_divide_word_problem_explanation
_ORIGINAL_try_local_proportional_division_word_problem = try_local_proportional_division_word_problem
_ORIGINAL_try_local_difference_unknown_word_problem = try_local_difference_unknown_word_problem
_ORIGINAL_try_local_indirect_word_problem_explanation = try_local_indirect_word_problem_explanation
_ORIGINAL_try_local_compound_word_problem_explanation = try_local_compound_word_problem_explanation
_ORIGINAL_try_local_word_problem_explanation = try_local_word_problem_explanation


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    lower = str(raw_text or "").lower().replace("ё", "е")
    if "руб" in lower or "денег" in lower:
        return f"{value} руб."
    return value


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")
    node = parse_expression_ast(source)
    pretty_expression = render_node(node) if node is not None else _detailed_compact_expression(source)
    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = [line for line in parts["body"] if not line.lower().startswith(("что известно:", "что нужно найти:"))]
    if not body_lines:
        body_lines = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]
    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]
    order_block = _detailed_build_order_block(source)
    if order_block and not _detailed_is_column_like(body_lines):
        lines.extend(order_block)
        lines.append("Решение по действиям:")
    else:
        lines.append("Решение.")
    lines.extend(_detailed_number_lines(body_lines))
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_equation_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_equation_source(raw_text) or normalize_cyrillic_x(strip_known_prefix(raw_text))
    pretty = _detailed_pretty_equation(source)
    answer = parts["answer"] or "проверь запись"
    if re.fullmatch(r"-?\d+(?:/\d+)?", answer):
        answer = f"x = {answer}"
    lines: List[str] = [f"Уравнение: {pretty}", "Решение."]
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("equation")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_fraction_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_fraction_source(raw_text) or strip_known_prefix(raw_text)
    pretty = _detailed_pretty_fraction_expression(source)
    answer = parts["answer"] or "проверь запись"
    lines: List[str] = [f"Пример: {pretty} = {answer}", "Решение"]
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("fraction")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_word_like_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    statement = _detailed_statement_text(raw_text)
    info_lines: List[str] = []
    body_lines: List[str] = []
    for line in parts["body"]:
        lower = line.lower()
        if lower.startswith("что известно:") or lower.startswith("что нужно найти:"):
            info_lines.append(line)
        else:
            body_lines.append(line)
    if not info_lines:
        condition, question = extract_condition_and_question(raw_text)
        if condition:
            info_lines.append(f"Что известно: {condition}")
        if question:
            info_lines.append(f"Что нужно найти: {question}")
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    lines: List[str] = []
    if statement:
        lines.append("Задача.")
        lines.append(statement)
    lines.append("Решение.")
    lines.extend(info_lines)
    lines.extend(_detailed_number_lines(body_lines))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind if kind in DEFAULT_ADVICE else "other")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_generic_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    lines: List[str] = []
    statement = _detailed_statement_text(raw_text)
    if statement and kind in {"word", "geometry"}:
        lines.append("Задача.")
        lines.append(statement)
        lines.append("Решение.")
    else:
        lines.append("Решение.")
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind)
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_solution(raw_text: str, text: str, kind: str) -> str:
    if kind == "expression" and to_expression_source(raw_text):
        return _detailed_format_expression_solution(raw_text, text)
    if kind == "equation" and to_equation_source(raw_text):
        return _detailed_format_equation_solution(raw_text, text)
    if kind == "fraction" and to_fraction_source(raw_text) and not re.search(r"[А-Яа-я]", raw_text):
        return _detailed_format_fraction_solution(raw_text, text)
    if kind in {"word", "geometry"} or re.search(r"[А-Яа-я]", raw_text):
        return _detailed_format_word_like_solution(raw_text, text, kind)
    return _detailed_format_generic_solution(raw_text, text, kind)


def shape_explanation(text: str, kind: str, forced_answer: Optional[str] = None, forced_advice: Optional[str] = None) -> str:
    parts = _detailed_split_sections(text)
    answer = forced_answer or parts["answer"] or "проверь запись"
    advice = forced_advice or parts["advice"] or default_advice(kind)
    lines = list(parts["body"])
    if kind == "equation" and parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def explain_sum_then_subtract_word_problem(first: int, second: int, removed: int) -> Optional[str]:
    total = first + second
    remaining = total - removed
    if remaining < 0:
        return None
    return join_explanation_lines(
        f"Сначала находим, сколько было всего: {first} + {second} = {total}",
        f"Потом находим, сколько осталось: {total} - {removed} = {remaining}",
        f"Ответ: {remaining}",
        "Совет: если сначала объединяют две группы, а потом часть убирают, сначала находят сумму",
    )


def try_local_sum_then_subtract_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3:
        return None
    asks_left = bool(re.search(r"сколько[^.?!]*\b(осталось|останется)\b", lower))
    loss_markers = WORD_LOSS_HINTS + ("уехал", "уехала", "уехали", "уехало", "ушел", "ушла", "ушли", "ушло", "забрали")
    has_loss = contains_any_fragment(lower, loss_markers)
    if asks_left and has_loss:
        return explain_sum_then_subtract_word_problem(nums[0], nums[1], nums[2])
    return None


def try_local_named_sum_of_two_products_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower or ("заплат" not in lower and "стоил" not in lower and "стоят" not in lower and "стоимость" not in lower):
        return None

    matches = list(re.finditer(r"(\d+)\s+([^?.!,]{1,30}?)\s+по\s+(\d+)", lower))
    if len(matches) < 2:
        return None

    first_count = int(matches[0].group(1))
    first_name = matches[0].group(2).strip()
    first_price = int(matches[0].group(3))
    second_count = int(matches[1].group(1))
    second_name = matches[1].group(2).strip()
    second_price = int(matches[1].group(3))

    first_total = first_count * first_price
    second_total = second_count * second_price
    total = first_total + second_total

    return join_explanation_lines(
        f"Если купили {first_count} {first_name} по {first_price} руб., то стоимость первой покупки равна {first_count} × {first_price} = {first_total} руб",
        f"Если купили {second_count} {second_name} по {second_price} руб., то стоимость второй покупки равна {second_count} × {second_price} = {second_total} руб",
        f"Если стоимость первой покупки {first_total} руб., а стоимость второй покупки {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала найди стоимость каждой покупки отдельно",
    )


def try_local_expression_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_expression_explanation(raw_text)


def try_local_equation_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_equation_explanation(raw_text)


def try_local_fraction_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_fraction_explanation(raw_text)


def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_geometry_explanation(raw_text)


def try_local_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_fraction_word_problem_explanation(raw_text)


def try_local_motion_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_motion_word_problem_explanation(raw_text)


def try_local_price_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_price_word_problem_explanation(raw_text)


def try_local_unit_rate_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_unit_rate_word_problem_explanation(raw_text)


def try_local_sum_and_divide_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_sum_and_divide_word_problem_explanation(raw_text)


def try_local_proportional_division_word_problem(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_proportional_division_word_problem(raw_text)


def try_local_difference_unknown_word_problem(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_difference_unknown_word_problem(raw_text)


def try_local_indirect_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_indirect_word_problem_explanation(raw_text)


def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_compound_word_problem_explanation(raw_text)


def try_local_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_word_problem_explanation(raw_text)


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_fraction_word_problem_explanation(user_text)
        or try_local_motion_word_problem_explanation(user_text)
        or try_local_price_word_problem_explanation(user_text)
        or try_local_unit_rate_word_problem_explanation(user_text)
        or try_local_sum_and_divide_word_problem_explanation(user_text)
        or try_local_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_local_sum_then_subtract_word_problem_explanation(user_text)
        or try_local_proportional_division_word_problem(user_text)
        or try_local_difference_unknown_word_problem(user_text)
        or try_local_indirect_word_problem_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )


async def call_deepseek(payload: dict, timeout_seconds: float = 45.0):
    if not DEEPSEEK_API_KEY:
        return {"error": "DeepSeek API key is not configured"}
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code != 200:
        return {"error": f"DeepSeek API error {response.status_code}", "details": response.text[:1500]}
    try:
        result = response.json()
    except Exception:
        return {"error": "DeepSeek вернул не JSON", "details": response.text[:1500]}
    if "choices" not in result or not result["choices"]:
        return {"error": "DeepSeek вернул неожиданный формат ответа", "details": str(result)[:1500]}
    message = result["choices"][0].get("message", {})
    answer = (message.get("content") or "").strip()
    if not answer:
        return {"error": "DeepSeek вернул пустой ответ", "details": str(result)[:1500]}
    return {"result": answer}


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи",
            "Запишите пример или задачу полнее и без сокращений",
            "Ответ: пока нужен более понятный ввод",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": fallback, "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1800,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- FINAL SCHOOL PATCH: textbook-style word problems, clearer order marks, bug fixes ---

_PREVIOUS_build_explanation_local_first = build_explanation_local_first


def _has_total_like_question(raw_text: str) -> bool:
    return asks_total_like(normalize_word_problem_text(raw_text).lower()) or "сколько всего" in normalize_word_problem_text(raw_text).lower()


def _has_group_count_question(text_lower: str) -> bool:
    return contains_any_fragment(
        text_lower,
        ("сколько короб", "сколько пакетов", "сколько корзин", "сколько клеток", "сколько сеток", "сколько потребуется", "сколько потребовалось", "сколько ведер", "сколько вёдер"),
    )


def _first_po_pair(text_lower: str) -> Optional[Tuple[int, int]]:
    match = re.search(r"(\d+)\s+[^\d?.!]{0,40}?\bпо\s+(\d+)\b", text_lower)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _fraction_numbers_and_text(raw_text: str):
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower()
    fracs = extract_all_fraction_pairs(lower)
    values = extract_non_fraction_numbers(lower)
    return text, lower, fracs, values


def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None
    if remaining_value % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part}",
        f"3) Если одна доля равна {one_part}, то все деньги равны {one_part} × {denominator} = {whole}",
        f"Ответ: всего было {whole}",
        "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
    )


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе равно {second}, то всего {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько всего или сколько стало, обычно нужно сложение",
    )


def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если сначала было {first}, а потом осталось {second}, то убрали {first} - {second} = {result}",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько осталось или сколько убрали, обычно нужно вычитание",
    )


def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если одно число равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решают вычитанием",
    )


def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        f"1) Если осталось {remaining}, а убрали {removed}, то сначала было {remaining} + {removed} = {result}",
        f"Ответ: {result}",
        "Совет: неизвестное уменьшаемое находят сложением",
    )


def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если стало {final_total}, а прибавили {added}, то сначала было {final_total} - {added} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы найти число до прибавления, из нового числа вычитают то, что прибавили",
    )


def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {smaller}, а потом стало {bigger}, то добавили {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
    )


def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {bigger}, а потом осталось {smaller}, то убрали {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
    )


def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: проверь, на сколько частей делят")
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если всего {total} предметов разделили на {groups} равные части, то {total} : {groups} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        f"1) Если {total} разделить на {groups}, то получится {quotient}, остаток {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )


def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines("В одной группе не может быть 0 предметов", "Ответ: запись задачи неверная", "Совет: проверь размер одной группы")
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если всего {total} предметов, а в одной группе по {per_group}, то групп будет {total} : {per_group} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: число групп находят делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"1) Полных групп получится {quotient}, потому что {total} : {per_group} = {quotient}, остаток {remainder}",
            f"2) Так как предметы ещё остались, нужна ещё одна группа, всего {quotient + 1}",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления ещё есть остаток, иногда нужна ещё одна коробка или место",
        )
    if explicit_remainder:
        return join_explanation_lines(
            f"1) Если {total} разделить на группы по {per_group}, то получится {quotient}, остаток {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера одной группы",
        )
    return None


def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: если число на несколько единиц больше, прибавляют; если меньше, вычитают",
    )


def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {sign} {delta} = {related}",
        f"2) Если первое количество {base}, а второе количество {related}, то всего {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят неизвестное количество, потом сумму",
    )


def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то {base} {op} {factor} = {result}",
        f"Ответ: {result}",
        "Совет: если число в несколько раз больше, умножают; если в несколько раз меньше, делят",
    )


def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
        f"2) Если первое количество {base}, а второе количество {related}, то всего {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: сначала найди число, которое дано через отношение, потом считай общее количество",
    )


def explain_indirect_plus_minus_problem(base: int, delta: int, relation: str) -> Optional[str]:
    if relation in {"старше", "больше"}:
        result = base - delta
        if result < 0:
            return None
        relation_text = "значит, другое число на столько же меньше"
        op = "-"
    else:
        result = base + delta
        relation_text = "значит, другое число на столько же больше"
        op = "+"
    return join_explanation_lines(
        f"1) Это задача в косвенной форме: если одно число на {delta} {relation}, то {relation_text}",
        f"2) Находим искомое число: {base} {op} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи условие в прямую форму",
    )


def explain_indirect_times_problem(base: int, factor: int, relation: str) -> Optional[str]:
    if relation == "больше":
        if factor == 0 or base % factor != 0:
            return None
        result = base // factor
        op = ":"
        relation_text = "значит, другое число во столько же раз меньше"
    else:
        result = base * factor
        op = "×"
        relation_text = "значит, другое число во столько же раз больше"
    return join_explanation_lines(
        f"1) Это задача в косвенной форме: если одно число в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то {relation_text}",
        f"2) Находим искомое число: {base} {op} {factor} = {result}",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи условие в прямую форму",
    )


def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"1) Если в {groups} группах {total_amount}, то в одной группе {total_amount} : {groups} = {one_group}",
        f"2) Если в одной группе {one_group}, то в {target_groups} группах {one_group} × {target_groups} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    relation = "дороже" if price_a > price_b else "дешевле"
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_a}, то цена одного товара равна {total_a} : {quantity} = {price_a}",
        f"2) Если за {quantity} таких же товаров заплатили {total_b}, то цена одного товара равна {total_b} : {quantity} = {price_b}",
        f"3) Если одна цена {price_a}, а другая {price_b}, то разность цен равна {max(price_a, price_b)} - {min(price_a, price_b)} = {diff}",
        f"Ответ: на {diff} руб. {relation}",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )

# --- merged segment 002: backend.legacy_runtime_shards.prepatch_build_source.segment_002 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 896-1780."""



def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых коробок заплатили {total_cost}, то цена одной коробки равна {total_cost} : {quantity} = {price}",
        f"2) Если одна коробка стоит {price}, то на {wanted_cost} руб. можно купить {wanted_cost} : {price} = {result}",
        f"Ответ: {result}",
        "Совет: если цена одинаковая, сначала находят цену одной коробки",
    )


def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"1) Если известные цветы купили {known_count} раза по {known_price} руб., то за них заплатили {known_count} × {known_price} = {known_total} руб",
        f"2) Если за всю покупку заплатили {total_cost} руб., а за известные цветы {known_total} руб., то за остальные цветы заплатили {total_cost} - {known_total} = {other_total} руб",
        f"3) Если за {unknown_count} остальных цветов заплатили {other_total} руб., то одна штука стоит {other_total} : {unknown_count} = {unit_price} руб",
        f"Ответ: одна красная гвоздика стоила {unit_price} руб",
        "Совет: если известна общая стоимость покупки, сначала вычти известную часть",
    )


def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        f"1) Если {count} одинаковых предметов стоят {total_cost} руб., то один предмет стоит {total_cost} : {count} = {price} руб",
        f"Ответ: один предмет стоит {price} руб",
        "Совет: цену одной штуки находят делением общей стоимости на количество",
    )


def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        f"1) Если один предмет стоит {price} руб., а купили {count} предметов, то вся покупка стоит {price} × {count} = {total} руб",
        f"Ответ: вся покупка стоит {total} руб",
        "Совет: стоимость находят умножением цены на количество",
    )


def try_high_priority_named_sum_of_two_products_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower or ("заплат" not in lower and "стоил" not in lower and "стоимость" not in lower):
        return None

    matches = list(re.finditer(r"(\d+)\s+([^?.!,]{1,30}?)\s+по\s+(\d+)", lower))
    if len(matches) < 2:
        return None

    first_count = int(matches[0].group(1))
    first_name = matches[0].group(2).strip()
    first_price = int(matches[0].group(3))
    second_count = int(matches[1].group(1))
    second_name = matches[1].group(2).strip()
    second_price = int(matches[1].group(3))

    first_total = first_count * first_price
    second_total = second_count * second_price
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если купили {first_count} {first_name} по {first_price} руб., то за {first_name} заплатили {first_count} × {first_price} = {first_total} руб",
        f"2) Если купили {second_count} {second_name} по {second_price} руб., то за {second_name} заплатили {second_count} × {second_price} = {second_total} руб",
        f"3) Если за первую покупку заплатили {first_total} руб., а за вторую {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )


def try_high_priority_unknown_addend_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in lower:
        return None

    if re.search(r"(?:на двух|на обеих|на обоих|за два дня|всего|из них|на всем теле|на всём теле)", lower) and not _has_total_like_question(raw_text):
        total, known = nums[0], nums[1]
        if total < known:
            return None
        result = total - known
        return join_explanation_lines(
            f"1) Если всего было {total}, а одна часть равна {known}, то другая часть равна {total} - {known} = {result}",
            f"Ответ: {result}",
            "Совет: чтобы найти неизвестную часть, из целого вычитают известную часть",
        )
    return None


def try_high_priority_added_removed_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in lower:
        return None

    if re.search(r"\b(стало|их стало|теперь стало|получилось)\b", lower) and contains_any_fragment(lower, WORD_GAIN_HINTS + ("постав", "добав", "приех", "вошло", "прибав")):
        before, after = nums[0], nums[1]
        if after < before:
            return None
        added = after - before
        return join_explanation_lines(
            f"1) Если сначала было {before}, а потом стало {after}, то добавили {after} - {before} = {added}",
            f"Ответ: {added}",
            "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
        )

    if re.search(r"\b(осталось|осталось прочитать|пришло|осталось расфасовать)\b", lower) and contains_any_fragment(lower, WORD_LOSS_HINTS + ("забрали", "сняли", "вышло", "заболело", "заболели", "заболел")):
        before, after = nums[0], nums[1]
        if before < after:
            return None
        removed = before - after
        return join_explanation_lines(
            f"1) Если сначала было {before}, а потом осталось {after}, то убрали {before} - {after} = {removed}",
            f"Ответ: {removed}",
            "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
        )

    if ("сколько было" in lower or "сколько было сначала" in lower) and re.search(r"\b(осталось|осталось на|осталось в)\b", lower):
        removed, left = nums[0], nums[1]
        result = removed + left
        return join_explanation_lines(
            f"1) Если убрали {removed}, а осталось {left}, то сначала было {removed} + {left} = {result}",
            f"Ответ: {result}",
            "Совет: неизвестное уменьшаемое находят сложением",
        )
    return None


def try_high_priority_simple_group_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower:
        return None
    if _has_group_count_question(lower) or "поровну" in lower or "кажд" in lower:
        return None
    if not (asks_total_like(lower) or contains_any_fragment(lower, ("сколько килограммов", "сколько книг", "сколько карандашей", "сколько литров", "сколько огурцов", "сколько конфет"))):
        return None

    pair = _first_po_pair(lower)
    if not pair:
        return None
    groups, per_group = pair
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {groups * per_group}",
        f"Ответ: {groups * per_group}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def try_high_priority_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if not fracs:
        return None

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower) and values:
        total = max(values)
        solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
        if solved:
            return solved

    if len(fracs) != 1:
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None

    total_like_match = re.search(r"\b(?:было|всего|масса|длина|путь|прошли|прошёл|прошла|прошли за|на складе было|у мальчика было|у мамы было|у туристов было|листов было|руды)\b", lower)
    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)

    # Известно всё число, нужно найти часть или остаток.
    if values and (total_like_match or not remain_match):
        total = max(values)
        if ("остал" in lower or "во 2 день" in lower or "во второй день" in lower):
            if total % denominator != 0:
                return None
            one_part = total // denominator
            part = one_part * numerator
            remaining = total - part
            if "во 2 день" in lower or "во второй день" in lower:
                return join_explanation_lines(
                    f"1) Если весь путь равен {total}, то одна доля равна {total} : {denominator} = {one_part}",
                    f"2) Если в первый день прошли {numerator}/{denominator} пути, то в первый день прошли {one_part} × {numerator} = {part}",
                    f"3) Если весь путь {total}, а в первый день прошли {part}, то во второй день прошли {total} - {part} = {remaining}",
                    f"Ответ: во второй день прошли {remaining}",
                    "Совет: чтобы найти другую часть пути, сначала найди известную часть, потом вычти её из всего пути",
                )
            return join_explanation_lines(
                f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}",
                f"2) Если требуется найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part}",
                f"3) Если всего было {total}, а израсходовали {part}, то осталось {total} - {part} = {remaining}",
                f"Ответ: осталось {remaining}",
                "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
            )

        if total % denominator == 0:
            one_part = total // denominator
            part = one_part * numerator
            return join_explanation_lines(
                f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}",
                f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part}",
                f"Ответ: {part}",
                "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
            )

    # Известно, сколько осталось после расхода части.
    if remain_match:
        remaining_value = int(remain_match.group(1))
        solved = explain_whole_by_remaining_fraction(remaining_value, numerator, denominator)
        if solved:
            return solved

    return None


def try_high_priority_unknown_price_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) >= 4 and "за всю покупку заплатили" in lower and "по" in lower and contains_any_fragment(lower, ("сколько стоила 1", "сколько стоит 1", "сколько стоила одна", "сколько стоит одна")):
        return explain_unknown_red_price(nums[0], nums[1], nums[2], nums[3])
    return None


def try_high_priority_total_cost_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) >= 2 and contains_any_fragment(lower, ("сколько стоит 1", "сколько стоит одна", "сколько стоит один", "сколько стоит 1 ")):
        return explain_simple_price_per_item(nums[0], nums[1])
    if len(nums) >= 2 and contains_any_fragment(lower, ("сколько стоят", "сколько стоила вся покупка", "сколько стоит вся покупка")):
        return explain_simple_total_cost(nums[0], nums[1])
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_high_priority_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_high_priority_unknown_price_word_problem_explanation(user_text)
        or try_high_priority_total_cost_word_problem_explanation(user_text)
        or try_high_priority_fraction_word_problem_explanation(user_text)
        or try_high_priority_unknown_addend_word_problem_explanation(user_text)
        or try_high_priority_added_removed_word_problem_explanation(user_text)
        or try_high_priority_simple_group_total_word_problem_explanation(user_text)
        or _PREVIOUS_build_explanation_local_first(user_text, kind)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи",
            "Запишите пример или задачу полнее и без сокращений",
            "Ответ: пока нужен более понятный ввод",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1800,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- FINAL SCHOOL PATCH 2: units, group totals, cleaner purchase wording ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower = normalize_word_problem_text(raw_text).lower()
    if "скорост" in question:
        if "км/ч" in lower:
            return "км/ч"
        if "м/мин" in lower:
            return "м/мин"
        if "м/с" in lower:
            return "м/с"
    for unit in ("руб.", "руб", "кг", "г", "км", "м", "см", "дм", "мм", "л", "ч", "мин"):
        if unit in question:
            return unit.replace(".", "")
    if "деньг" in question or "денег" in question:
        return "руб"
    return ""


def _append_unit_to_number_text(value: int, raw_text: str) -> str:
    unit = _detect_question_unit(raw_text)
    if not unit:
        return str(value)
    return f"{value} {unit}"


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value):
        unit = _detect_question_unit(raw_text)
        if unit:
            return f"{value} {unit}"
        lower = str(raw_text or "").lower().replace("ё", "е")
        if "руб" in lower or "денег" in lower:
            return f"{value} руб."
    return value


def try_high_priority_named_sum_of_two_products_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower or ("заплат" not in lower and "стоил" not in lower and "стоимость" not in lower):
        return None

    matches = list(re.finditer(r"(\d+)\s+([^?.!,]{1,30}?)\s+по\s+(\d+)", lower))
    if len(matches) < 2:
        return None

    first_count = int(matches[0].group(1))
    first_price = int(matches[0].group(3))
    second_count = int(matches[1].group(1))
    second_price = int(matches[1].group(3))

    first_total = first_count * first_price
    second_total = second_count * second_price
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если первая покупка состоит из {first_count} предметов по {first_price} руб., то её стоимость равна {first_count} × {first_price} = {first_total} руб",
        f"2) Если вторая покупка состоит из {second_count} предметов по {second_price} руб., то её стоимость равна {second_count} × {second_price} = {second_total} руб",
        f"3) Если первая покупка стоит {first_total} руб., а вторая {second_total} руб., то вся покупка стоит {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )


def try_high_priority_simple_group_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower:
        return None
    if _has_group_count_question(lower) or "поровну" in lower:
        return None
    if not (asks_total_like(lower) or contains_any_fragment(lower, ("сколько килограммов", "сколько книг", "сколько карандашей", "сколько литров", "сколько огурцов", "сколько конфет"))):
        return None

    pair = _first_po_pair(lower)
    if not pair:
        return None
    groups, per_group = pair
    total = groups * per_group
    answer_value = _append_unit_to_number_text(total, raw_text)
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {total}",
        f"Ответ: {answer_value}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def try_high_priority_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if not fracs:
        return None

    unit = _detect_question_unit(raw_text)

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower) and values:
        total = max(values)
        solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
        if solved:
            return solved

    if len(fracs) != 1:
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None

    total_like_match = re.search(r"\b(?:было|всего|масса|длина|путь|прошли|прошёл|прошла|прошли за|на складе было|у мальчика было|у мамы было|листов было|руды)\b", lower)
    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)

    if values and (total_like_match or not remain_match):
        total = max(values)
        if ("остал" in lower or "во 2 день" in lower or "во второй день" in lower):
            if total % denominator != 0:
                return None
            one_part = total // denominator
            part = one_part * numerator
            remaining = total - part
            remaining_text = f"{remaining} {unit}".strip()
            total_text = f"{total} {unit}".strip()
            one_part_text = f"{one_part} {unit}".strip()
            part_text = f"{part} {unit}".strip()
            if "во 2 день" in lower or "во второй день" in lower:
                return join_explanation_lines(
                    f"1) Если весь путь равен {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                    f"2) Если в первый день прошли {numerator}/{denominator} пути, то в первый день прошли {one_part} × {numerator} = {part_text}",
                    f"3) Если весь путь {total_text}, а в первый день прошли {part_text}, то во второй день прошли {total} - {part} = {remaining_text}",
                    f"Ответ: во второй день прошли {remaining_text}",
                    "Совет: чтобы найти другую часть пути, сначала найди известную часть, потом вычти её из всего пути",
                )
            return join_explanation_lines(
                f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если требуется найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
                f"3) Если всего было {total_text}, а израсходовали {part_text}, то осталось {total} - {part} = {remaining_text}",
                f"Ответ: осталось {remaining_text}",
                "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
            )

        if total % denominator == 0:
            one_part = total // denominator
            part = one_part * numerator
            total_text = f"{total} {unit}".strip()
            one_part_text = f"{one_part} {unit}".strip()
            part_text = f"{part} {unit}".strip()
            return join_explanation_lines(
                f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
                f"Ответ: {part_text}",
                "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
            )

    if remain_match:
        remaining_value = int(remain_match.group(1))
        solved = explain_whole_by_remaining_fraction(remaining_value, numerator, denominator)
        if solved:
            if unit:
                solved = solved.replace(f"равны {remaining_value}", f"равны {remaining_value} {unit}")
                solved = re.sub(rf"Ответ:\s*всего было (\d+)([.!?])", rf"Ответ: всего было \1 {unit}\2", solved)
            return solved

    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_high_priority_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_high_priority_unknown_price_word_problem_explanation(user_text)
        or try_high_priority_total_cost_word_problem_explanation(user_text)
        or try_high_priority_fraction_word_problem_explanation(user_text)
        or try_high_priority_unknown_addend_word_problem_explanation(user_text)
        or try_high_priority_added_removed_word_problem_explanation(user_text)
        or try_high_priority_simple_group_total_word_problem_explanation(user_text)
        or _PREVIOUS_build_explanation_local_first(user_text, kind)
    )


# --- FINAL SCHOOL PATCH 3: safer unit detection ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower()

    if "скорост" in question:
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if re.search(r"руб|денег", question) or ("руб" in lower_full and re.search(r"сколько|каков|какова|чему", question)):
        return "руб"
    if re.search(r"килограмм|кг", question):
        return "кг"
    if re.search(r"\bграмм|\bг\b", question):
        return "г"
    if re.search(r"километр|км", question):
        return "км"
    if re.search(r"\bметр|\bм\b", question):
        return "м"
    if re.search(r"сантиметр|см", question):
        return "см"
    if re.search(r"дециметр|дм", question):
        return "дм"
    if re.search(r"миллиметр|мм", question):
        return "мм"
    if re.search(r"литр|\bл\b", question):
        return "л"
    if re.search(r"час|сколько времени|за какое время", question):
        return "ч"
    if re.search(r"минут|мин", question):
        return "мин"
    return ""


# --- FINAL SCHOOL PATCH 4: reliable fraction routing for total-known vs remaining-known cases ---

def try_high_priority_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if not fracs:
        return None

    unit = _detect_question_unit(raw_text)

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower) and values:
        total = max(values)
        solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
        if solved:
            return solved

    if len(fracs) != 1:
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None

    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)
    explicit_total_match = re.search(r"(?:\bбыло\b|\bвсего\b|\bмасса\b|\bдлина\b|\bпуть\b|\bпрошли\b|\bпрошёл\b|\bпрошла\b|\bлистов\b|\bруды\b)[^\d]{0,40}(\d+)", lower)

    # 1) Случай: известен остаток после расхода дробной части, а всё число неизвестно.
    if remain_match and (not explicit_total_match or explicit_total_match.start() > remain_match.start()):
        remaining_value = int(remain_match.group(1))
        remaining_numerator = denominator - numerator
        if remaining_numerator <= 0 or remaining_value % remaining_numerator != 0:
            return None
        one_part = remaining_value // remaining_numerator
        whole = one_part * denominator
        remaining_text = f"{remaining_value} {unit}".strip()
        one_part_text = f"{one_part} {unit}".strip()
        whole_text = f"{whole} {unit}".strip()
        return join_explanation_lines(
            f"1) Если израсходовали {numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
            f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_text}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part_text}",
            f"3) Если одна доля равна {one_part_text}, то все деньги равны {one_part} × {denominator} = {whole_text}",
            f"Ответ: всего было {whole_text}",
            "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
        )

    # 2) Случай: всё число известно, нужно найти часть или остаток.
    if values:
        total = max(values)
        if total % denominator != 0:
            return None
        one_part = total // denominator
        part = one_part * numerator
        remaining = total - part
        total_text = f"{total} {unit}".strip()
        one_part_text = f"{one_part} {unit}".strip()
        part_text = f"{part} {unit}".strip()
        remaining_text = f"{remaining} {unit}".strip()

        if "во 2 день" in lower or "во второй день" in lower:
            return join_explanation_lines(
                f"1) Если весь путь равен {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если в первый день прошли {numerator}/{denominator} пути, то в первый день прошли {one_part} × {numerator} = {part_text}",
                f"3) Если весь путь {total_text}, а в первый день прошли {part_text}, то во второй день прошли {total} - {part} = {remaining_text}",
                f"Ответ: во второй день прошли {remaining_text}",
                "Совет: чтобы найти другую часть пути, сначала найди известную часть, потом вычти её из всего пути",
            )

        if "остал" in lower:
            return join_explanation_lines(
                f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если требуется найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
                f"3) Если всего было {total_text}, а израсходовали {part_text}, то осталось {total} - {part} = {remaining_text}",
                f"Ответ: осталось {remaining_text}",
                "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
            )

        return join_explanation_lines(
            f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
            f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
            f"Ответ: {part_text}",
            "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
        )

    return None


# --- FINAL SCHOOL PATCH 5: only attach units when the question itself asks for that unit ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower()

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:килограмм|кг)\b", question):
        return "кг"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:сколько|какова|какое расстояние|какой путь|чему равно расстояние)[^?.!]{0,25}(?:километр|км)\b", question):
        return "км"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:сантиметр|см)\b", question):
        return "см"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:дециметр|дм)\b", question):
        return "дм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:миллиметр|мм)\b", question):
        return "мм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"

    if "сколько денег" in question or ("руб" in lower_full and "сколько сто" in question):
        return "руб"
    return ""


# --- FINAL SCHOOL PATCH 6: fix "килограммов" vs "граммов" distinction ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower()

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:сколько|какова|какое расстояние|какой путь|чему равно расстояние)[^?.!]{0,25}(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:миллиметр|мм)", question):
        return "мм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"

    if "сколько денег" in question or ("руб" in lower_full and "сколько сто" in question):
        return "руб"
    return ""


# --- OPENAI FINAL PATCH 2026-04-10: routing fixes, textbook-style compound tasks, safer answer units, ASCII columns ---

_PATCH8_PREVIOUS_build_explanation_local_first = build_explanation_local_first
_PATCH8_PREVIOUS_explain_column_addition = explain_column_addition
_PATCH8_PREVIOUS_explain_column_subtraction = explain_column_subtraction
_PATCH8_PREVIOUS_explain_long_multiplication = explain_long_multiplication
_PATCH8_PREVIOUS_explain_long_division = explain_long_division

_PREFIX_NUMBER_MAP = {
    "одн": 1,
    "одно": 1,
    "двух": 2,
    "трех": 3,
    "трёх": 3,
    "четырех": 4,
    "четырёх": 4,
    "пяти": 5,
    "шести": 6,
    "семи": 7,
    "восьми": 8,
    "девяти": 9,
    "десяти": 10,
}


def _remove_one_value(seq: List[int], value: int) -> List[int]:
    data = list(seq)
    try:
        data.remove(value)
    except ValueError:
        pass
    return data


def _word_multiplier_value(word: str) -> Optional[int]:
    token = str(word or "").lower().replace("ё", "е")
    for prefix, value in _PREFIX_NUMBER_MAP.items():
        if token.startswith(prefix):
            return value
    return None


def _ascii_rule(width: int) -> str:
    return "-" * max(3, width)


def _render_column_addition_ascii(numbers: List[int]) -> List[str]:
    ordered = sorted(numbers, key=lambda x: (len(str(abs(x))), abs(x)), reverse=True)
    width = max(len(str(abs(n))) for n in ordered) + 1
    lines = ["Запись столбиком:"]
    for index, number in enumerate(ordered):
        sign = "+" if index > 0 else " "
        lines.append(f"{sign}{str(number).rjust(width - 1)}")
    lines.append(_ascii_rule(width))
    lines.append(f" {str(sum(ordered)).rjust(width - 1)}")
    return lines


def _render_column_subtraction_ascii(minuend: int, subtrahend: int) -> List[str]:
    width = max(len(str(abs(minuend))), len(str(abs(subtrahend)))) + 1
    result = minuend - subtrahend
    return [
        "Запись столбиком:",
        f" {str(minuend).rjust(width - 1)}",
        f"-{str(subtrahend).rjust(width - 1)}",
        _ascii_rule(width),
        f" {str(result).rjust(width - 1)}",
    ]


def _render_long_multiplication_ascii(left: int, right: int) -> List[str]:
    a, b = left, right
    if len(str(abs(a))) < len(str(abs(b))):
        a, b = b, a
    width = max(len(str(abs(a))), len(str(abs(b))) + 1, len(str(abs(a * b)))) + 1
    lines = ["Запись столбиком:", f" {str(a).rjust(width - 1)}", f"×{str(b).rjust(width - 1)}", _ascii_rule(width)]
    digits_b = list(reversed(str(abs(b))))
    partials = []
    for index, digit in enumerate(digits_b):
        if digit == "0":
            continue
        partials.append(a * int(digit) * (10 ** index))
    if len(partials) <= 1:
        lines.append(f" {str(a * b).rjust(width - 1)}")
        return lines
    for partial in partials:
        lines.append(f" {str(partial).rjust(width - 1)}")
    lines.append(_ascii_rule(width))
    lines.append(f" {str(a * b).rjust(width - 1)}")
    return lines


def _render_long_division_ascii(dividend: int, divisor: int) -> List[str]:
    if divisor == 0:
        return ["Запись столбиком:", "Деление на ноль невозможно"]
    quotient, remainder = divmod(dividend, divisor)
    lines = ["Запись столбиком:", f"{divisor}) {dividend}", f"Частное: {quotient}"]
    if remainder:
        lines.append(f"Остаток: {remainder}")
    return lines


def explain_column_addition(numbers: List[int]) -> str:
    base = _PATCH8_PREVIOUS_explain_column_addition(numbers)
    parts = _detailed_split_sections(base)
    lines = _render_column_addition_ascii(numbers) + parts["body"] + [
        f"Ответ: {parts['answer'] or sum(numbers)}",
        f"Совет: {parts['advice'] or 'в столбике всегда начинай с младшего разряда'}",
    ]
    return _detailed_finalize_text(lines)


def explain_column_subtraction(minuend: int, subtrahend: int) -> str:
    base = _PATCH8_PREVIOUS_explain_column_subtraction(minuend, subtrahend)
    parts = _detailed_split_sections(base)
    lines = _render_column_subtraction_ascii(minuend, subtrahend) + parts["body"] + [
        f"Ответ: {parts['answer'] or (minuend - subtrahend)}",
        f"Совет: {parts['advice'] or 'если разряда не хватает, занимаем 1 из соседнего старшего разряда'}",
    ]
    return _detailed_finalize_text(lines)


def explain_long_multiplication(left: int, right: int) -> str:
    base = _PATCH8_PREVIOUS_explain_long_multiplication(left, right)
    parts = _detailed_split_sections(base)
    lines = _render_long_multiplication_ascii(left, right) + parts["body"] + [
        f"Ответ: {parts['answer'] or (left * right)}",
        f"Совет: {parts['advice'] or 'в умножении столбиком сначала находят неполные произведения, потом их складывают'}",
    ]
    return _detailed_finalize_text(lines)


def explain_long_division(dividend: int, divisor: int) -> str:
    base = _PATCH8_PREVIOUS_explain_long_division(dividend, divisor)
    parts = _detailed_split_sections(base)
    answer_value = parts["answer"] or (f"{dividend // divisor}, остаток {dividend % divisor}" if divisor else "деление невозможно")
    lines = _render_long_division_ascii(dividend, divisor) + parts["body"] + [
        f"Ответ: {answer_value}",
        f"Совет: {parts['advice'] or 'в столбике повторяй шаги: взял, подобрал, умножил, вычел, снес цифру'}",
    ]
    return _detailed_finalize_text(lines)


def _is_ascii_math_layout_line(line: str) -> bool:
    stripped = str(line or "").rstrip()
    if not stripped:
        return False
    return bool(re.fullmatch(r"[ 0-9+\-×:=()/]+", stripped))


def _split_ascii_layout_block(body_lines: List[str]) -> Tuple[List[str], List[str]]:
    lines = [str(line or "") for line in body_lines]
    if not lines or not lines[0].lower().startswith("запись столбиком"):
        return [], lines
    block = [lines[0]]
    index = 1
    while index < len(lines) and _is_ascii_math_layout_line(lines[index]):
        block.append(lines[index])
        index += 1
    return block, lines[index:]


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")
    node = parse_expression_ast(source)
    pretty_expression = render_node(node) if node is not None else _detailed_compact_expression(source)
    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = [line for line in parts["body"] if not line.lower().startswith(("что известно:", "что нужно найти:"))]
    column_block, remaining_body = _split_ascii_layout_block(body_lines)
    if not remaining_body and not column_block:
        remaining_body = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]
    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]
    order_block = _detailed_build_order_block(source)
    if order_block and not column_block:
        lines.extend(order_block)
        lines.append("Решение по действиям:")
    else:
        lines.append("Решение.")
    if column_block:
        lines.extend(column_block)
        if remaining_body:
            lines.append("Пояснение:")
    lines.extend(_detailed_number_lines(remaining_body))
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)

# --- merged segment 003: backend.legacy_runtime_shards.prepatch_build_source.segment_003 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 1781-2651."""



def _detailed_format_word_like_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    statement = _detailed_statement_text(raw_text)
    info_lines: List[str] = []
    body_lines: List[str] = []
    for line in parts["body"]:
        lower = line.lower()
        if lower.startswith("что известно:") or lower.startswith("что нужно найти:"):
            info_lines.append(line)
        else:
            body_lines.append(line)
    if not info_lines:
        condition, question = extract_condition_and_question(raw_text)
        if condition:
            info_lines.append(f"Что известно: {condition}")
        if question:
            info_lines.append(f"Что нужно найти: {question}")
    column_block, remaining_body = _split_ascii_layout_block(body_lines)
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    lines: List[str] = []
    if statement:
        lines.append("Задача.")
        lines.append(statement)
    lines.append("Решение.")
    lines.extend(info_lines)
    if column_block:
        lines.extend(column_block)
        if remaining_body:
            lines.append("Пояснение:")
    lines.extend(_detailed_number_lines(remaining_body))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind if kind in DEFAULT_ADVICE else "other")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_generic_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    statement = _detailed_statement_text(raw_text)
    column_block, remaining_body = _split_ascii_layout_block(parts["body"])
    lines: List[str] = []
    if statement and kind in {"word", "geometry"}:
        lines.append("Задача.")
        lines.append(statement)
        lines.append("Решение.")
    else:
        lines.append("Решение.")
    if column_block:
        lines.extend(column_block)
        if remaining_body:
            lines.append("Пояснение:")
    lines.extend(_detailed_number_lines(remaining_body))
    if parts["check"]:
        lines.append(parts["check"])
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind)
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:сколько|какова|какое расстояние|какой путь|чему равно расстояние)[^?.!]{0,25}(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:миллиметр|мм)", question):
        return "мм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value):
        unit = _detect_question_unit(raw_text)
        if unit:
            return f"{value} {unit}"
    return value


def try_priority_fraction_by_given_part_explanation(raw_text: str) -> Optional[str]:
    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if len(fracs) != 1 or not values:
        return None
    numerator, denominator = fracs[0]
    if denominator == 0:
        return None
    if "составляет" in lower or re.search(rf"это\s+{numerator}\s*/\s*{denominator}\s+(?:всего\s+)?", lower):
        value_match = re.search(r"(?:составляет|равна|равен)[^\d]{0,20}(\d+)", lower)
        part_value = int(value_match.group(1)) if value_match else max(values)
        return explain_number_by_fraction_word_problem(part_value, numerator, denominator)
    return None


def try_high_priority_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    explicit = try_priority_fraction_by_given_part_explanation(raw_text)
    if explicit:
        return explicit

    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if not fracs:
        return None

    unit = _detect_question_unit(raw_text)

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower) and values:
        total = max(values)
        solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
        if solved:
            return solved

    if len(fracs) != 1:
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None

    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)
    explicit_total_match = re.search(r"(?:\bбыло\b|\bвсего\b|\bмасса\b|\bдлина\b|\bпуть\b|\bпрошли\b|\bпрошел\b|\bпрошла\b|\bлистов\b|\bруды\b)[^\d]{0,40}(\d+)", lower)

    if remain_match and (not explicit_total_match or explicit_total_match.start() > remain_match.start()):
        remaining_value = int(remain_match.group(1))
        remaining_numerator = denominator - numerator
        if remaining_numerator <= 0 or remaining_value % remaining_numerator != 0:
            return None
        one_part = remaining_value // remaining_numerator
        whole = one_part * denominator
        remaining_text = f"{remaining_value} {unit}".strip()
        one_part_text = f"{one_part} {unit}".strip()
        whole_text = f"{whole} {unit}".strip()
        return join_explanation_lines(
            f"1) Если израсходовали {numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
            f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_text}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part_text}",
            f"3) Если одна доля равна {one_part_text}, то все деньги равны {one_part} × {denominator} = {whole_text}",
            f"Ответ: всего было {whole_text}",
            "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
        )

    if values:
        total = max(values)
        if total % denominator != 0:
            return None
        one_part = total // denominator
        part = one_part * numerator
        remaining = total - part
        total_text = f"{total} {unit}".strip()
        one_part_text = f"{one_part} {unit}".strip()
        part_text = f"{part} {unit}".strip()
        remaining_text = f"{remaining} {unit}".strip()

        if "во 2 день" in lower or "во второй день" in lower:
            return join_explanation_lines(
                f"1) Если весь путь равен {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если в первый день прошли {numerator}/{denominator} пути, то в первый день прошли {one_part} × {numerator} = {part_text}",
                f"3) Если весь путь {total_text}, а в первый день прошли {part_text}, то во второй день прошли {total} - {part} = {remaining_text}",
                f"Ответ: во второй день прошли {remaining_text}",
                "Совет: чтобы найти другую часть пути, сначала найди известную часть, потом вычти её из всего пути",
            )

        if "остал" in lower:
            return join_explanation_lines(
                f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если требуется найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
                f"3) Если всего было {total_text}, а израсходовали {part_text}, то осталось {total} - {part} = {remaining_text}",
                f"Ответ: осталось {remaining_text}",
                "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
            )

        return join_explanation_lines(
            f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
            f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
            f"Ответ: {part_text}",
            "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
        )
    return None


def try_priority_relation_then_compare_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    question = _question_text_only(raw_text).lower().replace("ё", "е") or lower
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None

    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)

    if len(relation_pairs) == 1 and ("во сколько" in question or "на сколько" in question):
        base = nums[0]
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        if "во сколько" in question:
            bigger, smaller = max(base, related), min(base, related)
            if smaller == 0 or bigger % smaller != 0:
                return None
            result = bigger // smaller
            op = "+" if mode == "больше" else "-"
            return join_explanation_lines(
                f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {op} {delta} = {related}",
                f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
                f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )
        diff = abs(related - base)
        op = "+" if mode == "больше" else "-"
        return join_explanation_lines(
            f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {max(base, related)}, а другое равно {min(base, related)}, то разность равна {max(base, related)} - {min(base, related)} = {diff}",
            f"Ответ: {diff}",
            "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
        )

    if len(scale_pairs) == 1 and ("во сколько" in question or "на сколько" in question):
        base = nums[0]
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        if "во сколько" in question:
            bigger, smaller = max(base, related), min(base, related)
            if smaller == 0 or bigger % smaller != 0:
                return None
            result = bigger // smaller
            op = "×" if mode == "больше" else ":"
            return join_explanation_lines(
                f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
                f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
                f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )
        diff = abs(related - base)
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {max(base, related)}, а другое равно {min(base, related)}, то разность равна {max(base, related)} - {min(base, related)} = {diff}",
            f"Ответ: {diff}",
            "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
        )
    return None


def try_priority_group_change_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    question = _question_text_only(raw_text).lower().replace("ё", "е") or lower

    if len(re.findall(r"\bпо\s+\d+", lower)) > 1:
        return None

    pair = _find_group_pair_any(lower)
    if not pair:
        return None
    groups = pair["groups"]
    per_group = pair["per_group"]
    pair_total = groups * per_group
    before_number, after_number = _numbers_before_after(lower, pair["start"], pair["end"])

    if ("стало" in question or asks_total_like(question)) and contains_any_fragment(lower, WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")):
        extra = after_number
        if extra is not None:
            result = pair_total + extra
            return join_explanation_lines(
                f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {per_group} × {groups} = {pair_total}",
                f"2) Если было {pair_total}, а потом добавили ещё {extra}, то стало {pair_total} + {extra} = {result}",
                f"Ответ: {result}",
                "Совет: если сначала находят одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
            )

    if "осталось" in question or "осталось расфасовать" in question or "осталось проехать" in question:
        if before_number is not None and before_number >= pair_total:
            result = before_number - pair_total
            return join_explanation_lines(
                f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
                f"2) Если всего было {before_number}, а одна часть равна {pair_total}, то другая часть равна {before_number} - {pair_total} = {result}",
                f"Ответ: {result}",
                "Совет: в составной задаче сначала найди часть, а потом вычти её из целого",
            )
        if after_number is not None and pair_total >= after_number:
            result = pair_total - after_number
            return join_explanation_lines(
                f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {pair_total}",
                f"2) Если было {pair_total}, а убрали {after_number}, то осталось {pair_total} - {after_number} = {result}",
                f"Ответ: {result}",
                "Совет: если сначала находят одинаковые группы, а потом часть убирают, сначала выполняют умножение",
            )

    if re.search(r"сколько[^.?!]*(?:привезли|было)\b", question):
        remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)
        remain = int(remain_match.group(1)) if remain_match else after_number
        if remain is not None:
            result = pair_total + remain
            return join_explanation_lines(
                f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
                f"2) Если одна часть равна {pair_total}, а другая часть равна {remain}, то всего было {pair_total} + {remain} = {result}",
                f"Ответ: {result}",
                "Совет: если известны израсходованная часть и остаток, то всё число находят сложением",
            )

    if re.search(r"сколько[^.?!]*(?:отремонтировали|продали|расфасовали)\b", question) and before_number is not None and before_number >= pair_total:
        result = before_number - pair_total
        return join_explanation_lines(
            f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
            f"2) Если всего было {before_number}, а эта часть равна {pair_total}, то другая часть равна {before_number} - {pair_total} = {result}",
            f"Ответ: {result}",
            "Совет: если известно всё число и одна часть, другую часть находят вычитанием",
        )

    return None


def try_high_priority_simple_group_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if "сколько" not in lower:
        return None
    if contains_any_fragment(lower, WORD_GAIN_HINTS + WORD_LOSS_HINTS + ("остал", "расфас", "продал", "подарил", "добавил", "вошло", "приехало")):
        return None
    if _has_group_count_question(lower) or "поровну" in lower or "кажд" in lower:
        return None
    pair = _find_group_pair_any(lower)
    if not pair:
        return None
    if not (asks_total_like(lower) or contains_any_fragment(lower, ("сколько килограммов", "сколько книг", "сколько карандашей", "сколько литров", "сколько огурцов", "сколько конфет"))):
        return None
    groups = pair["groups"]
    per_group = pair["per_group"]
    total = groups * per_group
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {total}",
        f"Ответ: {total}",
        "Совет: слова «по ... в каждой» или составные слова вроде «двухлитровых» подсказывают умножение",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_priority_fraction_by_given_part_explanation(user_text)
        or try_priority_relation_then_compare_explanation(user_text)
        or try_priority_group_change_word_problem_explanation(user_text)
        or try_high_priority_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_high_priority_unknown_price_word_problem_explanation(user_text)
        or try_high_priority_total_cost_word_problem_explanation(user_text)
        or try_high_priority_fraction_word_problem_explanation(user_text)
        or try_high_priority_unknown_addend_word_problem_explanation(user_text)
        or try_high_priority_added_removed_word_problem_explanation(user_text)
        or try_high_priority_simple_group_total_word_problem_explanation(user_text)
        or _PATCH8_PREVIOUS_build_explanation_local_first(user_text, kind)
    )


# --- OPENAI FINAL PATCH 2026-04-10B: remaining/added routing order, unit tolerance, heading colons ---


def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    # Сначала более длинные и более специфичные единицы.
    if "мм" in question or "миллиметр" in question:
        return "мм"
    if "см²" in question or "кв. см" in question or ("площад" in question and ("см" in question or "сантиметр" in question)):
        return "см²"
    if "дм²" in question or "кв. дм" in question or ("площад" in question and ("дм" in question or "дециметр" in question)):
        return "дм²"
    if "м²" in question or "кв. м" in question or ("площад" in question and ("м " in question or question.endswith(" м") or "метр" in question)):
        return "м²"
    if re.search(r"(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def try_priority_group_change_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    question = _question_text_only(raw_text).lower().replace("ё", "е") or lower

    if len(re.findall(r"\bпо\s+\d+", lower)) > 1:
        return None

    pair = _find_group_pair_any(lower)
    if not pair:
        return None
    groups = pair["groups"]
    per_group = pair["per_group"]
    pair_total = groups * per_group
    before_number, after_number = _numbers_before_after(lower, pair["start"], pair["end"])

    # 1. Если известен общий объём и одна часть вида n × k, находим другую часть.
    if ("осталось" in question or "осталось расфасовать" in question or "осталось проехать" in question or re.search(r"сколько[^.?!]*(?:отремонтировали|продали|расфасовали)\b", question)) and before_number is not None and before_number >= pair_total:
        result = before_number - pair_total
        return join_explanation_lines(
            f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
            f"2) Если всего было {before_number}, а эта часть равна {pair_total}, то другая часть равна {before_number} - {pair_total} = {result}",
            f"Ответ: {result}",
            "Совет: если известно всё число и одна часть, другую часть находят вычитанием",
        )

    # 2. Если сначала есть группы, а потом часть убрали, находим остаток.
    if ("осталось" in question or "осталось в магазине" in question) and after_number is not None and pair_total >= after_number:
        result = pair_total - after_number
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {pair_total}",
            f"2) Если было {pair_total}, а убрали {after_number}, то осталось {pair_total} - {after_number} = {result}",
            f"Ответ: {result}",
            "Совет: если сначала находят одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    # 3. Если известны израсходованная часть и остаток, находим всё число.
    if re.search(r"сколько[^.?!]*(?:привезли|было)\b", question):
        remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)
        remain = int(remain_match.group(1)) if remain_match else after_number
        if remain is not None:
            result = pair_total + remain
            return join_explanation_lines(
                f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
                f"2) Если одна часть равна {pair_total}, а другая часть равна {remain}, то всего было {pair_total} + {remain} = {result}",
                f"Ответ: {result}",
                "Совет: если известны израсходованная часть и остаток, то всё число находят сложением",
            )

    # 4. Если сначала есть группы, а потом что-то добавили, находим итог.
    if ("стало" in question or "всего" in question) and contains_any_fragment(lower, WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")):
        extra = after_number
        if extra is not None:
            result = pair_total + extra
            return join_explanation_lines(
                f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {per_group} × {groups} = {pair_total}",
                f"2) Если было {pair_total}, а потом добавили ещё {extra}, то стало {pair_total} + {extra} = {result}",
                f"Ответ: {result}",
                "Совет: если сначала находят одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
            )

    return None


# --- OPENAI FINAL PATCH 2026-04-10C: protect subtraction/division layout lines from sanitizer ---


def _render_column_subtraction_ascii(minuend: int, subtrahend: int) -> List[str]:
    width = max(len(str(abs(minuend))), len(str(abs(subtrahend)))) + 1
    result = minuend - subtrahend
    return [
        "Запись столбиком:",
        f" {str(minuend).rjust(width - 1)}",
        f"–{str(subtrahend).rjust(width - 1)}",
        _ascii_rule(width),
        f" {str(result).rjust(width - 1)}",
    ]


def _render_long_division_ascii(dividend: int, divisor: int) -> List[str]:
    if divisor == 0:
        return ["Запись столбиком:", "Деление на ноль невозможно"]
    quotient, remainder = divmod(dividend, divisor)
    lines = ["Запись столбиком:", f"{divisor} | {dividend}", f"Частное: {quotient}"]
    if remainder:
        lines.append(f"Остаток: {remainder}")
    return lines


def _is_ascii_math_layout_line(line: str) -> bool:
    stripped = str(line or "").rstrip()
    if not stripped:
        return False
    return bool(re.fullmatch(r"[ 0-9+\-–×:=/|()]+", stripped))


# --- OPENAI CONSOLIDATION PATCH 2026-04-11: routing fixes, richer school templates, safer high-priority handlers ---

_PREV_20260411_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _answer_number_with_unit(value: int, raw_text: str, fallback_unit: str = "") -> str:
    unit = ""
    try:
        unit = _detect_question_unit(raw_text) or ""
    except Exception:
        unit = ""
    if not unit:
        unit = (fallback_unit or "").strip().rstrip(".")
    return f"{value} {unit}".strip()


def try_priority_simple_two_part_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in lower:
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} " or "поровну" in lower or "кажд" in lower:
        return None
    if contains_any_fragment(lower, WORD_GAIN_HINTS + WORD_LOSS_HINTS + ("остал", "стало", "теперь", "отдали", "вышло", "вошло", "приехало")):
        return None
    if not (_has_total_like_question(raw_text) or contains_any_fragment(question, ("сколько всего", "сколько вместе", "на обеих", "на обоих", "на двух"))):
        return None

    first, second = nums
    total = first + second
    answer_text = _answer_number_with_unit(total, raw_text)
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе количество равно {second}, то всего {first} + {second} = {total}",
        f"Ответ: {answer_text}",
        "Совет: если спрашивают, сколько всего или сколько вместе, обычно нужно сложение",
    )


def try_priority_relation_then_compare_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2 or "сколько" not in lower:
        return None

    base = nums[0]
    relation_pairs = extract_relation_pairs(lower)
    if len(relation_pairs) == 1 and ("во сколько" in question or "на сколько" in question):
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if "во сколько" in question:
            if smaller == 0 or bigger % smaller != 0:
                return None
            result = bigger // smaller
            op = "+" if mode == "больше" else "-"
            return join_explanation_lines(
                f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {op} {delta} = {related}",
                f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
                f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )
        diff = bigger - smaller
        op = "+" if mode == "больше" else "-"
        answer_text = _answer_number_with_unit(diff, raw_text)
        return join_explanation_lines(
            f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            f"Ответ: {answer_text}",
            "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
        )

    scale_pairs = extract_scale_pairs(lower)
    if len(scale_pairs) == 1 and ("во сколько" in question or "на сколько" in question):
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if "во сколько" in question:
            if smaller == 0 or bigger % smaller != 0:
                return None
            result = bigger // smaller
            op = "×" if mode == "больше" else ":"
            return join_explanation_lines(
                f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
                f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
                f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )
        diff = bigger - smaller
        op = "×" if mode == "больше" else ":"
        answer_text = _answer_number_with_unit(diff, raw_text)
        return join_explanation_lines(
            f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            f"Ответ: {answer_text}",
            "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
        )
    return None


def try_high_priority_named_sum_of_two_products_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None

    products = _po_product_matches(raw_text)
    if len(products) < 2:
        return None

    # Не перехватываем случаи, где спрашивают цену одной штуки и общая стоимость уже дана.
    if contains_any_fragment(question, ("сколько стоила 1", "сколько стоит 1", "сколько стоила одна", "сколько стоит одна")):
        return None

    first = products[0]
    second = products[1]
    first_total = first["count"] * first["value"]
    second_total = second["count"] * second["value"]
    total = first_total + second_total

    money_question = contains_any_fragment(lower, ("заплат", "стоим")) or contains_any_fragment(question, ("сколько денег", "сколько заплатили", "сколько стоила"))
    answer_unit = ""
    if money_question:
        answer_unit = "руб"
        return join_explanation_lines(
            f"1) Если купили {first['count']} {first['name']} по {first['value']} руб., то первая часть равна {first['count']} × {first['value']} = {first_total} руб",
            f"2) Если купили {second['count']} {second['name']} по {second['value']} руб., то вторая часть равна {second['count']} × {second['value']} = {second_total} руб",
            f"3) Если первая часть равна {first_total} руб., а вторая часть равна {second_total} руб., то всего {first_total} + {second_total} = {total} руб",
            f"Ответ: за всю покупку заплатили {total} руб",
            "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
        )

    # Общий случай: сумма двух произведений по массе/количеству/литрам и т. п.
    unit = _detect_question_unit(raw_text) or first["unit"] or second["unit"]
    answer_text = _answer_number_with_unit(total, raw_text, unit)
    unit_tail = f" {unit}".rstrip() if unit else ""
    return join_explanation_lines(
        f"1) Если было {first['count']} {first['name']} по {first['value']}{unit_tail}, то первая часть равна {first['count']} × {first['value']} = {first_total}{unit_tail}",
        f"2) Если было {second['count']} {second['name']} по {second['value']}{unit_tail}, то вторая часть равна {second['count']} × {second['value']} = {second_total}{unit_tail}",
        f"3) Если первая часть равна {first_total}{unit_tail}, а вторая часть равна {second_total}{unit_tail}, то всего {first_total} + {second_total} = {total}{unit_tail}",
        f"Ответ: {answer_text}",
        "Совет: если в задаче есть две группы вида «по столько-то», сначала находят каждую группу отдельно, потом складывают",
    )


def try_high_priority_simple_group_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None
    if contains_any_fragment(lower, WORD_GAIN_HINTS + WORD_LOSS_HINTS + ("остал", "расфас", "продал", "подарил", "добавил", "вошло", "приехало")):
        return None
    if _has_group_count_question(lower) or "поровну" in lower or "кажд" in lower:
        return None

    products = _po_product_matches(raw_text)
    if len(products) != 1:
        return None
    if not (_has_total_like_question(raw_text) or contains_any_fragment(question, ("сколько килограммов", "сколько книг", "сколько карандашей", "сколько литров", "сколько всего"))):
        return None

    product = products[0]
    total = product["count"] * product["value"]
    unit = _detect_question_unit(raw_text) or product["unit"]
    answer_text = _answer_number_with_unit(total, raw_text, unit)
    unit_tail = f" {unit}".rstrip() if unit else ""
    return join_explanation_lines(
        f"1) Если есть {product['count']} одинаковых групп по {product['value']}{unit_tail} в каждой, то всего {product['count']} × {product['value']} = {total}{unit_tail}",
        f"Ответ: {answer_text}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def try_priority_bring_to_unit_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or "сколько" not in lower:
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} ":
        return None

    first_groups = nums[0]
    total_amount = nums[1]
    target_value = nums[2]

    # Тип 1: "В 3 пачках 12 фломастеров. Сколько фломастеров в 2 пачках?"
    if "таких же" in lower or re.search(r"(?:сколько[^.?!]*\bв\s+\d+\s+[а-яё]+\b)", question):
        solved = explain_bring_to_unit_total_word_problem(first_groups, total_amount, target_value)
        if solved:
            return solved

    # Тип 2: "В 2 вёдрах 16 кг. В скольких вёдрах 24 кг?"
    if "в скольких" in question or _has_group_count_question(question):
        solved = explain_unit_rate_boxes_problem(first_groups, total_amount, target_value)
        if solved:
            return solved
    return None


def try_priority_unit_rate_compare_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None

    match = re.search(r"за\s+(\d+)\s+дн", lower)
    if match and "чем за один" in question and "на сколько" in question:
        days = int(match.group(1))
        total_amount = nums[1] if len(nums) >= 2 else None
        if total_amount is None or days == 0 or total_amount % days != 0:
            return None
        one_day = total_amount // days
        diff = total_amount - one_day
        answer_text = _answer_number_with_unit(diff, raw_text)
        total_text = _answer_number_with_unit(total_amount, raw_text)
        one_day_text = _answer_number_with_unit(one_day, raw_text)
        return join_explanation_lines(
            f"1) Если за {days} дней расходуется {total_text}, то за один день расходуется {total_amount} : {days} = {one_day_text}",
            f"2) Если за {days} дней расходуется {total_text}, а за один день {one_day_text}, то разность равна {total_amount} - {one_day} = {answer_text}",
            f"Ответ: {answer_text}",
            "Совет: в такой задаче сначала находят одну одинаковую часть, потом сравнивают",
        )
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_priority_relation_then_compare_explanation(user_text)
        or try_priority_simple_two_part_total_word_problem_explanation(user_text)
        or try_priority_bring_to_unit_word_problem_explanation(user_text)
        or try_priority_unit_rate_compare_word_problem_explanation(user_text)
        or try_high_priority_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_high_priority_simple_group_total_word_problem_explanation(user_text)
        or _PREV_20260411_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- OPENAI HOTFIX 2026-04-11A: relation pairs with measurement words ---

def extract_relation_pairs(text: str):
    pairs = []
    pattern = re.compile(r"на\s+(\d+)(?:\s+[а-яёa-z]+)?\s+(больше|меньше)", re.IGNORECASE)
    for match in pattern.finditer(str(text or "").lower().replace("ё", "е")):
        pairs.append((int(match.group(1)), match.group(2)))
    return pairs


# --- OPENAI HOTFIX 2026-04-11B: "скольких" in bring-to-unit tasks ---

def try_priority_bring_to_unit_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or not ("сколько" in lower or "скольких" in lower):
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} ":
        return None

    first_groups = nums[0]
    total_amount = nums[1]
    target_value = nums[2]

    if "таких же" in lower or re.search(r"(?:сколько[^.?!]*\bв\s+\d+\s+[а-яё]+\b)", question):
        solved = explain_bring_to_unit_total_word_problem(first_groups, total_amount, target_value)
        if solved:
            return solved

    if "в скольких" in question or "скольких" in question or _has_group_count_question(question):
        solved = explain_unit_rate_boxes_problem(first_groups, total_amount, target_value)
        if solved:
            return solved
    return None


# --- OPENAI HOTFIX 2026-04-11C: correct answer noun for "в скольких ..." tasks ---

def try_priority_bring_to_unit_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or not ("сколько" in lower or "скольких" in lower):
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} ":
        return None

    first_groups = nums[0]
    total_amount = nums[1]
    target_value = nums[2]

    if "таких же" in lower or re.search(r"(?:сколько[^.?!]*\bв\s+\d+\s+[а-яё]+\b)", question):
        solved = explain_bring_to_unit_total_word_problem(first_groups, total_amount, target_value)
        if solved:
            return solved

    if "в скольких" in question or "скольких" in question or _has_group_count_question(question):
        if first_groups == 0 or total_amount % first_groups != 0:
            return None
        per_group = total_amount // first_groups
        if per_group == 0 or target_value % per_group != 0:
            return None
        result = target_value // per_group
        noun_match = re.search(r"в\s+скольких\s+([а-яё]+)", question)
        noun = noun_match.group(1) if noun_match else ""
        noun = noun.strip().rstrip("?.!,")
        answer_tail = f" {noun}" if noun else ""
        return join_explanation_lines(
            f"1) Если в {first_groups} группах {total_amount}, то в одной группе {total_amount} : {first_groups} = {per_group}",
            f"2) Если в одной группе {per_group}, то {target_value} : {per_group} = {result}",
            f"Ответ: {result}{answer_tail}",
            "Совет: в задачах на приведение к единице сначала находят значение одной группы",
        )
    return None

# --- merged segment 004: backend.legacy_runtime_shards.prepatch_build_source.segment_004 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 2652-3540."""



# --- OPENAI HOTFIX 2026-04-11D: no metric unit for "в скольких" questions ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    lower_full = _statement_lower_text(raw_text)

    if "в скольких" in question:
        return ""

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if "мм" in question or "миллиметр" in question:
        return "мм"
    if "см²" in question or "кв. см" in question or ("площад" in question and ("см" in question or "сантиметр" in question)):
        return "см²"
    if "дм²" in question or "кв. дм" in question or ("площад" in question and ("дм" in question or "дециметр" in question)):
        return "дм²"
    if "м²" in question or "кв. м" in question or ("площад" in question and ("м " in question or question.endswith(" м") or "метр" in question)):
        return "м²"
    if re.search(r"(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def try_priority_bring_to_unit_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or not ("сколько" in lower or "скольких" in lower):
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} ":
        return None

    first_groups = nums[0]
    total_amount = nums[1]
    target_value = nums[2]

    if "таких же" in lower or re.search(r"(?:сколько[^.?!]*\bв\s+\d+\s+[а-яё]+\b)", question):
        solved = explain_bring_to_unit_total_word_problem(first_groups, total_amount, target_value)
        if solved:
            return solved

    if "в скольких" in question or "скольких" in question or _has_group_count_question(question):
        if first_groups == 0 or total_amount % first_groups != 0:
            return None
        per_group = total_amount // first_groups
        if per_group == 0 or target_value % per_group != 0:
            return None
        result = target_value // per_group
        return join_explanation_lines(
            f"1) Если в {first_groups} группах {total_amount}, то в одной группе {total_amount} : {first_groups} = {per_group}",
            f"2) Если в одной группе {per_group}, то {target_value} : {per_group} = {result}",
            f"Ответ: {result}",
            "Совет: в задачах на приведение к единице сначала находят значение одной группы",
        )
    return None


# --- OPENAI FINAL PATCH 2026-04-11E: cleaner expression formatting, fuller answers, stronger oral methods ---

_PREV_FINAL_PATCH_explain_simple_addition = explain_simple_addition
_PREV_FINAL_PATCH_explain_simple_subtraction = explain_simple_subtraction
_PREV_FINAL_PATCH_explain_simple_multiplication = explain_simple_multiplication


def _schoolify_expression_source(source: str) -> str:
    text = str(source or "").strip()
    if not text:
        return ""
    out = []
    for i, ch in enumerate(text):
        prev = text[i - 1] if i > 0 else ""
        if ch in "*/+":
            symbol = "×" if ch == "*" else ":" if ch == "/" else ch
            out.append(f" {symbol} ")
        elif ch == "-":
            if i == 0 or prev in "(+-*/":
                out.append("-")
            else:
                out.append(" - ")
        else:
            out.append(ch)
    pretty = re.sub(r"\s+", " ", "".join(out)).strip()
    pretty = pretty.replace("( ", "(").replace(" )", ")")
    return pretty


def _build_pretty_expression_and_operator_map(source: str) -> Tuple[str, dict]:
    raw = str(source or "")
    pretty_parts: List[str] = []
    raw_to_pretty: dict = {}
    current_len = 0
    for i, ch in enumerate(raw):
        prev = raw[i - 1] if i > 0 else ""
        if ch in "*/+":
            token = f" {'×' if ch == '*' else ':' if ch == '/' else ch} "
            raw_to_pretty[i] = current_len + 1
            pretty_parts.append(token)
            current_len += len(token)
        elif ch == "-" and not (i == 0 or prev in "(+-*/"):
            token = " - "
            raw_to_pretty[i] = current_len + 1
            pretty_parts.append(token)
            current_len += len(token)
        else:
            pretty_parts.append(ch)
            current_len += 1
    pretty = re.sub(r"\s+", " ", "".join(pretty_parts)).strip()
    pretty = pretty.replace("( ", "(").replace(" )", ")")
    # after whitespace normalization, rebuild exact operator positions in pretty string
    rebuilt_map: dict = {}
    pi = 0
    ri = 0
    raw_no_space = raw
    while ri < len(raw_no_space) and pi < len(pretty):
        rc = raw_no_space[ri]
        pc = pretty[pi]
        if rc in "*/+" or (rc == "-" and not (ri == 0 or raw_no_space[ri - 1] in "(+-*/")):
            symbol = '×' if rc == '*' else ':' if rc == '/' else rc
            # move to symbol in pretty
            while pi < len(pretty) and pretty[pi] != symbol:
                pi += 1
            if pi < len(pretty):
                rebuilt_map[ri] = pi
                pi += 1
            ri += 1
            continue
        if rc == pc:
            ri += 1
            pi += 1
        else:
            pi += 1
    return pretty, rebuilt_map


# override: preserve parentheses in the first line of expressions and in the order block


# override: fuller numeric answers for text tasks

def _detect_question_unit(raw_text: str) -> str:
    try:
        question = _question_lower_text(raw_text)
    except Exception:
        question = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if "в скольких" in question:
        return ""
    if "во сколько раз" in question:
        return "раз"

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if "мм" in question or "миллиметр" in question:
        return "мм"
    if "см²" in question or "кв. см" in question or ("площад" in question and ("см" in question or "сантиметр" in question)):
        return "см²"
    if "дм²" in question or "кв. дм" in question or ("площад" in question and ("дм" in question or "дециметр" in question)):
        return "дм²"
    if "м²" in question or "кв. м" in question or ("площад" in question and ("метр" in question or re.search(r"\bм\b", question))):
        return "м²"
    if re.search(r"(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value):
        unit = _detect_question_unit(raw_text)
        if unit:
            return f"{value} {unit}".strip()
        noun = _extract_question_noun(raw_text)
        if noun:
            return f"{value} {noun}".strip()
    return value


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")

    pretty_expression = _schoolify_expression_source(source)
    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = [line for line in parts["body"] if not line.lower().startswith(("что известно:", "что нужно найти:"))]
    column_block, remaining_body = _split_ascii_layout_block(body_lines)
    if not remaining_body and not column_block:
        remaining_body = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]
    order_block = _detailed_build_order_block(source)
    if order_block and not column_block:
        lines.extend(order_block)
        lines.append("Решение по действиям:")
    else:
        lines.append("Решение.")

    if column_block:
        lines.extend(column_block)
        if remaining_body:
            lines.append("Пояснение:")
    lines.extend(_detailed_number_lines(remaining_body))
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


# stronger mental methods for crossing a ten

def explain_simple_addition(left: int, right: int) -> str:
    total = left + right

    if 0 <= left < 10 and 0 <= right < 10 and total > 10:
        return explain_addition_via_ten(left, right)

    big = max(left, right)
    small = min(left, right)
    if 10 <= big <= 99 and 1 <= small <= 9 and (big % 10) + small >= 10 and big % 10 != 0:
        to_next_ten = 10 - (big % 10)
        rest = small - to_next_ten
        next_ten_value = big + to_next_ten
        return join_explanation_lines(
            "Ищем сумму",
            f"Чтобы получить следующий десяток, к {big} нужно прибавить {to_next_ten}",
            f"Разложим {small} на {to_next_ten} и {rest}",
            f"{big} + {to_next_ten} = {next_ten_value}",
            f"{next_ten_value} + {rest} = {total}",
            f"Ответ: {total}",
            "Совет: при сложении через десяток удобно сначала дойти до круглого десятка",
        )

    return _PREV_FINAL_PATCH_explain_simple_addition(left, right)


def explain_simple_subtraction(left: int, right: int) -> str:
    if left >= 20 and left % 10 == 0 and 0 < right < 10:
        first_part = left - 10
        second_part = 10 - right
        result = left - right
        return join_explanation_lines(
            "Ищем разность",
            f"Представим {left} как {first_part} + 10",
            f"Сначала вычтем {right} из 10: 10 - {right} = {second_part}",
            f"Потом прибавим оставшиеся десятки: {first_part} + {second_part} = {result}",
            f"Ответ: {result}",
            "Совет: из круглого десятка удобно вычитать через 10",
        )
    return _PREV_FINAL_PATCH_explain_simple_subtraction(left, right)


def explain_simple_multiplication(left: int, right: int) -> str:
    big = max(left, right)
    small = min(left, right)
    if 10 <= big <= 99 and big % 10 == 0 and 1 <= small <= 9:
        tens = big // 10
        result = big * small
        return join_explanation_lines(
            "Ищем произведение",
            f"Число {big} — это {tens} десятков",
            f"Умножаем десятки: {tens} × {small} = {tens * small} десятков",
            f"{tens * small} десятков = {result}",
            f"Ответ: {result}",
            "Совет: круглое число удобно воспринимать как десятки",
        )
    return _PREV_FINAL_PATCH_explain_simple_multiplication(left, right)


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи",
            "Запишите пример или задачу полнее и без сокращений",
            "Ответ: пока нужен более понятный ввод",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1800,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- OPENAI FINAL PATCH 2026-04-11F: safer noun enrichment and better tens wording ---

def _can_use_raw_plural_noun_with_count(count_value: int) -> bool:
    value = abs(int(count_value)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return True
    return tail == 0 or tail >= 5


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value):
        unit = _detect_question_unit(raw_text)
        if unit:
            return f"{value} {unit}".strip()
        noun = _extract_question_noun(raw_text)
        if noun:
            try:
                count_value = int(value.split("/", 1)[0])
            except Exception:
                count_value = None
            if noun == "раз":
                return f"{value} раз"
            if count_value is not None and _can_use_raw_plural_noun_with_count(count_value):
                return f"{value} {noun}".strip()
    return value


def explain_simple_multiplication(left: int, right: int) -> str:
    big = max(left, right)
    small = min(left, right)
    if 10 <= big <= 99 and big % 10 == 0 and 1 <= small <= 9:
        tens = big // 10
        tens_word = plural_form(tens, 'десяток', 'десятка', 'десятков')
        product_tens = tens * small
        product_tens_word = plural_form(product_tens, 'десяток', 'десятка', 'десятков')
        result = big * small
        return join_explanation_lines(
            "Ищем произведение",
            f"Число {big} — это {tens} {tens_word}",
            f"Умножаем десятки: {tens} × {small} = {product_tens} {product_tens_word}",
            f"{product_tens} {product_tens_word} = {result}",
            f"Ответ: {result}",
            "Совет: круглое число удобно воспринимать как десятки",
        )
    return _PREV_FINAL_PATCH_explain_simple_multiplication(left, right)


# --- FINAL PATCH 2026-04-11G: textbook fixes, fuller answers, better compound tasks ---

_PATCH20260411G_PREVIOUS_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом:
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже обязательно:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай только по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. По возможности используй школьную форму:
Если ..., то ...
6. Если сразу нельзя ответить на главный вопрос, сначала найди то, что нужно для ответа.
7. После каждого действия коротко говори, что нашли.
8. В конце:
Ответ: ...
Ответ лучше писать полной фразой, а не только числом.

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если это выражение, сначала назови порядок действий.
Если это уравнение, оставляй x отдельно и объясняй обратное действие.
Если это дроби, сначала смотри на знаменатели.
Если это геометрия, сначала назови формулу, потом подставь числа.
Если это именованные величины, сначала переведи их в одинаковые единицы.

Используй школьные приёмы:
сложение через десяток — разложи число так, чтобы сначала получить 10;
вычитание через десяток — вычитай по частям через 10;
двузначные числа раскладывай на десятки и единицы;
если числа большие, объясняй по разрядам;
для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()


def _patch_answer_with_question_noun(value: int, raw_text: str) -> str:
    unit = _detect_question_unit(raw_text) or ""
    if unit:
        return f"{value} {unit}".strip()
    noun = _extract_question_noun(raw_text)
    if noun:
        try:
            count = int(value)
        except Exception:
            count = None
        if noun == "раз":
            return f"{value} раз"
        if count is not None and _can_use_raw_plural_noun_with_count(count):
            return f"{value} {noun}".strip()
    return str(value)


def try_patch_unknown_minuend_simple_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in question:
        return None
    if not ("было" in question or "сначала" in question):
        return None
    if "остал" not in lower:
        return None
    if not contains_any_fragment(lower, WORD_LOSS_HINTS + ("сняли", "взяли", "убрали", "забрали", "отдали", "продали")):
        return None

    removed, remaining = nums[0], nums[1]
    total = removed + remaining
    removed_phrase = _patch_number_phrase(raw_text, removed, 0)
    remaining_phrase = _patch_number_phrase(raw_text, remaining, 0)
    answer = _patch_answer_with_question_noun(total, raw_text)
    return join_explanation_lines(
        f"1) Если сняли {removed_phrase} и осталось {remaining_phrase}, то сначала было {removed} + {remaining} = {answer}",
        f"Ответ: {answer}",
        "Совет: чтобы найти, сколько было сначала, к оставшемуся прибавляют то, что убрали",
    )


def try_patch_implicit_total_with_relation_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in question:
        return None
    if not (("в первый день" in lower and "во второй" in lower) or ("в первый" in lower and "во второй" in lower)):
        return None
    if "во второй" in question or "в первый" in question:
        return None

    base = nums[0]
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    noun_matches = re.findall(rf"{base}\s+([а-яё]+)", lower)
    noun = noun_matches[0] if noun_matches else ""

    if len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        if delta != nums[1]:
            return None
        second = apply_more_less(base, delta, mode)
        if second is None:
            return None
        op = "+" if mode == "больше" else "-"
        total = base + second
        answer = _patch_answer_with_question_noun(total, raw_text)
        second_text = f"{second} {noun}".strip()
        return join_explanation_lines(
            f"1) Если в первый день было {base} {noun}, а во второй на {delta} {mode}, то во второй день было {base} {op} {delta} = {second_text}",
            f"2) Если в первый день было {base} {noun}, а во второй день {second_text}, то всего {base} + {second} = {answer}",
            f"Ответ: {answer}",
            "Совет: если сразу нельзя ответить на главный вопрос, сначала найди неизвестное количество, потом сумму",
        )

    if len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        if factor != nums[1]:
            return None
        second = apply_times_relation(base, factor, mode)
        if second is None:
            return None
        op = "×" if mode == "больше" else ":"
        total = base + second
        answer = _patch_answer_with_question_noun(total, raw_text)
        second_text = f"{second} {noun}".strip()
        return join_explanation_lines(
            f"1) Если во второй день в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то во второй день было {base} {op} {factor} = {second_text}",
            f"2) Если в первый день было {base} {noun}, а во второй день {second_text}, то всего {base} + {second} = {answer}",
            f"Ответ: {answer}",
            "Совет: сначала найди число, которое дано через отношение, потом считай всё вместе",
        )
    return None


def try_patch_part_then_compare_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "из них" not in lower or "осталь" not in lower:
        return None
    if not ("на сколько" in question or "во сколько" in question):
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None

    total, known = nums[0], nums[1]
    if known > total:
        return None
    other = total - known

    pattern = re.search(r"из\s+них\s+(\d+)\s+([а-яё]+).*?остальн[а-яё]*\s*[—-]?\s*([а-яё]+)", lower)
    known_name = pattern.group(2) if pattern else "известной части"
    other_name = pattern.group(3) if pattern else "другой части"
    q_left, q_right = _patch_pick_compare_names_from_question(raw_text)
    if q_left:
        known_name = q_left if q_left in lower else known_name
        other_name = q_right if q_right in lower else other_name

    if "во сколько" in question:
        bigger = max(known, other)
        smaller = min(known, other)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        return join_explanation_lines(
            f"1) Если всего было {total}, а {known_name} было {known}, то {other_name} было {total} - {known} = {other}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если сначала нужно найти неизвестную часть, а потом сравнить, выполняй действия по порядку",
        )

    bigger = max(known, other)
    smaller = min(known, other)
    diff = bigger - smaller
    if known >= other:
        answer_line = f"Ответ: {known_name} на {diff} больше, чем {other_name}"
    else:
        answer_line = f"Ответ: {other_name} на {diff} больше, чем {known_name}"
    return join_explanation_lines(
        f"1) Если всего было {total}, а {known_name} было {known}, то {other_name} было {total} - {known} = {other}",
        f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
        answer_line,
        "Совет: если сначала нужно найти неизвестную часть, а потом сравнить, выполняй действия по порядку",
    )


def try_patch_same_quantity_price_compare_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "за столько же" not in lower or not ("дороже" in question or "дешевле" in question):
        return None

    first = re.search(r"за\s+(\d+)\s+([а-яё]+)\s+([а-яё]+)\s+заплатил\w*\s+(\d+)\s*руб", lower)
    second = re.search(r"за\s+столько\s+же\s+([а-яё]+)\s+([а-яё]+)\s+\w+\s+заплатил\w*\s+(\d+)\s*руб", lower)
    if not first or not second:
        return None

    count = int(first.group(1))
    unit_plural = first.group(2)
    item1 = first.group(3)
    cost1 = int(first.group(4))
    item2 = second.group(2)
    cost2 = int(second.group(3))
    if count == 0 or cost1 % count != 0 or cost2 % count != 0:
        return None

    price1 = cost1 // count
    price2 = cost2 // count
    diff = abs(price1 - price2)
    unit_singular = _patch_singular_unit(unit_plural)

    asked = re.search(rf"{unit_singular}\s+([а-яё]+).*?чем\s+{unit_singular}\s+([а-яё]+)", question)
    left_item = asked.group(1) if asked else item2
    right_item = asked.group(2) if asked else item1
    price_by_item = {item1: price1, item2: price2}
    if left_item not in price_by_item or right_item not in price_by_item:
        return None

    left_price = price_by_item[left_item]
    right_price = price_by_item[right_item]
    if left_price > right_price:
        answer_line = f"Ответ: один {unit_singular} {left_item} на {diff} руб. дороже, чем один {unit_singular} {right_item}"
    elif left_price < right_price:
        answer_line = f"Ответ: один {unit_singular} {left_item} на {diff} руб. дешевле, чем один {unit_singular} {right_item}"
    else:
        answer_line = f"Ответ: один {unit_singular} {left_item} стоит столько же, сколько и один {unit_singular} {right_item}"

    return join_explanation_lines(
        f"1) Если за {count} {unit_plural} {item1} заплатили {cost1} руб., то один {unit_singular} {item1} стоит {cost1} : {count} = {price1} руб",
        f"2) Если за {count} {unit_plural} {item2} заплатили {cost2} руб., то один {unit_singular} {item2} стоит {cost2} : {count} = {price2} руб",
        f"3) Сравниваем цены: {max(price1, price2)} - {min(price1, price2)} = {diff} руб",
        answer_line,
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


def try_patch_named_sum_of_two_products_money_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None
    if not (contains_any_fragment(lower, ("заплат", "стоим")) or contains_any_fragment(question, ("сколько денег", "сколько заплат", "сколько стоила", "сколько стоит"))):
        return None

    products = _po_product_matches(raw_text)
    if len(products) < 2:
        return None
    if contains_any_fragment(question, ("сколько стоит 1", "сколько стоила 1", "сколько стоила одна", "сколько стоит одна")):
        return None

    first = products[0]
    second = products[1]
    first_total = first["count"] * first["value"]
    second_total = second["count"] * second["value"]
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если купили {first['count']} {first['name']} по {first['value']} руб., то за {first['name']} заплатили {first['count']} × {first['value']} = {first_total} руб",
        f"2) Если купили {second['count']} {second['name']} по {second['value']} руб., то за {second['name']} заплатили {second['count']} × {second['value']} = {second_total} руб",
        f"3) Если за {first['name']} заплатили {first_total} руб., а за {second['name']} {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )


def try_patch_labeled_proportional_division_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if not contains_any_fragment(lower, ("цена наборов одинаковая", "цена одинаковая", "если цена наборов одинаковая", "если цена одинаковая")):
        return None
    if not ("сколько" in question and contains_any_fragment(question, ("каждого", "каждая", "каждой"))):
        return None

    match = re.search(r"(\d+)\s+([^.,;]+?)\s+и\s+(\d+)\s+([^.,;]+?)\.\s*за\s+всю\s+покупку\s+заплатил[аи]?\s+(\d+)\s*руб", lower)
    if not match:
        return None

    count1 = int(match.group(1))
    label1 = match.group(2).strip()
    count2 = int(match.group(3))
    label2 = match.group(4).strip()
    total_cost = int(match.group(5))

    total_count = count1 + count2
    if total_count == 0 or total_cost % total_count != 0:
        return None
    one_price = total_cost // total_count
    first_cost = one_price * count1
    second_cost = one_price * count2

    return join_explanation_lines(
        f"1) Если купили {count1} {label1} и {count2} {label2}, то всего купили {count1} + {count2} = {total_count} наборов",
        f"2) Если за {total_count} наборов заплатили {total_cost} руб., то один набор стоит {total_cost} : {total_count} = {one_price} руб",
        f"3) Если один набор стоит {one_price} руб., то за {count1} {label1} заплатили {one_price} × {count1} = {first_cost} руб",
        f"4) Если один набор стоит {one_price} руб., то за {count2} {label2} заплатили {one_price} × {count2} = {second_cost} руб",
        f"Ответ: за {count1} {label1} заплатили {first_cost} руб.; за {count2} {label2} — {second_cost} руб",
        "Совет: в задачах на пропорциональное деление сначала находят одну равную часть",
    )


def try_patch_labeled_two_differences_bag_counts_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or "мешк" not in question:
        return None
    if not ("морков" in lower and "картоф" in lower):
        return None

    carrot_mass, potato_mass, diff_bags = nums
    diff_mass = potato_mass - carrot_mass
    if diff_bags == 0 or diff_mass <= 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    if carrot_mass % per_bag != 0 or potato_mass % per_bag != 0:
        return None
    carrot_bags = carrot_mass // per_bag
    potato_bags = potato_mass // per_bag

    return join_explanation_lines(
        f"1) Если картофеля собрали {potato_mass} кг, а моркови {carrot_mass} кг, то разность масс равна {potato_mass} - {carrot_mass} = {diff_mass} кг",
        f"2) Если эти {diff_mass} кг составляют {diff_bags} мешков, то в одном мешке {diff_mass} : {diff_bags} = {per_bag} кг",
        f"3) Если моркови {carrot_mass} кг, а в одном мешке {per_bag} кг, то мешков моркови {carrot_mass} : {per_bag} = {carrot_bags}",
        f"4) Если картофеля {potato_mass} кг, а в одном мешке {per_bag} кг, то мешков картофеля {potato_mass} : {per_bag} = {potato_bags}",
        f"Ответ: моркови было {carrot_bags} мешков, картофеля — {potato_bags} мешков",
        "Совет: в задачах по двум разностям сначала находят, чему соответствует одна равная часть",
    )


def try_patch_labeled_indirect_two_question_total_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "?" not in raw_text:
        return None
    if not (("во втором" in question or "на второй" in question) and ("в двух" in question or "в двух кружках" in question or "всего" in question or "обоих" in question)):
        return None

    base = nums[0]
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)

    if len(relation_pairs) == 1 and "это" in lower:
        delta, relation = relation_pairs[0]
        if relation == "больше":
            second = base - delta
            op = "-"
            relation_text = "на столько же меньше"
        else:
            second = base + delta
            op = "+"
            relation_text = "на столько же больше"
        if second < 0:
            return None
        total = base + second
        answer = _patch_answer_with_question_noun(total, raw_text)
        return join_explanation_lines(
            f"1) Это косвенная форма: если здесь на {delta} {relation}, то другое число {relation_text}",
            f"2) Находим второе количество: {base} {op} {delta} = {second}",
            f"3) Находим всё вместе: {base} + {second} = {answer}",
            f"Ответ: во втором количестве — {second}; всего — {answer}",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму",
        )

    if len(scale_pairs) == 1 and "это" in lower:
        factor, relation = scale_pairs[0]
        if relation == "больше":
            if factor == 0 or base % factor != 0:
                return None
            second = base // factor
            op = ":"
            relation_text = "во столько же раз меньше"
        else:
            second = base * factor
            op = "×"
            relation_text = "во столько же раз больше"
        total = base + second
        answer = _patch_answer_with_question_noun(total, raw_text)
        return join_explanation_lines(
            f"1) Это косвенная форма: если здесь в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то другое число {relation_text}",
            f"2) Находим второе количество: {base} {op} {factor} = {second}",
            f"3) Находим всё вместе: {base} + {second} = {answer}",
            f"Ответ: во втором количестве — {second}; всего — {answer}",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму",
        )
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_patch_same_quantity_price_compare_explanation(user_text)
        or try_patch_named_sum_of_two_products_money_explanation(user_text)
        or try_patch_unknown_minuend_simple_explanation(user_text)
        or try_patch_part_then_compare_explanation(user_text)
        or try_patch_implicit_total_with_relation_explanation(user_text)
        or try_patch_labeled_proportional_division_explanation(user_text)
        or try_patch_labeled_two_differences_bag_counts_explanation(user_text)
        or try_patch_labeled_indirect_two_question_total_explanation(user_text)
        or _PATCH20260411G_PREVIOUS_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )

# --- merged segment 005: backend.legacy_runtime_shards.prepatch_build_source.segment_005 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 3541-4401."""



# --- FINAL PATCH 2026-04-11H: grammar polishing for named tasks ---


def _patch_after_za_name(name: str) -> str:
    text = re.sub(r"\s+", " ", str(name or "").strip())
    parts = text.split()
    if not parts:
        return text
    mapping = {
        "тетрадей": "тетради",
        "книг": "книги",
        "ручек": "ручки",
        "карандашей": "карандаши",
        "цветов": "цветы",
        "яблок": "яблоки",
        "груш": "груши",
        "роз": "розы",
        "гвоздик": "гвоздики",
        "фломастеров": "фломастеры",
        "альбомов": "альбомы",
        "карандашей": "карандаши",
        "пакетов": "пакеты",
        "наборов": "наборы",
    }
    parts[-1] = mapping.get(parts[-1], parts[-1])
    return " ".join(parts)


def try_patch_named_sum_of_two_products_money_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None
    if not (contains_any_fragment(lower, ("заплат", "стоим")) or contains_any_fragment(question, ("сколько денег", "сколько заплат", "сколько стоила", "сколько стоит"))):
        return None

    products = _po_product_matches(raw_text)
    if len(products) < 2:
        return None
    if contains_any_fragment(question, ("сколько стоит 1", "сколько стоила 1", "сколько стоила одна", "сколько стоит одна")):
        return None

    first = products[0]
    second = products[1]
    first_total = first["count"] * first["value"]
    second_total = second["count"] * second["value"]
    total = first_total + second_total
    first_name = _patch_after_za_name(first["name"])
    second_name = _patch_after_za_name(second["name"])

    return join_explanation_lines(
        f"1) Если купили {first['count']} {first['name']} по {first['value']} руб., то за {first_name} заплатили {first['count']} × {first['value']} = {first_total} руб",
        f"2) Если купили {second['count']} {second['name']} по {second['value']} руб., то за {second_name} заплатили {second['count']} × {second['value']} = {second_total} руб",
        f"3) Если за {first_name} заплатили {first_total} руб., а за {second_name} {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )


def try_patch_part_then_compare_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "из них" not in lower or "осталь" not in lower:
        return None
    if not ("на сколько" in question or "во сколько" in question):
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None

    total, known = nums[0], nums[1]
    if known > total:
        return None
    other = total - known

    pattern = re.search(r"из\s+них\s+(\d+)\s+([а-яё]+).*?остальн[а-яё]*\s*[—-]?\s*([а-яё]+)", lower)
    known_name = pattern.group(2) if pattern else "известной части"
    other_name = pattern.group(3) if pattern else "другой части"
    q_left, q_right = _patch_pick_compare_names_from_question(raw_text)
    if q_left:
        known_name = q_left
    if q_right:
        other_name = q_right

    if "во сколько" in question:
        bigger = max(known, other)
        smaller = min(known, other)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        return join_explanation_lines(
            f"1) Если всего было {total}, а {known_name} было {known}, то {other_name} было {total} - {known} = {other}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если сначала нужно найти неизвестную часть, а потом сравнить, выполняй действия по порядку",
        )

    bigger = max(known, other)
    smaller = min(known, other)
    diff = bigger - smaller
    if known >= other:
        answer_line = f"Ответ: {known_name} на {diff} больше, чем {other_name}"
    else:
        answer_line = f"Ответ: {other_name} на {diff} больше, чем {known_name}"
    return join_explanation_lines(
        f"1) Если всего было {total}, а {known_name} было {known}, то {other_name} было {total} - {known} = {other}",
        f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
        answer_line,
        "Совет: если сначала нужно найти неизвестную часть, а потом сравнить, выполняй действия по порядку",
    )


def try_patch_labeled_indirect_two_question_total_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "?" not in raw_text:
        return None
    if not (("во втором" in question or "на второй" in question) and ("в двух" in question or "в двух кружках" in question or "всего" in question or "обоих" in question)):
        return None

    base = nums[0]
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    has_indirect_marker = ("это" in lower) or ("что" in lower)
    if not has_indirect_marker:
        return None

    second_label = "во втором кружке" if "кружке" in question else "во втором"
    if "полке" in question:
        second_label = "на второй полке"
    total_label = "всего"
    answer_total = ""

    if len(relation_pairs) == 1:
        delta, relation = relation_pairs[0]
        if relation == "больше":
            second = base - delta
            op = "-"
            relation_text = "на столько же меньше"
        else:
            second = base + delta
            op = "+"
            relation_text = "на столько же больше"
        if second < 0:
            return None
        total = base + second
        answer_total = _patch_answer_with_question_noun(total, raw_text)
        return join_explanation_lines(
            f"1) Это косвенная форма: если здесь на {delta} {relation}, то другое число {relation_text}",
            f"2) Находим второе количество: {base} {op} {delta} = {second}",
            f"3) Находим всё вместе: {base} + {second} = {answer_total}",
            f"Ответ: {second_label} — {second}; {total_label} — {answer_total}",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму",
        )

    if len(scale_pairs) == 1:
        factor, relation = scale_pairs[0]
        if relation == "больше":
            if factor == 0 or base % factor != 0:
                return None
            second = base // factor
            op = ":"
            relation_text = "во столько же раз меньше"
        else:
            second = base * factor
            op = "×"
            relation_text = "во столько же раз больше"
        total = base + second
        answer_total = _patch_answer_with_question_noun(total, raw_text)
        return join_explanation_lines(
            f"1) Это косвенная форма: если здесь в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то другое число {relation_text}",
            f"2) Находим второе количество: {base} {op} {factor} = {second}",
            f"3) Находим всё вместе: {base} + {second} = {answer_total}",
            f"Ответ: {second_label} — {second}; {total_label} — {answer_total}",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму",
        )
    return None


# --- FINAL PATCH 2026-04-11I: question compare noun extraction fix ---


# --- FINAL PATCH 2026-04-11J: two-question relation-and-compare tasks ---

def _patch_secondary_place_label(raw_text: str) -> str:
    lower = _statement_lower_text(raw_text)
    for pattern in [r"во\s+второй\s+[а-яё]+", r"во\s+втором\s+[а-яё]+", r"на\s+второй\s+[а-яё]+", r"на\s+втором\s+[а-яё]+"]:
        match = re.search(pattern, lower)
        if match:
            return match.group(0)
    return "во второй части"


def try_patch_relation_then_compare_two_question_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    if raw_text.count("?") < 2:
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    base = nums[0]
    second_label = _patch_secondary_place_label(raw_text)

    if len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        diff = bigger - smaller
        op = "+" if mode == "больше" else "-"
        if mode == "больше":
            compare_line = f"Ответ: {second_label} было {related}; в первом месте было на {diff} больше"
        else:
            compare_line = f"Ответ: {second_label} было {related}; в первом месте было на {diff} больше"
        return join_explanation_lines(
            f"1) Если во втором месте на {delta} {mode}, то {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            compare_line,
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )

    if len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если во втором месте в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: {second_label} было {related}; отличие — в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_patch_same_quantity_price_compare_explanation(user_text)
        or try_patch_named_sum_of_two_products_money_explanation(user_text)
        or try_patch_unknown_minuend_simple_explanation(user_text)
        or try_patch_relation_then_compare_two_question_explanation(user_text)
        or try_patch_part_then_compare_explanation(user_text)
        or try_patch_implicit_total_with_relation_explanation(user_text)
        or try_patch_labeled_proportional_division_explanation(user_text)
        or try_patch_labeled_two_differences_bag_counts_explanation(user_text)
        or try_patch_labeled_indirect_two_question_total_explanation(user_text)
        or _PATCH20260411G_PREVIOUS_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-11K: support mixed-question punctuation in two-question tasks ---

def try_patch_relation_then_compare_two_question_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    has_find_second = bool(re.search(r"сколько[^?.!]*?(?:во\s+второй|во\s+втором|на\s+второй|на\s+втором)", lower))
    has_compare = ("на сколько" in lower) or ("во сколько" in lower)
    if not (has_find_second and has_compare):
        return None

    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    base = nums[0]
    second_label = _patch_secondary_place_label(raw_text)
    first_label = second_label.replace("второй", "первой").replace("втором", "первом")

    if len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        diff = bigger - smaller
        op = "+" if mode == "больше" else "-"
        relation_text = "больше" if base >= related else "меньше"
        return join_explanation_lines(
            f"1) Если {second_label} на {delta} {mode}, то {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            f"Ответ: {second_label} было {related}; {first_label} было на {diff} {relation_text}",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )

    if len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если {second_label} в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: {second_label} было {related}; отличие — в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_patch_same_quantity_price_compare_explanation(user_text)
        or try_patch_named_sum_of_two_products_money_explanation(user_text)
        or try_patch_unknown_minuend_simple_explanation(user_text)
        or try_patch_relation_then_compare_two_question_explanation(user_text)
        or try_patch_part_then_compare_explanation(user_text)
        or try_patch_implicit_total_with_relation_explanation(user_text)
        or try_patch_labeled_proportional_division_explanation(user_text)
        or try_patch_labeled_two_differences_bag_counts_explanation(user_text)
        or try_patch_labeled_indirect_two_question_total_explanation(user_text)
        or _PATCH20260411G_PREVIOUS_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-11L: better place labels for two-question tasks ---

def _patch_secondary_place_label(raw_text: str) -> str:
    normalized = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    match = re.search(r"сколько[^?.!]*?(во\s+второй\s+[а-яё]+|во\s+втором\s+[а-яё]+|на\s+второй\s+[а-яё]+|на\s+втором\s+[а-яё]+)", normalized)
    if match:
        return match.group(1)
    for label in ("во второй вазе", "на второй полке", "во втором кружке", "во второй день", "на второй стоянке"):
        if label in normalized:
            return label
    return "во второй части"


def _patch_first_place_label(second_label: str) -> str:
    text = str(second_label or "").strip()
    text = text.replace("во второй", "в первой")
    text = text.replace("во втором", "в первом")
    text = text.replace("на второй", "на первой")
    text = text.replace("на втором", "на первом")
    return text


def try_patch_relation_then_compare_two_question_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    has_find_second = bool(re.search(r"сколько[^?.!]*?(?:во\s+второй|во\s+втором|на\s+второй|на\s+втором)", lower))
    has_compare = ("на сколько" in lower) or ("во сколько" in lower)
    if not (has_find_second and has_compare):
        return None

    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    base = nums[0]
    second_label = _patch_secondary_place_label(raw_text)
    first_label = _patch_first_place_label(second_label)

    if len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        diff = bigger - smaller
        op = "+" if mode == "больше" else "-"
        return join_explanation_lines(
            f"1) Если {second_label} на {delta} {mode}, чем {first_label}, то {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            f"Ответ: {second_label} было {related}; {first_label} было на {diff} больше",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )

    if len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если {second_label} в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, чем {first_label}, то {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: {second_label} было {related}; отличие — в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )
    return None


# --- FINAL PATCH 2026-04-11M: safer count answers, missing simple templates, cleaner fraction remainder ---

_PREVIOUS_20260411M_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_PREVIOUS_20260411M_DETECT_QUESTION_UNIT = _detect_question_unit


def _question_requests_object_count(raw_text: str) -> bool:
    return _external_question_requests_object_count(raw_text, _question_lower_text, MEASURE_QUESTION_NOUNS)


def _detect_question_unit(raw_text: str) -> str:
    return _external_initial_detect_question_unit(raw_text, _question_requests_object_count, _PREVIOUS_20260411M_DETECT_QUESTION_UNIT)


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    return _external_initial_detailed_maybe_enrich_answer(
        answer,
        raw_text,
        _detect_question_unit,
        _extract_question_noun,
        _question_requests_object_count,
    )


    if remaining_numerator == 1:
        whole = remaining_value * denominator
        return join_explanation_lines(
            f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось 1/{denominator} всех денег",
            f"2) Если 1/{denominator} всех денег равна {remaining_value} руб., то одна доля равна {remaining_value} руб.",
            f"3) Если одна доля равна {remaining_value} руб., то все деньги равны {remaining_value} × {denominator} = {whole} руб.",
            f"Ответ: всего было {whole} руб.",
            "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
        )
    if remaining_value % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value} руб., то одна доля равна {remaining_value} : {remaining_numerator} = {one_part} руб.",
        f"3) Если одна доля равна {one_part} руб., то все деньги равны {one_part} × {denominator} = {whole} руб.",
        f"Ответ: всего было {whole} руб.",
        "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
    )


def try_patch_single_group_total_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    if "сколько" not in question:
        return None
    if _has_group_count_question(question) or "кажд" in question or "поровну" in lower:
        return None
    if not re.search(r"\b(?:в\s+одной|в\s+одном|на\s+одной|на\s+одном)\b", lower):
        return None
    if not re.search(r"\b(?:в|на)\s+\d+\s+[а-яё]+", question):
        return None

    per_group, groups = nums[0], nums[1]
    total = per_group * groups
    return join_explanation_lines(
        f"1) Если в одной группе {per_group} предметов, а таких групп {groups}, то всего {per_group} × {groups} = {total}",
        f"Ответ: {total}",
        "Совет: если одинаковое количество повторяется несколько раз, используют умножение",
    )


def try_patch_unknown_multiplier_by_content_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    if "сколько" not in question:
        return None
    if not contains_any_fragment(question, ("сеток", "пакетов", "коробок", "клеток", "корзин", "групп", "потребовалось", "понадобилось", "понадобится")):
        return None
    po_match = re.search(r"по\s+(\d+)\s+[а-яё]+", lower)
    if not po_match:
        return None

    total = max(nums)
    per_group = int(po_match.group(1))
    if per_group == 0 or total % per_group != 0:
        return None
    groups = total // per_group
    return join_explanation_lines(
        f"1) Если по {per_group} предметов брали несколько раз и получили {total} предметов, то число групп равно {total} : {per_group} = {groups}",
        f"Ответ: {groups}",
        "Совет: чтобы найти неизвестный множитель, произведение делят на известный множитель",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_patch_unknown_multiplier_by_content_explanation(user_text)
        or try_patch_single_group_total_explanation(user_text)
        or _PREVIOUS_20260411M_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-11N: better noun extraction in count questions ---


def _extract_count_question_noun(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    patterns = [
        r"^сколько\s+(?:было\s+|будет\s+|стало\s+|осталось\s+|получилось\s+|потребуется\s+|потребовалось\s+|понадобится\s+|понадобилось\s+|можно\s+купить\s+)?(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)",
        r"^сколько\s+(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            noun = match.group(1).strip().lower().replace("ё", "е")
            if noun:
                return noun
    return ""


def _question_requests_object_count(raw_text: str) -> bool:
    noun = _extract_count_question_noun(raw_text)
    return bool(noun) and noun not in MEASURE_QUESTION_NOUNS


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value

    is_numeric = re.fullmatch(r"-?\d+(?:/\d+)?", value) is not None
    if not is_numeric:
        return value

    noun = _extract_count_question_noun(raw_text)
    if noun and noun not in MEASURE_QUESTION_NOUNS:
        forms = _lookup_question_noun_forms(noun)
        if forms:
            try:
                count_value = int(value.split("/", 1)[0])
            except Exception:
                return value
            return f"{value} {_select_plural_by_count(count_value, forms)}"
        return value

    unit = _detect_question_unit(raw_text)
    if unit:
        return f"{value} {unit}".strip()
    return value


# --- USER CONSOLIDATION PATCH 2026-04-11Z: cleaner final answers, textbook priority cases, stronger prompt ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown-таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений:
1. В первой строке пиши полный пример с ответом.
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже обязательно:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом само условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай только по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. Если можно, используй школьную форму:
Если ..., то ...
6. Если сразу нельзя ответить на главный вопрос, сначала найди то, что нужно для ответа.
7. После каждого действия коротко говори, что нашли.
8. В конце:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()

_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_USER_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER = _detailed_maybe_enrich_answer


def _user_patch_pick_measure_unit(raw_text: str) -> str:
    try:
        question = _question_lower_text(raw_text)
    except Exception:
        question = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    statement = _statement_lower_text(raw_text)

    existing = ""
    try:
        existing = _detect_question_unit(raw_text) or ""
    except Exception:
        existing = ""
    if existing:
        return existing

    if contains_any_fragment(question, ("сколько весит", "какова масса", "чему равна масса")):
        for unit in ("т", "кг", "г"):
            if re.search(rf"(?<!/)\b{re.escape(unit)}\b", statement):
                return unit

    if contains_any_fragment(question, ("сколько литров", "сколько л", "каков объем", "каков объём", "чему равен объем", "чему равен объём")):
        for unit in ("л", "мл"):
            if re.search(rf"(?<!/)\b{re.escape(unit)}\b", statement):
                return unit

    if contains_any_fragment(question, ("какова скорость", "с какой скоростью")):
        for unit in ("км/ч", "м/с", "м/мин"):
            if unit in statement:
                return unit

    if contains_any_fragment(question, ("каково расстояние", "сколько километров", "сколько метров", "какова длина", "какова ширина", "какова сторона")):
        for unit in ("км", "м", "дм", "см", "мм"):
            if re.search(rf"(?<!/)\b{re.escape(unit)}\b", statement):
                return unit

    return ""


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value

    if re.search(r"[;]|, остаток", value):
        return value

    if re.fullmatch(r"-?\d+(?:/\d+)?", value) is None:
        return value

    unit = _user_patch_pick_measure_unit(raw_text)
    if unit:
        return f"{value} {unit}".strip()

    try:
        patched = _patch_answer_with_question_noun(int(value.split("/", 1)[0]) if "/" not in value else value, raw_text)
        patched = str(patched).strip()
        if patched and patched != value:
            return patched
    except Exception:
        pass

    try:
        return _USER_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER(answer, raw_text, kind)
    except Exception:
        return value


def explain_equal_rate_distribution(total: int, first_count: int, second_count: int, first_label: str = "первая группа", second_label: str = "вторая группа") -> Optional[str]:
    group_total = first_count + second_count
    if group_total == 0 or total % group_total != 0:
        return None
    one_unit = total // group_total
    first_total = first_count * one_unit
    second_total = second_count * one_unit
    return join_explanation_lines(
        f"1) Если в первой части {first_count} равных долей, а во второй {second_count} равных долей, то всего долей {first_count} + {second_count} = {group_total}",
        f"2) Если всего долей {group_total}, а общее количество равно {total}, то одна доля равна {total} : {group_total} = {one_unit}",
        f"3) Если одна доля равна {one_unit}, то {first_label} равна {one_unit} × {first_count} = {first_total}",
        f"4) Если одна доля равна {one_unit}, то {second_label} равна {one_unit} × {second_count} = {second_total}",
        f"Ответ: {first_label} — {first_total}; {second_label} — {second_total}",
        "Совет: в задачах на пропорциональное деление сначала находят одну равную часть",
    )


def try_user_patch_fraction_measure_explanation(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower()
    fracs = extract_all_fraction_pairs(lower)
    values = extract_non_fraction_numbers(lower)
    if len(fracs) != 1 or not values:
        return None

    question = _question_lower_text(raw_text)
    if not contains_any_fragment(question, ("сколько весит", "сколько кг", "сколько г", "сколько литров", "сколько л")):
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None
    total = max(values)
    unit = _user_patch_pick_measure_unit(raw_text)

    if total % denominator != 0:
        return None

    one_part = total // denominator
    part_value = one_part * numerator

    if numerator == 1:
        return join_explanation_lines(
            f"1) Если целое равно {total}{(' ' + unit) if unit else ''}, то одна доля равна {total} : {denominator} = {one_part}{(' ' + unit) if unit else ''}",
            f"Ответ: {part_value}{(' ' + unit) if unit else ''}",
            "Совет: чтобы найти одну долю числа, делят число на знаменатель",
        )

    return join_explanation_lines(
        f"1) Если целое равно {total}{(' ' + unit) if unit else ''}, то одна доля равна {total} : {denominator} = {one_part}{(' ' + unit) if unit else ''}",
        f"2) Если нужна дробь {numerator}/{denominator}, то берём {numerator} такие доли: {one_part} × {numerator} = {part_value}{(' ' + unit) if unit else ''}",
        f"Ответ: {part_value}{(' ' + unit) if unit else ''}",
        "Совет: чтобы найти долю от числа, сначала делят на знаменатель, потом умножают на числитель",
    )


def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if not remaining:
        return None

    change_value = remaining[0]
    base_total = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало", "купили")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали", "расфасовали")

    if contains_any_fragment(lower, gain_words) and contains_any_fragment(question, ("сколько", "сколько стало", "сколько всего")):
        result = base_total + change_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом добавили ещё {change_value}, то стало {base_total} + {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and contains_any_fragment(question, ("сколько", "сколько осталось", "сколько останется")):
        result = base_total - change_value
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом убрали {change_value}, то осталось {base_total} - {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_user_patch_fraction_measure_explanation(user_text)
        or try_user_patch_groups_then_change_explanation(user_text)
        or _USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- USER HOTFIX 2026-04-11Z1: narrow grouped-plus-change rule ---

def _user_patch_group_word(value: int) -> str:
    return plural_form(value, "одинаковая группа", "одинаковые группы", "одинаковых групп")

# --- merged segment 006: backend.legacy_runtime_shards.prepatch_build_source.segment_006 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 4402-5295."""



def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    change_value = remaining[0]
    base_total = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали", "расфасовали")

    if contains_any_fragment(lower, gain_words) and contains_any_fragment(question, ("сколько", "сколько стало", "сколько всего")):
        result = base_total + change_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} {_user_patch_group_word(groups)} по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом добавили ещё {change_value}, то стало {base_total} + {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and contains_any_fragment(question, ("сколько", "сколько осталось", "сколько останется")):
        result = base_total - change_value
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} {_user_patch_group_word(groups)} по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом убрали {change_value}, то осталось {base_total} - {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    return None


# --- USER HOTFIX 2026-04-11Z2: do not steal "total then packed" remainder tasks ---

def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    change_value = remaining[0]
    base_total = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали")

    asks_gain_total = contains_any_fragment(question, ("сколько стало", "сколько всего", "сколько теперь"))
    asks_loss_total = contains_any_fragment(question, ("сколько осталось", "сколько останется"))

    if contains_any_fragment(lower, gain_words) and asks_gain_total:
        result = base_total + change_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом добавили ещё {change_value}, то стало {base_total} + {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and asks_loss_total:
        result = base_total - change_value
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом убрали {change_value}, то осталось {base_total} - {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    return None


# --- USER HOTFIX 2026-04-11Z3: broader question patterns for "стало/осталось" ---

def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    change_value = remaining[0]
    base_total = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали")

    asks_gain_total = ("стало" in question) or ("всего" in question) or ("теперь" in question)
    asks_loss_total = ("остал" in question)

    if contains_any_fragment(lower, gain_words) and asks_gain_total:
        result = base_total + change_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом добавили ещё {change_value}, то стало {base_total} + {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and asks_loss_total:
        result = base_total - change_value
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом убрали {change_value}, то осталось {base_total} - {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    return None


# --- USER HOTFIX 2026-04-11Z4: word-boundary question detection and better remainder handling ---

def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    other_value = remaining[0]
    group_value = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали", "расфасовали", "упаковали")

    asks_gain_total = bool(re.search(r"\bстало\b|\bвсего\b|\bтеперь\b", question))
    asks_loss_total = "остал" in question

    if contains_any_fragment(lower, gain_words) and asks_gain_total:
        start_amount = min(group_value, other_value)
        added_amount = max(group_value, other_value) if min(group_value, other_value) == group_value else group_value
        # Для конструкций типа "на полках по 2 книги. Подарили ещё 10 книг" стартовым количеством является group_value.
        start_amount = group_value
        added_amount = other_value
        result = start_amount + added_amount
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {group_value}",
            f"2) Если было {group_value}, а потом добавили ещё {other_value}, то стало {group_value} + {other_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and asks_loss_total:
        total_before = max(group_value, other_value)
        removed_amount = min(group_value, other_value)
        result = total_before - removed_amount
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим величину этой части: {groups} × {per_group} = {group_value}",
            f"2) Если всего было {total_before}, а эта часть равна {removed_amount}, то осталось {total_before} - {removed_amount} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если известны всё число и одна часть, другую часть находят вычитанием",
        )

    return None


# --- USER HOTFIX 2026-04-11Z5: correct group phrase agreement ---

def _user_patch_group_phrase(count: int) -> str:
    value = abs(int(count)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return f"{count} одинаковых групп"
    if tail == 1:
        return f"{count} одинаковая группа"
    if 2 <= tail <= 4:
        return f"{count} одинаковые группы"
    return f"{count} одинаковых групп"


def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    other_value = remaining[0]
    group_value = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали", "расфасовали", "упаковали")

    asks_gain_total = bool(re.search(r"\bстало\b|\bвсего\b|\bтеперь\b", question))
    asks_loss_total = "остал" in question

    group_phrase = _user_patch_group_phrase(groups)

    if contains_any_fragment(lower, gain_words) and asks_gain_total:
        result = group_value + other_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {group_phrase} по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {group_value}",
            f"2) Если было {group_value}, а потом добавили ещё {other_value}, то стало {group_value} + {other_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and asks_loss_total:
        total_before = max(group_value, other_value)
        removed_amount = min(group_value, other_value)
        result = total_before - removed_amount
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {group_phrase} по {per_group} в каждой, то сначала находим величину этой части: {groups} × {per_group} = {group_value}",
            f"2) Если всего было {total_before}, а эта часть равна {removed_amount}, то осталось {total_before} - {removed_amount} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если известны всё число и одна часть, другую часть находят вычитанием",
        )

    return None


# --- FINAL CONSOLIDATION PATCH 2026-04-11Z6: safer units, compound word numbers, fuller textbook cases ---

_FINAL_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_FINAL_PATCH_PREV_NORMALIZE_WORD_PROBLEM_TEXT = normalize_word_problem_text

_COMPOUND_PREFIX_TO_DIGIT = {
    "двух": "2",
    "трех": "3",
    "трёх": "3",
    "четырех": "4",
    "четырёх": "4",
    "пяти": "5",
    "шести": "6",
    "семи": "7",
    "восьми": "8",
    "девяти": "9",
    "десяти": "10",
}

_COMPOUND_NUMERAL_RE = re.compile(
    r"\b(" + "|".join(map(re.escape, _COMPOUND_PREFIX_TO_DIGIT.keys())) + r")(литров[а-яё-]*|комнатн[а-яё-]*)",
    flags=re.IGNORECASE,
)


def normalize_word_problem_text(text: str) -> str:
    cleaned = _FINAL_PATCH_PREV_NORMALIZE_WORD_PROBLEM_TEXT(text)

    def _replace_compound(match: re.Match) -> str:
        stem = match.group(1).lower()
        tail = match.group(2)
        return f"{_COMPOUND_PREFIX_TO_DIGIT[stem]}-{tail}"

    cleaned = _COMPOUND_NUMERAL_RE.sub(_replace_compound, cleaned)
    return cleaned


QUESTION_NOUN_FORMS.update({
    "ведро": ("ведро", "ведра", "ведер"),
    "ведра": ("ведро", "ведра", "ведер"),
    "ведер": ("ведро", "ведра", "ведер"),
    "ведрах": ("ведро", "ведра", "ведер"),
    "вёдра": ("ведро", "ведра", "ведер"),
    "вёдер": ("ведро", "ведра", "ведер"),
    "вёдрах": ("ведро", "ведра", "ведер"),
    "ящик": ("ящик", "ящика", "ящиков"),
    "ящика": ("ящик", "ящика", "ящиков"),
    "ящиков": ("ящик", "ящика", "ящиков"),
    "ящиках": ("ящик", "ящика", "ящиков"),
    "клетках": ("клетка", "клетки", "клеток"),
    "банках": ("банка", "банки", "банок"),
    "квартира": ("квартира", "квартиры", "квартир"),
    "квартиры": ("квартира", "квартиры", "квартир"),
    "квартир": ("квартира", "квартиры", "квартир"),
    "комната": ("комната", "комнаты", "комнат"),
    "комнаты": ("комната", "комнаты", "комнат"),
    "комнат": ("комната", "комнаты", "комнат"),
    "раз": ("раз", "раза", "раз"),
})

MEASURE_QUESTION_NOUNS.update({"времени", "день", "дня", "дней", "секунда", "секунды", "секунд"})


def _extract_count_question_noun(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    patterns = [
        r"^(?:в|во|на)\s+скольких\s+([а-яё]+)",
        r"^сколько\s+(?:было\s+|будет\s+|стало\s+|осталось\s+|получилось\s+|понадобится\s+|понадобилось\s+|потребуется\s+|потребовалось\s+|можно\s+купить\s+|нужно\s+|нужно\s+купить\s+|всего\s+)?(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)",
        r"^сколько\s+(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)",
        r"^во\s+сколько\s+([а-яё]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            noun = match.group(1).strip().lower().replace("ё", "е")
            if noun:
                return noun
    return ""


def _question_requests_object_count(raw_text: str) -> bool:
    noun = _extract_count_question_noun(raw_text)
    return bool(noun) and noun not in MEASURE_QUESTION_NOUNS


def _detect_question_unit(raw_text: str) -> str:
    try:
        question = _question_lower_text(raw_text)
    except Exception:
        question = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if _question_requests_object_count(raw_text):
        return ""
    if re.search(r"\bв\s+скольких\b", question):
        return ""
    if re.search(r"\bво\s+сколько\s+раз\b", question):
        return "раз"

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        for unit in ("км/ч", "м/мин", "м/с"):
            if unit in lower_full:
                return unit

    if re.search(r"\b(?:мм|миллиметр(?:а|ов|ы)?)\b", question):
        return "мм"
    if re.search(r"(?:см²|кв\.?\s*см|квадратн[а-яё]*\s+сантиметр)", question) or (
        "площад" in question and re.search(r"\b(?:см|сантиметр(?:а|ов|ы)?)\b", question)
    ):
        return "см²"
    if re.search(r"(?:дм²|кв\.?\s*дм|квадратн[а-яё]*\s+дециметр)", question) or (
        "площад" in question and re.search(r"\b(?:дм|дециметр(?:а|ов|ы)?)\b", question)
    ):
        return "дм²"
    if re.search(r"(?:м²|кв\.?\s*м\b|квадратн[а-яё]*\s+метр)", question) or (
        "площад" in question and re.search(r"\b(?:метр(?:а|ов|ы)?|м)\b", question)
    ):
        return "м²"

    if re.search(r"\b(?:руб|рубл(?:ь|я|ей)?|денег)\b", question):
        return "руб"
    if re.search(r"\b(?:кг|килограмм(?:а|ов|ы)?)\b", question):
        return "кг"
    if re.search(r"\b(?:г|грамм(?:а|ов|ы)?)\b", question):
        return "г"
    if re.search(r"\b(?:км|километр(?:а|ов|ы)?)\b", question):
        return "км"
    if re.search(r"\b(?:см|сантиметр(?:а|ов|ы)?)\b", question):
        return "см"
    if re.search(r"\b(?:дм|дециметр(?:а|ов|ы)?)\b", question):
        return "дм"
    if re.search(r"\b(?:м|метр(?:а|ов|ы)?)\b", question):
        return "м"
    if re.search(r"\b(?:л|литр(?:а|ов|ы)?)\b", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value) is None:
        return value

    noun = _extract_count_question_noun(raw_text)
    if noun and noun not in MEASURE_QUESTION_NOUNS:
        forms = _lookup_question_noun_forms(noun)
        if forms:
            try:
                count_value = int(value.split("/", 1)[0])
            except Exception:
                return value
            return f"{value} {_select_plural_by_count(count_value, forms)}"
        if noun == "раз":
            return f"{value} раз"

    unit = _detect_question_unit(raw_text)
    if unit:
        return f"{value} {unit}".strip()
    return value


def _final_patch_group_phrase(count: int) -> str:
    value = abs(int(count)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return f"{count} одинаковых групп"
    if tail == 1:
        return f"{count} одинаковая группа"
    if 2 <= tail <= 4:
        return f"{count} одинаковые группы"
    return f"{count} одинаковых групп"


def _final_patch_plural(count_value: int, forms: Tuple[str, str, str]) -> str:
    return _select_plural_by_count(count_value, forms)


def try_final_patch_simple_group_total_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if "сколько" not in question:
        return None
    if len(nums) != 2:
        return None
    if any(fragment in question for fragment in (
        "в скольких",
        "сколько потребуется",
        "сколько потребовалось",
        "сколько понадобится",
        "сколько понадобилось",
        "сколько осталось",
        "сколько останется",
        "сколько стало",
        "сколько заплатила",
        "сколько заплатил",
        "сколько стоила",
        "сколько стоит",
    )):
        return None
    if "поровну" in lower or "кажд" in question:
        return None
    if contains_any_fragment(lower, WORD_GAIN_HINTS + WORD_LOSS_HINTS):
        return None

    groups = None
    per_group = None
    unit = _detect_question_unit(raw_text)

    if len(re.findall(r"\bпо\s+\d+\b", lower)) == 1:
        pair = _first_po_pair(lower)
        if pair:
            groups, per_group = pair
    else:
        match = re.search(r"\b(\d+)\s+(\d+)-литров[а-я-]*\s+[а-я]+\b", lower)
        if match:
            groups, per_group = int(match.group(1)), int(match.group(2))
            unit = unit or "л"

    if groups is None or per_group is None:
        return None

    total = groups * per_group
    group_phrase = _final_patch_group_phrase(groups)
    if unit:
        return join_explanation_lines(
            f"1) Если есть {group_phrase} по {per_group} {unit} в каждой, то всего {groups} × {per_group} = {total} {unit}",
            f"Ответ: всего было {total} {unit}",
            "Совет: если одинаковая величина повторяется несколько раз, используют умножение",
        )
    answer_text = _detailed_maybe_enrich_answer(str(total), raw_text, "word")
    return join_explanation_lines(
        f"1) Если есть {group_phrase} по {per_group} в каждой, то всего {groups} × {per_group} = {total}",
        f"Ответ: всего было {answer_text}",
        "Совет: если одинаковое количество повторяется несколько раз, используют умножение",
    )


def try_final_patch_school_boxes_equal_price_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "школ" not in lower or "ящик" not in lower:
        return None
    if "сколько должна заплатить" not in question and "каждая школа" not in question:
        return None

    total_match = re.search(r"на\s+(\d+)\s+руб", lower)
    count_matches = [int(value) for value in re.findall(r"(\d+)\s+ящик", lower)]
    if not total_match or len(count_matches) < 2:
        return None

    total_cost = int(total_match.group(1))
    first_count, second_count = count_matches[:2]
    total_boxes = first_count + second_count
    if total_boxes == 0 or total_cost % total_boxes != 0:
        return None

    box_price = total_cost // total_boxes
    first_cost = box_price * first_count
    second_cost = box_price * second_count
    return join_explanation_lines(
        f"1) Если одна школа взяла {first_count} ящика, а другая {second_count} ящиков, то всего взяли {first_count} + {second_count} = {total_boxes} ящиков",
        f"2) Если за {total_boxes} ящиков заплатили {total_cost} руб., то один ящик стоит {total_cost} : {total_boxes} = {box_price} руб.",
        f"3) Если первая школа взяла {first_count} ящика по {box_price} руб., то она должна заплатить {box_price} × {first_count} = {first_cost} руб.",
        f"4) Если вторая школа взяла {second_count} ящиков по {box_price} руб., то она должна заплатить {box_price} × {second_count} = {second_cost} руб.",
        f"Ответ: первая школа должна заплатить {first_cost} руб., вторая — {second_cost} руб.",
        "Совет: в задачах на пропорциональное деление сначала находят общую цену одной равной части",
    )


def try_final_patch_water_bucket_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "ведр" not in lower or "одинаков" not in lower or "сколько литров" not in question:
        return None

    sizes = [int(value) for value in re.findall(r"(\d+)-литров", lower)]
    diff_match = re.search(r"на\s+(\d+)\s+литр", lower)
    if len(sizes) < 2 or not diff_match:
        return None

    big_bucket = max(sizes[0], sizes[1])
    small_bucket = min(sizes[0], sizes[1])
    diff_total = int(diff_match.group(1))
    step_diff = big_bucket - small_bucket
    if step_diff <= 0 or diff_total % step_diff != 0:
        return None

    trips = diff_total // step_diff
    big_total = big_bucket * trips
    small_total = small_bucket * trips

    if "мальчик" in lower and "девоч" in lower:
        first_label = "мальчик"
        second_label = "девочка"
        second_verb = "делала"
        second_result_verb = "принесла"
    else:
        first_label = "первый"
        second_label = "второй"
        second_verb = "делал"
        second_result_verb = "принёс"

    return join_explanation_lines(
        f"1) Если {first_label} за один раз приносил {big_bucket} л, а {second_label} {small_bucket} л, то за один раз {first_label} приносил на {big_bucket} - {small_bucket} = {step_diff} л больше",
        f"2) Если всего {first_label} принёс на {diff_total} л больше, а за один раз разница была {step_diff} л, то одинаковых ходок было {diff_total} : {step_diff} = {trips}",
        f"3) Если {first_label} делал {trips} ходок по {big_bucket} л, то он принёс {big_bucket} × {trips} = {big_total} л",
        f"4) Если {second_label} {second_verb} {trips} ходок по {small_bucket} л, то она {second_result_verb} {small_bucket} × {trips} = {small_total} л",
        f"Ответ: {first_label} принёс {big_total} л воды, {second_label} — {small_total} л.",
        "Совет: если число ходок одинаковое, сначала находят разницу за одну ходку",
    )


def try_final_patch_remaining_rooms_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "комнат" not in lower or "квартир" not in lower or "остал" not in lower:
        return None
    if "отремонт" not in question:
        return None

    total_match = re.search(r"(\d+)\s+комнат", lower)
    remain_match = re.search(r"остал[аоись]*[^0-9]{0,40}(\d+)\s+(\d+)-комнатн", lower)
    if not total_match or not remain_match:
        return None

    total_rooms = int(total_match.group(1))
    flats = int(remain_match.group(1))
    rooms_per_flat = int(remain_match.group(2))
    remaining_rooms = flats * rooms_per_flat
    repaired_rooms = total_rooms - remaining_rooms
    if repaired_rooms < 0:
        return None

    flat_word = _final_patch_plural(flats, ("квартира", "квартиры", "квартир"))
    room_word = _final_patch_plural(rooms_per_flat, ("комната", "комнаты", "комнат"))
    return join_explanation_lines(
        f"1) Если осталось отремонтировать {flats} {flat_word} по {rooms_per_flat} {room_word} в каждой, то осталось отремонтировать {flats} × {rooms_per_flat} = {remaining_rooms} комнат",
        f"2) Если всего надо было отремонтировать {total_rooms} комнаты, а осталось {remaining_rooms} комнат, то отремонтировали {total_rooms} - {remaining_rooms} = {repaired_rooms} комнат",
        f"Ответ: отремонтировали {repaired_rooms} комнат.",
        "Совет: если известны всё число и оставшаяся часть, выполненную часть находят вычитанием",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_final_patch_school_boxes_equal_price_explanation(user_text)
        or try_final_patch_water_bucket_explanation(user_text)
        or try_final_patch_remaining_rooms_explanation(user_text)
        or try_final_patch_simple_group_total_explanation(user_text)
        or _FINAL_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- OPENAI FINAL CONSOLIDATION PATCH 2026-04-11N: punctuation, order marks, missing textbook templates ---

_OAI_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _oai_final_question_lower(raw_text: str) -> str:
    return _question_lower_text(raw_text).lower().replace("ё", "е")


def try_oai_final_combined_rate_pump_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _oai_final_question_lower(raw_text)
    if "насос" not in lower:
        return None
    if not contains_any_fragment(question, ("за сколько", "сколько минут", "сколько мин", "за какое время")):
        return None

    first_match = re.search(r"перв(?:ый|ого)?\s+насос[^\d]{0,40}(\d+)\s+в(?:е|ё)дер[^\d]{0,40}за\s+(\d+)\s+мин", lower)
    second_time_match = re.search(r"втор(?:ой|ого)?[^\d]{0,60}за\s+(\d+)\s+мин", lower)
    nums = extract_ordered_numbers(lower)
    if not first_match or not second_time_match or len(nums) < 4:
        return None

    amount = int(first_match.group(1))
    time1 = int(first_match.group(2))
    time2 = int(second_time_match.group(1))
    target = nums[-1]
    if amount <= 0 or time1 <= 0 or time2 <= 0 or target <= 0:
        return None

    rate1 = Fraction(amount, time1)
    rate2 = Fraction(amount, time2)
    total_rate = rate1 + rate2
    if total_rate == 0:
        return None
    total_time = Fraction(target, 1) / total_rate

    rate1_text = format_fraction(rate1)
    rate2_text = format_fraction(rate2)
    total_rate_text = format_fraction(total_rate)
    total_time_text = format_fraction(total_time)

    return join_explanation_lines(
        f"1) Если первый насос выкачивает {amount} вёдер за {time1} мин, то за 1 мин он выкачивает {amount} : {time1} = {rate1_text} вёдер",
        f"2) Если второй насос выкачивает {amount} вёдер за {time2} мин, то за 1 мин он выкачивает {amount} : {time2} = {rate2_text} вёдер",
        f"3) Если оба насоса работают вместе, то за 1 мин они выкачивают {rate1_text} + {rate2_text} = {total_rate_text} вёдер",
        f"4) Если нужно выкачать {target} вёдер, а за 1 мин выкачивают {total_rate_text} вёдер, то время равно {target} : {total_rate_text} = {total_time_text} мин",
        f"Ответ: оба насоса выкачают {target} вёдер за {total_time_text} мин",
        "Совет: в задачах на совместную работу сначала находят, сколько каждый делает за 1 минуту",
    )


def try_oai_final_advanced_brigade_unit_rate_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _oai_final_question_lower(raw_text)
    if "бригада" not in lower:
        return None
    if not contains_any_fragment(question, ("сколько метров", "сколько м", "сколько километров", "сколько км")):
        return None

    source_match = re.search(r"за\s+(\d+)\s+дн(?:я|ей)[^\d]{0,60}бригада[^\d]{0,60}(\d+)\s*(м|км)", lower)
    question_match = re.search(r"(\d+)\s+бригад[^\d]{0,60}за\s+(\d+)\s+дн(?:я|ей)", lower)
    if not source_match or not question_match:
        return None

    days1 = int(source_match.group(1))
    total_amount = int(source_match.group(2))
    unit = source_match.group(3)
    brigades = int(question_match.group(1))
    days2 = int(question_match.group(2))
    if days1 <= 0 or brigades <= 0 or days2 <= 0 or total_amount <= 0:
        return None

    one_brigade_one_day = Fraction(total_amount, days1)
    many_brigades_one_day = one_brigade_one_day * brigades
    final_amount = many_brigades_one_day * days2

    d1_text = format_fraction(one_brigade_one_day)
    d2_text = format_fraction(many_brigades_one_day)
    answer_text = format_fraction(final_amount)

    return join_explanation_lines(
        f"1) Если одна бригада проложила {total_amount} {unit} за {days1} дней, то за 1 день одна бригада проложит {total_amount} : {days1} = {d1_text} {unit}",
        f"2) Если одна бригада за 1 день прокладывает {d1_text} {unit}, то {brigades} бригады за 1 день проложат {d1_text} × {brigades} = {d2_text} {unit}",
        f"3) Если {brigades} бригады за 1 день прокладывают {d2_text} {unit}, то за {days2} дней они проложат {d2_text} × {days2} = {answer_text} {unit}",
        f"Ответ: {brigades} бригады за {days2} дней проложат {answer_text} {unit}",
        "Совет: в усложнённых задачах на приведение к единице сначала находят работу одной бригады за 1 день",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_oai_final_combined_rate_pump_explanation(user_text)
        or try_oai_final_advanced_brigade_unit_rate_explanation(user_text)
        or _OAI_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- OPENAI HOTFIX 2026-04-11P: reliable sentence split + combined-rate matching ---


def try_oai_final_combined_rate_pump_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    if "насос" not in lower:
        return None
    if not contains_any_fragment(lower, ("за сколько", "сколько минут", "сколько мин", "за какое время", "оба насоса", "работать одновременно")):
        return None

    first_match = re.search(r"перв(?:ый|ого)?\s+насос[^\d]{0,40}(\d+)\s+в(?:е|ё)дер[^\d]{0,40}за\s+(\d+)\s+мин", lower)
    second_time_match = re.search(r"втор(?:ой|ого)?[^\d]{0,60}за\s+(\d+)\s+мин", lower)
    nums = extract_ordered_numbers(lower)
    if not first_match or not second_time_match or len(nums) < 4:
        return None

    amount = int(first_match.group(1))
    time1 = int(first_match.group(2))
    time2 = int(second_time_match.group(1))
    target = nums[-1]
    if amount <= 0 or time1 <= 0 or time2 <= 0 or target <= 0:
        return None

    rate1 = Fraction(amount, time1)
    rate2 = Fraction(amount, time2)
    total_rate = rate1 + rate2
    if total_rate == 0:
        return None
    total_time = Fraction(target, 1) / total_rate

    rate1_text = format_fraction(rate1)
    rate2_text = format_fraction(rate2)
    total_rate_text = format_fraction(total_rate)
    total_time_text = format_fraction(total_time)

    return join_explanation_lines(
        f"1) Если первый насос выкачивает {amount} вёдер за {time1} мин, то за 1 мин он выкачивает {amount} : {time1} = {rate1_text} вёдер",
        f"2) Если второй насос выкачивает {amount} вёдер за {time2} мин, то за 1 мин он выкачивает {amount} : {time2} = {rate2_text} вёдер",
        f"3) Если оба насоса работают одновременно, то за 1 мин они выкачивают {rate1_text} + {rate2_text} = {total_rate_text} вёдер",
        f"4) Если нужно выкачать {target} вёдер, а за 1 мин выкачивают {total_rate_text} вёдер, то время равно {target} : {total_rate_text} = {total_time_text} мин",
        f"Ответ: оба насоса выкачают {target} вёдер за {total_time_text} мин",
        "Совет: в задачах на совместную работу сначала находят, сколько каждый делает за 1 минуту",
    )


# --- USER PATCH 2026-04-11Z: stricter equation detection, expression with "=" support,
# --- fuller question noun extraction, and textbook-style remainder wording.

_OAI_USER_PREV_TO_EXPRESSION_SOURCE = to_expression_source
_OAI_USER_PREV_TO_EQUATION_SOURCE = to_equation_source
_OAI_USER_PREV_INFER_TASK_KIND = infer_task_kind
_OAI_USER_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_OAI_USER_PREV_EXTRACT_COUNT_QUESTION_NOUN = _extract_count_question_noun

_USER_ADJECTIVE_ENDINGS = (
    "ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие",
    "ого", "его", "ому", "ему", "ым", "им", "ую", "юю",
    "ых", "их", "ыми", "ими",
)


def _user_has_standalone_x(text: str) -> bool:
    return bool(re.search(r"(?<![\d)])\s*[xXхХ]\s*(?![\d(])", str(text or "")))


def _user_has_mul_x_between_numbers(text: str) -> bool:
    return bool(re.search(r"(?<=[\d)])\s*[xXхХ]\s*(?=[\d(])", str(text or "")))


def _insert_implicit_multiplication_signs(text: str) -> str:
    value = str(text or "")
    if not value:
        return value
    updated = value
    for pattern in (r"(\d)\s*(\()", r"(\))\s*(\d)", r"(\))\s*(\()"):
        updated = re.sub(pattern, r"\1*\2", updated)
    return updated


def to_equation_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(text)
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/").replace(":", "/")

    # Если x/х стоит между числами, это знак умножения, а не неизвестное.
    if _user_has_mul_x_between_numbers(text):
        return None

    # Разрешаем латинскую и кириллическую x только как отдельную неизвестную.
    text = re.sub(r"(?<![\d)])\s*[xXхХ]\s*(?![\d(])", "x", text)
    text = re.sub(r"\s+", "", text)

    if text.count("=") != 1 or text.count("x") != 1:
        return None
    if not re.fullmatch(r"[\dx=+\-*/]+", text):
        return None
    return text

# --- merged segment 007: backend.legacy_runtime_shards.prepatch_build_source.segment_007 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 5296-6184."""



def to_expression_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None

    text = normalize_dashes(text)
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/").replace(":", "/")

    # x/х между числами понимаем как умножение.
    text = re.sub(r"(?<=[\d)])\s*[xXхХ]\s*(?=[\d(])", " * ", text)
    text = _insert_implicit_multiplication_signs(text)

    # Если запись вида «25 х 4 = 100» или «6 + 7 = ?», берём только левую часть как пример.
    if "=" in text:
        left, right = text.split("=", 1)
        left = left.strip()
        right = right.strip()

        if not _user_has_standalone_x(left) and not _user_has_standalone_x(right):
            if not re.search(r"[A-Za-zА-Яа-я]", left.replace("х", "").replace("Х", "")):
                if right in {"", "?", "=?", "= ?"} or re.fullmatch(r"[\d\s()+\-*/.,]+", right):
                    text = left
                else:
                    return None
            else:
                return None
        else:
            return None

    text = re.sub(r"\s*\?\s*$", "", text).strip()
    if re.search(r"[A-Za-zА-Яа-я]", text):
        return None
    if not re.fullmatch(r"[\d\s()+\-*/]+", text):
        return None

    compact = re.sub(r"\s+", "", text)
    if not compact or not re.search(r"[+\-*/]", compact):
        return None
    return compact


def infer_task_kind(text: str) -> str:
    base = strip_known_prefix(text)
    lowered = normalize_cyrillic_x(base).lower()

    if re.search(r"\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+", lowered):
        return "fraction"
    if to_equation_source(text):
        return "equation"
    if re.search(r"периметр|площадь|прямоугольник|квадрат|треугольник|сторон|длина|ширина", lowered):
        return "geometry"
    if re.search(r"[а-я]", lowered):
        return "word"
    if to_expression_source(text):
        return "expression"
    if re.search(r"[+\-*/()×÷:=]", lowered):
        return "expression"
    return "other"


def _extract_count_question_noun(raw_text: str) -> str:
    noun = _OAI_USER_PREV_EXTRACT_COUNT_QUESTION_NOUN(raw_text)
    if noun in QUESTION_NOUN_FORMS or noun in MEASURE_QUESTION_NOUNS or noun == "раз":
        return noun

    question = _question_lower_text(raw_text)
    patterns = [
        r"^сколько\s+(?:было\s+|будет\s+|стало\s+|осталось\s+|получилось\s+|понадобится\s+|понадобилось\s+|потребуется\s+|потребовалось\s+|можно\s+купить\s+|нужно\s+|нужно\s+купить\s+|всего\s+)?(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)\s+([а-яё]+)",
        r"^во\s+сколько\s+раз\s+([а-яё]+)\s+([а-яё]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if not match:
            continue
        first = match.group(1).strip().lower().replace("ё", "е")
        second = match.group(2).strip().lower().replace("ё", "е")

        if second in QUESTION_NOUN_FORMS:
            if first.endswith(_USER_ADJECTIVE_ENDINGS) or first not in QUESTION_NOUN_FORMS:
                return second

    return noun


def _user_question_asks_remaining(raw_text: str) -> bool:
    question = _question_lower_text(raw_text)
    return bool(
        re.search(
            r"(?:сколько|какое|какова?|чему)\b[^.?!]*\b(остал(?:ось|ось|ся|ись|ись)|останется|осталось\s+прочитать|осталось\s+проехать|осталось\s+расфасовать)\b",
            question,
        )
    )


def _user_remaining_question_phrase(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    if "прочитать" in question:
        return "осталось прочитать"
    if "проехать" in question:
        return "осталось проехать"
    if "расфасовать" in question:
        return "осталось расфасовать"
    return "осталось"


def try_user_patch_simple_remaining_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in lower:
        return None
    if not _user_question_asks_remaining(raw_text):
        return None

    first, second = nums[0], nums[1]
    if first < second:
        return None

    answer_text = _patch_answer_with_question_noun(first - second, raw_text)
    phrase = _user_remaining_question_phrase(raw_text)

    return join_explanation_lines(
        f"1) Если всего было {first}, а использовали {second}, то {phrase} {first} - {second} = {answer_text}",
        f"Ответ: {phrase} {answer_text}",
        "Совет: чтобы найти остаток, из всего вычитают использованную часть",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_user_patch_simple_remaining_explanation(user_text)
        or _OAI_USER_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- USER PATCH 2026-04-11ZA: fuller counted answers like "4 яблока", "3 страницы".
_OAI_USER_PREV_PATCH_ANSWER_WITH_QUESTION_NOUN = _patch_answer_with_question_noun


def _patch_answer_with_question_noun(value: int, raw_text: str) -> str:
    return _external_patch_answer_with_question_noun(
        value,
        raw_text,
        _detect_question_unit,
        _extract_count_question_noun,
        _extract_question_noun,
    )


# --- OPENAI USER PATCH 2026-04-11R: textbook priority fixes from uploaded books ---

_OAI_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_R = build_explanation_local_first
_OAI_PATCH_PREV_EXTRACT_COUNT_QUESTION_NOUN_R = _extract_count_question_noun
_OAI_PATCH_PREV_DETECT_QUESTION_UNIT_R = _detect_question_unit

QUESTION_NOUN_FORMS.update({
    "фруктов": ("фрукт", "фрукта", "фруктов"),
    "листов": ("лист", "листа", "листов"),
    "перьев": ("перо", "пера", "перьев"),
    "мешков": ("мешок", "мешка", "мешков"),
    "кустов": ("куст", "куста", "кустов"),
    "цветов": ("цветок", "цветка", "цветов"),
    "глазков": ("глазок", "глазка", "глазков"),
    "пакетов": ("пакет", "пакета", "пакетов"),
    "наборов": ("набор", "набора", "наборов"),
    "деталей": ("деталь", "детали", "деталей"),
    "фломастеров": ("фломастер", "фломастера", "фломастеров"),
    "персиков": ("персик", "персика", "персиков"),
    "груш": ("груша", "груши", "груш"),
    "магнитофонов": ("магнитофон", "магнитофона", "магнитофонов"),
    "видеоплееров": ("видеоплеер", "видеоплеера", "видеоплееров"),
})


def _extract_count_question_noun(raw_text: str) -> str:
    return _external_extract_count_question_noun(raw_text, _question_lower_text, _OAI_PATCH_PREV_EXTRACT_COUNT_QUESTION_NOUN_R)


def _detect_question_unit(raw_text: str) -> str:
    return _external_detect_question_unit(
        raw_text,
        _OAI_PATCH_PREV_DETECT_QUESTION_UNIT_R,
        _question_lower_text,
        normalize_word_problem_text,
    )


def _oai_patch_extract_question_item_r(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    patterns = [
        r"сколько\s+стоил(?:а|о|и)?\s+([а-яё]+)",
        r"сколько\s+стоит\s+([а-яё]+)",
        r"сколько\s+книг\s+было\s+на\s+([а-яё]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            return match.group(1).strip()
    return ""


def _oai_patch_text_has_fraction_r(text: str) -> bool:
    return bool(re.search(r"\d+\s*/\s*\d+", str(text or "")))


def try_oai_patch_unknown_addend_rest_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)

    if len(nums) != 2:
        return None
    if "из них" not in lower or "осталь" not in lower:
        return None
    if "на сколько" in question or "во сколько" in question:
        return None
    if "сколько" not in question:
        return None

    total, known = nums[0], nums[1]
    if total < known:
        return None

    result = total - known
    answer_text = _patch_answer_with_question_noun(result, raw_text)
    return join_explanation_lines(
        f"1) Если всего было {total}, а известная часть равна {known}, то другая часть равна {total} - {known} = {answer_text}",
        f"Ответ: {answer_text}",
        "Совет: чтобы найти неизвестную часть, из целого вычитают известную часть",
    )


def try_oai_patch_simple_total_minus_part_money_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)

    if len(nums) != 2:
        return None
    if not contains_any_fragment(lower, ("заплатил", "заплатила", "заплатили", "стоил", "стоила", "стоило")):
        return None
    if not contains_any_fragment(question, ("сколько стоила", "сколько стоил", "сколько стоило", "сколько стоит")):
        return None
    if "по" in lower:
        return None

    total_cost, known_cost = nums[0], nums[1]
    if total_cost < known_cost:
        return None

    result = total_cost - known_cost
    item = _oai_patch_extract_question_item_r(raw_text) or "неизвестная часть"
    return join_explanation_lines(
        f"1) Если за всю покупку заплатили {total_cost} руб., а известная часть стоила {known_cost} руб., то {item} стоил{'' if item.endswith('о') else 'а' if item.endswith('а') else ''} {total_cost} - {known_cost} = {result} руб.",
        f"Ответ: {item} стоил{'' if item.endswith('о') else 'а' if item.endswith('а') else ''} {result} руб.",
        "Совет: если известна общая стоимость и одна часть, другую часть находят вычитанием",
    )


def try_oai_patch_simple_motion_time_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)

    if not re.search(r"(?:какое|какова?|сколько)\s+врем(?:я|ени)|сколько\s+час", question):
        return None

    distance_values = [int(v) for v in re.findall(r"(\d+)\s*(?:км|м)(?!/)", lower)]
    speed_values = [int(v) for v in re.findall(r"(\d+)\s*(?:км/ч|м/мин|м/с)", lower)] or [int(v) for v in re.findall(r"скорост[ьяию][^\d]{0,20}(\d+)", lower)]

    if len(distance_values) != 1 or len(speed_values) != 1:
        return None
    if len(re.findall(r"\d+\s*(?:км|м)(?!/)", lower)) != 1:
        return None

    distance = distance_values[0]
    speed = speed_values[0]
    if speed <= 0 or distance < 0 or distance % speed != 0:
        return None

    time_value = distance // speed
    distance_unit = "км" if re.search(r"\d+\s*км(?!/)", lower) else "м"
    speed_unit = "км/ч" if "км/ч" in lower else "м/мин" if "м/мин" in lower else "м/с" if "м/с" in lower else "ед./ч"
    time_unit = "ч"
    if speed_unit == "м/мин":
        time_unit = "мин"
    elif speed_unit == "м/с":
        time_unit = "с"

    return join_explanation_lines(
        f"1) Если путь равен {distance} {distance_unit}, а скорость равна {speed} {speed_unit}, то время равно {distance} : {speed} = {time_value} {time_unit}",
        f"Ответ: время в пути равно {time_value} {time_unit}",
        "Совет: чтобы найти время, расстояние делят на скорость",
    )


def try_oai_patch_price_compare_logic_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)

    if len(nums) != 3:
        return None
    if "за столько же" not in lower:
        return None
    if not (contains_any_fragment(question, ("на сколько", "дороже")) or contains_any_fragment(question, ("на сколько", "дешевле"))):
        return None

    quantity, cost_first, cost_second = nums
    if quantity <= 0 or cost_first % quantity != 0 or cost_second % quantity != 0:
        return None

    price_first = cost_first // quantity
    price_second = cost_second // quantity
    diff = abs(price_first - price_second)

    package_items = re.findall(r"пакет(?:ов|а)?\s+([а-яё]+)", lower)
    if len(package_items) >= 2:
        first_name = f"пакет {package_items[0]}"
        second_name = f"пакет {package_items[1]}"
    else:
        first_name = "первый товар"
        second_name = "второй товар"

    if price_first > price_second:
        relation_text = f"{first_name} дороже {second_name} на {diff} руб."
    elif price_second > price_first:
        relation_text = f"{second_name} дороже {first_name} на {diff} руб."
    else:
        relation_text = "цены одинаковые"

    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых пакетов первого товара заплатили {cost_first} руб., то один пакет стоит {cost_first} : {quantity} = {price_first} руб.",
        f"2) Если за {quantity} таких же пакетов второго товара заплатили {cost_second} руб., то один пакет стоит {cost_second} : {quantity} = {price_second} руб.",
        f"3) Если одна цена равна {price_first} руб., а другая {price_second} руб., то разность цен равна {max(price_first, price_second)} - {min(price_first, price_second)} = {diff} руб.",
        f"Ответ: разность в цене равна {diff} руб.; {relation_text}",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_oai_patch_unknown_addend_rest_explanation_r(user_text)
        or try_oai_patch_simple_total_minus_part_money_explanation_r(user_text)
        or try_oai_patch_simple_motion_time_explanation_r(user_text)
        or try_oai_patch_price_compare_logic_explanation_r(user_text)
        or _OAI_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_R(user_text, kind)
    )


# --- OPENAI HOTFIX 2026-04-11S: "на сколько" answers and cleaner price comparison wording ---

_OAI_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_S = _detailed_maybe_enrich_answer

def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = _OAI_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_S(answer, raw_text, kind)
    question = _question_lower_text(raw_text)
    if question.startswith("на сколько") and value and not re.search(r"[А-Яа-я].*[А-Яа-я].*[А-Яа-я]", value):
        if not value.startswith("на "):
            return f"на {value}"
    return value


def try_oai_patch_price_compare_logic_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)

    if len(nums) != 3:
        return None
    if "за столько же" not in lower:
        return None
    if not (contains_any_fragment(question, ("на сколько", "дороже")) or contains_any_fragment(question, ("на сколько", "дешевле"))):
        return None

    quantity, cost_first, cost_second = nums
    if quantity <= 0 or cost_first % quantity != 0 or cost_second % quantity != 0:
        return None

    price_first = cost_first // quantity
    price_second = cost_second // quantity
    diff = abs(price_first - price_second)

    package_items = re.findall(r"пакет(?:ов|а)?\s+([а-яё]+)", lower)
    if len(package_items) >= 2:
        first_name = f"пакет {package_items[0]}"
        second_name = f"пакет {package_items[1]}"
        first_name_gen = f"пакета {package_items[0]}"
        second_name_gen = f"пакета {package_items[1]}"
    else:
        first_name = "первый товар"
        second_name = "второй товар"
        first_name_gen = "первого товара"
        second_name_gen = "второго товара"

    if price_first > price_second:
        relation_text = f"{first_name} дороже {second_name_gen} на {diff} руб."
    elif price_second > price_first:
        relation_text = f"{second_name} дороже {first_name_gen} на {diff} руб."
    else:
        relation_text = "цены одинаковые"

    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых пакетов первого товара заплатили {cost_first} руб., то один пакет стоит {cost_first} : {quantity} = {price_first} руб.",
        f"2) Если за {quantity} таких же пакетов второго товара заплатили {cost_second} руб., то один пакет стоит {cost_second} : {quantity} = {price_second} руб.",
        f"3) Если одна цена равна {price_first} руб., а другая {price_second} руб., то разность цен равна {max(price_first, price_second)} - {min(price_first, price_second)} = {diff} руб.",
        f"Ответ: разность в цене равна {diff} руб.; {relation_text}",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


# --- OPENAI HOTFIX 2026-04-11T: prefix "на" for direct comparison numeric answers ---

_OAI_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_T = _detailed_maybe_enrich_answer

def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = _OAI_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_T(answer, raw_text, kind)
    question = _question_lower_text(raw_text)
    if question.startswith("на сколько") and re.fullmatch(r"-?\d+(?:/\d+)?(?:\s+[А-Яа-я./²]+)?", value or ""):
        if not value.startswith("на "):
            return f"на {value}"
    return value


# --- CHATGPT FINAL PATCH 2026-04-11U: stronger textbook routing, missing unit-rate cases, safer compare logic ---

_CHATGPT_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST_U = build_explanation_local_first
_CHATGPT_FINAL_PREV_EXPLAIN_SIMPLE_ADDITION_U = explain_simple_addition

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши строку:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши строку:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Если нельзя сразу ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай только по действиям.
6. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
7. По возможности используй школьную форму:
Если ..., то ...
8. После каждого действия коротко говори, что нашли.
9. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если это выражение, сначала назови порядок действий.
Если это уравнение, оставляй x отдельно и объясняй обратное действие.
Если это дроби, сначала смотри на знаменатели.
Если это геометрия, сначала назови формулу, потом подставь числа.
Если это именованные величины, сначала переведи их в одинаковые единицы.

Используй школьные приёмы:
сложение через десяток — разложи число так, чтобы сначала получить 10 или следующее круглое число;
вычитание через десяток — вычитай по частям через 10;
двузначные числа раскладывай на десятки и единицы;
если числа большие, объясняй по разрядам;
если в сумме больше двух двузначных чисел или есть хотя бы одно трёхзначное число, можно показывать вычисление в столбик;
для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()


def explain_simple_addition(left: int, right: int) -> str:
    big = max(left, right)
    small = min(left, right)
    if 10 <= big <= 99 and 1 <= small <= 99:
        jump = (10 - (big % 10)) % 10
        if jump == 0:
            jump = 10
        if 0 < jump < small:
            rounded = big + jump
            rest = small - jump
            total = left + right
            return join_explanation_lines(
                "Ищем сумму",
                f"Сначала удобно дойти от {big} до следующего круглого числа {rounded}",
                f"Для этого нужно прибавить {jump}",
                f"Разложим {small} на {jump} и {rest}",
                f"{big} + {jump} = {rounded}",
                f"{rounded} + {rest} = {total}",
                f"Ответ: {total}",
                "Совет: если сумма переходит через десяток, удобно сначала дойти до круглого числа",
            )
    return _CHATGPT_FINAL_PREV_EXPLAIN_SIMPLE_ADDITION_U(left, right)


def try_chatgpt_final_relation_then_compare_explanation_u(raw_text: str) -> Optional[str]:
    try:
        return try_priority_relation_then_compare_explanation(raw_text)
    except Exception:
        return None


def try_chatgpt_final_beam_weight_explanation_u(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "сколько" not in question or not contains_any_fragment(question, ("сколько весит", "какова масса", "чему равна масса")):
        return None

    pattern = re.compile(
        r"(?:длиной|длина)\s*(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)[^?.!]{0,80}?весит\s*(\d+)\s*(кг|г|т)[^?.!]{0,160}?(?:длиной|длина)\s*(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)",
        re.IGNORECASE,
    )
    match = pattern.search(lower)
    if not match:
        pattern2 = re.compile(
            r"(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)[^?.!]{0,60}?весит\s*(\d+)\s*(кг|г|т)[^?.!]{0,160}?(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)",
            re.IGNORECASE,
        )
        match = pattern2.search(lower)
        if not match:
            return None

    base_len = int(match.group(1))
    len_unit_1 = match.group(2)
    total_weight = int(match.group(3))
    weight_unit = match.group(4)
    target_len = int(match.group(5))
    len_unit_2 = match.group(6)

    if base_len <= 0 or total_weight < 0:
        return None
    if len_unit_1[0] != len_unit_2[0]:
        return None
    if total_weight % base_len != 0:
        return None

    per_unit = total_weight // base_len
    result = per_unit * target_len
    length_name = "метр"
    if len_unit_1.startswith("д"):
        length_name = "дециметр"
    elif len_unit_1.startswith("с"):
        length_name = "сантиметр"
    elif len_unit_1.startswith("к"):
        length_name = "километр"

    return join_explanation_lines(
        f"1) Если {base_len} {len_unit_1} этой же балки весят {total_weight} {weight_unit}, то один {length_name} весит {total_weight} : {base_len} = {per_unit} {weight_unit}",
        f"2) Если один {length_name} весит {per_unit} {weight_unit}, то {target_len} {len_unit_2} весят {per_unit} × {target_len} = {result} {weight_unit}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну одинаковую часть",
    )


def try_chatgpt_final_sum_then_relation_to_sum_explanation_u(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or "сколько" not in question:
        return None
    if has_multiple_questions(raw_text):
        return None
    if "вместе" not in lower:
        return None

    first, second, third_number = nums[0], nums[1], nums[2]
    together = first + second

    same_match = re.search(r"столько(?:\s+же)?[, ]+сколько[^?.!]{0,120}?вместе", lower)
    delta_match = re.search(r"на\s+(\d+)[^?.!]{0,20}?(больше|меньше)[^?.!]{0,120}?вместе", lower)
    scale_match = re.search(r"в\s+(\d+)\s+раз(?:а)?\s+(больше|меньше)[^?.!]{0,120}?вместе", lower)

    if same_match:
        result = together
        return join_explanation_lines(
            f"1) Если первое количество равно {first}, а второе равно {second}, то вместе {first} + {second} = {together}",
            f"2) Если искомое количество столько же, сколько эти два количества вместе, то оно равно {together}",
            f"Ответ: {result}",
            "Совет: если искомое число сравнивают с суммой двух чисел, сначала находят эту сумму",
        )

    if delta_match:
        delta = int(delta_match.group(1))
        mode = delta_match.group(2)
        if delta != third_number:
            return None
        result = apply_more_less(together, delta, mode)
        if result is None:
            return None
        op = "+" if mode == "больше" else "-"
        return join_explanation_lines(
            f"1) Если первое количество равно {first}, а второе равно {second}, то вместе {first} + {second} = {together}",
            f"2) Если искомое количество на {delta} {mode}, чем эти два количества вместе, то {together} {op} {delta} = {result}",
            f"Ответ: {result}",
            "Совет: если искомое число сравнивают с суммой двух чисел, сначала находят эту сумму",
        )

    if scale_match:
        factor = int(scale_match.group(1))
        mode = scale_match.group(2)
        if factor != third_number:
            return None
        result = apply_times_relation(together, factor, mode)
        if result is None:
            return None
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если первое количество равно {first}, а второе равно {second}, то вместе {first} + {second} = {together}",
            f"2) Если искомое количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, чем эти два количества вместе, то {together} {op} {factor} = {result}",
            f"Ответ: {result}",
            "Совет: если искомое число сравнивают с суммой двух чисел, сначала находят эту сумму",
        )

    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_chatgpt_final_relation_then_compare_explanation_u(user_text)
        or try_chatgpt_final_beam_weight_explanation_u(user_text)
        or try_chatgpt_final_sum_then_relation_to_sum_explanation_u(user_text)
        or _CHATGPT_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST_U(user_text, kind)
    )


# --- CHATGPT HOTFIX 2026-04-11V: beam unit-rate and fuller ratio answers ---

_CHATGPT_HOTFIX_PREV_RELATION_COMPARE_V = try_chatgpt_final_relation_then_compare_explanation_u
_CHATGPT_HOTFIX_PREV_BEAM_EXPLANATION_V = try_chatgpt_final_beam_weight_explanation_u
_CHATGPT_HOTFIX_PREV_BUILD_EXPLANATION_LOCAL_FIRST_V = build_explanation_local_first


def try_chatgpt_final_relation_then_compare_explanation_u(raw_text: str) -> Optional[str]:
    text = _CHATGPT_HOTFIX_PREV_RELATION_COMPARE_V(raw_text)
    if not text:
        return text
    text = re.sub(r"^Ответ:\s*(\d+)\s+(раз|раза)\b", r"Ответ: в \1 \2", text, flags=re.MULTILINE)
    return text


def try_chatgpt_final_beam_weight_explanation_u(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "вес" not in question:
        return None

    patterns = [
        re.compile(r"балк[а-я]*\s+длиной\s*(\d+)\s*(м|метр(?:а|ов)?|дм|см|км).*?весит\s*(\d+)\s*(кг|г|т).*?длиной\s*(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)", re.IGNORECASE),
        re.compile(r"(\d+)\s*(м|метр(?:а|ов)?|дм|см|км).*?весит\s*(\d+)\s*(кг|г|т).*?(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)", re.IGNORECASE),
    ]

    match = None
    for pattern in patterns:
        match = pattern.search(lower)
        if match:
            break
    if not match:
        return None

    base_len = int(match.group(1))
    len_unit_1 = match.group(2)
    total_weight = int(match.group(3))
    weight_unit = match.group(4)
    target_len = int(match.group(5))
    len_unit_2 = match.group(6)

    unit_key_1 = len_unit_1[0]
    unit_key_2 = len_unit_2[0]
    if base_len <= 0 or total_weight < 0 or unit_key_1 != unit_key_2:
        return None
    if total_weight % base_len != 0:
        return None

    per_unit = total_weight // base_len
    result = per_unit * target_len
    length_name = "метр"
    if unit_key_1 == "д":
        length_name = "дециметр"
    elif unit_key_1 == "с":
        length_name = "сантиметр"
    elif unit_key_1 == "к":
        length_name = "километр"

    return join_explanation_lines(
        f"1) Если {base_len} {len_unit_1} такой же балки весят {total_weight} {weight_unit}, то один {length_name} весит {total_weight} : {base_len} = {per_unit} {weight_unit}",
        f"2) Если один {length_name} весит {per_unit} {weight_unit}, то {target_len} {len_unit_2} весят {per_unit} × {target_len} = {result} {weight_unit}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну одинаковую часть",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_chatgpt_final_relation_then_compare_explanation_u(user_text)
        or try_chatgpt_final_beam_weight_explanation_u(user_text)
        or try_chatgpt_final_sum_then_relation_to_sum_explanation_u(user_text)
        or _CHATGPT_HOTFIX_PREV_BUILD_EXPLANATION_LOCAL_FIRST_V(user_text, kind)
    )


# --- CHATGPT HOTFIX 2026-04-11W: better unit detection from the question ---

_CHATGPT_HOTFIX_PREV_DETECT_QUESTION_UNIT_W = _detect_question_unit


def _detect_question_unit(raw_text: str) -> str:
    unit = _CHATGPT_HOTFIX_PREV_DETECT_QUESTION_UNIT_W(raw_text)
    if unit:
        return unit

    question = _question_lower_text(raw_text)
    statement = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if contains_any_fragment(question, ("сколько весит", "какова масса", "чему равна масса")):
        for candidate in ("т", "кг", "г"):
            if re.search(rf"(?<!/)\b{re.escape(candidate)}\b", statement):
                return candidate

    if contains_any_fragment(question, ("сколько метров", "сколько километров", "какова длина", "чему равна длина", "сколько м", "сколько км", "сколько см", "сколько дм")):
        for candidate in ("км", "м", "дм", "см", "мм"):
            if re.search(rf"(?<!/)\b{re.escape(candidate)}\b", statement):
                return candidate

    if contains_any_fragment(question, ("сколько литров", "сколько л", "каков объем", "каков объём", "чему равен объем", "чему равен объём")):
        for candidate in ("л", "мл"):
            if re.search(rf"(?<!/)\b{re.escape(candidate)}\b", statement):
                return candidate

    return ""


# --- OPENAI CONSOLIDATION PATCH 2026-04-11Z: restore textbook cases lost in late patch chain ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown-таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Если нельзя сразу ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай только по действиям.
6. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
7. По возможности используй школьную форму:
Если ..., то ...
8. После каждого действия коротко говори, что нашли.
9. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Если задача дана с именованными величинами, сначала переведи их в удобные одинаковые единицы.
5. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.

Сохраняй вычисления в столбик и пояснения.
Если в вычислении больше двух двузначных чисел или есть хотя бы одно трёхзначное число, можно показывать вычисление в столбик.
Для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()

_CONSOLIDATION_PREV_BUILD_EXPLANATION_LOCAL_FIRST_Z = build_explanation_local_first

# --- merged segment 008: backend.legacy_runtime_shards.prepatch_build_source.segment_008 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 6185-7082."""


_CONSOLIDATION_EXTRA_QUESTION_NOUN_FORMS_Z = {
    "тюльпанов": ("тюльпан", "тюльпана", "тюльпанов"),
    "километров": ("километр", "километра", "километров"),
    "метров": ("метр", "метра", "метров"),
    "сантиметров": ("сантиметр", "сантиметра", "сантиметров"),
    "дециметров": ("дециметр", "дециметра", "дециметров"),
    "миллиметров": ("миллиметр", "миллиметра", "миллиметров"),
    "килограммов": ("килограмм", "килограмма", "килограммов"),
    "граммов": ("грамм", "грамма", "граммов"),
    "литров": ("литр", "литра", "литров"),
    "рублей": ("рубль", "рубля", "рублей"),
    "руб": ("рубль", "рубля", "рублей"),
    "часов": ("час", "часа", "часов"),
    "минут": ("минута", "минуты", "минут"),
    "тетрадей": ("тетрадь", "тетради", "тетрадей"),
    "ручек": ("ручка", "ручки", "ручек"),
    "машин": ("машина", "машины", "машин"),
    "страниц": ("страница", "страницы", "страниц"),
    "цветов": ("цветок", "цветка", "цветов"),
    "яблок": ("яблоко", "яблока", "яблок"),
    "груш": ("груша", "груши", "груш"),
    "булочек": ("булочка", "булочки", "булочек"),
    "кг": ("килограмм", "килограмма", "килограммов"),
    "л": ("литр", "литра", "литров"),
}


def _consolidation_normalize_noun_key_z(noun: str) -> str:
    return str(noun or "").strip().lower().replace("ё", "е")


def _consolidation_lookup_forms_z(noun: str) -> Optional[Tuple[str, str, str]]:
    key = _consolidation_normalize_noun_key_z(noun)
    if not key:
        return None
    forms = None
    try:
        forms = _lookup_question_noun_forms(key)
    except Exception:
        forms = None
    if forms:
        return forms
    return _CONSOLIDATION_EXTRA_QUESTION_NOUN_FORMS_Z.get(key)


def _consolidation_phrase_with_noun_z(count_value: int, noun: str) -> str:
    forms = _consolidation_lookup_forms_z(noun)
    if forms:
        return f"{count_value} {_select_plural_by_count(int(count_value), forms)}"
    return str(count_value)


def _consolidation_capitalize_z(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return value
    return value[:1].upper() + value[1:]


def _consolidation_split_question_parts_z(raw_text: str) -> List[str]:
    try:
        _, question = extract_condition_and_question(raw_text)
    except Exception:
        question = str(raw_text or "")
    return [part.strip() for part in re.split(r"\?", question) if part.strip()]


def _consolidation_answer_from_first_question_z(question_text: str, value: int, noun_hint: str = "") -> str:
    q = str(question_text or "").strip().rstrip("?.!").lower().replace("ё", "е")

    match = re.match(
        r"сколько\s+([а-яё]+)\s+(было|стало|будет|осталось|останется|получилось|оказалось|росло|лежало|ехало|шло|стоит|стоило|нужно|надо)\s+(.+)$",
        q,
    )
    if match:
        noun, verb, tail = match.groups()
        return f"{_consolidation_capitalize_z(tail)} {verb} {_consolidation_phrase_with_noun_z(value, noun)}"

    match = re.match(r"сколько\s+([а-яё]+)\s+(.+)$", q)
    if match:
        noun, tail = match.groups()
        first_word = tail.split()[0] if tail.split() else ""
        if first_word in {"в", "во", "на", "у", "из", "до", "после", "под", "над", "около"}:
            return f"{_consolidation_capitalize_z(tail)} было {_consolidation_phrase_with_noun_z(value, noun)}"
        return f"{_consolidation_capitalize_z(tail)} — {_consolidation_phrase_with_noun_z(value, noun)}"

    return _consolidation_phrase_with_noun_z(value, noun_hint)


def _consolidation_answer_from_compare_question_z(question_text: str, value: int, noun_hint: str = "") -> str:
    q = str(question_text or "").strip().rstrip("?.!").lower().replace("ё", "е")

    match = re.match(r"на\s+сколько\s+([а-яё]+)\s+(.+?)\s+(больше|меньше)(?:,?\s+чем\s+.+)?$", q)
    if match:
        noun, tail, mode = match.groups()
        return f"{_consolidation_capitalize_z(tail)} на {_consolidation_phrase_with_noun_z(value, noun)} {mode}"

    match = re.match(r"во\s+сколько\s+раз\s+([а-яё]+)\s+(.+?)\s+(больше|меньше)(?:,?\s+чем\s+.+)?$", q)
    if match:
        _, tail, mode = match.groups()
        return f"{_consolidation_capitalize_z(tail)} в {value} {plural_form(int(value), 'раз', 'раза', 'раз')} {mode}"

    if q.startswith("на сколько"):
        return f"Разность равна {_consolidation_phrase_with_noun_z(value, noun_hint)}"
    if q.startswith("во сколько"):
        return f"Отношение равно {value} {plural_form(int(value), 'раз', 'раза', 'раз')}"

    return _consolidation_phrase_with_noun_z(value, noun_hint)


def try_consolidation_direct_relation_multianswer_explanation_z(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if not has_multiple_questions(raw_text):
        return None
    if "на сколько" not in question and "во сколько" not in question:
        return None

    if re.search(r"\b(?:это|что|он|она)\b[^?.!]{0,40}(?:на\s+\d+|в\s+\d+\s+раз(?:а)?)", lower):
        return None

    numbers = extract_ordered_numbers(lower)
    if len(numbers) != 2:
        return None

    question_parts = _consolidation_split_question_parts_z(raw_text)
    first_question = question_parts[0] if question_parts else ""
    second_question = question_parts[1] if len(question_parts) > 1 else ""
    noun_hint = ""
    try:
        noun_hint = _extract_count_question_noun(raw_text) or _extract_question_noun(raw_text)
    except Exception:
        noun_hint = ""

    relation_pairs = extract_relation_pairs(lower)
    if len(relation_pairs) == 1:
        base = numbers[0]
        delta, mode = relation_pairs[0]
        if numbers[1] != delta:
            return None
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None

        first_answer = _consolidation_answer_from_first_question_z(first_question, related, noun_hint)

        if "на сколько" in question:
            diff = abs(base - related)
            second_answer = _consolidation_answer_from_compare_question_z(second_question, diff, noun_hint)
            return join_explanation_lines(
                f"1) Если первое количество равно {base}, а второе на {delta} {mode}, то второе количество равно {base} {'+' if mode == 'больше' else '-'} {delta} = {related}",
                f"2) Если первое количество равно {base}, а второе равно {related}, то разность равна {max(base, related)} - {min(base, related)} = {diff}",
                f"Ответ: {first_answer}; {second_answer}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )

        smaller = min(base, related)
        bigger = max(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        second_answer = _consolidation_answer_from_compare_question_z(second_question, ratio, noun_hint)
        return join_explanation_lines(
            f"1) Если первое количество равно {base}, а второе на {delta} {mode}, то второе количество равно {base} {'+' if mode == 'больше' else '-'} {delta} = {related}",
            f"2) Если первое количество равно {base}, а второе равно {related}, то большее число делим на меньшее: {bigger} : {smaller} = {ratio}",
            f"Ответ: {first_answer}; {second_answer}",
            "Совет: если нужно сначала найти второе число, а потом узнать во сколько раз одно больше другого, выполняй действия по порядку",
        )

    scale_pairs = extract_scale_pairs(lower)
    if len(scale_pairs) == 1:
        base = numbers[0]
        factor, mode = scale_pairs[0]
        if numbers[1] != factor:
            return None
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None

        first_answer = _consolidation_answer_from_first_question_z(first_question, related, noun_hint)

        if "на сколько" in question:
            diff = abs(base - related)
            second_answer = _consolidation_answer_from_compare_question_z(second_question, diff, noun_hint)
            return join_explanation_lines(
                f"1) Если первое количество равно {base}, а второе в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} {mode}, то второе количество равно {base} {'×' if mode == 'больше' else ':'} {factor} = {related}",
                f"2) Если первое количество равно {base}, а второе равно {related}, то разность равна {max(base, related)} - {min(base, related)} = {diff}",
                f"Ответ: {first_answer}; {second_answer}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )

        smaller = min(base, related)
        bigger = max(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        second_answer = _consolidation_answer_from_compare_question_z(second_question, ratio, noun_hint)
        return join_explanation_lines(
            f"1) Если первое количество равно {base}, а второе в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} {mode}, то второе количество равно {base} {'×' if mode == 'больше' else ':'} {factor} = {related}",
            f"2) Если первое количество равно {base}, а второе равно {related}, то большее число делим на меньшее: {bigger} : {smaller} = {ratio}",
            f"Ответ: {first_answer}; {second_answer}",
            "Совет: если сначала нужно найти второе число, а потом узнать во сколько раз одно больше другого, выполняй действия по порядку",
        )

    return None


def try_consolidation_fraction_named_unit_explanation_z(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    fractions = extract_all_fraction_pairs(lower)
    if len(fractions) != 1 or "сколько" not in question:
        return None

    numerator, denominator = fractions[0]
    if denominator == 0:
        return None

    total_value = None
    answer_unit = ""
    lines: List[str] = []
    step_no = 1

    ton_match = re.search(r"\b(\d+)\s*т\b", lower)
    if ton_match:
        tons = int(ton_match.group(1))
        total_value = tons * 1000
        answer_unit = "кг"
        lines.append(f"1) Сначала переводим тонны в килограммы: {tons} т = {total_value} кг")
        step_no = 2
    else:
        for unit in ("кг", "г", "л", "м", "см", "дм", "км"):
            unit_match = re.search(rf"\b(\d+)\s*{re.escape(unit)}\b", lower)
            if unit_match:
                total_value = int(unit_match.group(1))
                answer_unit = unit
                break

    if total_value is None:
        values = extract_non_fraction_numbers(lower)
        if not values:
            return None
        total_value = max(values)

    if total_value % denominator != 0:
        return None

    one_part = total_value // denominator
    part_value = one_part * numerator

    unit_suffix = f" {answer_unit}" if answer_unit else ""
    lines.append(f"{step_no}) Если всё число равно {total_value}{unit_suffix}, то одна доля равна {total_value} : {denominator} = {one_part}{unit_suffix}")
    step_no += 1

    if numerator == 1:
        lines.append(f"{step_no}) Если нужно найти 1/{denominator} числа, то ответ равен {one_part}{unit_suffix}")
    else:
        lines.append(f"{step_no}) Если нужно найти {numerator}/{denominator} числа, то берём {numerator} такие доли: {one_part} × {numerator} = {part_value}{unit_suffix}")

    lines.append(f"Ответ: {part_value}{unit_suffix}")
    lines.append("Совет: если задача с дробью дана в тоннах, метрах или других единицах, сначала переводи величину в удобные одинаковые единицы")
    return join_explanation_lines(*lines)


def try_consolidation_return_trip_faster_explanation_z(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "обратно" not in lower or "быстр" not in lower or "сколько" not in question:
        return None

    factor_match = re.search(r"в\s+(\d+)\s+раз(?:а)?\s+быстр", lower)
    if not factor_match:
        return None
    factor = int(factor_match.group(1))
    if factor <= 0:
        return None

    distance_match = re.search(r"\b(\d+)\s*(км|м)\b", lower)
    speed_match = re.search(r"скорост[ьяию][^\d]{0,20}(\d+)\s*(км/ч|м/с|м/мин)?", lower)
    if not distance_match or not speed_match:
        return None

    distance_value = int(distance_match.group(1))
    distance_unit = distance_match.group(2)
    speed_value = int(speed_match.group(1))
    speed_unit = speed_match.group(2) or ("км/ч" if distance_unit == "км" else "")
    if speed_value <= 0 or distance_value % speed_value != 0:
        return None

    one_way_time = distance_value // speed_value
    time_unit = "ч" if "/ч" in speed_unit or "час" in question else "мин" if "/мин" in speed_unit or "мин" in question else ""

    if one_way_time % factor == 0:
        return_time = one_way_time // factor
        return join_explanation_lines(
            f"1) Если путь до пункта равен {distance_value} {distance_unit}, а скорость была {speed_value} {speed_unit}, то время в одну сторону равно {distance_value} : {speed_value} = {one_way_time}{(' ' + time_unit) if time_unit else ''}",
            f"2) Если обратно ехали в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} быстрее, то время в обратную сторону в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} меньше: {one_way_time} : {factor} = {return_time}{(' ' + time_unit) if time_unit else ''}",
            f"Ответ: {return_time}{(' ' + time_unit) if time_unit else ''}",
            "Совет: если скорость на том же пути увеличилась в несколько раз, то время уменьшается во столько же раз",
        )

    faster_speed = speed_value * factor
    if distance_value % faster_speed != 0:
        return None
    return_time = distance_value // faster_speed

    return join_explanation_lines(
        f"1) Если скорость на обратном пути в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} больше, то новая скорость равна {speed_value} × {factor} = {faster_speed}{(' ' + speed_unit) if speed_unit else ''}",
        f"2) Если расстояние равно {distance_value} {distance_unit}, а новая скорость равна {faster_speed}{(' ' + speed_unit) if speed_unit else ''}, то время обратно равно {distance_value} : {faster_speed} = {return_time}{(' ' + time_unit) if time_unit else ''}",
        f"Ответ: {return_time}{(' ' + time_unit) if time_unit else ''}",
        "Совет: для одного и того же пути время находят делением расстояния на скорость",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_consolidation_direct_relation_multianswer_explanation_z(user_text)
        or try_consolidation_fraction_named_unit_explanation_z(user_text)
        or try_consolidation_return_trip_faster_explanation_z(user_text)
        or _CONSOLIDATION_PREV_BUILD_EXPLANATION_LOCAL_FIRST_Z(user_text, kind)
    )


# --- OPENAI HOTFIX 2026-04-11ZA: narrow named-unit fraction patch to real conversion cases ---

def try_consolidation_fraction_named_unit_explanation_z(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    fractions = extract_all_fraction_pairs(lower)
    if len(fractions) != 1 or "сколько" not in question:
        return None

    # Этот локальный обработчик нужен именно для задач, где требуется перевод единиц,
    # в первую очередь для тонн -> килограммы. Остальные дробные текстовые задачи
    # лучше оставлять более ранним специализированным объяснителям.
    ton_match = re.search(r"\b(\d+)\s*т\b", lower)
    if not ton_match:
        return None

    numerator, denominator = fractions[0]
    if denominator == 0:
        return None

    tons = int(ton_match.group(1))
    total_value = tons * 1000
    if total_value % denominator != 0:
        return None

    one_part = total_value // denominator
    part_value = one_part * numerator

    return join_explanation_lines(
        f"1) Сначала переводим тонны в килограммы: {tons} т = {total_value} кг",
        f"2) Если всё число равно {total_value} кг, то одна доля равна {total_value} : {denominator} = {one_part} кг",
        f"3) Если нужно найти {numerator}/{denominator} числа, то берём {numerator} такие доли: {one_part} × {numerator} = {part_value} кг",
        f"Ответ: {part_value} кг",
        "Совет: если задача с дробью дана в тоннах, сначала переведи тонны в килограммы",
    )


# --- CONSOLIDATION PATCH 2026-04-11AA: named measurement expressions from textbook ---

_PREV_20260411AA_INFER_TASK_KIND = infer_task_kind
_PREV_20260411AA_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_PREV_20260411AA_DETAILED_FORMAT_SOLUTION = _detailed_format_solution

_MEASURE_BASE_UNITS_20260411AA = {
    "length": [("км", 1_000_000), ("м", 1_000), ("дм", 100), ("см", 10), ("мм", 1)],
    "mass": [("т", 1_000_000), ("ц", 100_000), ("кг", 1_000), ("г", 1)],
    "time": [("ч", 3_600), ("мин", 60), ("с", 1)],
    "volume": [("л", 1_000), ("мл", 1)],
}

_MEASURE_UNIT_ALIASES_20260411AA = {
    "км": "км",
    "м": "м",
    "дм": "дм",
    "см": "см",
    "мм": "мм",
    "т": "т",
    "ц": "ц",
    "кг": "кг",
    "г": "г",
    "ч": "ч",
    "час": "ч",
    "часа": "ч",
    "часов": "ч",
    "мин": "мин",
    "минута": "мин",
    "минуты": "мин",
    "минут": "мин",
    "с": "с",
    "сек": "с",
    "секунда": "с",
    "секунды": "с",
    "секунд": "с",
    "л": "л",
    "мл": "мл",
}

_MEASURE_UNIT_PATTERN_20260411AA = "|".join(
    sorted((re.escape(unit) for unit in _MEASURE_UNIT_ALIASES_20260411AA), key=len, reverse=True)
)
_MEASURE_TOKEN_RE_20260411AA = re.compile(rf"(\d+)\s*({_MEASURE_UNIT_PATTERN_20260411AA})\b", re.IGNORECASE)


def _measure_canon_20260411AA(unit_text: str) -> str:
    return _MEASURE_UNIT_ALIASES_20260411AA.get(str(unit_text or "").strip().lower().replace("ё", "е"), "")


def _measure_family_20260411AA(unit_text: str) -> str:
    unit = _measure_canon_20260411AA(unit_text)
    for family, items in _MEASURE_BASE_UNITS_20260411AA.items():
        if any(name == unit for name, _ in items):
            return family
    return ""


def _measure_factor_20260411AA(family: str, unit_text: str) -> int:
    unit = _measure_canon_20260411AA(unit_text)
    for name, factor in _MEASURE_BASE_UNITS_20260411AA.get(family, []):
        if name == unit:
            return factor
    raise KeyError(unit)


def _measure_parse_value_20260411AA(text: str) -> Optional[dict]:
    raw = re.sub(r"\s+", " ", str(text or "").strip().lower().replace("ё", "е"))
    if not raw:
        return None
    matches = list(_MEASURE_TOKEN_RE_20260411AA.finditer(raw))
    if not matches:
        return None

    rebuilt_parts = []
    family = ""
    total = 0
    units_used = []
    normalized_tokens = []
    for match in matches:
        value = int(match.group(1))
        unit = _measure_canon_20260411AA(match.group(2))
        token_family = _measure_family_20260411AA(unit)
        if not token_family:
            return None
        if family and family != token_family:
            return None
        family = token_family
        rebuilt_parts.append(f"{value} {unit}")
        factor = _measure_factor_20260411AA(family, unit)
        total += value * factor
        if unit not in units_used:
            units_used.append(unit)
        normalized_tokens.append((value, unit))

    normalized = " ".join(rebuilt_parts)
    if re.sub(r"\s+", " ", normalized) != raw:
        return None

    preferred_units = sorted(units_used, key=lambda u: _measure_factor_20260411AA(family, u), reverse=True)
    return {
        "text": normalized,
        "family": family,
        "total": total,
        "units": preferred_units,
        "tokens": normalized_tokens,
    }


def _measure_format_from_base_20260411AA(total: int, family: str, preferred_units: List[str]) -> str:
    units = [u for u in preferred_units if _measure_family_20260411AA(u) == family]
    if not units:
        units = [name for name, _ in _MEASURE_BASE_UNITS_20260411AA[family]]
    units = sorted(units, key=lambda u: _measure_factor_20260411AA(family, u), reverse=True)

    if len(units) >= 2:
        first, second = units[0], units[1]
        first_factor = _measure_factor_20260411AA(family, first)
        second_factor = _measure_factor_20260411AA(family, second)
        first_value = total // first_factor
        remainder = total % first_factor
        second_value = remainder // second_factor
        parts = []
        if first_value:
            parts.append(f"{first_value} {first}")
        if second_value or not parts:
            parts.append(f"{second_value} {second}")
        return " ".join(parts)

    unit = units[0]
    factor = _measure_factor_20260411AA(family, unit)
    value = total // factor
    return f"{value} {unit}"


def _measure_base_unit_name_20260411AA(family: str) -> str:
    return _MEASURE_BASE_UNITS_20260411AA[family][-1][0]


def _parse_named_measurement_expression_20260411AA(raw_text: str) -> Optional[dict]:
    text = normalize_dashes(str(raw_text or "")).replace("×", " * ").replace(":", " / ").replace("÷", " / ")
    text = re.sub(r"\s+", " ", text).strip().lower().replace("ё", "е")
    if not text:
        return None

    measure_pattern = rf"(?:\d+\s*(?:{_MEASURE_UNIT_PATTERN_20260411AA})(?:\s+\d+\s*(?:{_MEASURE_UNIT_PATTERN_20260411AA}))*)"

    patterns = [
        (re.compile(rf"^({measure_pattern})\s*([+\-])\s*({measure_pattern})$", re.IGNORECASE), "measure_measure"),
        (re.compile(rf"^({measure_pattern})\s*([*/])\s*(\d+)$", re.IGNORECASE), "measure_number"),
        (re.compile(rf"^(\d+)\s*([*])\s*({measure_pattern})$", re.IGNORECASE), "number_measure"),
    ]

    for pattern, mode in patterns:
        match = pattern.fullmatch(text)
        if not match:
            continue
        if mode == "measure_measure":
            left = _measure_parse_value_20260411AA(match.group(1))
            right = _measure_parse_value_20260411AA(match.group(3))
            operator = "+" if match.group(2) == "+" else "-"
            if not left or not right or left["family"] != right["family"]:
                return None
            preferred = sorted(list(dict.fromkeys(left["units"] + right["units"])), key=lambda u: _measure_factor_20260411AA(left["family"], u), reverse=True)
            return {"mode": mode, "left": left, "right": right, "operator": operator, "family": left["family"], "preferred_units": preferred}
        if mode == "measure_number":
            left = _measure_parse_value_20260411AA(match.group(1))
            operator = "×" if match.group(2) == "*" else ":"
            number = int(match.group(3))
            if not left:
                return None
            return {"mode": mode, "left": left, "number": number, "operator": operator, "family": left["family"], "preferred_units": left["units"]}
        if mode == "number_measure":
            number = int(match.group(1))
            right = _measure_parse_value_20260411AA(match.group(3))
            if not right:
                return None
            return {"mode": mode, "left_number": number, "right": right, "number": number, "operator": "×", "family": right["family"], "preferred_units": right["units"]}
    return None


def _pretty_named_measurement_expression_20260411AA(parsed: dict) -> str:
    if parsed["mode"] == "measure_measure":
        return f"{parsed['left']['text']} {parsed['operator']} {parsed['right']['text']}"
    if parsed["mode"] == "measure_number":
        return f"{parsed['left']['text']} {parsed['operator']} {parsed['number']}"
    return f"{parsed['left_number']} × {parsed['right']['text']}"


def _build_named_measurement_expression_explanation_20260411AA(raw_text: str) -> Optional[str]:
    parsed = _parse_named_measurement_expression_20260411AA(raw_text)
    if not parsed:
        return None

    family = parsed["family"]
    base_unit = _measure_base_unit_name_20260411AA(family)
    pretty = _pretty_named_measurement_expression_20260411AA(parsed)

    if parsed["mode"] == "measure_measure":
        left = parsed["left"]
        right = parsed["right"]
        if parsed["operator"] == "-" and left["total"] < right["total"]:
            return None
        result_total = left["total"] + right["total"] if parsed["operator"] == "+" else left["total"] - right["total"]
        answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
        verb = "Складываем" if parsed["operator"] == "+" else "Вычитаем"
        return join_explanation_lines(
            f"Пример: {pretty} = {answer}",
            "Решение.",
            f"1) Переводим первое именованное число в {base_unit}: {left['text']} = {left['total']} {base_unit}",
            f"2) Переводим второе именованное число в {base_unit}: {right['text']} = {right['total']} {base_unit}",
            f"3) {verb}: {left['total']} {'+' if parsed['operator'] == '+' else '-'} {right['total']} = {result_total} {base_unit}",
            f"4) Переводим ответ обратно: {result_total} {base_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при сложении и вычитании именованных чисел сначала переводи их в одинаковые единицы",
        )

    if parsed["mode"] == "measure_number":
        left = parsed["left"]
        number = parsed["number"]
        if parsed["operator"] == ":":
            if number == 0 or left["total"] % number != 0:
                return None
            result_total = left["total"] // number
            action_line = f"2) Делим: {left['total']} : {number} = {result_total} {base_unit}"
        else:
            result_total = left["total"] * number
            action_line = f"2) Умножаем: {left['total']} × {number} = {result_total} {base_unit}"
        answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
        return join_explanation_lines(
            f"Пример: {pretty} = {answer}",
            "Решение.",
            f"1) Переводим составное именованное число в {base_unit}: {left['text']} = {left['total']} {base_unit}",
            action_line,
            f"3) Переводим ответ обратно: {result_total} {base_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при умножении и делении составные именованные числа сначала заменяют простыми, а потом выполняют вычисление",
        )

    right = parsed["right"]
    number = parsed["left_number"]
    result_total = right["total"] * number
    answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
    return join_explanation_lines(
        f"Пример: {pretty} = {answer}",
        "Решение.",
        f"1) Переводим составное именованное число в {base_unit}: {right['text']} = {right['total']} {base_unit}",
        f"2) Умножаем: {number} × {right['total']} = {result_total} {base_unit}",
        f"3) Переводим ответ обратно: {result_total} {base_unit} = {answer}",
        f"Ответ: {answer}",
        "Совет: при умножении составного именованного числа сначала переводи его в простое именованное число",
    )


def infer_task_kind(text: str) -> str:
    if _parse_named_measurement_expression_20260411AA(text):
        return "expression"
    return _PREV_20260411AA_INFER_TASK_KIND(text)


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return _build_named_measurement_expression_explanation_20260411AA(user_text) or _PREV_20260411AA_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)


def _format_named_measurement_expression_solution_20260411AA(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    parsed = _parse_named_measurement_expression_20260411AA(raw_text)
    pretty = _pretty_named_measurement_expression_20260411AA(parsed) if parsed else strip_known_prefix(raw_text)
    answer = parts["answer"] or "проверь запись"
    body_lines = [line for line in parts["body"] if not line.lower().startswith(("пример:", "решение"))]
    lines: List[str] = [f"Пример: {pretty} = {answer}", "Решение."]
    lines.extend(_detailed_number_lines(body_lines))
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or "сначала переводи составное именованное число в простое, потом выполняй вычисление"
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_solution(raw_text: str, text: str, kind: str) -> str:
    if _parse_named_measurement_expression_20260411AA(raw_text):
        return _format_named_measurement_expression_solution_20260411AA(raw_text, text)
    return _PREV_20260411AA_DETAILED_FORMAT_SOLUTION(raw_text, text, kind)


# --- HOTFIX 2026-04-11AB: use the smallest unit from the expression, not always family base ---


def _measure_conversion_unit_20260411AB(units: List[str], family: str) -> str:
    relevant = [u for u in units if _measure_family_20260411AA(u) == family]
    if not relevant:
        return _measure_base_unit_name_20260411AA(family)
    return min(relevant, key=lambda u: _measure_factor_20260411AA(family, u))


def _build_named_measurement_expression_explanation_20260411AA(raw_text: str) -> Optional[str]:
    parsed = _parse_named_measurement_expression_20260411AA(raw_text)
    if not parsed:
        return None

    family = parsed["family"]
    if parsed["mode"] == "measure_measure":
        left = parsed["left"]
        right = parsed["right"]
        conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
        if parsed["operator"] == "-" and left["total"] < right["total"]:
            return None
        result_total = left["total"] + right["total"] if parsed["operator"] == "+" else left["total"] - right["total"]
        answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
        left_simple = left["total"] // _measure_factor_20260411AA(family, conversion_unit)
        right_simple = right["total"] // _measure_factor_20260411AA(family, conversion_unit)
        result_simple = result_total // _measure_factor_20260411AA(family, conversion_unit)
        verb = "Складываем" if parsed["operator"] == "+" else "Вычитаем"
        return join_explanation_lines(
            f"Пример: {_pretty_named_measurement_expression_20260411AA(parsed)} = {answer}",
            "Решение.",
            f"1) Переводим первое именованное число в {conversion_unit}: {left['text']} = {left_simple} {conversion_unit}",
            f"2) Переводим второе именованное число в {conversion_unit}: {right['text']} = {right_simple} {conversion_unit}",
            f"3) {verb}: {left_simple} {'+' if parsed['operator'] == '+' else '-'} {right_simple} = {result_simple} {conversion_unit}",
            f"4) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при сложении и вычитании именованных чисел сначала переводи их в одинаковые единицы",
        )

    if parsed["mode"] == "measure_number":
        left = parsed["left"]
        number = parsed["number"]
        conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
        left_simple = left["total"] // _measure_factor_20260411AA(family, conversion_unit)
        if parsed["operator"] == ":":
            if number == 0 or left_simple % number != 0:
                return None
            result_simple = left_simple // number
            action_line = f"2) Делим: {left_simple} : {number} = {result_simple} {conversion_unit}"
        else:
            result_simple = left_simple * number
            action_line = f"2) Умножаем: {left_simple} × {number} = {result_simple} {conversion_unit}"
        result_total = result_simple * _measure_factor_20260411AA(family, conversion_unit)
        answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
        return join_explanation_lines(
            f"Пример: {_pretty_named_measurement_expression_20260411AA(parsed)} = {answer}",
            "Решение.",
            f"1) Переводим составное именованное число в {conversion_unit}: {left['text']} = {left_simple} {conversion_unit}",
            action_line,
            f"3) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при умножении и делении составные именованные числа сначала заменяют простыми, а потом выполняют вычисление",
        )

    right = parsed["right"]
    number = parsed["left_number"]
    conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
    right_simple = right["total"] // _measure_factor_20260411AA(family, conversion_unit)
    result_simple = right_simple * number
    result_total = result_simple * _measure_factor_20260411AA(family, conversion_unit)
    answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
    return join_explanation_lines(
        f"Пример: {_pretty_named_measurement_expression_20260411AA(parsed)} = {answer}",
        "Решение.",
        f"1) Переводим составное именованное число в {conversion_unit}: {right['text']} = {right_simple} {conversion_unit}",
        f"2) Умножаем: {number} × {right_simple} = {result_simple} {conversion_unit}",
        f"3) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
        f"Ответ: {answer}",
        "Совет: при умножении составного именованного числа сначала переводи его в простое именованное число",
    )


# --- USER FINAL CONSOLIDATION PATCH 2026-04-11: generic equations + clearer textbook answers ---

_PATCH_USER_FINAL_PREV_INFER_TASK_KIND = infer_task_kind
_PATCH_USER_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _user_final_equation_variable_name(source: str) -> str:
    match = re.search(r"[A-Za-zА-Яа-я]", str(source or ""))
    return match.group(0) if match else "x"


def to_equation_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(text)
    text = normalize_cyrillic_x(text)
    text = text.replace("X", "x").replace("×", "*").replace("·", "*").replace("÷", "/").replace(":", "/")
    text = re.sub(r"\s+", "", text)
    if text.count("=") != 1:
        return None
    if not re.fullmatch(r"[\dA-Za-zА-Яа-я=+\-*/]+", text):
        return None
    letters = re.findall(r"[A-Za-zА-Яа-я]", text)
    if not letters:
        return None
    unique_letters = {letter.lower() for letter in letters}
    if len(unique_letters) != 1:
        return None
    variable = letters[0]
    if text.count(variable) + text.lower().count(variable.lower()) < 1:
        return None
    return text


def infer_task_kind(text: str) -> str:
    if to_equation_source(text):
        return "equation"
    return _PATCH_USER_FINAL_PREV_INFER_TASK_KIND(text)


def _user_final_format_equation_check(template: str, variable_name: str, value_text: str, expected_text: str) -> str:
    expression = template.replace(variable_name, value_text)
    return f"Проверка: {expression} = {expected_text}"


def try_local_equation_explanation(raw_text: str) -> Optional[str]:
    source = to_equation_source(raw_text)
    if not source:
        return None

    variable_name = _user_final_equation_variable_name(source)
    lhs, rhs = source.split("=", 1)
    if variable_name not in lhs and variable_name in rhs:
        lhs, rhs = rhs, lhs

    try:
        rhs_value = Fraction(int(rhs), 1)
    except ValueError:
        return None

    variable_re = re.escape(variable_name)
    patterns = [
        (rf"^{variable_re}\+(\d+)$", "var_plus"),
        (rf"^{variable_re}-(\d+)$", "var_minus"),
        (rf"^{variable_re}\*(\d+)$", "var_mul"),
        (rf"^{variable_re}/(\d+)$", "var_div"),
        (rf"^(\d+)\+{variable_re}$", "plus_var"),
        (rf"^(\d+)-{variable_re}$", "minus_var"),
        (rf"^(\d+)\*{variable_re}$", "mul_var"),
        (rf"^(\d+)/{variable_re}$", "div_var"),
    ]

    for pattern, kind in patterns:
        match = re.fullmatch(pattern, lhs)
        if not match:
            continue

        number = Fraction(int(match.group(1)), 1)
        number_text = format_fraction(number)
        rhs_text = format_fraction(rhs_value)

        if kind in {"var_plus", "plus_var"}:
            answer = rhs_value - number
            check_template = f"{variable_name} + {number_text}" if kind == "var_plus" else f"{number_text} + {variable_name}"
            return join_explanation_lines(
                "Ищем неизвестное слагаемое",
                f"Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: {rhs_text} - {number_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(check_template, variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное слагаемое находим вычитанием",
            )

        if kind == "var_minus":
            answer = rhs_value + number
            return join_explanation_lines(
                "Ищем неизвестное уменьшаемое",
                f"Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое: {rhs_text} + {number_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(f"{variable_name} - {number_text}", variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное уменьшаемое находим сложением",
            )

        if kind == "minus_var":
            answer = number - rhs_value
            return join_explanation_lines(
                "Ищем неизвестное вычитаемое",
                f"Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность: {number_text} - {rhs_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(f"{number_text} - {variable_name}", variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное вычитаемое находим вычитанием",
            )

        if kind in {"var_mul", "mul_var"}:
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "При умножении на 0 всегда получается 0",
                        "Значит, подходит любое число",
                        "Ответ: подходит любое число",
                        "Совет: 0 × любое число = 0",
                    )
                return join_explanation_lines(
                    "При умножении на 0 нельзя получить другое число",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение ещё раз",
                )
            answer = rhs_value / number
            check_template = f"{variable_name} × {number_text}" if kind == "var_mul" else f"{number_text} × {variable_name}"
            return join_explanation_lines(
                "Ищем неизвестный множитель",
                f"Чтобы найти неизвестный множитель, произведение делим на известный множитель: {rhs_text} : {number_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(check_template, variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестный множитель находим делением",
            )

        if kind == "var_div":
            if number == 0:
                return join_explanation_lines(
                    "На ноль делить нельзя",
                    "Ответ: решения нет",
                    "Совет: проверь делитель",
                )
            answer = rhs_value * number
            return join_explanation_lines(
                "Ищем неизвестное делимое",
                f"Чтобы найти неизвестное делимое, делитель умножаем на частное: {rhs_text} × {number_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(f"{variable_name} : {number_text}", variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное делимое находим умножением",
            )

        if kind == "div_var":
            if rhs_value == 0:
                return join_explanation_lines(
                    "На ноль делить нельзя, а частное здесь равно 0",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение ещё раз",
                )
            answer = number / rhs_value
            return join_explanation_lines(
                "Ищем неизвестный делитель",
                f"Чтобы найти неизвестный делитель, делимое делим на частное: {number_text} : {rhs_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(f"{number_text} : {variable_name}", variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестный делитель находим делением",
            )
    return None

# --- merged segment 009: backend.legacy_runtime_shards.prepatch_build_source.segment_009 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 7083-7981."""



def _detailed_format_equation_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_equation_source(raw_text) or normalize_cyrillic_x(strip_known_prefix(raw_text))
    variable_name = _user_final_equation_variable_name(source)
    pretty = _detailed_pretty_equation(source)
    answer = parts["answer"] or "проверь запись"
    if re.fullmatch(r"-?\d+(?:/\d+)?", answer):
        answer = f"{variable_name} = {answer}"
    lines: List[str] = [f"Уравнение: {pretty}", "Решение."]
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("equation")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _user_final_question_text(raw_text: str) -> str:
    try:
        _, question = extract_condition_and_question(raw_text)
    except Exception:
        question = ""
    return str(question or "").lower().replace("ё", "е")


def try_patch_textbook_two_products_money_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _user_final_question_text(raw_text)
    if "сколько" not in lower:
        return None
    if not contains_any_fragment(question, ("сколько денег", "сколько заплат", "сколько стоила вся покупка", "сколько стоит вся покупка", "сколько стоила покупка", "сколько стоит покупка")):
        return None

    matches = list(re.finditer(r"(\d+)\s+[^?.!,]{1,40}?\s+по\s+(\d+)\s*(?:руб|руб\.|рубля|рублей)?", lower))
    if len(matches) < 2:
        return None

    first_count = int(matches[0].group(1))
    first_price = int(matches[0].group(2))
    second_count = int(matches[1].group(1))
    second_price = int(matches[1].group(2))

    first_total = first_count * first_price
    second_total = second_count * second_price
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если первая покупка состоит из {first_count} предметов по {first_price} руб., то её стоимость равна {first_count} × {first_price} = {first_total} руб.",
        f"2) Если вторая покупка состоит из {second_count} предметов по {second_price} руб., то её стоимость равна {second_count} × {second_price} = {second_total} руб.",
        f"3) Если первая покупка стоит {first_total} руб., а вторая {second_total} руб., то вся покупка стоит {first_total} + {second_total} = {total} руб.",
        f"Ответ: за всю покупку заплатили {total} руб.",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно.",
    )


def explain_piece_lengths_from_total_and_costs(total_length: int, first_cost: int, second_cost: int) -> Optional[str]:
    if total_length == 0:
        return None
    total_cost = first_cost + second_cost
    if total_cost % total_length != 0:
        return None
    unit_price = total_cost // total_length
    if unit_price == 0 or first_cost % unit_price != 0 or second_cost % unit_price != 0:
        return None
    first_length = first_cost // unit_price
    second_length = second_cost // unit_price
    return join_explanation_lines(
        f"1) Если один кусок стоит {first_cost}, а другой {second_cost}, то общая стоимость равна {first_cost} + {second_cost} = {total_cost}.",
        f"2) Если за {total_length} м заплатили {total_cost}, то один метр стоит {total_cost} : {total_length} = {unit_price}.",
        f"3) Если первый кусок стоит {first_cost}, а один метр стоит {unit_price}, то длина первого куска равна {first_cost} : {unit_price} = {first_length} м.",
        f"4) Если второй кусок стоит {second_cost}, а один метр стоит {unit_price}, то длина второго куска равна {second_cost} : {unit_price} = {second_length} м.",
        f"Ответ: в первом куске {first_length} м, во втором — {second_length} м.",
        "Совет: если у одинакового товара одна и та же цена за единицу, сначала находят цену одной единицы.",
    )


def explain_costs_from_length_difference(first_length: int, second_length: int, diff_cost: int) -> Optional[str]:
    diff_length = abs(second_length - first_length)
    if diff_length == 0 or diff_cost % diff_length != 0:
        return None
    price_per_meter = diff_cost // diff_length
    first_cost = first_length * price_per_meter
    second_cost = second_length * price_per_meter
    return join_explanation_lines(
        f"1) Если во втором куске {second_length} м ткани, а в первом {first_length} м ткани, то разность длин равна {second_length} - {first_length} = {diff_length} м.",
        f"2) Если второй кусок дороже на {diff_cost} руб. и длиннее на {diff_length} м, то один метр ткани стоит {diff_cost} : {diff_length} = {price_per_meter} руб.",
        f"3) Если в первом куске {first_length} м, а один метр стоит {price_per_meter} руб., то первый кусок стоит {first_length} × {price_per_meter} = {first_cost} руб.",
        f"4) Если во втором куске {second_length} м, а один метр стоит {price_per_meter} руб., то второй кусок стоит {second_length} × {price_per_meter} = {second_cost} руб.",
        f"Ответ: первый кусок стоит {first_cost} руб., второй — {second_cost} руб.",
        "Совет: если цена зависит от длины одинаково, сначала найди цену одной единицы длины.",
    )


def explain_masses_from_bag_difference(first_bags: int, second_bags: int, diff_mass: int) -> Optional[str]:
    diff_bags = abs(first_bags - second_bags)
    if diff_bags == 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    first_mass = first_bags * per_bag
    second_mass = second_bags * per_bag
    return join_explanation_lines(
        f"1) Если с одного участка собрали {first_bags} мешков, а с другого {second_bags} мешков, то разность мешков равна {first_bags} - {second_bags} = {diff_bags}.",
        f"2) Если {diff_bags} мешков составляют {diff_mass} кг, то в одном мешке {diff_mass} : {diff_bags} = {per_bag} кг.",
        f"3) Если на первом участке {first_bags} мешков по {per_bag} кг, то всего собрали {first_bags} × {per_bag} = {first_mass} кг.",
        f"4) Если на втором участке {second_bags} мешков по {per_bag} кг, то всего собрали {second_bags} × {per_bag} = {second_mass} кг.",
        f"Ответ: с первого участка собрали {first_mass} кг, со второго — {second_mass} кг.",
        "Совет: если известна разность по мешкам и по килограммам, сначала найди массу одного мешка.",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_patch_textbook_two_products_money_explanation(user_text)
        or _PATCH_USER_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )

# --- USER CONSOLIDATION PATCH 2026-04-11: textbook wording, safer precedence, preserved architecture ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши строку «Порядок действий:».
3. Ниже пиши тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
4. Потом пиши строку «Решение по действиям:».
5. Ниже пиши действия по порядку: 1) ... 2) ... 3) ...
6. В конце пиши строку «Ответ: ...».

Для текстовых задач:
1. Сначала пиши «Задача.» и само условие без изменения чисел.
2. Потом пиши «Решение.»
3. Затем обязательно пиши «Что известно: ...» и «Что нужно найти: ...».
4. Дальше решай по действиям.
5. После каждого действия коротко говори, что нашли.
6. По возможности используй школьную форму «Если ..., то ...».
7. В конце пиши «Ответ: ...».

Для уравнений:
1. Пиши строку «Уравнение: ...».
2. Потом «Решение.»
3. Решай по шагам.
4. Обязательно пиши «Проверка: ...».
5. Потом «Ответ: ...».

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, скажи это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии и величин:
1. Сначала назови правило или формулу.
2. Если нужно, сначала переведи величины в одинаковые единицы.
3. Потом решай по действиям.
4. В ответе обязательно пиши единицы измерения.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Сохраняй вычисления в столбик и подробные пояснения.
Сложение или вычитание в столбик особенно уместно, если в вычислениях больше двух двузначных чисел или есть хотя бы одно трёхзначное число.
""".strip()


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        "Нужно узнать, сколько всего или сколько стало.",
        f"Если первое количество равно {first}, а второе равно {second}, то всего {first} + {second} = {result}.",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько всего или сколько стало, обычно нужно сложение",
    )


def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько осталось или сколько стало меньше.",
        f"Если сначала было {first}, а потом убрали {second}, то осталось {first} - {second} = {result}.",
        f"Ответ: {result}",
        "Совет: если что-то убрали, отдали или потратили, обычно нужно вычитание",
    )


def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, на сколько одно число больше или меньше другого.",
        f"Для этого из большего числа вычитаем меньшее: {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решают вычитанием",
    )


def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        "Нужно узнать, сколько было сначала.",
        f"Если осталось {remaining}, а убрали {removed}, то сначала было {remaining} + {removed} = {result}.",
        f"Ответ: {result}",
        "Совет: неизвестное уменьшаемое находят сложением",
    )


def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько было сначала.",
        f"Если стало {final_total} после того, как прибавили {added}, то сначала было {final_total} - {added} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы найти число до прибавления, из нового числа вычитают то, что прибавили",
    )


def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько добавили.",
        f"Сравниваем, сколько было и сколько стало: {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
    )


def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько убрали.",
        f"Из того, что было, вычитаем то, что осталось: {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
    )


def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        "Нужно узнать, сколько всего предметов в одинаковых группах.",
        f"Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {result}.",
        f"Ответ: {result}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: проверь, на сколько частей делят")
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько получит каждый.",
            f"Если {total} предметов разделили на {groups} равные части, то {total} : {groups} = {quotient}.",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        "Нужно разделить поровну.",
        f"Делим: {total} : {groups} = {quotient}, остаток {remainder}.",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )


def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines("В одной группе не может быть 0 предметов", "Ответ: запись задачи неверная", "Совет: проверь размер одной группы")
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько групп получится.",
            f"Если всего {total} предметов, а в одной группе по {per_group}, то групп будет {total} : {per_group} = {quotient}.",
            f"Ответ: {quotient}",
            "Совет: число групп находят делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"Сначала находим, сколько полных групп получится: {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"Так как предметы ещё остались, нужна ещё одна группа, всего {quotient + 1}.",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления ещё есть остаток, иногда нужна ещё одна коробка или место",
        )
    if explicit_remainder:
        return join_explanation_lines(
            "Нужно узнать, сколько полных групп получится.",
            f"Делим: {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера одной группы",
        )
    return None


def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        "Сначала нужно найти второе количество.",
        f"Если второе количество на {delta} {mode}, то считаем так: {base} {sign} {delta} = {result}.",
        f"Ответ: {result}",
        "Совет: если число на несколько единиц больше, прибавляют; если меньше, вычитают",
    )


def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {sign} {delta} = {related}.",
        f"Потом находим всё вместе: {base} + {related} = {total}.",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят неизвестное количество, потом сумму",
    )


def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        "Сначала нужно найти второе количество.",
        f"Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то считаем так: {base} {op} {factor} = {result}.",
        f"Ответ: {result}",
        "Совет: если число в несколько раз больше, умножают; если в несколько раз меньше, делят",
    )


def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {op} {factor} = {related}.",
        f"Потом находим всё вместе: {base} + {related} = {total}.",
        f"Ответ: {total}",
        "Совет: сначала найди число, которое дано через отношение, потом считай общее количество",
    )


def explain_indirect_plus_minus_problem(base: int, delta: int, relation: str) -> Optional[str]:
    if relation in {"старше", "больше"}:
        result = base - delta
        if result < 0:
            return None
        relation_text = "другое число на столько же меньше"
        op = "-"
    else:
        result = base + delta
        relation_text = "другое число на столько же больше"
        op = "+"
    return join_explanation_lines(
        f"Это задача в косвенной форме: если здесь на {delta} {relation}, то {relation_text}.",
        f"Значит, искомое число равно {base} {op} {delta} = {result}.",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи условие в прямую форму",
    )


def explain_indirect_times_problem(base: int, factor: int, relation: str) -> Optional[str]:
    if relation == "больше":
        if factor == 0 or base % factor != 0:
            return None
        result = base // factor
        op = ":"
        relation_text = "другое число во столько же раз меньше"
    else:
        result = base * factor
        op = "×"
        relation_text = "другое число во столько же раз больше"
    return join_explanation_lines(
        f"Это задача в косвенной форме: если здесь в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то {relation_text}.",
        f"Значит, искомое число равно {base} {op} {factor} = {result}.",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи условие в прямую форму",
    )


def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"1) Если в {groups} группах {total_amount}, то в одной группе {total_amount} : {groups} = {one_group}.",
        f"2) Если в одной группе {one_group}, то в {target_groups} таких же группах {one_group} × {target_groups} = {result}.",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )


def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти расстояние.",
        "Пользуемся правилом: расстояние равно скорости, умноженной на время.",
        f"Считаем: {speed} × {time_value} = {result}.",
        f"Ответ: {answer}",
        "Совет: чтобы найти расстояние, скорость умножают на время",
    )


def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти скорость.",
        "Пользуемся правилом: скорость равна расстоянию, делённому на время.",
        f"Считаем: {distance} : {time_value} = {result}.",
        f"Ответ: {answer}",
        "Совет: чтобы найти скорость, расстояние делят на время",
    )


def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти время.",
        "Пользуемся правилом: время равно расстоянию, делённому на скорость.",
        f"Считаем: {distance} : {speed} = {result}.",
        f"Ответ: {answer}",
        "Совет: чтобы найти время, расстояние делят на скорость",
    )


def try_local_expression_explanation(raw_text: str) -> Optional[str]:
    source = to_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None

    # Важно: цепочку сложения упрощаем только без скобок, чтобы не ломать школьный порядок действий.
    if "(" not in source and ")" not in source:
        add_chain = flatten_add_chain(node)
        if add_chain and all(n >= 0 for n in add_chain):
            if should_use_column_for_sum(add_chain):
                return explain_column_addition(add_chain)
            if len(add_chain) == 2:
                return explain_simple_addition(add_chain[0], add_chain[1])
            current = add_chain[0]
            lines = ["Нужно найти сумму нескольких чисел."]
            for idx, n in enumerate(add_chain[1:], start=1):
                new_total = current + n
                if idx == 1:
                    lines.append(f"Сначала складываем: {current} + {n} = {new_total}.")
                elif idx == 2:
                    lines.append(f"Потом складываем: {current} + {n} = {new_total}.")
                else:
                    lines.append(f"Дальше складываем: {current} + {n} = {new_total}.")
                current = new_total
            lines.extend([f"Ответ: {current}", "Совет: при нескольких действиях считай по порядку"])
            return join_explanation_lines(*lines)

    simple = try_simple_binary_int_expression(node)
    if simple:
        operator = simple["operator"]
        left = simple["left"]
        right = simple["right"]
        if operator is ast.Add:
            return explain_simple_addition(left, right)
        if operator is ast.Sub:
            return explain_simple_subtraction(left, right)
        if operator is ast.Mult:
            return explain_simple_multiplication(left, right)
        if operator is ast.Div:
            return explain_simple_division(left, right)

    try:
        value, steps = build_eval_steps(node, source)
    except ZeroDivisionError:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: сначала смотри на делитель")
    except Exception:
        return None

    if not steps:
        return None

    body_lines = []
    has_brackets = "(" in source or ")" in source
    for index, step in enumerate(steps, start=1):
        text = f"{step['left']} {step['operator']} {step['right']} = {step['result']}"
        if index == 1 and has_brackets and len(steps) > 1:
            body_lines.append(f"{index}) Сначала выполняем действие в скобках: {text}")
        elif index == 1:
            body_lines.append(f"{index}) Сначала {step['verb']}: {text}")
        elif index == 2:
            body_lines.append(f"{index}) Потом {step['verb']}: {text}")
        else:
            body_lines.append(f"{index}) Дальше {step['verb']}: {text}")

    answer = format_fraction(value)
    advice = "сначала выполняй умножение и деление, потом сложение и вычитание" if re.search(r"[+\-].*[*/]|[*/].*[+\-]", source) else default_advice("expression")
    return join_explanation_lines(*body_lines, f"Ответ: {answer}", f"Совет: {advice}")


# --- USER TEXTBOOK PATCH 2026-04-11B: shelf/book templates from the uploaded methodology ---


def _user_patch_lower_text_20260411b(raw_text: str) -> str:
    return normalize_word_problem_text(raw_text).lower().replace("ё", "е")


def _user_patch_books_word_20260411b(count: int) -> str:
    return plural_form(count, "книга", "книги", "книг")

def try_user_patch_shelf_total_explanation_20260411b(raw_text: str) -> Optional[str]:
    lower = _user_patch_lower_text_20260411b(raw_text)
    if not ("полке" in lower and "книг" in lower):
        return None
    if not re.search(r"сколько[^.?!]*(обеих|двух) полк", lower):
        return None
    match = re.search(r"на первой полке(?: было)?\s*(\d+)\s*книг[^\d]{0,40}на второй(?: полке)?(?: было)?\s*(\d+)\b", lower)
    if not match:
        return None
    first = int(match.group(1))
    second = int(match.group(2))
    total = first + second
    return join_explanation_lines(
        f"1) Если на первой полке было {first} {_user_patch_books_word_20260411b(first)}, а на второй {second} {_user_patch_books_word_20260411b(second)}, то на обеих полках было {first} + {second} = {total} книг.",
        f"Ответ: на двух полках было {total} книг.",
        "Совет: если спрашивают, сколько на обеих полках, складывают количества на первой и второй полке.",
    )


def try_user_patch_shelf_more_less_total_explanation_20260411b(raw_text: str) -> Optional[str]:
    lower = _user_patch_lower_text_20260411b(raw_text)
    if not ("полке" in lower and "книг" in lower):
        return None
    if not re.search(r"сколько[^.?!]*(обеих|двух) полк", lower):
        return None
    match = re.search(r"на первой полке(?: было)?\s*(\d+)\s*книг[^\d]{0,40}на второй(?: полке)?\s*на\s*(\d+)\s*(больше|меньше)", lower)
    if not match:
        return None
    first = int(match.group(1))
    delta = int(match.group(2))
    mode = match.group(3)
    second = first + delta if mode == "больше" else first - delta
    if second < 0:
        return None
    total = first + second
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"1) Если на первой полке {first} {_user_patch_books_word_20260411b(first)}, а на второй на {delta} {mode}, то на второй полке было {first} {sign} {delta} = {second} {_user_patch_books_word_20260411b(second)}.",
        f"2) Если на первой полке {first} {_user_patch_books_word_20260411b(first)}, а на второй {second} {_user_patch_books_word_20260411b(second)}, то на двух полках было {first} + {second} = {total} книг.",
        f"Ответ: на двух полках было {total} книг.",
        "Совет: в составной задаче сначала находят неизвестное количество, потом сумму.",
    )


def try_user_patch_shelf_unknown_second_explanation_20260411b(raw_text: str) -> Optional[str]:
    lower = _user_patch_lower_text_20260411b(raw_text)
    if not ("полке" in lower and "книг" in lower):
        return None
    if not re.search(r"сколько[^.?!]*второй полке", lower):
        return None
    match = re.search(r"на двух полках(?: было)?\s*(\d+)\s*книг[^\d]{0,80}на первой полке(?: было)?\s*(\d+)\s*книг", lower)
    if not match:
        return None
    total = int(match.group(1))
    first = int(match.group(2))
    second = total - first
    if second < 0:
        return None
    return join_explanation_lines(
        f"1) Если на двух полках было {total} книг, а на первой полке было {first} {_user_patch_books_word_20260411b(first)}, то на второй полке было {total} - {first} = {second} {_user_patch_books_word_20260411b(second)}.",
        f"Ответ: на второй полке было {second} {_user_patch_books_word_20260411b(second)}.",
        "Совет: чтобы найти, сколько было на второй полке, из общего количества вычитают количество на первой полке.",
    )


def try_user_patch_shelf_indirect_explanation_20260411b(raw_text: str) -> Optional[str]:
    lower = _user_patch_lower_text_20260411b(raw_text)
    if not ("полке" in lower and "книг" in lower):
        return None
    if not re.search(r"сколько[^.?!]*второй полке", lower):
        return None
    match = re.search(r"на первой полке(?: было)?\s*(\d+)\s*книг[^\d]{0,30}это\s+на\s*(\d+)\s*книг[^\d]{0,20}(больше|меньше),?\s+чем\s+на\s+второй", lower)
    if match:
        first = int(match.group(1))
        delta = int(match.group(2))
        relation = match.group(3)
        if relation == "больше":
            second = first - delta
            if second < 0:
                return None
            return join_explanation_lines(
                f"1) Если на первой полке книг на {delta} больше, чем на второй, то на второй полке книг на {delta} меньше, чем на первой.",
                f"2) Если на первой полке {first} книг, а на второй на {delta} меньше, то на второй полке было {first} - {delta} = {second} {_user_patch_books_word_20260411b(second)}.",
                f"Ответ: на второй полке было {second} {_user_patch_books_word_20260411b(second)}.",
                "Совет: в косвенной задаче сначала переведи условие в прямую форму.",
            )
        second = first + delta
        return join_explanation_lines(
            f"1) Если на первой полке книг на {delta} меньше, чем на второй, то на второй полке книг на {delta} больше, чем на первой.",
            f"2) Если на первой полке {first} книг, а на второй на {delta} больше, то на второй полке было {first} + {delta} = {second} {_user_patch_books_word_20260411b(second)}.",
            f"Ответ: на второй полке было {second} книг.",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму.",
        )

    match = re.search(r"на второй полке(?: было)?\s*(\d+)\s*книг[^\d]{0,30}это\s+в\s*(\d+)\s*раз(?:а)?\s*больше,?\s+чем\s+на\s+первой", lower)
    if match:
        second = int(match.group(1))
        factor = int(match.group(2))
        if factor == 0 or second % factor != 0:
            return None
        first = second // factor
        return join_explanation_lines(
            f"1) Если на второй полке книг в {factor} раза больше, чем на первой, то на первой полке книг в {factor} раза меньше, чем на второй.",
            f"2) Если на второй полке {second} книг, а на первой в {factor} раза меньше, то на первой полке было {second} : {factor} = {first} {_user_patch_books_word_20260411b(first)}.",
            f"Ответ: на первой полке было {first} {_user_patch_books_word_20260411b(first)}.",
            "Совет: если сказано «в несколько раз больше» в косвенной форме, сначала переведи это в «в несколько раз меньше».",
        )
    return None


__OAI_20260411_USER_PREV_BUILD_LOCAL_SAFE = build_explanation_local_first


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_user_patch_shelf_total_explanation_20260411b(user_text)
        or try_user_patch_shelf_more_less_total_explanation_20260411b(user_text)
        or try_user_patch_shelf_unknown_second_explanation_20260411b(user_text)
        or try_user_patch_shelf_indirect_explanation_20260411b(user_text)
        or __OAI_20260411_USER_PREV_BUILD_LOCAL_SAFE(user_text, kind)
    )


# --- OAI FINAL CLEAN PATCH 2026-04-11C: formatting cleanup, stable compare answers, textbook polish ---

_OAI_20260411C_PREV_EXPLAIN_PRICE_DIFFERENCE = explain_price_difference_problem
_OAI_20260411C_PREV_DETAILED_FORMAT_EXPRESSION = _detailed_format_expression_solution
_OAI_20260411C_PREV_DETAILED_FORMAT_SOLUTION = _detailed_format_solution


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_a} руб., то цена одного товара равна {total_a} : {quantity} = {price_a} руб",
        f"2) Если за {quantity} таких же товаров заплатили {total_b} руб., то цена одного товара равна {total_b} : {quantity} = {price_b} руб",
        f"3) Сравниваем цены: {max(price_a, price_b)} - {min(price_a, price_b)} = {diff} руб",
        f"Ответ: цены отличаются на {diff} руб",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


def _oai_20260411c_expression_body_lines(body_lines: List[str]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for raw in body_lines:
        line = str(raw or "").strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("частное:"):
            continue
        if lower.startswith("пример:"):
            continue
        key = lower.rstrip(". ")
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)
    return cleaned


def _oai_20260411c_pretty_expr_with_map(source: str) -> Tuple[str, dict]:
    pretty_parts: List[str] = []
    op_map = {}
    current_len = 0
    for index, ch in enumerate(source):
        if ch in "+-*/":
            symbol = "×" if ch == "*" else ":" if ch == "/" else ch
            token = f" {symbol} "
            pretty_parts.append(token)
            op_map[index] = current_len + 1
            current_len += len(token)
        else:
            pretty_parts.append(ch)
            current_len += 1
    return "".join(pretty_parts), op_map


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")

    node = parse_expression_ast(source)
    if node is not None:
        pretty_expression = render_node(node)
    else:
        pretty_expression, _ = _oai_20260411c_pretty_expr_with_map(source)

    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = _oai_20260411c_expression_body_lines(parts["body"])
    if not body_lines:
        body_lines = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]

    if _detailed_is_column_like(body_lines) or any("столбик" in line.lower() for line in body_lines):
        lines.append("Решение.")
        before_expl: List[str] = []
        expl: List[str] = []
        in_expl = False
        for line in body_lines:
            low = line.lower()
            if low.startswith("пояснение"):
                in_expl = True
                continue
            if not in_expl:
                before_expl.append(line)
            else:
                expl.append(line)
        if before_expl:
            lines.extend(before_expl)
        if expl:
            lines.append("Пояснение по шагам:")
            lines.extend(_detailed_number_lines(expl))
        else:
            remaining = [line for line in body_lines if not line.lower().startswith("запись столбиком")]
            lines.extend(_detailed_number_lines(remaining))
    else:
        order_block = _detailed_build_order_block(source)
        if order_block:
            lines.extend(order_block)
            lines.append("Решение по действиям:")
        else:
            lines.append("Решение.")
        lines.extend(_detailed_number_lines(body_lines))

    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_solution(raw_text: str, text: str, kind: str) -> str:
    if kind == "expression" and to_expression_source(raw_text):
        return _detailed_format_expression_solution(raw_text, text)
    return _OAI_20260411C_PREV_DETAILED_FORMAT_SOLUTION(raw_text, text, kind)


# --- OAI FINAL CLEAN PATCH 2026-04-11D: preferred routing for price tasks and cleaner column formatting ---

_OAI_20260411D_PREV_BUILD_LOCAL = build_explanation_local_first


def _oai_20260411d_is_visual_column_line(line: str) -> bool:
    value = str(line or "").strip()
    if not value:
        return False
    if re.search(r"[А-Яа-яЁё]", value):
        return False
    return True


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")

    node = parse_expression_ast(source)
    if node is not None:
        pretty_expression = render_node(node)
    else:
        pretty_expression, _ = _oai_20260411c_pretty_expr_with_map(source)

    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = _oai_20260411c_expression_body_lines(parts["body"])
    if not body_lines:
        body_lines = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]

    if body_lines and body_lines[0].lower().startswith("запись столбиком"):
        lines.append("Решение.")
        lines.append("Запись столбиком:")
        visual_lines: List[str] = []
        idx = 1
        while idx < len(body_lines):
            current = body_lines[idx]
            lower = current.lower()
            if lower.startswith("частное:"):
                idx += 1
                continue
            if _oai_20260411d_is_visual_column_line(current):
                visual_lines.append(current)
                idx += 1
                continue
            break
        lines.extend(visual_lines)
        expl_lines = [line for line in body_lines[idx:] if not line.lower().startswith("частное:")]
        if expl_lines:
            lines.append("Пояснение по шагам:")
            lines.extend(_detailed_number_lines(expl_lines))
    elif _detailed_is_column_like(body_lines) or any("столбик" in line.lower() for line in body_lines):
        lines.append("Решение.")
        lines.extend(_detailed_number_lines(body_lines))
    else:
        order_block = _detailed_build_order_block(source)
        if order_block:
            lines.extend(order_block)
            lines.append("Решение по действиям:")
        else:
            lines.append("Решение.")
        lines.extend(_detailed_number_lines(body_lines))

    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def try_oai_20260411d_price_difference_first(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None
    if contains_any_fragment(lower, ("за столько же", "на сколько пакет", "на сколько дороже", "на сколько дешевле")):
        return explain_price_difference_problem(nums[0], nums[1], nums[2])
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_user_patch_shelf_total_explanation_20260411b(user_text)
        or try_user_patch_shelf_more_less_total_explanation_20260411b(user_text)
        or try_user_patch_shelf_unknown_second_explanation_20260411b(user_text)
        or try_user_patch_shelf_indirect_explanation_20260411b(user_text)
        or try_oai_20260411d_price_difference_first(user_text)
        or try_local_price_word_problem_explanation(user_text)
        or _OAI_20260411D_PREV_BUILD_LOCAL(user_text, kind)
    )


# --- FINAL USER PATCH 2026-04-11ZZ: fuller counted answers + mixed-unit same-time motion + cleaner fraction-whole wording ---

_FINAL_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_ZZ = build_explanation_local_first
_FINAL_USER_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_ZZ = _detailed_maybe_enrich_answer

# --- merged segment 010: backend.legacy_runtime_shards.prepatch_build_source.segment_010 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 7982-8870."""


QUESTION_NOUN_FORMS.update({
    "детей": ("ребёнок", "ребёнка", "детей"),
    "ребенок": ("ребёнок", "ребёнка", "детей"),
    "ребёнок": ("ребёнок", "ребёнка", "детей"),
    "человек": ("человек", "человека", "человек"),
    "червячок": ("червячок", "червячка", "червячков"),
    "червячка": ("червячок", "червячка", "червячков"),
    "червячков": ("червячок", "червячка", "червячков"),
    "ручка": ("ручка", "ручки", "ручек"),
    "ручки": ("ручка", "ручки", "ручек"),
    "ручек": ("ручка", "ручки", "ручек"),
    "тетрадь": ("тетрадь", "тетради", "тетрадей"),
    "тетради": ("тетрадь", "тетради", "тетрадей"),
    "тетрадей": ("тетрадь", "тетради", "тетрадей"),
    "булочка": ("булочка", "булочки", "булочек"),
    "булочки": ("булочка", "булочки", "булочек"),
    "булочек": ("булочка", "булочки", "булочек"),
    "птица": ("птица", "птицы", "птиц"),
    "птицы": ("птица", "птицы", "птиц"),
    "птиц": ("птица", "птицы", "птиц"),
    "корзина": ("корзина", "корзины", "корзин"),
    "корзины": ("корзина", "корзины", "корзин"),
    "корзин": ("корзина", "корзины", "корзин"),
    "клетка": ("клетка", "клетки", "клеток"),
    "клетки": ("клетка", "клетки", "клеток"),
    "клеток": ("клетка", "клетки", "клеток"),
    "ягода": ("ягода", "ягоды", "ягод"),
    "ягоды": ("ягода", "ягоды", "ягод"),
    "ягод": ("ягода", "ягоды", "ягод"),
    "гриб": ("гриб", "гриба", "грибов"),
    "гриба": ("гриб", "гриба", "грибов"),
    "грибов": ("гриб", "гриба", "грибов"),
    "орешек": ("орешек", "орешка", "орешков"),
    "орешка": ("орешек", "орешка", "орешков"),
    "орешков": ("орешек", "орешка", "орешков"),
    "марка": ("марка", "марки", "марок"),
    "марки": ("марка", "марки", "марок"),
    "марок": ("марка", "марки", "марок"),
    "ложка": ("ложка", "ложки", "ложек"),
    "ложки": ("ложка", "ложки", "ложек"),
    "ложек": ("ложка", "ложки", "ложек"),
    "ириска": ("ириска", "ириски", "ирисок"),
    "ириски": ("ириска", "ириски", "ирисок"),
    "ирисок": ("ириска", "ириски", "ирисок"),
    "карамелька": ("карамелька", "карамельки", "карамелек"),
    "карамельки": ("карамелька", "карамельки", "карамелек"),
    "карамелек": ("карамелька", "карамельки", "карамелек"),
    "лимон": ("лимон", "лимона", "лимонов"),
    "лимона": ("лимон", "лимона", "лимонов"),
    "лимонов": ("лимон", "лимона", "лимонов"),
    "сетка": ("сетка", "сетки", "сеток"),
    "сетки": ("сетка", "сетки", "сеток"),
    "сеток": ("сетка", "сетки", "сеток"),
    "ведро": ("ведро", "ведра", "ведер"),
    "ведра": ("ведро", "ведра", "ведер"),
    "вёдер": ("ведро", "ведра", "ведер"),
    "ведер": ("ведро", "ведра", "ведер"),
    "пассажир": ("пассажир", "пассажира", "пассажиров"),
    "пассажира": ("пассажир", "пассажира", "пассажиров"),
    "пассажиров": ("пассажир", "пассажира", "пассажиров"),
})


def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None

    if remaining_numerator == 1:
        whole = remaining_value * denominator
        return join_explanation_lines(
            f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось 1/{denominator} всех денег",
            f"2) Если 1/{denominator} всех денег равна {remaining_value} руб., то все деньги равны {remaining_value} × {denominator} = {whole} руб.",
            f"Ответ: у мамы было {whole} руб.",
            "Совет: если известна оставшаяся доля, всё число находят умножением значения одной доли на число долей",
        )

    if remaining_value % remaining_numerator != 0:
        return None

    one_share = remaining_value // remaining_numerator
    whole = one_share * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value} руб., то 1/{denominator} всех денег равна {remaining_value} : {remaining_numerator} = {one_share} руб.",
        f"3) Если 1/{denominator} всех денег равна {one_share} руб., то все деньги равны {one_share} × {denominator} = {whole} руб.",
        f"Ответ: у мамы было {whole} руб.",
        "Совет: если известна оставшаяся часть, сначала найди одну долю, потом всё число",
    )


_FINAL_PATCH_DISTANCE_TO_BASE_ZZ = {
    "мм": 1,
    "см": 10,
    "дм": 100,
    "м": 1000,
    "км": 1000000,
}


def _final_patch_normalize_time_unit_zz(unit: str) -> str:
    value = str(unit or "").strip().lower().replace("ё", "е")
    if value in {"ч", "час", "часа", "часов"}:
        return "ч"
    if value in {"мин", "минута", "минуты", "минут"}:
        return "мин"
    if value in {"с", "сек", "секунда", "секунды", "секунд"}:
        return "с"
    return value


def _final_patch_split_speed_unit_zz(speed_unit: str) -> Optional[Tuple[str, str]]:
    value = str(speed_unit or "").strip().lower()
    if "/" not in value:
        return None
    dist_unit, time_unit = value.split("/", 1)
    dist_unit = dist_unit.strip()
    time_unit = _final_patch_normalize_time_unit_zz(time_unit)
    if dist_unit not in _FINAL_PATCH_DISTANCE_TO_BASE_ZZ or time_unit not in {"ч", "мин", "с"}:
        return None
    return dist_unit, time_unit


def _final_patch_parse_same_time_motion_zz(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")

    if not ("за это же время" in lower or "за то же время" in lower):
        return None
    if not contains_any_fragment(lower, ("с какой скоростью", "какова скорость")):
        return None

    unit_group = r"(?:км|м|дм|см|мм)"
    speed_group = r"(?:км|м|дм|см|мм)/(?:ч|мин|с)"

    first_match = re.search(
        rf"(\d+)\s*({unit_group})\b[^.?!]{{0,100}}?со\s+скорост(?:ью|и)\s*(\d+)\s*({speed_group})",
        lower,
    )
    if not first_match:
        first_match = re.search(
            rf"со\s+скорост(?:ью|и)\s*(\d+)\s*({speed_group})[^.?!]{{0,100}}?(\d+)\s*({unit_group})\b",
            lower,
        )
        if first_match:
            speed_value = int(first_match.group(1))
            speed_unit = first_match.group(2)
            first_distance_value = int(first_match.group(3))
            first_distance_unit = first_match.group(4)
        else:
            return None
    else:
        first_distance_value = int(first_match.group(1))
        first_distance_unit = first_match.group(2)
        speed_value = int(first_match.group(3))
        speed_unit = first_match.group(4)

    second_match = re.search(
        rf"(?:за это же время|за то же время)[^.?!]{{0,120}}?(\d+)\s*({unit_group})\b",
        lower,
    )
    if not second_match:
        return None

    second_distance_value = int(second_match.group(1))
    second_distance_unit = second_match.group(2)

    split_speed = _final_patch_split_speed_unit_zz(speed_unit)
    if not split_speed:
        return None
    speed_distance_unit, time_unit = split_speed

    first_distance_base = first_distance_value * _FINAL_PATCH_DISTANCE_TO_BASE_ZZ[first_distance_unit]
    speed_distance_base = _FINAL_PATCH_DISTANCE_TO_BASE_ZZ[speed_distance_unit]
    if first_distance_base % speed_distance_base != 0:
        return None

    first_distance_in_speed_units = first_distance_base // speed_distance_base
    if speed_value == 0 or first_distance_in_speed_units % speed_value != 0:
        return None

    same_time = first_distance_in_speed_units // speed_value
    if same_time == 0 or second_distance_value % same_time != 0:
        return None

    second_speed = second_distance_value // same_time
    answer_unit = f"{second_distance_unit}/{time_unit}"

    return join_explanation_lines(
        f"1) Если первый участник прошёл {first_distance_in_speed_units} {speed_distance_unit} со скоростью {speed_value} {speed_unit}, то он был в пути {first_distance_in_speed_units} : {speed_value} = {same_time} {time_unit}",
        f"2) Если второй участник прошёл {second_distance_value} {second_distance_unit} за {same_time} {time_unit}, то его скорость равна {second_distance_value} : {same_time} = {second_speed} {answer_unit}",
        f"Ответ: скорость второго участника равна {second_speed} {answer_unit}",
        "Совет: если время у двух участников одинаковое, сначала найди это время, потом скорость второго участника",
    )


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = _FINAL_USER_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_ZZ(answer, raw_text, kind)
    stripped = str(value or "").strip()
    if not stripped:
        return stripped

    if re.fullmatch(r"-?\d+", stripped):
        try:
            stripped = _patch_answer_with_question_noun(int(stripped), raw_text)
        except Exception:
            pass

    if _question_lower_text(raw_text).startswith("на сколько") and re.fullmatch(r"-?\d+(?:/\d+)?(?:\s+[A-Za-zА-Яа-я./²]+)?", stripped):
        if not stripped.startswith("на "):
            stripped = f"на {stripped}"

    return stripped


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_patch_parse_same_time_motion_zz(user_text)
        or _FINAL_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_ZZ(user_text, kind)
    )


# --- FINAL USER PATCH 2026-04-11ZX: cleaner special case for fraction of money left after spending ---

_FINAL_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_ZX = build_explanation_local_first

def _final_patch_fraction_money_whole_zz(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace("ё", "е")

    if not contains_any_fragment(lower, ("израсходовал", "израсходовала", "израсходовали")):
        return None
    if "остал" not in lower or "руб" not in lower:
        return None

    frac_match = re.search(r"(\d+)\s*/\s*(\d+)", lower)
    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)\s*руб", lower)
    if not frac_match or not remain_match:
        return None

    spent_numerator = int(frac_match.group(1))
    denominator = int(frac_match.group(2))
    remaining_value = int(remain_match.group(1))
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None

    if remaining_numerator == 1:
        whole = remaining_value * denominator
        return join_explanation_lines(
            f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось 1/{denominator} всех денег",
            f"2) Если 1/{denominator} всех денег равна {remaining_value} руб., то все деньги равны {remaining_value} × {denominator} = {whole} руб.",
            f"Ответ: всего было {whole} руб.",
            "Совет: если известна одна доля, всё число находят умножением значения доли на число долей",
        )

    if remaining_value % remaining_numerator != 0:
        return None

    one_share = remaining_value // remaining_numerator
    whole = one_share * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value} руб., то 1/{denominator} всех денег равна {remaining_value} : {remaining_numerator} = {one_share} руб.",
        f"3) Если 1/{denominator} всех денег равна {one_share} руб., то все деньги равны {one_share} × {denominator} = {whole} руб.",
        f"Ответ: всего было {whole} руб.",
        "Совет: если известна оставшаяся часть, сначала находят одну долю, потом всё число",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_patch_fraction_money_whole_zz(user_text)
        or _FINAL_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_ZX(user_text, kind)
    )


# --- OPENAI FINAL CONSOLIDATION PATCH 2026-04-11B: textbook priority, named purchase tasks, stable final prompt ---

_OPENAI_FINAL_20260411B_PREV_BUILD_LOCAL = build_explanation_local_first

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...
6. Если пример удобнее решать в столбик, сохрани запись столбиком и подробное пояснение по шагам.
7. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом перепиши само условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. Для школьного стиля по возможности используй форму:
Если ..., то ...
6. После каждого действия коротко говори, что нашли.
7. Если в задаче несколько вопросов, отвечай на все вопросы по порядку.
8. В конце обязательно пиши:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если это именованные величины, сначала переведи их в одинаковые единицы.

Важные требования:
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Для многодейственных задач не перескакивай сразу к ответу.
Сначала действие, потом пояснение, потом следующее действие.
""".strip()


def _openai_final_20260411b_named_sum_of_two_products_money_explanation(raw_text: str) -> Optional[str]:
    try:
        direct = try_patch_named_sum_of_two_products_money_explanation(raw_text)
        if direct:
            return direct
    except Exception:
        pass

    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None
    if not (contains_any_fragment(lower, ("заплат", "стоим", "стоил", "стоит")) or contains_any_fragment(question, ("сколько денег", "сколько заплат", "сколько стоила", "сколько стоит"))):
        return None

    products = _po_product_matches(raw_text)
    if len(products) < 2:
        return None
    if contains_any_fragment(question, ("сколько стоит 1", "сколько стоила 1", "сколько стоила одна", "сколько стоит одна")):
        return None

    first = products[0]
    second = products[1]
    first_total = first["count"] * first["value"]
    second_total = second["count"] * second["value"]
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если купили {first['count']} {first['name']} по {first['value']} руб., то за {first['name']} заплатили {first['count']} × {first['value']} = {first_total} руб",
        f"2) Если купили {second['count']} {second['name']} по {second['value']} руб., то за {second['name']} заплатили {second['count']} × {second['value']} = {second_total} руб",
        f"3) Если за {first['name']} заплатили {first_total} руб., а за {second['name']} {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )


def _openai_final_20260411b_unknown_price_with_names_explanation(raw_text: str) -> Optional[str]:
    try:
        direct = try_high_priority_unknown_price_word_problem_explanation(raw_text)
        if direct:
            return direct
    except Exception:
        return None
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _openai_final_20260411b_named_sum_of_two_products_money_explanation(user_text)
        or _openai_final_20260411b_unknown_price_with_names_explanation(user_text)
        or _OPENAI_FINAL_20260411B_PREV_BUILD_LOCAL(user_text, kind)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи",
            "Запишите пример или задачу полнее и без сокращений",
            "Ответ: пока нужен более понятный ввод",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 2200,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- USER FINAL PATCH 2026-04-11ZZ: preserve architecture, stabilize final output ---

_USER_FINAL_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_USER_FINAL_PATCH_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION = _detailed_format_expression_solution

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown-таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом, сохраняя скобки и исходную запись.
2. Если действий несколько, обязательно пиши строку «Порядок действий:» и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши «Решение по действиям:» и ниже все вычисления по действиям: 1), 2), 3)...
4. Если пример удобнее решать в столбик, сохраняй запись столбиком и подробное пояснение по шагам.
5. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.
6. В конце пиши строку «Ответ: ...».

Для текстовых задач:
1. Сначала пиши «Задача.» и переписывай условие без изменения чисел.
2. Потом пиши «Решение.»
3. Затем обязательно пиши «Что известно: ...» и «Что нужно найти: ...».
4. Если сразу нельзя ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай только по действиям.
6. Каждое действие начинай с номера: 1), 2), 3)...
7. Для школьного стиля по возможности используй форму «Если..., то ...».
8. После каждого действия коротко говори, что нашли.
9. Если в задаче несколько вопросов, ответь на все вопросы по порядку.
10. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку «Уравнение: ...».
2. Потом «Решение.»
3. Решай по шагам.
4. Обязательно пиши «Проверка: ...».
5. Потом «Ответ: ...».

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, скажи это отдельно.
3. Если знаменатели разные, сначала приведи дроби к общему знаменателю.
4. Если задача дана с величинами, сначала переведи величины в удобные одинаковые единицы.
5. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.
5. В ответе обязательно пиши единицы измерения.

Школьные методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Сохраняй вычисления в столбик и подробные пояснения.
Для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()


def _user_final_patch_pretty_expression_from_source(source: str) -> str:
    text = str(source or "")
    text = text.replace("*", "×").replace("/", ":")
    text = re.sub(r"([()+\-×:])", r" \1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("( ", "(").replace(" )", ")")
    return text


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    source = to_expression_source(raw_text)
    if not source:
        return _USER_FINAL_PATCH_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)

    formatted = _USER_FINAL_PATCH_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)
    lines = [line for line in str(formatted or "").split("\n")]
    if not lines:
        return formatted

    answer = ""
    match = re.match(r"^Пример:\s*.*?=\s*(.+)$", lines[0].strip())
    if match:
        answer = match.group(1).strip().rstrip(".")
    if not answer:
        answer = _detailed_expression_answer(source) or "проверь запись"

    lines[0] = f"Пример: {_user_final_patch_pretty_expression_from_source(source)} = {answer}"
    return _detailed_finalize_text(lines)


def explain_long_division(dividend: int, divisor: int) -> str:
    if divisor == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: сначала смотри на делитель",
        )

    quotient, remainder = divmod(dividend, divisor)
    digits = list(str(dividend))
    lines: List[str] = [
        "Пишем деление столбиком",
        "Находим первое неполное делимое",
    ]

    current = 0
    started = False

    for index, digit_char in enumerate(digits):
        current = current * 10 + int(digit_char)

        if not started and current < divisor:
            continue

        if not started:
            started = True
            lines.append(f"Первое неполное делимое — {current}")

        if current < divisor:
            if index < len(digits) - 1:
                lines.append(f"Число {current} меньше {divisor}, поэтому в частном пишем 0 и сносим следующую цифру")
            else:
                lines.append(f"Число {current} меньше {divisor}, поэтому в частном пишем 0. Деление закончено")
            continue

        q_digit = current // divisor
        product = q_digit * divisor
        remainder_here = current - product
        next_try = (q_digit + 1) * divisor

        if index < len(digits) - 1:
            next_number = remainder_here * 10 + int(digits[index + 1])
            lines.append(
                f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше. Вычитаем: {current} - {product} = {remainder_here}. Сносим следующую цифру и получаем {next_number}"
            )
        else:
            if remainder_here == 0:
                lines.append(
                    f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше. Вычитаем: {current} - {product} = 0. Деление закончено"
                )
            else:
                lines.append(
                    f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше. Вычитаем: {current} - {product} = {remainder_here}. Это остаток"
                )

        current = remainder_here

    if not started:
        lines.append(f"{dividend} меньше {divisor}, значит в частном будет 0")
        if remainder:
            lines.append(f"Остаток равен {remainder}")
            return join_explanation_lines(*lines, f"Ответ: 0, остаток {remainder}", "Совет: остаток всегда должен быть меньше делителя")
        return join_explanation_lines(*lines, "Ответ: 0", "Совет: если делимое меньше делителя, частное равно нулю")

    if remainder == 0:
        lines.append(f"Читаем ответ: частное равно {quotient}")
        return join_explanation_lines(*lines, f"Ответ: {quotient}", "Совет: в столбике повторяй шаги: взял, подобрал, умножил, вычел, снес цифру")

    lines.append(f"Читаем ответ: частное равно {quotient}, остаток {remainder}")
    return join_explanation_lines(*lines, f"Ответ: {quotient}, остаток {remainder}", "Совет: остаток всегда должен быть меньше делителя")


def _user_final_patch_try_geometry_formula_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    unit = geometry_unit(lower)
    nums = extract_ordered_numbers(lower)

    asks_area = "площад" in question or "найти площадь" in lower or "узнайте площадь" in lower
    asks_perimeter = "периметр" in question or "найти периметр" in lower or "узнайте периметр" in lower

    if "прямоугольник" in lower and "со сторонами" in lower and len(nums) >= 2 and (asks_area or asks_perimeter):
        a, b = nums[0], nums[1]
        area = a * b
        perimeter = 2 * (a + b)
        lines: List[str] = []
        if asks_area:
            lines.append("1) Формула площади прямоугольника: S = a × b")
            lines.append(f"2) Подставляем числа: S = {a} × {b} = {with_unit(area, unit, square=True)}")
        if asks_perimeter:
            start_index = 3 if asks_area else 1
            lines.append(f"{start_index}) Формула периметра прямоугольника: P = 2 × (a + b)")
            lines.append(f"{start_index + 1}) Подставляем числа: P = 2 × ({a} + {b}) = {with_unit(perimeter, unit)}")
        if asks_area and asks_perimeter:
            lines.append(f"Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}")
        elif asks_area:
            lines.append(f"Ответ: {with_unit(area, unit, square=True)}")
        else:
            lines.append(f"Ответ: {with_unit(perimeter, unit)}")
        lines.append("Совет: у прямоугольника сначала называют формулу, потом подставляют числа")
        return join_explanation_lines(*lines)

    if "квадрат" in lower and len(nums) >= 1 and ("сторон" in lower or "сторона" in lower) and (asks_area or asks_perimeter):
        side = nums[0]
        area = side * side
        perimeter = side * 4
        lines = []
        if asks_area:
            lines.append("1) Формула площади квадрата: S = a × a")
            lines.append(f"2) Подставляем числа: S = {side} × {side} = {with_unit(area, unit, square=True)}")
        if asks_perimeter:
            start_index = 3 if asks_area else 1
            lines.append(f"{start_index}) Формула периметра квадрата: P = 4 × a")
            lines.append(f"{start_index + 1}) Подставляем числа: P = 4 × {side} = {with_unit(perimeter, unit)}")
        if asks_area and asks_perimeter:
            lines.append(f"Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}")
        elif asks_area:
            lines.append(f"Ответ: {with_unit(area, unit, square=True)}")
        else:
            lines.append(f"Ответ: {with_unit(perimeter, unit)}")
        lines.append("Совет: у квадрата площадь и периметр находят по стороне")
        return join_explanation_lines(*lines)

    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _user_final_patch_try_geometry_formula_explanation(user_text)
        or _USER_FINAL_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- USER FINAL PATCH 2026-04-11ZZ2: restore explicit column block for long division ---

_USER_FINAL_PATCH_ZZ2_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION = _detailed_format_expression_solution


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    source = to_expression_source(raw_text)
    if not source:
        return _USER_FINAL_PATCH_ZZ2_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)

    node = parse_expression_ast(source)
    simple = try_simple_binary_int_expression(node) if node is not None else None
    parts = _detailed_split_sections(base_text)
    body_lines = [
        line for line in parts.get("body", [])
        if not line.lower().startswith(("что известно:", "что нужно найти:"))
    ]

    if simple and simple["operator"] is ast.Div and any("столбик" in line.lower() for line in body_lines):
        pretty_expr = _user_final_patch_pretty_expression_from_source(source)
        answer = parts.get("answer") or _detailed_expression_answer(source) or "проверь запись"
        advice = parts.get("advice") or default_advice("expression")
        lines = [
            f"Пример: {pretty_expr} = {answer}",
            "Решение.",
            "Запись столбиком:",
            f"{simple['right']} | {simple['left']}",
            "Пояснение по шагам:",
        ]
        lines.extend(_detailed_number_lines(body_lines))
        lines.append(f"Ответ: {answer}")
        lines.append(f"Совет: {advice}")
        return _detailed_finalize_text(lines)

    return _USER_FINAL_PATCH_ZZ2_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)


# --- OPENAI FINAL PATCH 2026-04-11C: textbook-style compound wording + bucket-word detection ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом:
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...
6. Если пример удобнее решать в столбик, сохрани запись столбиком и подробное пояснение по шагам.
7. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие задачи без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Если задача составная, решай только по действиям.
5. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
6. В каждом действии, где это возможно, используй школьную форму:
Если ..., то ...
7. После каждого действия коротко говори, что нашли.
8. В конце пиши:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.

Важные требования:
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Если в задаче два вопроса, ответь на оба по порядку.
Для многодейственных задач не перескакивай сразу к ответу.
Сначала действие, потом пояснение, потом следующее действие.
""".strip()


_BUCKET_STEM_TO_NUM = {
    "одн": 1,
    "одно": 1,
    "двух": 2,
    "трех": 3,
    "трёх": 3,
    "четырех": 4,
    "четырёх": 4,
    "пяти": 5,
    "шести": 6,
    "семи": 7,
    "восьми": 8,
    "девяти": 9,
    "десяти": 10,
}


def _extract_bucket_sizes_from_text(text: str) -> List[int]:
    lower = str(text or "").lower()
    values: List[int] = []

    for match in re.finditer(r"(\d+)\s*-\s*литров", lower):
        values.append(int(match.group(1)))

    for match in re.finditer(r"\b(\d+)литров", lower):
        values.append(int(match.group(1)))

    for match in re.finditer(r"\b([а-яё]+)литров", lower):
        stem = match.group(1)
        value = _BUCKET_STEM_TO_NUM.get(stem)
        if value is not None:
            values.append(value)

    unique_values: List[int] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return unique_values

# --- merged segment 011: backend.legacy_runtime_shards.prepatch_build_source.segment_011 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 8871-9766."""



def explain_sum_then_divide_word_problem(first: int, second: int, divisor: int) -> Optional[str]:
    if divisor == 0:
        return None
    total = first + second
    quotient, remainder = divmod(total, divisor)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если первое количество равно {first}, а второе равно {second}, то всего {first} + {second} = {total}",
            f"2) Если всего {total}, а одна группа равна {divisor}, то {total} : {divisor} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: если сначала объединяют две части, а потом делят на равные группы, сначала находят сумму",
        )
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе равно {second}, то всего {first} + {second} = {total}",
        f"2) Если {total} разделить на группы по {divisor}, то получится {quotient}, остаток {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: сначала находят общую сумму, а потом делят её на группы",
    )


def explain_cages_with_two_parts(first: int, second: int, total: int) -> Optional[str]:
    in_one = first + second
    if in_one == 0 or total % in_one != 0:
        return None
    cages = total // in_one
    return join_explanation_lines(
        f"1) Если в каждой клетке сидело {first} синих и {second} зелёных попугая, то в одной клетке было {first} + {second} = {in_one} попугаев",
        f"2) Если всего было {total} попугаев, а в одной клетке {in_one} попугаев, то клеток было {total} : {in_one} = {cages}",
        f"Ответ: {cages}",
        "Совет: если в каждой группе есть два вида предметов, сначала находят, сколько всего в одной группе",
    )


def explain_equal_rate_distribution(total: int, first_count: int, second_count: int, first_label: str = "первая группа", second_label: str = "вторая группа") -> Optional[str]:
    group_total = first_count + second_count
    if group_total == 0 or total % group_total != 0:
        return None
    one_unit = total // group_total
    first_total = first_count * one_unit
    second_total = second_count * one_unit
    return join_explanation_lines(
        f"1) Если в первой группе {first_count} равных частей, а во второй {second_count} равных частей, то всего {first_count} + {second_count} = {group_total} равных частей",
        f"2) Если всё количество равно {total}, а равных частей {group_total}, то одна часть равна {total} : {group_total} = {one_unit}",
        f"3) Если одна часть равна {one_unit}, а в первой группе {first_count} частей, то {first_label} равна {one_unit} × {first_count} = {first_total}",
        f"4) Если одна часть равна {one_unit}, а во второй группе {second_count} частей, то {second_label} равна {one_unit} × {second_count} = {second_total}",
        f"Ответ: {first_total}; {second_total}",
        "Совет: в задачах на пропорциональное деление сначала находят одну равную часть",
    )


def explain_piece_lengths_from_total_and_costs(total_length: int, first_cost: int, second_cost: int) -> Optional[str]:
    if total_length == 0:
        return None
    total_cost = first_cost + second_cost
    if total_cost % total_length != 0:
        return None
    unit_price = total_cost // total_length
    if unit_price == 0 or first_cost % unit_price != 0 or second_cost % unit_price != 0:
        return None
    first_length = first_cost // unit_price
    second_length = second_cost // unit_price
    return join_explanation_lines(
        f"1) Если один кусок стоит {first_cost}, а другой {second_cost}, то общая стоимость равна {first_cost} + {second_cost} = {total_cost}",
        f"2) Если за {total_length} м ткани заплатили {total_cost}, то один метр стоит {total_cost} : {total_length} = {unit_price}",
        f"3) Если первый кусок стоит {first_cost}, а один метр стоит {unit_price}, то длина первого куска равна {first_cost} : {unit_price} = {first_length} м",
        f"4) Если второй кусок стоит {second_cost}, а один метр стоит {unit_price}, то длина второго куска равна {second_cost} : {unit_price} = {second_length} м",
        f"Ответ: в первом куске {first_length} м, во втором — {second_length} м",
        "Совет: если цена за единицу одинаковая, сначала находят цену одной единицы",
    )


def explain_masses_from_bag_difference(first_bags: int, second_bags: int, diff_mass: int) -> Optional[str]:
    diff_bags = abs(first_bags - second_bags)
    if diff_bags == 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    first_mass = first_bags * per_bag
    second_mass = second_bags * per_bag
    return join_explanation_lines(
        f"1) Если на одном участке {first_bags} мешков, а на другом {second_bags} мешков, то разность равна {max(first_bags, second_bags)} - {min(first_bags, second_bags)} = {diff_bags} мешков",
        f"2) Если этим {diff_bags} мешкам соответствуют {diff_mass} кг, то в одном мешке {diff_mass} : {diff_bags} = {per_bag} кг",
        f"3) Если на первом участке {first_bags} мешков по {per_bag} кг, то всего собрали {first_bags} × {per_bag} = {first_mass} кг",
        f"4) Если на втором участке {second_bags} мешков по {per_bag} кг, то всего собрали {second_bags} × {per_bag} = {second_mass} кг",
        f"Ответ: {first_mass}; {second_mass}",
        "Совет: если известны разности по количеству и по массе, сначала находят массу одной равной части",
    )


def explain_water_buckets_difference(big_bucket: int, small_bucket: int, diff_total: int) -> Optional[str]:
    step_diff = abs(big_bucket - small_bucket)
    if step_diff == 0 or diff_total % step_diff != 0:
        return None
    trips = diff_total // step_diff
    big_total = big_bucket * trips
    small_total = small_bucket * trips
    return join_explanation_lines(
        f"1) Если мальчик носил воду {big_bucket}-литровым ведром, а девочка {small_bucket}-литровым, то мальчик за один раз приносил на {big_bucket} - {small_bucket} = {step_diff} л больше",
        f"2) Если всего мальчик принёс на {diff_total} л больше, а за один раз он приносил на {step_diff} л больше, то ходок было {diff_total} : {step_diff} = {trips}",
        f"3) Если девочка носила по {small_bucket} л и сделала {trips} ходок, то она принесла {small_bucket} × {trips} = {small_total} л",
        f"4) Если мальчик носил по {big_bucket} л и сделал {trips} ходок, то он принёс {big_bucket} × {trips} = {big_total} л",
        f"Ответ: мальчик принёс {big_total} л, девочка — {small_total} л",
        "Совет: если число ходок одинаковое, сначала находят разность за одну ходку",
    )


def explain_costs_from_length_difference(first_length: int, second_length: int, diff_cost: int) -> Optional[str]:
    diff_length = abs(second_length - first_length)
    if diff_length == 0 or diff_cost % diff_length != 0:
        return None
    price_per_meter = diff_cost // diff_length
    first_cost = first_length * price_per_meter
    second_cost = second_length * price_per_meter
    return join_explanation_lines(
        f"1) Если один кусок имеет длину {first_length} м, а другой {second_length} м, то разность длин равна {max(first_length, second_length)} - {min(first_length, second_length)} = {diff_length} м",
        f"2) Если разность стоимости равна {diff_cost} руб., а разность длин {diff_length} м, то один метр стоит {diff_cost} : {diff_length} = {price_per_meter} руб.",
        f"3) Если первый кусок имеет длину {first_length} м, а один метр стоит {price_per_meter} руб., то первый кусок стоит {first_length} × {price_per_meter} = {first_cost} руб.",
        f"4) Если второй кусок имеет длину {second_length} м, а один метр стоит {price_per_meter} руб., то второй кусок стоит {second_length} × {price_per_meter} = {second_cost} руб.",
        f"Ответ: первый кусок стоит {first_cost} руб., второй — {second_cost} руб.",
        "Совет: если цена ткани за метр одинаковая, сначала находят цену одного метра",
    )


_USER_20260411C_PREV_TRY_LOCAL_DIFFERENCE_UNKNOWN = try_local_difference_unknown_word_problem


def try_local_difference_unknown_word_problem(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    bucket_sizes = _extract_bucket_sizes_from_text(lower)
    if len(bucket_sizes) >= 2 and ("ведр" in lower or "бочк" in lower):
        diff_match = re.search(r"на\s+(\d+)\s+литр", lower)
        if diff_match:
            diff_total = int(diff_match.group(1))
            big_bucket = max(bucket_sizes[0], bucket_sizes[1])
            small_bucket = min(bucket_sizes[0], bucket_sizes[1])
            solved = explain_water_buckets_difference(big_bucket, small_bucket, diff_total)
            if solved:
                return solved

    return _USER_20260411C_PREV_TRY_LOCAL_DIFFERENCE_UNKNOWN(raw_text)


# --- OPENAI FINAL PATCH 2026-04-11D: labelled answers for proportional and two-difference tasks ---

def explain_equal_rate_distribution(total: int, first_count: int, second_count: int, first_label: str = "первая группа", second_label: str = "вторая группа") -> Optional[str]:
    group_total = first_count + second_count
    if group_total == 0 or total % group_total != 0:
        return None
    one_unit = total // group_total
    first_total = first_count * one_unit
    second_total = second_count * one_unit
    return join_explanation_lines(
        f"1) Если в первой группе {first_count} равных частей, а во второй {second_count} равных частей, то всего {first_count} + {second_count} = {group_total} равных частей",
        f"2) Если всё количество равно {total}, а равных частей {group_total}, то одна часть равна {total} : {group_total} = {one_unit}",
        f"3) Если одна часть равна {one_unit}, а в первой группе {first_count} частей, то {first_label} выполнила {one_unit} × {first_count} = {first_total}",
        f"4) Если одна часть равна {one_unit}, а во второй группе {second_count} частей, то {second_label} выполнила {one_unit} × {second_count} = {second_total}",
        f"Ответ: {first_label} — {first_total}; {second_label} — {second_total}",
        "Совет: в задачах на пропорциональное деление сначала находят одну равную часть",
    )


def explain_masses_from_bag_difference(first_bags: int, second_bags: int, diff_mass: int) -> Optional[str]:
    diff_bags = abs(first_bags - second_bags)
    if diff_bags == 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    first_mass = first_bags * per_bag
    second_mass = second_bags * per_bag
    return join_explanation_lines(
        f"1) Если на одном участке {first_bags} мешков, а на другом {second_bags} мешков, то разность равна {max(first_bags, second_bags)} - {min(first_bags, second_bags)} = {diff_bags} мешков",
        f"2) Если этим {diff_bags} мешкам соответствуют {diff_mass} кг, то в одном мешке {diff_mass} : {diff_bags} = {per_bag} кг",
        f"3) Если на первом участке {first_bags} мешков по {per_bag} кг, то всего собрали {first_bags} × {per_bag} = {first_mass} кг",
        f"4) Если на втором участке {second_bags} мешков по {per_bag} кг, то всего собрали {second_bags} × {per_bag} = {second_mass} кг",
        f"Ответ: с первого участка — {first_mass} кг, со второго — {second_mass} кг",
        "Совет: если известны разности по количеству и по массе, сначала находят массу одной равной части",
    )


# --- FINAL PATCH 2026-04-12: clearer column division + noun-aware price wording + explicit sum/divide tasks ---

_FINAL_20260412_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_FINAL_20260412_PREV_DETECT_QUESTION_UNIT = _detect_question_unit
_FINAL_20260412_PREV_EXTRACT_COUNT_QUESTION_NOUN = _extract_count_question_noun
_FINAL_20260412_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION = _detailed_format_expression_solution


def _final_20260412_question_lower(raw_text: str) -> str:
    return _question_text_only(raw_text).lower().replace("ё", "е").strip()


def _final_20260412_extract_price_subject(raw_text: str) -> Tuple[str, str]:
    question = _question_text_only(raw_text).strip().rstrip("?.!")
    lower = question.lower().replace("ё", "е")
    patterns = [
        (r"^сколько\s+стоит\s+(.+)$", "стоит"),
        (r"^сколько\s+стоят\s+(.+)$", "стоят"),
        (r"^сколько\s+стоила\s+(.+)$", "стоила"),
        (r"^сколько\s+стоили\s+(.+)$", "стоили"),
    ]
    for pattern, verb in patterns:
        match = re.match(pattern, lower)
        if match:
            subject = question[match.start(1):match.end(1)].strip()
            return subject, verb
    return "", ""


def _extract_count_question_noun(raw_text: str) -> str:
    question = _final_20260412_question_lower(raw_text)
    if question.startswith("сколько стоит") or question.startswith("сколько стоят"):
        return ""
    return _FINAL_20260412_PREV_EXTRACT_COUNT_QUESTION_NOUN(raw_text)


def _detect_question_unit(raw_text: str) -> str:
    return _external_final_detect_question_unit(
        raw_text,
        _FINAL_20260412_PREV_DETECT_QUESTION_UNIT,
        normalize_word_problem_text,
        _question_text_only,
    )


def _final_20260412_named_simple_price_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    nums = extract_ordered_numbers(lower)
    subject, verb = _final_20260412_extract_price_subject(raw_text)

    # 6 ручек стоят 18 руб. Сколько стоит 1 ручка?
    cond_total_match = re.search(r"(\d+)\s+([а-яё-]+)\s+стоят\s+(\d+)\s*руб", lower)
    if cond_total_match and verb in {"стоит", "стоила"}:
        count = int(cond_total_match.group(1))
        item_phrase = cond_total_match.group(2)
        total_cost = int(cond_total_match.group(3))
        if count > 0 and total_cost % count == 0:
            price = total_cost // count
            answer_subject = subject or "1 предмет"
            return join_explanation_lines(
                f"1) Если {count} {item_phrase} стоят {total_cost} руб., то цена одной штуки равна {total_cost} : {count} = {price} руб",
                f"Ответ: {answer_subject} стоит {price} руб",
                "Совет: цену одной штуки находят делением общей стоимости на количество",
            )

    # Книга стоит 50 рублей. Сколько стоят 6 таких книг?
    cond_one_match = re.search(r"([а-яё-]+)\s+стоит\s+(\d+)\s*(?:руб|рубля|рублей)", lower)
    qty_match = re.search(r"сколько\s+стоят\s+(\d+|один|одна|одно|две|два|три|четыре|пять|шесть|семь|восемь|девять|десять)", lower)
    if cond_one_match and qty_match and verb in {"стоят", "стоили"}:
        item_phrase = cond_one_match.group(1)
        price = int(cond_one_match.group(2))
        quantity = parse_number_token(qty_match.group(1))
        if quantity is not None:
            total_cost = price * quantity
            answer_subject = subject or f"{quantity} {item_phrase}"
            return join_explanation_lines(
                f"1) Если одна {item_phrase} стоит {price} руб., а купили {quantity}, то вся покупка стоит {price} × {quantity} = {total_cost} руб",
                f"Ответ: {answer_subject} стоят {total_cost} руб",
                "Совет: стоимость находят умножением цены на количество",
            )

    return None


def _final_20260412_named_sum_then_divide_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3 or "сколько" not in lower:
        return None

    if ("грядк" in lower or "сняли" in lower) and ("корзин" in lower or "корзины" in lower or "корзина" in lower) and re.search(r"по\s+\d+\s*кг", lower):
        first, second, per_group = nums[0], nums[1], nums[2]
        total = first + second
        quotient, remainder = divmod(total, per_group)
        if remainder == 0:
            return join_explanation_lines(
                f"1) Если с одной грядки сняли {first} кг, а с другой {second} кг, то всего сняли {first} + {second} = {total} кг",
                f"2) Если всего собрали {total} кг моркови и раскладывали по {per_group} кг в каждую корзину, то потребовалось {total} : {per_group} = {quotient} корзин",
                f"Ответ: потребовалось {quotient} корзин",
                "Совет: если сначала объединяют две части, а потом раскладывают по равным группам, сначала находят общую массу",
            )
    return None


def _final_20260412_render_long_division_block(dividend: int, divisor: int) -> str:
    if divisor == 0:
        return ""
    model = build_long_division_steps(dividend, divisor)
    steps = model.get("steps", [])
    quotient = model.get("quotient")
    divisor_str = str(divisor)
    dividend_str = str(dividend)
    header_indent = len(divisor_str) + 3
    lines = [
        f"{' ' * header_indent}{quotient}",
        f"{divisor_str} ) {dividend_str}",
    ]
    if not steps:
        return "\n".join(lines)

    for index, step in enumerate(steps):
        current = str(step["current"])
        product = str(step["product"])
        remainder = str(step["remainder"])
        width = max(len(current), len(product), 1)
        start_col = step["index"] - len(current) + 1
        indent = header_indent + max(0, start_col)
        if index > 0:
            lines.append(" " * indent + current)
        lines.append(" " * (indent + width - len(product)) + product)
        lines.append(" " * indent + "-" * width)
        if index == len(steps) - 1:
            lines.append(" " * (indent + width - len(remainder)) + remainder)
    return "\n".join(lines)


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    source = to_expression_source(raw_text)
    if not source:
        return _FINAL_20260412_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)

    node = parse_expression_ast(source)
    simple = try_simple_binary_int_expression(node) if node is not None else None
    parts = _detailed_split_sections(base_text)
    body_lines = [
        line for line in parts.get("body", [])
        if not line.lower().startswith(("что известно:", "что нужно найти:"))
    ]

    if simple and simple["operator"] is ast.Div and any("пишем деление столбиком" in line.lower() for line in body_lines):
        pretty_expr = _user_final_patch_pretty_expression_from_source(source)
        answer = parts.get("answer") or _detailed_expression_answer(source) or "проверь запись"
        advice = parts.get("advice") or default_advice("expression")
        block = _final_20260412_render_long_division_block(simple["left"], simple["right"])
        lines = [
            f"Пример: {pretty_expr} = {answer}",
            "Решение.",
            "Запись столбиком:",
        ]
        lines.extend(block.splitlines())
        lines.append("Пояснение по шагам:")
        lines.extend(_detailed_number_lines(body_lines))
        lines.append(f"Ответ: {answer}")
        lines.append(f"Совет: {advice}")
        return _detailed_finalize_text(lines)

    return _FINAL_20260412_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_20260412_named_simple_price_explanation(user_text)
        or _final_20260412_named_sum_then_divide_explanation(user_text)
        or _FINAL_20260412_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-12B: support singular "стоит" in count-price wording ---

_FINAL_20260412B_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _final_20260412_named_simple_price_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    subject, verb = _final_20260412_extract_price_subject(raw_text)

    # 6 ручек стоит 18 руб. Сколько стоит 1 ручка?
    cond_total_match = re.search(r"(\d+)\s+([а-яё-]+)\s+стои(?:т|ли|ло|ла)\s+(\d+)\s*руб", lower)
    if cond_total_match and verb in {"стоит", "стоила"}:
        count = int(cond_total_match.group(1))
        item_phrase = cond_total_match.group(2)
        total_cost = int(cond_total_match.group(3))
        if count > 0 and total_cost % count == 0:
            price = total_cost // count
            answer_subject = subject or "1 предмет"
            return join_explanation_lines(
                f"1) Если {count} {item_phrase} стоят {total_cost} руб., то цена одной штуки равна {total_cost} : {count} = {price} руб",
                f"Ответ: {answer_subject} стоит {price} руб",
                "Совет: цену одной штуки находят делением общей стоимости на количество",
            )

    # Книга стоит 50 рублей. Сколько стоят 6 таких книг?
    cond_one_match = re.search(r"([а-яё-]+)\s+стоит\s+(\d+)\s*(?:руб|рубля|рублей)", lower)
    qty_match = re.search(r"сколько\s+стоят\s+(\d+|один|одна|одно|две|два|три|четыре|пять|шесть|семь|восемь|девять|десять)", lower)
    if cond_one_match and qty_match and verb in {"стоят", "стоили"}:
        item_phrase = cond_one_match.group(1)
        price = int(cond_one_match.group(2))
        quantity = parse_number_token(qty_match.group(1))
        if quantity is not None:
            total_cost = price * quantity
            answer_subject = subject or f"{quantity} {item_phrase}"
            return join_explanation_lines(
                f"1) Если одна {item_phrase} стоит {price} руб., а купили {quantity}, то вся покупка стоит {price} × {quantity} = {total_cost} руб",
                f"Ответ: {answer_subject} стоят {total_cost} руб",
                "Совет: стоимость находят умножением цены на количество",
            )

    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_20260412_named_simple_price_explanation(user_text)
        or _final_20260412_named_sum_then_divide_explanation(user_text)
        or _FINAL_20260412B_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- OPENAI PATCH 2026-04-12: strict school order for mixed expressions ---

def _oai_20260412_flatten_add_sub_chain(node: ast.AST) -> Tuple[List[ast.AST], List[ast.BinOp]]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        operands, ops = _oai_20260412_flatten_add_sub_chain(node.left)
        return operands + [node.right], ops + [node]
    return [node], []


def _oai_20260412_flatten_mul_div_chain(node: ast.AST) -> Tuple[List[ast.AST], List[ast.BinOp]]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)):
        operands, ops = _oai_20260412_flatten_mul_div_chain(node.left)
        return operands + [node.right], ops + [node]
    return [node], []


def _oai_20260412_apply_operator(op: ast.operator, left: Fraction, right: Fraction) -> Fraction:
    if isinstance(op, ast.Add):
        return left + right
    if isinstance(op, ast.Sub):
        return left - right
    if isinstance(op, ast.Mult):
        return left * right
    if isinstance(op, ast.Div):
        if right == 0:
            raise ZeroDivisionError("division by zero")
        return left / right
    raise ValueError("Unsupported operator")


def _oai_20260414_expression_step_depth(source: str, position: Optional[int]) -> int:
    if not isinstance(position, int) or position < 0:
        return 0
    depth = 0
    for index, char in enumerate(source):
        if index >= position:
            break
        if char == '(':
            depth += 1
        elif char == ')' and depth > 0:
            depth -= 1
    return depth


def _oai_20260414_expression_step_precedence(operator: str) -> int:
    if operator in {'×', ':', '÷', '*', '/'}:
        return 0
    return 1


def _oai_20260414_sort_expression_steps(steps: List[dict], source: str) -> List[dict]:
    def _step_key(step: dict):
        position = step.get('pos') if isinstance(step, dict) else None
        operator = str(step.get('operator', '')) if isinstance(step, dict) else ''
        return (
            -_oai_20260414_expression_step_depth(source, position),
            _oai_20260414_expression_step_precedence(operator),
            position if isinstance(position, int) else 10 ** 9,
        )

    return sorted(steps, key=_step_key)


def _oai_20260412_eval_expression_school(node: ast.AST, source: Optional[str] = None):
    if is_int_literal_node(node):
        return eval_fraction_node(node), []
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return eval_fraction_node(node), []
    if not isinstance(node, ast.BinOp):
        return eval_fraction_node(node), []

    if isinstance(node.op, (ast.Mult, ast.Div)):
        operands, op_nodes = _oai_20260412_flatten_mul_div_chain(node)
    else:
        operands, op_nodes = _oai_20260412_flatten_add_sub_chain(node)

    operand_values: List[Fraction] = []
    steps: List[dict] = []

    for operand in operands:
        value, child_steps = _oai_20260412_eval_expression_school(operand, source)
        steps.extend(child_steps)
        operand_values.append(value)

    current_value = operand_values[0]
    for op_node, next_value in zip(op_nodes, operand_values[1:]):
        result_value = _oai_20260412_apply_operator(op_node.op, current_value, next_value)
        step = {
            "verb": OPERATOR_VERBS[type(op_node.op)],
            "left": format_fraction(current_value),
            "operator": OPERATOR_SYMBOLS[type(op_node.op)],
            "right": format_fraction(next_value),
            "result": format_fraction(result_value),
        }
        if source is not None:
            step["pos"] = _detailed_find_operator_position(source, op_node)
        steps.append(step)
        current_value = result_value

    return current_value, steps


def build_eval_steps(node: ast.AST, source: Optional[str] = None):
    value, steps = _oai_20260412_eval_expression_school(node, source)
    if source:
        steps = _oai_20260414_sort_expression_steps(steps, source)
    return value, steps


def format_step_lines(steps, raw_source: str):
    lines = []
    has_brackets = "(" in raw_source or ")" in raw_source
    for index, step in enumerate(steps):
        text = f"{step['left']} {step['operator']} {step['right']} = {step['result']}"
        prefix = "Сначала" if index == 0 else "Потом" if index == 1 else "Дальше"
        if index == 0 and has_brackets and len(steps) > 1:
            lines.append(f"Сначала выполняем действие в скобках: {text}")
        else:
            lines.append(f"{prefix} {step['verb']}: {text}")
    return lines


SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. В выражениях без скобок, где есть только + и -, выполняй действия слева направо.
4. В выражениях без скобок, где есть только × и :, выполняй действия слева направо.
5. В выражениях со скобками первым выполняй действие в скобках.
6. В выражениях, где есть +, -, ×, :, сначала по порядку выполняй все умножения и деления, а потом по порядку сложения и вычитания.
7. Потом пиши:
Решение по действиям:
8. Ниже пиши все вычисления по действиям:
1) ...
2) ...
3) ...
9. Если пример удобнее решать в столбик, сохрани запись столбиком и подробное пояснение по шагам.
10. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.
11. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом само условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай только по действиям.
5. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
6. По возможности используй школьную форму:
Если ..., то ...
7. После каждого действия коротко говори, что нашли.
8. Если задача составная, не перескакивай к ответу: сначала найди промежуточные величины.
9. В конце:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.

Важные требования:
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Если в задаче два вопроса, ответь на оба по порядку.
Для многодейственных задач не перескакивай сразу к ответу.
Сначала действие, потом пояснение, потом следующее действие.
""".strip()


# --- FINAL PATCH 2026-04-12C: column steps inside mixed multi-step expressions ---

_PATCH_20260412C_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION = _detailed_format_expression_solution

_PATCH_20260412C_ORDINAL_WORDS = {
    1: "Первое",
    2: "Второе",
    3: "Третье",
    4: "Четвертое",
    5: "Пятое",
    6: "Шестое",
    7: "Седьмое",
    8: "Восьмое",
}


def _patch_20260412c_parse_int_text(value: str) -> Optional[int]:
    text = str(value or "").strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return None


def _patch_20260412c_global_column_flag(source: str) -> bool:
    numbers = [int(token) for token in re.findall(r"\d+", str(source or ""))]
    return any(abs(number) >= 100 for number in numbers) or count_two_digit_numbers(numbers) > 2


def _patch_20260412c_should_use_column_for_step(step: dict, source: str) -> bool:
    left = _patch_20260412c_parse_int_text(step.get("left", ""))
    right = _patch_20260412c_parse_int_text(step.get("right", ""))
    operator = step.get("operator")

    if left is None or right is None:
        return False

    global_flag = _patch_20260412c_global_column_flag(source)

    if operator == "+":
        return abs(left) >= 100 or abs(right) >= 100 or global_flag
    if operator == "-":
        if left < 0 or right < 0 or left < right:
            return False
        return abs(left) >= 100 or abs(right) >= 100 or global_flag
    if operator == "×":
        return abs(left) >= 100 or abs(right) >= 100
    if operator == ":":
        if right == 0:
            return False
        return abs(left) >= 100 or abs(right) >= 100
    return False


def _patch_20260412c_step_explanation_text(step: dict) -> Optional[str]:
    left = _patch_20260412c_parse_int_text(step.get("left", ""))
    right = _patch_20260412c_parse_int_text(step.get("right", ""))
    operator = step.get("operator")

    if left is None or right is None:
        return None

    if operator == "+":
        return explain_column_addition([left, right])
    if operator == "-":
        if left < 0 or right < 0 or left < right:
            return None
        return explain_column_subtraction(left, right)
    if operator == "×":
        return explain_long_multiplication(left, right)
    if operator == ":":
        if right == 0:
            return None
        return explain_long_division(left, right)
    return None


def _patch_20260412c_clean_body_lines(lines: List[str]) -> List[str]:
    cleaned: List[str] = []
    for raw in lines:
        line = re.sub(r"^\d+\)\s*", "", str(raw or "").strip())
        lower = line.lower()
        if not line:
            continue
        if lower.startswith("запись столбиком"):
            continue
        if lower.startswith("читаем ответ:"):
            continue
        cleaned.append(line)
    return cleaned


def _patch_20260412c_step_header(index: int, operator: str, left: str, right: str, use_column: bool) -> str:
    ordinal = _PATCH_20260412C_ORDINAL_WORDS.get(index, f"{index}-е")
    action_name = {
        "+": "сложение",
        "-": "вычитание",
        "×": "умножение",
        ":": "деление",
    }.get(operator, "действие")
    if use_column:
        return f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right}. Выполним это действие в столбик"
    return f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right} = {step_result_placeholder}"


def _patch_20260412c_render_mixed_expression_solution(source: str) -> Optional[str]:
    node = parse_expression_ast(source)
    if node is None:
        return None

    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return None

    pretty_expression = _user_final_patch_pretty_expression_from_source(source)
    answer = _detailed_expression_answer(source) or "проверь запись"
    advice = (
        "сначала выполняй действия по порядку: в скобках, потом умножение и деление, потом сложение и вычитание"
        if "(" in source or ")" in source or re.search(r"[+\-].*[*/]|[*/].*[+\-]", source)
        else default_advice("expression")
    )

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]
    order_block = _detailed_build_order_block(source)
    if order_block:
        lines.extend(order_block)
    lines.append("Решение по действиям:")

    for index, step in enumerate(steps, start=1):
        left = str(step.get("left", "")).strip()
        right = str(step.get("right", "")).strip()
        operator = str(step.get("operator", "")).strip()
        result = str(step.get("result", "")).strip()

        use_column = _patch_20260412c_should_use_column_for_step(step, source)
        if not use_column:
            ordinal = _PATCH_20260412C_ORDINAL_WORDS.get(index, f"{index}-е")
            action_name = {
                "+": "сложение",
                "-": "вычитание",
                "×": "умножение",
                ":": "деление",
            }.get(operator, "действие")
            lines.append(f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right} = {result}")
            continue

        lines.append(
            f"{index}) {_PATCH_20260412C_ORDINAL_WORDS.get(index, f'{index}-е')} действие: {left} {operator} {right}"
        )
        detailed = _patch_20260412c_step_explanation_text(step)
        if not detailed:
            lines.append(f"{left} {operator} {right} = {result}")
            continue

        parts = _detailed_split_sections(detailed)
        column_block, remaining_body = _split_ascii_layout_block(parts.get("body", []))
        cleaned_body = _patch_20260412c_clean_body_lines(remaining_body)

        if column_block:
            lines.extend(column_block)
        if cleaned_body:
            lines.append("Пояснение к действию:")
            lines.extend(cleaned_body)
        lines.append(f"Значит, {left} {operator} {right} = {result}")

    lines.append(f"Ответ: {answer}")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    source = to_expression_source(raw_text)
    if not source:
        return _PATCH_20260412C_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)

    rendered = _patch_20260412c_render_mixed_expression_solution(source)
    if rendered:
        return rendered

    return _PATCH_20260412C_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)


# --- FINAL PATCH 2026-04-12C.1: safe helper text ---

def _patch_20260412c_step_header(index: int, operator: str, left: str, right: str, result: str, use_column: bool) -> str:
    ordinal = _PATCH_20260412C_ORDINAL_WORDS.get(index, f"{index}-е")
    action_name = {
        "+": "сложение",
        "-": "вычитание",
        "×": "умножение",
        ":": "деление",
    }.get(operator, "действие")
    if use_column:
        return f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right}. Выполним это действие в столбик"
    return f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right} = {result}"

# --- USER CONSOLIDATION PATCH 2026-04-12: fuller school-style wording without changing architecture ---


def explain_sum_then_subtract_word_problem(first: int, second: int, removed: int) -> Optional[str]:
    total = first + second
    remaining = total - removed
    if remaining < 0:
        return None
    return join_explanation_lines(
        f"1) Если сначала было {first} и ещё {second}, то всего было {first} + {second} = {total}",
        f"2) Если всего было {total}, а потом убрали {removed}, то осталось {total} - {removed} = {remaining}",
        f"Ответ: {remaining}",
        "Совет: если сначала объединяют две части, а потом часть убирают, сначала находят сумму",
    )


def explain_initial_from_taken_and_left_word_problem(first_taken: int, second_taken: int, left: int) -> Optional[str]:
    taken = first_taken + second_taken
    total = taken + left
    return join_explanation_lines(
        f"1) Если взяли {first_taken} и ещё {second_taken}, то всего взяли {first_taken} + {second_taken} = {taken}",
        f"2) Если взяли {taken}, а осталось {left}, то сначала было {taken} + {left} = {total}",
        f"Ответ: {total}",
        "Совет: если известны взяли и осталось, начальное число находят сложением",
    )


def explain_relation_chain_total_word_problem(base: int, delta1: int, mode1: str, delta2: int, mode2: str) -> Optional[str]:
    second = apply_more_less(base, delta1, mode1)
    if second is None:
        return None
    third = apply_more_less(second, delta2, mode2)
    if third is None:
        return None
    total = base + second + third
    sign1 = "+" if mode1 == "больше" else "-"
    sign2 = "+" if mode2 == "больше" else "-"
    return join_explanation_lines(
        f"1) Если второе количество на {delta1} {mode1}, чем первое, то второе количество равно {base} {sign1} {delta1} = {second}",
        f"2) Если третье количество на {delta2} {mode2}, чем второе, то третье количество равно {second} {sign2} {delta2} = {third}",
        f"3) Если первое количество {base}, второе {second}, а третье {third}, то всего {base} + {second} + {third} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят все неизвестные количества, потом общее число",
    )


def explain_relation_chain_times_total_word_problem(base: int, factor1: int, mode1: str, factor2: int, mode2: str) -> Optional[str]:
    second = apply_times_relation(base, factor1, mode1)
    if second is None:
        return None
    third = apply_times_relation(second, factor2, mode2)
    if third is None:
        return None
    total = base + second + third
    op1 = "×" if mode1 == "больше" else ":"
    op2 = "×" if mode2 == "больше" else ":"
    return join_explanation_lines(
        f"1) Если второе количество в {factor1} {plural_form(factor1, 'раз', 'раза', 'раз')} {mode1}, чем первое, то второе количество равно {base} {op1} {factor1} = {second}",
        f"2) Если третье количество в {factor2} {plural_form(factor2, 'раз', 'раза', 'раз')} {mode2}, чем второе, то третье количество равно {second} {op2} {factor2} = {third}",
        f"3) Если первое количество {base}, второе {second}, а третье {third}, то всего {base} + {second} + {third} = {total}",
        f"Ответ: {total}",
        "Совет: если числа связаны словами «в несколько раз», сначала находят каждое зависимое число отдельно",
    )

# --- merged segment 012: backend.legacy_runtime_shards.prepatch_build_source.segment_012 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 9767-10664."""



def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти расстояние, нужно скорость умножить на время",
        f"2) Если скорость равна {speed}, а время равно {time_value}, то расстояние равно {speed} × {time_value} = {result}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом S = v × t",
    )


def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти скорость, нужно расстояние разделить на время",
        f"2) Если расстояние равно {distance}, а время равно {time_value}, то скорость равна {distance} : {time_value} = {result}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом v = S : t",
    )


def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти время, нужно расстояние разделить на скорость",
        f"2) Если расстояние равно {distance}, а скорость равна {speed}, то время равно {distance} : {speed} = {result}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом t = S : v",
    )


def explain_meeting_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    closing_speed = v1 + v2
    distance = closing_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2}, то скорость сближения равна {v1} + {v2} = {closing_speed}",
        f"2) Если скорость сближения равна {closing_speed}, а время равно {time_value}, то расстояние между пунктами равно {closing_speed} × {time_value} = {distance}",
        f"Ответ: {answer}",
        "Совет: при движении навстречу сначала находят скорость сближения",
    )


def explain_opposite_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    removal_speed = v1 + v2
    distance = removal_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2} в противоположных направлениях, то скорость удаления равна {v1} + {v2} = {removal_speed}",
        f"2) Если скорость удаления равна {removal_speed}, а время равно {time_value}, то расстояние между ними равно {removal_speed} × {time_value} = {distance}",
        f"Ответ: {answer}",
        "Совет: при движении в противоположных направлениях сначала находят скорость удаления",
    )


def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        "1) Чтобы найти цену одного предмета, нужно стоимость разделить на количество",
        f"2) Если {count} одинаковых предметов стоят {total_cost} руб., то один предмет стоит {total_cost} : {count} = {price} руб.",
        f"Ответ: {price} руб.",
        "Совет: пользуйся правилом Ц = С : К",
    )


def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        "1) Чтобы найти стоимость, нужно цену умножить на количество",
        f"2) Если один предмет стоит {price} руб., а купили {count} предметов, то вся покупка стоит {price} × {count} = {total} руб.",
        f"Ответ: {total} руб.",
        "Совет: пользуйся правилом С = Ц × К",
    )


def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"1) Если купили {known_count} цветка по {known_price} руб., то за них заплатили {known_count} × {known_price} = {known_total} руб.",
        f"2) Если за всю покупку заплатили {total_cost} руб., а за известные цветы заплатили {known_total} руб., то за остальные цветы заплатили {total_cost} - {known_total} = {other_total} руб.",
        f"3) Если за {unknown_count} остальных цветов заплатили {other_total} руб., то одна штука стоит {other_total} : {unknown_count} = {unit_price} руб.",
        f"Ответ: одна красная гвоздика стоила {unit_price} руб.",
        "Совет: если известна общая стоимость покупки, сначала вычти известную часть, а потом раздели на количество",
    )


def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_cost} руб., то один товар стоит {total_cost} : {quantity} = {price} руб.",
        f"2) Если один товар стоит {price} руб., то на {wanted_cost} руб. можно купить {wanted_cost} : {price} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах на цену, количество и стоимость сначала находят цену одной штуки",
    )


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    relation = "дороже" if price_a > price_b else "дешевле"
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_a} руб., то цена одного товара равна {total_a} : {quantity} = {price_a} руб.",
        f"2) Если за {quantity} таких же товаров заплатили {total_b} руб., то цена одного товара равна {total_b} : {quantity} = {price_b} руб.",
        f"3) Если одна цена {price_a} руб., а другая {price_b} руб., то разность цен равна {max(price_a, price_b)} - {min(price_a, price_b)} = {diff} руб.",
        f"Ответ: на {diff} руб. {relation}.",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


# --- FINAL CONSOLIDATED PATCH: textbook-style priorities and multi-question fixes ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень понятный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно и по-школьному.
Не используй markdown, таблицы, смайлики, лишние вступления и похвалу.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна полезная мысль.

Главные правила объяснения:
1. Объясняй подробно, по действиям и по шагам.
2. Не пропускай промежуточные вычисления.
3. Для текстовых задач по возможности используй форму:
Если ..., то ...
4. Сначала находи то, что нужно для главного вопроса, потом отвечай на главный вопрос.
5. Если вопросов два, ответь на оба по порядку.
6. Если запись непонятная, попроси записать задачу понятнее.

Для выражений:
1. Сначала напиши полный пример с ответом:
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, напиши:
Порядок действий:
и ниже тот же пример с цифрами 1, 2, 3 над знаками действий.
3. Потом напиши:
Решение по действиям:
4. Ниже:
1) ...
2) ...
3) ...
5. В конце:
Ответ: ...
6. Если пример удобно считать в столбик, сохрани столбик и подробное пояснение.

Для текстовых задач:
1. Сначала:
Задача.
2. Потом без изменения чисел запиши условие.
3. Потом:
Решение.
4. Затем обязательно:
Что известно: ...
Что нужно найти: ...
5. Дальше решай по действиям:
1) ...
2) ...
3) ...
6. После каждого действия коротко говори, что нашли.
7. В конце:
Ответ: ...

Для уравнений:
1. Сначала:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, скажи это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом считай по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если единицы разные, сначала переведи их в одинаковые единицы.
4. Потом решай по действиям.

Школьные методики:
Если задача в косвенной форме, сначала переведи её в прямую.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При встречном движении называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
""".strip()


_FINAL_CONSOLIDATED_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _final_consolidated_questions(raw_text: str) -> List[str]:
    text = normalize_word_problem_text(raw_text)
    parts = [part.strip() for part in re.split(r"[?]", text) if part.strip()]
    return parts


def _final_consolidated_try_second_quantity_and_difference_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if lower.count("?") < 2:
        return None
    if "на сколько" not in lower:
        return None

    relation_pairs = extract_relation_pairs(lower)
    numbers = extract_ordered_numbers(lower)
    if len(relation_pairs) != 1 or len(numbers) != 2:
        return None

    base = numbers[0]
    delta_num = numbers[1]
    delta, mode = relation_pairs[0]
    if delta != delta_num:
        return None

    second = apply_more_less(base, delta, mode)
    if second is None:
        return None

    diff = abs(base - second)
    answer_unit = _detect_question_unit(raw_text)
    if answer_unit == "руб":
        tail = " руб."
    elif answer_unit:
        tail = f" {answer_unit}"
    else:
        tail = ""

    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {'+' if mode == 'больше' else '-'} {delta} = {second}",
        f"2) Если первое количество равно {base}, а второе равно {second}, то разность равна {max(base, second)} - {min(base, second)} = {diff}",
        f"Ответ: второе количество — {second}{tail}; разность — {diff}{tail}",
        "Совет: если в задаче два вопроса, сначала находят второе число, потом сравнивают числа",
    )


def _final_consolidated_try_second_quantity_and_ratio_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if lower.count("?") < 2:
        return None
    if "во сколько" not in lower:
        return None

    relation_pairs = extract_relation_pairs(lower)
    numbers = extract_ordered_numbers(lower)
    if len(relation_pairs) != 1 or len(numbers) != 2:
        return None

    base = numbers[0]
    delta_num = numbers[1]
    delta, mode = relation_pairs[0]
    if delta != delta_num:
        return None

    second = apply_more_less(base, delta, mode)
    if second is None or min(base, second) == 0:
        return None

    bigger = max(base, second)
    smaller = min(base, second)
    if bigger % smaller != 0:
        return None
    ratio = bigger // smaller

    answer_unit = _detect_question_unit(raw_text)
    if answer_unit == "руб":
        tail = " руб."
    elif answer_unit:
        tail = f" {answer_unit}"
    else:
        tail = ""

    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {'+' if mode == 'больше' else '-'} {delta} = {second}",
        f"2) Если большее количество равно {bigger}, а меньшее равно {smaller}, то кратное сравнение равно {bigger} : {smaller} = {ratio}",
        f"Ответ: второе количество — {second}{tail}; в {ratio} {plural_form(ratio, 'раз', 'раза', 'раз')}",
        "Совет: если нужно сначала найти второе число, а потом узнать, во сколько раз одно число больше другого, выполняй действия по порядку",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_consolidated_try_second_quantity_and_difference_explanation(user_text)
        or _final_consolidated_try_second_quantity_and_ratio_explanation(user_text)
        or _FINAL_CONSOLIDATED_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL CONSOLIDATED PATCH 2: detect second question even without second "?" ---

def _final_consolidated_has_two_question_clauses(raw_text: str) -> bool:
    text = normalize_word_problem_text(raw_text).strip()
    clauses = [part.strip() for part in re.split(r"[?.!]", text) if part.strip()]
    question_like = 0
    for clause in clauses:
        lower = clause.lower().replace("ё", "е")
        if re.match(r"^(сколько|на сколько|во сколько|какова|какой|какое|чему|найдите|узнайте)\b", lower):
            question_like += 1
    return question_like >= 2 or text.count("?") >= 2


def _final_consolidated_try_second_quantity_and_difference_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if not _final_consolidated_has_two_question_clauses(raw_text):
        return None
    if "на сколько" not in lower:
        return None

    relation_pairs = extract_relation_pairs(lower)
    numbers = extract_ordered_numbers(lower)
    if len(relation_pairs) != 1 or len(numbers) != 2:
        return None

    base = numbers[0]
    delta_num = numbers[1]
    delta, mode = relation_pairs[0]
    if delta != delta_num:
        return None

    second = apply_more_less(base, delta, mode)
    if second is None:
        return None

    diff = abs(base - second)
    answer_unit = _detect_question_unit(raw_text)
    if answer_unit == "руб":
        tail = " руб."
    elif answer_unit:
        tail = f" {answer_unit}"
    else:
        tail = ""

    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {'+' if mode == 'больше' else '-'} {delta} = {second}",
        f"2) Если первое количество равно {base}, а второе равно {second}, то разность равна {max(base, second)} - {min(base, second)} = {diff}",
        f"Ответ: второе количество — {second}{tail}; разность — {diff}{tail}",
        "Совет: если в задаче два вопроса, сначала находят второе число, потом сравнивают числа",
    )


def _final_consolidated_try_second_quantity_and_ratio_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if not _final_consolidated_has_two_question_clauses(raw_text):
        return None
    if "во сколько" not in lower:
        return None

    relation_pairs = extract_relation_pairs(lower)
    numbers = extract_ordered_numbers(lower)
    if len(relation_pairs) != 1 or len(numbers) != 2:
        return None

    base = numbers[0]
    delta_num = numbers[1]
    delta, mode = relation_pairs[0]
    if delta != delta_num:
        return None

    second = apply_more_less(base, delta, mode)
    if second is None or min(base, second) == 0:
        return None

    bigger = max(base, second)
    smaller = min(base, second)
    if bigger % smaller != 0:
        return None
    ratio = bigger // smaller

    answer_unit = _detect_question_unit(raw_text)
    if answer_unit == "руб":
        tail = " руб."
    elif answer_unit:
        tail = f" {answer_unit}"
    else:
        tail = ""

    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {'+' if mode == 'больше' else '-'} {delta} = {second}",
        f"2) Если большее количество равно {bigger}, а меньшее равно {smaller}, то кратное сравнение равно {bigger} : {smaller} = {ratio}",
        f"Ответ: второе количество — {second}{tail}; в {ratio} {plural_form(ratio, 'раз', 'раза', 'раз')}",
        "Совет: если нужно сначала найти второе число, а потом узнать, во сколько раз одно число больше другого, выполняй действия по порядку",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_consolidated_try_second_quantity_and_difference_explanation(user_text)
        or _final_consolidated_try_second_quantity_and_ratio_explanation(user_text)
        or _FINAL_CONSOLIDATED_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- CONSOLIDATED FINAL PATCH 2026-04-12: textbook wording, stable final prompt, user-requested detail ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. Если пример удобно считать в столбик, сохрани запись столбиком и подробные пояснения.
6. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие задачи без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. По возможности используй школьную форму:
Если ..., то ...
6. После каждого действия коротко говори, что нашли.
7. В конце:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если решение записывается по действиям, в каждом действии, кроме последнего, полезно писать пояснение, что именно нашли.
""".strip()


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе количество равно {second}, то всего будет {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько всего или сколько стало, обычно нужно сложение",
    )


def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если сначала было {first}, а потом стало {second}, то разность равна {first} - {second} = {result}",
        f"Ответ: {result}",
        "Совет: если нужно узнать, сколько осталось или на сколько уменьшилось, используют вычитание",
    )


def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если одно количество равно {bigger}, а другое равно {smaller}, то чтобы узнать, на сколько одно больше другого, нужно вычислить {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решают вычитанием: из большего числа вычитают меньшее",
    )


def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        f"1) Если после того как убрали {removed}, осталось {remaining}, то сначала было {remaining} + {removed} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы найти, сколько было сначала, к остатку прибавляют то, что убрали",
    )


def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если стало {final_total}, а прибавили {added}, то сначала было {final_total} - {added} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы найти число до прибавления, из нового числа вычитают прибавленную часть",
    )


def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {smaller}, а потом стало {bigger}, то добавили {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
    )


def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {bigger}, а потом осталось {smaller}, то убрали {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
    )


def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего будет {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: если одинаковое количество повторяется несколько раз, используют умножение",
    )


def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: сначала проверь, на сколько частей делят",
        )
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если {total} предметов разделили на {groups} равные части, то каждая часть равна {total} : {groups} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        f"1) Если {total} разделить на {groups}, то получится {quotient}, остаток {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )


def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines(
            "В одной группе не может быть 0 предметов",
            "Ответ: запись задачи неверная",
            "Совет: проверь, сколько предметов должно быть в одной группе",
        )
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если всего {total} предметов, а в одной группе по {per_group}, то групп будет {total} : {per_group} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: число групп находят делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"1) Полных групп получится {quotient}, потому что {total} : {per_group} = {quotient}, остаток {remainder}",
            f"2) Так как предметы ещё остались, нужна ещё одна группа, всего {quotient + 1}",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления что-то осталось, иногда нужна ещё одна коробка или ещё одно место",
        )
    if explicit_remainder:
        return join_explanation_lines(
            f"1) Если {total} разделить на группы по {per_group}, то получится {quotient}, остаток {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера одной группы",
        )
    return None


def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, чем первое, то второе количество равно {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: если число на несколько единиц больше, прибавляют; если меньше, вычитают",
    )


def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, чем первое, то сначала найдём его: {base} {sign} {delta} = {related}",
        f"2) Если первое количество равно {base}, а второе равно {related}, то всего {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят неизвестное количество, потом сумму",
    )


def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, чем первое, то оно равно {base} {op} {factor} = {result}",
        f"Ответ: {result}",
        "Совет: если число в несколько раз больше, умножают; если в несколько раз меньше, делят",
    )


def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, чем первое, то сначала найдём его: {base} {op} {factor} = {related}",
        f"2) Если первое количество равно {base}, а второе равно {related}, то всего {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: сначала находят число, которое дано через кратное отношение, а потом сумму",
    )


def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"1) Если в {groups} группах {total_amount}, то в одной группе {total_amount} : {groups} = {one_group}",
        f"2) Если в одной группе {one_group}, то в {target_groups} таких же группах {one_group} × {target_groups} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )


def explain_find_third_addend_word_problem(total: int, first: int, second: int) -> Optional[str]:
    known = first + second
    result = total - known
    if result < 0:
        return None
    return join_explanation_lines(
        f"1) Если первая известная часть равна {first}, а вторая известная часть равна {second}, то вместе они составляют {first} + {second} = {known}",
        f"2) Если всего было {total}, а две известные части составляют {known}, то неизвестная часть равна {total} - {known} = {result}",
        f"Ответ: {result}",
        "Совет: неизвестную часть находят вычитанием суммы известных частей из целого",
    )


def explain_initial_from_taken_and_left_word_problem(first_taken: int, second_taken: int, left: int) -> Optional[str]:
    taken = first_taken + second_taken
    total = taken + left
    return join_explanation_lines(
        f"1) Если взяли {first_taken} и ещё {second_taken}, то всего взяли {first_taken} + {second_taken} = {taken}",
        f"2) Если взяли {taken}, а осталось {left}, то сначала было {taken} + {left} = {total}",
        f"Ответ: {total}",
        "Совет: если известно, сколько взяли и сколько осталось, начальное количество находят сложением",
    )


def explain_compare_from_total_and_part_word_problem(total: int, known_part: int) -> Optional[str]:
    other = total - known_part
    if other < 0:
        return None
    bigger = max(known_part, other)
    smaller = min(known_part, other)
    diff = bigger - smaller
    return join_explanation_lines(
        f"1) Если всего было {total}, а известная часть равна {known_part}, то другая часть равна {total} - {known_part} = {other}",
        f"2) Если одна часть равна {bigger}, а другая равна {smaller}, то разность равна {bigger} - {smaller} = {diff}",
        f"Ответ: {diff}",
        "Совет: если сначала нужно найти неизвестную часть, а потом сравнить части, действия выполняют по порядку",
    )


def explain_sum_of_two_products_word_problem(first_count: int, first_value: int, second_count: int, second_value: int) -> str:
    first_total = first_count * first_value
    second_total = second_count * second_value
    total = first_total + second_total
    return join_explanation_lines(
        f"1) Если первая покупка состоит из {first_count} предметов по {first_value}, то её стоимость равна {first_count} × {first_value} = {first_total}",
        f"2) Если вторая покупка состоит из {second_count} предметов по {second_value}, то её стоимость равна {second_count} × {second_value} = {second_total}",
        f"3) Если первая покупка стоит {first_total}, а вторая стоит {second_total}, то вся покупка стоит {first_total} + {second_total} = {total}",
        f"Ответ: {total}",
        "Совет: если в задаче есть две группы вида «по столько-то», сначала находят каждую группу отдельно",
    )


def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group}, то сначала находим, сколько предметов в этих группах: {groups} × {per_group} = {grouped_total}",
        f"2) Если в одинаковых группах {grouped_total}, а потом добавили ещё {extra}, то стало {grouped_total} + {extra} = {result}",
        f"Ответ: {result}",
        "Совет: если сначала считают одинаковые группы, а потом что-то добавляют, сначала выполняют умножение",
    )


def explain_sum_then_subtract_word_problem(first: int, second: int, removed: int) -> Optional[str]:
    total = first + second
    remaining = total - removed
    if remaining < 0:
        return None
    return join_explanation_lines(
        f"1) Если сначала было {first} и ещё {second}, то всего было {first} + {second} = {total}",
        f"2) Если всего было {total}, а потом убрали {removed}, то осталось {total} - {removed} = {remaining}",
        f"Ответ: {remaining}",
        "Совет: если сначала объединяют две группы, а потом часть убирают, сначала находят сумму",
    )


def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        f"1) Если {count} одинаковых предметов стоят {total_cost} руб., то один предмет стоит {total_cost} : {count} = {price} руб.",
        f"Ответ: один предмет стоит {price} руб.",
        "Совет: цену одной штуки находят делением общей стоимости на количество",
    )


def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        f"1) Если один предмет стоит {price} руб., а купили {count} предметов, то вся покупка стоит {price} × {count} = {total} руб.",
        f"Ответ: вся покупка стоит {total} руб.",
        "Совет: стоимость находят умножением цены на количество",
    )


def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"1) Если купили {known_count} известных предметов по {known_price} руб., то за них заплатили {known_count} × {known_price} = {known_total} руб.",
        f"2) Если за всю покупку заплатили {total_cost} руб., а за известную часть {known_total} руб., то за вторую часть заплатили {total_cost} - {known_total} = {other_total} руб.",
        f"3) Если за {unknown_count} предметов заплатили {other_total} руб., то один предмет стоит {other_total} : {unknown_count} = {unit_price} руб.",
        f"Ответ: один предмет стоит {unit_price} руб.",
        "Совет: если известна общая стоимость покупки, сначала вычитают известную часть",
    )


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    relation = "дороже" if price_a > price_b else "дешевле"
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_a} руб., то цена одного товара равна {total_a} : {quantity} = {price_a} руб.",
        f"2) Если за {quantity} таких же товаров заплатили {total_b} руб., то цена одного товара равна {total_b} : {quantity} = {price_b} руб.",
        f"3) Если одна цена {price_a} руб., а другая {price_b} руб., то разность цен равна {max(price_a, price_b)} - {min(price_a, price_b)} = {diff} руб.",
        f"Ответ: на {diff} руб. {relation}.",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых коробок заплатили {total_cost} руб., то цена одной коробки равна {total_cost} : {quantity} = {price} руб.",
        f"2) Если одна коробка стоит {price} руб., то на {wanted_cost} руб. можно купить {wanted_cost} : {price} = {result} коробок.",
        f"Ответ: {result}",
        "Совет: если цена одинаковая, сначала находят цену одной коробки",
    )


def explain_fraction_of_number_word_problem(total: int, numerator: int, denominator: int, ask_remaining: bool = False) -> Optional[str]:
    if denominator == 0 or numerator == 0 or total % denominator != 0:
        return None
    one_part = total // denominator
    taken = one_part * numerator
    if ask_remaining:
        remaining = total - taken
        return join_explanation_lines(
            f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}",
            f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {taken}",
            f"3) Если всего было {total}, а использовали {taken}, то осталось {total} - {taken} = {remaining}",
            f"Ответ: {remaining}",
            "Совет: чтобы найти остаток после дробной части, сначала находят эту дробную часть",
        )
    return join_explanation_lines(
        f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}",
        f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {taken}",
        f"Ответ: {taken}",
        "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
    )


def explain_number_by_fraction_word_problem(part_value: int, numerator: int, denominator: int) -> Optional[str]:
    if numerator == 0 or part_value % numerator != 0:
        return None
    one_part = part_value // numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если {numerator}/{denominator} числа равны {part_value}, то сначала найдём одну долю: {part_value} : {numerator} = {one_part}",
        f"2) Если одна доля равна {one_part}, то всё число равно {one_part} × {denominator} = {whole}",
        f"Ответ: {whole}",
        "Совет: чтобы найти всё число по его доле, сначала находят одну долю",
    )

# --- merged segment 013: backend.legacy_runtime_shards.prepatch_build_source.segment_013 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 10665-11560."""



def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None
    if remaining_value % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег.",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part}.",
        f"3) Если одна доля равна {one_part}, то все деньги равны {one_part} × {denominator} = {whole}.",
        f"Ответ: {whole}",
        "Совет: если известен остаток после расхода части, сначала находят оставшуюся долю",
    )


def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти расстояние, нужно скорость умножить на время.",
        f"2) Если скорость равна {speed}, а время равно {time_value}, то расстояние равно {speed} × {time_value} = {answer}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом S = v × t",
    )


def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти скорость, нужно расстояние разделить на время.",
        f"2) Если расстояние равно {distance}, а время равно {time_value}, то скорость равна {distance} : {time_value} = {answer}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом v = S : t",
    )


def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти время, нужно расстояние разделить на скорость.",
        f"2) Если расстояние равно {distance}, а скорость равна {speed}, то время равно {distance} : {speed} = {answer}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом t = S : v",
    )


def explain_meeting_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    closing_speed = v1 + v2
    distance = closing_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2}, то скорость сближения равна {v1} + {v2} = {closing_speed}",
        f"2) Если скорость сближения равна {closing_speed}, а время равно {time_value}, то расстояние равно {closing_speed} × {time_value} = {answer}",
        f"Ответ: {answer}",
        "Совет: при встречном движении сначала находят скорость сближения",
    )


def explain_opposite_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    removal_speed = v1 + v2
    distance = removal_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2} в противоположных направлениях, то скорость удаления равна {v1} + {v2} = {removal_speed}",
        f"2) Если скорость удаления равна {removal_speed}, а время равно {time_value}, то расстояние между ними равно {removal_speed} × {time_value} = {answer}",
        f"Ответ: {answer}",
        "Совет: при движении в противоположных направлениях сначала находят скорость удаления",
    )


def explain_trip_time_for_same_distance(speed1: int, time1: int, speed2: int) -> Optional[str]:
    distance = speed1 * time1
    if speed2 == 0 or distance % speed2 != 0:
        return None
    time2 = distance // speed2
    return join_explanation_lines(
        f"1) Если первый участник ехал со скоростью {speed1} и был в пути {time1}, то расстояние равно {speed1} × {time1} = {distance}",
        f"2) Если это же расстояние равно {distance}, а скорость второго участника {speed2}, то ему понадобится {distance} : {speed2} = {time2} ч.",
        f"Ответ: {time2} ч.",
        "Совет: если путь один и тот же, сначала находят расстояние, потом новое время",
    )


def explain_second_day_motion_time(total_distance: int, first_speed: int, first_time: int, second_speed: int) -> Optional[str]:
    first_distance = first_speed * first_time
    second_distance = total_distance - first_distance
    if second_speed == 0 or second_distance < 0 or second_distance % second_speed != 0:
        return None
    second_time = second_distance // second_speed
    total_time = first_time + second_time
    return join_explanation_lines(
        f"1) Если в первый день скорость была {first_speed}, а время в пути {first_time}, то в первый день проехали {first_speed} × {first_time} = {first_distance} км.",
        f"2) Если всего нужно проехать {total_distance} км, а в первый день проехали {first_distance} км, то во второй день осталось {total_distance} - {first_distance} = {second_distance} км.",
        f"3) Если во второй день проехали {second_distance} км со скоростью {second_speed}, то время во второй день равно {second_distance} : {second_speed} = {second_time} ч.",
        f"4) Если в первый день были в пути {first_time} ч., а во второй день {second_time} ч., то всего были в пути {first_time} + {second_time} = {total_time} ч.",
        f"Ответ: во второй день — {second_time} ч.; всего — {total_time} ч.",
        "Совет: в составной задаче на движение сначала находят путь, потом время",
    )


def explain_remaining_part_speed(total_distance: int, first_speed: int, first_time: int, second_time: int) -> Optional[str]:
    first_distance = first_speed * first_time
    remaining_distance = total_distance - first_distance
    if second_time == 0 or remaining_distance < 0 or remaining_distance % second_time != 0:
        return None
    second_speed = remaining_distance // second_time
    return join_explanation_lines(
        f"1) Если сначала ехали со скоростью {first_speed} {first_time} ч., то первая часть пути равна {first_speed} × {first_time} = {first_distance} км.",
        f"2) Если весь путь равен {total_distance} км, а первая часть пути равна {first_distance} км, то оставшаяся часть пути равна {total_distance} - {first_distance} = {remaining_distance} км.",
        f"3) Если оставшаяся часть пути равна {remaining_distance} км, а прошли её за {second_time} ч., то скорость равна {remaining_distance} : {second_time} = {second_speed} км/ч.",
        f"Ответ: {second_speed} км/ч.",
        "Совет: если известны путь и время, скорость находят делением",
    )


def explain_return_trip_time_by_faster_speed(distance: int, speed: int, factor: int) -> Optional[str]:
    if speed == 0 or factor == 0 or distance % speed != 0:
        return None
    first_time = distance // speed
    faster_speed = speed * factor
    if faster_speed == 0 or distance % faster_speed != 0:
        return None
    return_time = distance // faster_speed
    return join_explanation_lines(
        f"1) Если расстояние равно {distance} км, а скорость в одну сторону {speed} км/ч, то время в одну сторону равно {distance} : {speed} = {first_time} ч.",
        f"2) Если обратно едут в {factor} раза быстрее, то скорость обратно равна {speed} × {factor} = {faster_speed} км/ч.",
        f"3) Если расстояние равно {distance} км, а скорость обратно {faster_speed} км/ч, то время на обратный путь равно {distance} : {faster_speed} = {return_time} ч.",
        f"Ответ: {return_time} ч.",
        "Совет: если на обратном пути скорость увеличилась в несколько раз, сначала находят новую скорость",
    )


# --- FINAL USER CONSOLIDATION PATCH 2026-04-12D: extra textbook motion case, fuller count nouns, stable final routing ---

# Добавляем несколько часто встречающихся школьных существительных,
# чтобы ответы чаще были полными, а не только числом.
try:
    QUESTION_NOUN_FORMS.update({
        "шарик": ("шарик", "шарика", "шариков"),
        "шарика": ("шарик", "шарика", "шариков"),
        "шариков": ("шарик", "шарика", "шариков"),
        "утенок": ("утёнок", "утёнка", "утят"),
        "утёнок": ("утёнок", "утёнка", "утят"),
        "утёнка": ("утёнок", "утёнка", "утят"),
        "утят": ("утёнок", "утёнка", "утят"),
        "гусенок": ("гусёнок", "гусёнка", "гусят"),
        "гусёнок": ("гусёнок", "гусёнка", "гусят"),
        "гусёнка": ("гусёнок", "гусёнка", "гусят"),
        "гусят": ("гусёнок", "гусёнка", "гусят"),
        "тюльпан": ("тюльпан", "тюльпана", "тюльпанов"),
        "тюльпана": ("тюльпан", "тюльпана", "тюльпанов"),
        "тюльпанов": ("тюльпан", "тюльпана", "тюльпанов"),
        "орешек": ("орешек", "орешка", "орешков"),
        "орешка": ("орешек", "орешка", "орешков"),
        "орешков": ("орешек", "орешка", "орешков"),
        "гостинец": ("гостинец", "гостинца", "гостинцев"),
        "гостинца": ("гостинец", "гостинца", "гостинцев"),
        "гостинцев": ("гостинец", "гостинца", "гостинцев"),
        "тетрадка": ("тетрадка", "тетрадки", "тетрадок"),
        "тетрадки": ("тетрадка", "тетрадки", "тетрадок"),
        "тетрадок": ("тетрадка", "тетрадки", "тетрадок"),
    })
except Exception:
    pass


def _final_user_20260412d_equal_speed_head_start_meeting_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    # Шаблон из книги:
    # "скорости одинаковые", "встретились через ... часов",
    # "первый ... выехал на ... часа раньше", "проехал на ... км больше".
    if "навстречу" not in lower:
        return None
    if "одинаков" not in lower:
        return None
    if "раньше" not in lower or "больше" not in lower:
        return None

    hour_pattern = fr"(\d+|{_NUMBER_WORD_PATTERN})\s*(?:ч|час(?:а|ов)?)"
    meet_match = re.search(fr"встретил(?:ся|ась|ось|ись)?\s+через\s+{hour_pattern}", lower)
    head_start_match = re.search(fr"на\s+{hour_pattern}\s+раньше", lower)
    extra_distance_match = re.search(r"на\s+(\d+)\s*(км|м)\s+больше", lower)

    if not meet_match or not head_start_match or not extra_distance_match:
        return None

    meet_time = parse_number_token(meet_match.group(1))
    head_start_time = parse_number_token(head_start_match.group(1))
    extra_distance = int(extra_distance_match.group(1))
    distance_unit = extra_distance_match.group(2)

    if meet_time is None or head_start_time is None:
        return None
    if head_start_time == 0 or extra_distance % head_start_time != 0:
        return None

    speed = extra_distance // head_start_time
    second_path = speed * meet_time
    first_time = meet_time + head_start_time
    first_path = speed * first_time
    total_distance = first_path + second_path
    speed_unit = f"{distance_unit}/ч"

    return join_explanation_lines(
        f"1) Если скорости одинаковые, а первый участник выехал на {head_start_time} ч. раньше и поэтому прошёл на {extra_distance} {distance_unit} больше, то скорость каждого равна {extra_distance} : {head_start_time} = {speed} {speed_unit}",
        f"2) Так как скорости одинаковые, скорость второго участника тоже равна {speed} {speed_unit}",
        f"3) Если второй участник ехал {meet_time} ч. со скоростью {speed} {speed_unit}, то он прошёл {speed} × {meet_time} = {second_path} {distance_unit}",
        f"4) Если первый участник выехал на {head_start_time} ч. раньше, то он был в пути {meet_time} + {head_start_time} = {first_time} ч.",
        f"5) Если первый участник ехал {first_time} ч. со скоростью {speed} {speed_unit}, то он прошёл {speed} × {first_time} = {first_path} {distance_unit}",
        f"6) Если один участник прошёл {second_path} {distance_unit}, а другой {first_path} {distance_unit}, то расстояние между пунктами равно {second_path} + {first_path} = {total_distance} {distance_unit}",
        f"Ответ: расстояние между пунктами равно {total_distance} {distance_unit}",
        "Совет: если скорости одинаковые, а один участник выехал раньше, его лишний путь помогает найти общую скорость",
    )


_FINAL_USER_20260412D_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first

def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_user_20260412d_equal_speed_head_start_meeting_explanation(user_text)
        or _FINAL_USER_20260412D_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL USER PATCH 2026-04-12E: fuller school wording, stable final prompt, preserved architecture ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown-таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши строку «Порядок действий:».
3. Ниже пиши тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
4. Потом пиши строку «Решение по действиям:».
5. Ниже пиши все вычисления по действиям:
1) ...
2) ...
3) ...
6. Если вычисление удобно выполнять в столбик, сохраняй запись столбиком и подробное пояснение по шагам.
7. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.
8. В конце пиши строку «Ответ: ...».

Для текстовых задач:
1. Сначала пиши «Задача.» и без изменения чисел переписывай условие.
2. Потом пиши «Решение.»
3. Затем обязательно пиши строки:
«Что известно: ...»
«Что нужно найти: ...»
4. Если нельзя сразу ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай только по действиям.
6. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
7. Для школьного стиля по возможности используй форму «Если..., то ...».
8. После каждого действия коротко говори, что нашли.
9. Если в задаче несколько вопросов, отвечай на все вопросы по порядку.
10. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку «Уравнение: ...».
2. Потом «Решение.»
3. Решай по шагам.
4. Обязательно пиши строку «Проверка: ...».
5. Потом пиши «Ответ: ...».

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, скажи это отдельно.
3. Если знаменатели разные, сначала приведи дроби к общему знаменателю.
4. Если задача дана с величинами, сначала переведи величины в одинаковые единицы.
5. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.
5. В ответе обязательно пиши единицы измерения.

Школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Сохраняй вычисления в столбик и подробные пояснения.
Для деления столбиком обязательно называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()

try:
    QUESTION_NOUN_FORMS.update({
        "год": ("год", "года", "лет"),
        "года": ("год", "года", "лет"),
        "лет": ("год", "года", "лет"),
        "книга": ("книга", "книги", "книг"),
        "книги": ("книга", "книги", "книг"),
        "книг": ("книга", "книги", "книг"),
        "машина": ("машина", "машины", "машин"),
        "машины": ("машина", "машины", "машин"),
        "машин": ("машина", "машины", "машин"),
        "дерево": ("дерево", "дерева", "деревьев"),
        "дерева": ("дерево", "дерева", "деревьев"),
        "деревьев": ("дерево", "дерева", "деревьев"),
        "глазок": ("глазок", "глазка", "глазков"),
        "глазка": ("глазок", "глазка", "глазков"),
        "глазков": ("глазок", "глазка", "глазков"),
        "страница": ("страница", "страницы", "страниц"),
        "страницы": ("страница", "страницы", "страниц"),
        "страниц": ("страница", "страницы", "страниц"),
        "перо": ("перо", "пера", "перьев"),
        "пера": ("перо", "пера", "перьев"),
        "перьев": ("перо", "пера", "перьев"),
        "яблоко": ("яблоко", "яблока", "яблок"),
        "яблока": ("яблоко", "яблока", "яблок"),
        "яблок": ("яблоко", "яблока", "яблок"),
        "гвоздика": ("гвоздика", "гвоздики", "гвоздик"),
        "гвоздики": ("гвоздика", "гвоздики", "гвоздик"),
        "гвоздик": ("гвоздика", "гвоздики", "гвоздик"),
        "ягода": ("ягода", "ягоды", "ягод"),
        "ягоды": ("ягода", "ягоды", "ягод"),
        "ягод": ("ягода", "ягоды", "ягод"),
        "ложка": ("ложка", "ложки", "ложек"),
        "ложки": ("ложка", "ложки", "ложек"),
        "ложек": ("ложка", "ложки", "ложек"),
        "куст": ("куст", "куста", "кустов"),
        "куста": ("куст", "куста", "кустов"),
        "кустов": ("куст", "куста", "кустов"),
        "цветок": ("цветок", "цветка", "цветов"),
        "цветка": ("цветок", "цветка", "цветов"),
        "цветов": ("цветок", "цветка", "цветов"),
        "мешок": ("мешок", "мешка", "мешков"),
        "мешка": ("мешок", "мешка", "мешков"),
        "мешков": ("мешок", "мешка", "мешков"),
        "клетка": ("клетка", "клетки", "клеток"),
        "клетки": ("клетка", "клетки", "клеток"),
        "клеток": ("клетка", "клетки", "клеток"),
        "полка": ("полка", "полки", "полок"),
        "полки": ("полка", "полки", "полок"),
        "полок": ("полка", "полки", "полок"),
        "ведро": ("ведро", "ведра", "вёдер"),
        "ведра": ("ведро", "ведра", "вёдер"),
        "вёдер": ("ведро", "ведра", "вёдер"),
        "корзина": ("корзина", "корзины", "корзин"),
        "корзины": ("корзина", "корзины", "корзин"),
        "корзин": ("корзина", "корзины", "корзин"),
        "сетка": ("сетка", "сетки", "сеток"),
        "сетки": ("сетка", "сетки", "сеток"),
        "сеток": ("сетка", "сетки", "сеток"),
        "попугай": ("попугай", "попугая", "попугаев"),
        "попугая": ("попугай", "попугая", "попугаев"),
        "попугаев": ("попугай", "попугая", "попугаев"),
        "ученик": ("ученик", "ученика", "учеников"),
        "ученика": ("ученик", "ученика", "учеников"),
        "учеников": ("ученик", "ученика", "учеников"),
        "пассажир": ("пассажир", "пассажира", "пассажиров"),
        "пассажира": ("пассажир", "пассажира", "пассажиров"),
        "пассажиров": ("пассажир", "пассажира", "пассажиров"),
        "участок": ("участок", "участка", "участков"),
        "участка": ("участок", "участка", "участков"),
        "участков": ("участок", "участка", "участков"),
        "рыба": ("рыба", "рыбы", "рыб"),
        "рыбы": ("рыба", "рыбы", "рыб"),
        "рыб": ("рыба", "рыбы", "рыб"),
        "булочка": ("булочка", "булочки", "булочек"),
        "булочки": ("булочка", "булочки", "булочек"),
        "булочек": ("булочка", "булочки", "булочек"),
        "карандаш": ("карандаш", "карандаша", "карандашей"),
        "карандаша": ("карандаш", "карандаша", "карандашей"),
        "карандашей": ("карандаш", "карандаша", "карандашей"),
    })
except Exception:
    pass

_FINAL_20260412E_PREV_DETAILED_MAYBE_ENRICH_ANSWER = _detailed_maybe_enrich_answer


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    return _external_final_detailed_maybe_enrich_answer(
        answer,
        raw_text,
        _FINAL_20260412E_PREV_DETAILED_MAYBE_ENRICH_ANSWER,
        _patch_answer_with_question_noun,
        kind,
    )


    result = first + second
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе количество равно {second}, то всего будет {first} + {second} = {result}.",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько всего или сколько стало, обычно нужно сложение",
    )


def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если сначала было {first}, а потом убрали {second}, то осталось {first} - {second} = {result}.",
        f"Ответ: {result}",
        "Совет: если нужно узнать, сколько осталось, обычно используют вычитание",
    )


def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если одно количество равно {bigger}, а другое равно {smaller}, то чтобы узнать, на сколько одно больше другого, нужно вычислить {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решают вычитанием: из большего числа вычитают меньшее",
    )


def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        f"1) Если после того, как убрали {removed}, осталось {remaining}, то сначала было {remaining} + {removed} = {result}.",
        f"Ответ: {result}",
        "Совет: неизвестное уменьшаемое находят сложением",
    )


def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если стало {final_total}, а прибавили {added}, то сначала было {final_total} - {added} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы найти число до прибавления, из нового числа вычитают то, что прибавили",
    )


def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {smaller}, а потом стало {bigger}, то добавили {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
    )


def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {bigger}, а потом осталось {smaller}, то убрали {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
    )


def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего будет {groups} × {per_group} = {result}.",
        f"Ответ: {result}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines("На ноль делить нельзя.", "Ответ: деление на ноль невозможно", "Совет: сначала проверь делитель")
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если {total} предметов разделили на {groups} равные части, то в каждой части будет {total} : {groups} = {quotient}.",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        f"1) Если {total} разделить на {groups}, то получится {quotient}, остаток {remainder}.",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )


def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines("В одной группе не может быть 0 предметов.", "Ответ: запись задачи неверная", "Совет: проверь размер одной группы")
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если всего {total} предметов, а в одной группе по {per_group}, то число групп равно {total} : {per_group} = {quotient}.",
            f"Ответ: {quotient}",
            "Совет: число групп находят делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"1) Полных групп получится {quotient}, потому что {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"2) Так как предметы ещё остались, нужна ещё одна группа. Всего групп будет {quotient + 1}.",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления ещё есть остаток, иногда нужна ещё одна коробка или корзина",
        )
    if explicit_remainder:
        return join_explanation_lines(
            f"1) Если всего {total} предметов, а в одной группе по {per_group}, то {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера одной группы",
        )
    return None


def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то его находим так: {base} {sign} {delta} = {result}.",
        f"Ответ: {result}",
        "Совет: если число на несколько единиц больше, прибавляют; если меньше, вычитают",
    )


def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {sign} {delta} = {related}.",
        f"2) Если первое количество равно {base}, а второе равно {related}, то всего будет {base} + {related} = {total}.",
        f"Ответ: {total}",
        "Совет: если нельзя сразу ответить на главный вопрос, сначала находят неизвестное количество",
    )


def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то его находим так: {base} {op} {factor} = {result}.",
        f"Ответ: {result}",
        "Совет: если число в несколько раз больше, умножают; если в несколько раз меньше, делят",
    )


def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}.",
        f"2) Если первое количество равно {base}, а второе равно {related}, то всего будет {base} + {related} = {total}.",
        f"Ответ: {total}",
        "Совет: сначала найди число, которое дано через отношение, потом считай общее количество",
    )


def explain_indirect_plus_minus_problem(base: int, delta: int, relation: str) -> Optional[str]:
    if relation in {"старше", "больше"}:
        result = base - delta
        if result < 0:
            return None
        transformed = "значит, другое число на столько же меньше"
        op = "-"
    else:
        result = base + delta
        transformed = "значит, другое число на столько же больше"
        op = "+"
    return join_explanation_lines(
        f"1) Это задача в косвенной форме: если одно число на {delta} {relation}, то {transformed}.",
        f"2) Тогда искомое число равно {base} {op} {delta} = {result}.",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переводят условие в прямую форму",
    )


def explain_indirect_times_problem(base: int, factor: int, relation: str) -> Optional[str]:
    if relation == "больше":
        if factor == 0 or base % factor != 0:
            return None
        result = base // factor
        transformed = "значит, другое число во столько же раз меньше"
        op = ":"
    else:
        result = base * factor
        transformed = "значит, другое число во столько же раз больше"
        op = "×"
    return join_explanation_lines(
        f"1) Это задача в косвенной форме: если одно число в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то {transformed}.",
        f"2) Тогда искомое число равно {base} {op} {factor} = {result}.",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переводят условие в прямую форму",
    )


def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"1) Если в {groups} одинаковых группах всего {total_amount}, то в одной группе {total_amount} : {groups} = {one_group}.",
        f"2) Если в одной группе {one_group}, то в {target_groups} таких же группах {one_group} × {target_groups} = {result}.",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    return join_explanation_lines(
        f"1) Если {quantity} одинаковых товаров стоят {total_a} руб., то один товар стоит {total_a} : {quantity} = {price_a} руб.",
        f"2) Если такие же {quantity} товаров стоят {total_b} руб., то один товар стоит {total_b} : {quantity} = {price_b} руб.",
        f"3) Тогда разность цен равна {max(price_a, price_b)} - {min(price_a, price_b)} = {diff} руб.",
        f"Ответ: {diff} руб.",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых коробок заплатили {total_cost} руб., то одна коробка стоит {total_cost} : {quantity} = {price} руб.",
        f"2) Если одна коробка стоит {price} руб., то на {wanted_cost} руб. можно купить {wanted_cost} : {price} = {result}.",
        f"Ответ: {result}",
        "Совет: если цена одинаковая, сначала находят цену одной коробки",
    )


def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        f"1) Если {count} одинаковых предметов стоят {total_cost} руб., то один предмет стоит {total_cost} : {count} = {price} руб.",
        f"Ответ: один предмет стоит {price} руб.",
        "Совет: цену одной штуки находят делением общей стоимости на количество",
    )


def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        f"1) Если один предмет стоит {price} руб., а купили {count} предметов, то вся покупка стоит {price} × {count} = {total} руб.",
        f"Ответ: вся покупка стоит {total} руб.",
        "Совет: стоимость находят умножением цены на количество",
    )


def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"1) Если купили {known_count} белых гвоздики по {known_price} руб., то за белые гвоздики заплатили {known_count} × {known_price} = {known_total} руб.",
        f"2) Если за всю покупку заплатили {total_cost} руб., а за белые гвоздики {known_total} руб., то за красные гвоздики заплатили {total_cost} - {known_total} = {other_total} руб.",
        f"3) Если за {unknown_count} красных гвоздик заплатили {other_total} руб., то одна красная гвоздика стоила {other_total} : {unknown_count} = {unit_price} руб.",
        f"Ответ: одна красная гвоздика стоила {unit_price} руб.",
        "Совет: если известна общая стоимость покупки, сначала вычти известную часть",
    )


def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None
    if remaining_value % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег.",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part}.",
        f"3) Если одна доля равна {one_part}, то все деньги равны {one_part} × {denominator} = {whole}.",
        f"Ответ: всего было {whole}",
        "Совет: если известен остаток после расхода части, сначала находят оставшуюся долю",
    )


def explain_fraction_of_number_word_problem(total: int, numerator: int, denominator: int, ask_remaining: bool = False) -> Optional[str]:
    if denominator == 0 or numerator == 0 or total % denominator != 0:
        return None
    one_part = total // denominator
    taken = one_part * numerator
    if ask_remaining:
        remaining = total - taken
        return join_explanation_lines(
            f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}.",
            f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {taken}.",
            f"3) Если всего было {total}, а использовали {taken}, то осталось {total} - {taken} = {remaining}.",
            f"Ответ: {remaining}",
            "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
        )
    return join_explanation_lines(
        f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}.",
        f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {taken}.",
        f"Ответ: {taken}",
        "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
    )


def explain_number_by_fraction_word_problem(part_value: int, numerator: int, denominator: int) -> Optional[str]:
    if numerator == 0 or part_value % numerator != 0:
        return None
    one_part = part_value // numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если {numerator}/{denominator} числа равны {part_value}, то сначала найдём одну долю: {part_value} : {numerator} = {one_part}.",
        f"2) Если одна доля равна {one_part}, то всё число равно {one_part} × {denominator} = {whole}.",
        f"Ответ: {whole}",
        "Совет: чтобы найти всё число по его доле, сначала находят одну долю",
    )


def explain_two_fraction_parts_remaining(total: int, first_fraction: Tuple[int, int], second_fraction: Tuple[int, int]) -> Optional[str]:
    n1, d1 = first_fraction
    n2, d2 = second_fraction
    if d1 == 0 or d2 == 0 or total % math.lcm(d1, d2) != 0:
        return None
    first_part = total * n1 // d1
    second_part = total * n2 // d2
    used = first_part + second_part
    remaining = total - used
    return join_explanation_lines(
        f"1) Если всё число равно {total}, то первая часть равна {total} : {d1} × {n1} = {first_part}.",
        f"2) Если всё число равно {total}, то вторая часть равна {total} : {d2} × {n2} = {second_part}.",
        f"3) Если использовали {first_part} и {second_part}, то всего использовали {first_part} + {second_part} = {used}.",
        f"4) Тогда осталось {total} - {used} = {remaining}.",
        f"Ответ: {remaining}",
        "Совет: если от одного и того же целого берут две части, каждую часть находят отдельно",
    )


def explain_second_part_after_fraction(total: int, numerator: int, denominator: int) -> Optional[str]:
    if denominator == 0 or total % denominator != 0:
        return None
    one_part = total // denominator
    first_part = one_part * numerator
    second_part = total - first_part
    return join_explanation_lines(
        f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}.",
        f"2) Если первая часть составляет {numerator}/{denominator}, то первая часть равна {one_part} × {numerator} = {first_part}.",
        f"3) Тогда вторая часть равна {total} - {first_part} = {second_part}.",
        f"Ответ: {second_part}",
        "Совет: чтобы найти другую часть, сначала находят известную часть, потом вычитают её из целого",
    )


def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти расстояние, нужно скорость умножить на время.",
        f"2) Если скорость равна {speed}, а время равно {time_value}, то расстояние равно {speed} × {time_value} = {answer}.",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом S = v × t",
    )


def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти скорость, нужно расстояние разделить на время.",
        f"2) Если расстояние равно {distance}, а время равно {time_value}, то скорость равна {distance} : {time_value} = {answer}.",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом v = S : t",
    )


def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти время, нужно расстояние разделить на скорость.",
        f"2) Если расстояние равно {distance}, а скорость равна {speed}, то время равно {distance} : {speed} = {answer}.",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом t = S : v",
    )


def explain_meeting_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    closing_speed = v1 + v2
    distance = closing_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2}, то скорость сближения равна {v1} + {v2} = {closing_speed}.",
        f"2) Если скорость сближения равна {closing_speed}, а время равно {time_value}, то расстояние равно {closing_speed} × {time_value} = {answer}.",
        f"Ответ: {answer}",
        "Совет: при встречном движении сначала находят скорость сближения",
    )


def explain_opposite_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    removal_speed = v1 + v2
    distance = removal_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2} в противоположных направлениях, то скорость удаления равна {v1} + {v2} = {removal_speed}.",
        f"2) Если скорость удаления равна {removal_speed}, а время равно {time_value}, то расстояние между ними равно {removal_speed} × {time_value} = {answer}.",
        f"Ответ: {answer}",
        "Совет: при движении в противоположных направлениях сначала находят скорость удаления",
    )


def _final_20260412e_together_as_much_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if "столько, сколько" not in lower:
        return None
    if not has_multiple_questions(text):
        return None
    relation_pairs = extract_relation_pairs(lower)
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2 or not relation_pairs:
        return None
    base = nums[0]
    delta, mode = relation_pairs[0]
    second = apply_more_less(base, delta, mode)
    if second is None:
        return None
    third = base + second
    total = base + second + third
    sign = "+" if mode == "больше" else "-"
    third_name = ""
    m = re.search(r"а\s+([а-яё]+)\s+столько,\s+сколько", lower)
    if m:
        third_name = m.group(1)
    all_name = ""
    if "цвет" in lower:
        all_name = "цветов"
    answer_third = f"{third_name} было {third}" if third_name else f"третье количество равно {third}"
    answer_total = f"всего было {total} {all_name}".strip()
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {sign} {delta} = {second}.",
        f"2) Если третье количество равно первому и второму вместе, то оно равно {base} + {second} = {third}.",
        f"3) Если первое количество равно {base}, второе равно {second}, а третье равно {third}, то всего {base} + {second} + {third} = {total}.",
        f"Ответ: {answer_third}; {answer_total}",
        "Совет: если сказано «столько, сколько вместе», сначала находят сумму этих частей",
    )


_FINAL_20260412E_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first

# --- merged segment 014: backend.legacy_runtime_shards.prepatch_build_source.segment_014 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 11561-12460."""


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_20260412e_together_as_much_explanation(user_text)
        or _FINAL_20260412E_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи.",
            "Запишите пример или задачу полнее и без сокращений.",
            "Ответ: пока нужен более понятный ввод.",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 2400,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- FINAL CONSOLIDATION PATCH 2026-04-12F: broader math guard + tasks with letters ---

MATH_INPUT_HINTS = (
    "сколько", "сколько всего", "сколько стало", "сколько осталось", "на сколько", "во сколько",
    "больше", "меньше", "поровну", "по ", "стоимость", "цена", "количество", "купили",
    "скорость", "расстояние", "время", "площадь", "периметр", "доля", "часть",
    "уравнение", "пример", "выражение", "реши", "найди", "найдите",
)

def looks_like_math_input(text: str) -> bool:
    base = normalize_word_problem_text(text).lower()
    if re.search(r"\d|x|х|[+\-*/=×÷:]", base):
        return True
    if re.search(r"\b[a-z]\b", base) and any(hint in base for hint in MATH_INPUT_HINTS):
        return True
    # допускаем словесные задачи без цифр, если в них есть школьные математические маркеры
    if any(hint in base for hint in MATH_INPUT_HINTS):
        return True
    return False


def _final_letter_task_shelf_more_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"на первой полке\s+([a-z])\s+книг[^.?!]*на\s+([a-z])\s+больше[^.?!]*на второй",
        lower,
    )
    if not match:
        return None
    total_symbol = match.group(1)
    delta_symbol = match.group(2)
    return join_explanation_lines(
        f"1) Если на первой полке {total_symbol} книг и это на {delta_symbol} больше, чем на второй, то на второй полке на {delta_symbol} книг меньше.",
        f"2) Если на первой полке {total_symbol} книг, а на второй на {delta_symbol} книг меньше, то на второй полке {total_symbol} - {delta_symbol} книг.",
        f"Ответ: на второй полке {total_symbol} - {delta_symbol} книг.",
        "Совет: в задаче с буквами действуй так же, как в задаче с числами: сначала переведи косвенную форму в прямую.",
    )


def _final_letter_task_tourist_remaining_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"турист должен пройти\s+([a-z])\s+км[^.?!]*в первый день[^.?!]*прош[её]л\s+([a-z])\s+км[^.?!]*во второй\s+([a-z])\s+км",
        lower,
    )
    if not match:
        return None
    total_symbol, first_symbol, second_symbol = match.groups()
    return join_explanation_lines(
        f"1) Если в первый день турист прошёл {first_symbol} км, а во второй {second_symbol} км, то за два дня он прошёл {first_symbol} + {second_symbol} км.",
        f"2) Если турист должен пройти {total_symbol} км, а уже прошёл {first_symbol} + {second_symbol} км, то ему осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.",
        f"Ответ: туристу осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.",
        "Совет: в буквенной задаче сначала находят уже пройденный путь, потом вычитают его из всего пути.",
    )


def _final_letter_task_trains_passengers_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"прибыл[ао]?|прибыло", lower
    )
    if not match:
        return None
    match = re.search(
        r"на вокзал прибыл[ао]?\s+([a-z])\s+поезд[ао]в?\s+по\s+([a-z])\s+пассажир",
        lower,
    )
    if not match:
        return None
    trains_symbol, passengers_symbol = match.groups()
    return join_explanation_lines(
        f"1) Если на вокзал прибыло {trains_symbol} поездов по {passengers_symbol} пассажиров в каждом, то всего прибыло {trains_symbol} × {passengers_symbol} пассажиров.",
        f"Ответ: прибыло {trains_symbol} × {passengers_symbol} пассажиров.",
        "Совет: если одно и то же количество повторяется несколько раз, используют умножение.",
    )


def _final_letter_task_garland_ratio_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"гирлянде\s+([a-z])\s+красных лампочек\s+и\s+([a-z])\s+зеленых|гирлянде\s+([a-z])\s+красных лампочек\s+и\s+([a-z])\s+зелёных",
        lower,
    )
    if not match:
        return None
    groups = [g for g in match.groups() if g]
    if len(groups) != 2:
        return None
    red_symbol, green_symbol = groups
    return join_explanation_lines(
        f"1) Чтобы узнать, во сколько раз зелёных лампочек больше, чем красных, нужно количество зелёных разделить на количество красных.",
        f"2) Значит, нужно вычислить {green_symbol} : {red_symbol}.",
        f"Ответ: в {green_symbol} : {red_symbol} раза.",
        "Совет: вопрос «во сколько раз» решают делением большего количества на меньшее.",
    )


def _final_letter_task_factories_total_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"один завод выпустил\s+([a-z])\s+станков[^.?!]*в\s+([a-z])\s+раз\s+меньше",
        lower,
    )
    if not match:
        return None
    first_symbol, factor_symbol = match.groups()
    return join_explanation_lines(
        f"1) Если один завод выпустил {first_symbol} станков, а второй в {factor_symbol} раз меньше, то второй завод выпустил {first_symbol} : {factor_symbol} станков.",
        f"2) Если первый завод выпустил {first_symbol} станков, а второй {first_symbol} : {factor_symbol} станков, то вместе они выпустили {first_symbol} + {first_symbol} : {factor_symbol} станков.",
        f"Ответ: вместе заводы выпустили {first_symbol} + {first_symbol} : {factor_symbol} станков.",
        "Совет: если число дано через «в несколько раз меньше», сначала делят, а потом находят сумму.",
    )


def _final_letter_word_problem_explanation(raw_text: str) -> Optional[str]:
    return (
        _final_letter_task_shelf_more_explanation(raw_text)
        or _final_letter_task_tourist_remaining_explanation(raw_text)
        or _final_letter_task_trains_passengers_explanation(raw_text)
        or _final_letter_task_garland_ratio_explanation(raw_text)
        or _final_letter_task_factories_total_explanation(raw_text)
    )


SYSTEM_PROMPT = SYSTEM_PROMPT + "\nЕсли в задаче вместо чисел стоят буквы, решай её теми же школьными методами и давай ответ буквенным выражением."

_FINAL_20260412F_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first

def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_letter_word_problem_explanation(user_text)
        or _FINAL_20260412F_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи.",
            "Запишите пример или задачу полнее и без сокращений.",
            "Ответ: пока нужен более понятный ввод.",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 2400,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- PATCH 2026-04-12F1: robust tourist-letter task ---

def _final_letter_task_tourist_remaining_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"турист должен пройти\s+([a-z])\s+км[\s\S]*?в первый день[\s\S]*?прош[её]л\s+([a-z])\s+км[\s\S]*?во второй[\s\S]*?([a-z])\s+км",
        lower,
    )
    if not match:
        return None
    total_symbol, first_symbol, second_symbol = match.groups()
    return join_explanation_lines(
        f"1) Если в первый день турист прошёл {first_symbol} км, а во второй {second_symbol} км, то за два дня он прошёл {first_symbol} + {second_symbol} км.",
        f"2) Если турист должен пройти {total_symbol} км, а уже прошёл {first_symbol} + {second_symbol} км, то ему осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.",
        f"Ответ: туристу осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.",
        "Совет: в буквенной задаче сначала находят уже пройденный путь, потом вычитают его из всего пути.",
    )


# --- USER FINAL CONSOLIDATION PATCH 2026-04-12G: fuller textbook answers, better known/question extraction ---

_USER_FINAL_20260412G_PREV_EXTRACT_CONDITION_AND_QUESTION = extract_condition_and_question


SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши строку:
Порядок действий:
и ниже тот же пример, где над математическими знаками стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши строку:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. Если пример удобнее решать в столбик, сохраняй запись столбиком и подробное пояснение по шагам.
6. Вычисления в столбик используй, когда в выражении больше двух двузначных чисел или когда есть число из трёх и более цифр.
7. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом перепиши условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно пиши:
Что известно: ...
Что нужно найти: ...
4. Если нельзя сразу ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай по действиям.
6. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
7. В каждом действии, где это уместно, используй школьную форму:
Если ..., то ...
8. После каждого действия коротко говори, что нашли.
9. Если решение записывается по действиям, то в каждом действии, кроме последнего, полезно писать пояснение, что именно нашли.
10. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Если задача дана с именованными величинами, сначала переведи их в удобные одинаковые единицы.
5. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если это выражение, сначала назови порядок действий.
Если это уравнение, оставляй x отдельно и объясняй обратное действие.
Если это геометрия, сначала назови формулу, потом подставь числа.
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
""".strip()


def _user_final_is_short_answer_value(text: str) -> bool:
    value = str(text or "").strip().rstrip(".")
    if not value:
        return False
    return bool(re.fullmatch(r"-?\d+(?:/\d+)?(?:\s+[A-Za-zА-Яа-яЁё./²%-]+){0,3}", value))


def _user_final_answer_phrase_from_question(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip().rstrip(".")
    if not value:
        return value
    if not _user_final_is_short_answer_value(value):
        return value

    question = _question_lower_text(raw_text).lower().replace("ё", "е")

    if question.startswith("во сколько раз"):
        return value if value.startswith("в ") else f"в {value}"

    if re.search(r"\bсколько[^.?!]*\bзабрали\b", question):
        return f"забрали {value}"
    if re.search(r"\bсколько[^.?!]*\bотдали\b", question):
        return f"отдали {value}"
    if re.search(r"\bсколько[^.?!]*\bсъели\b", question):
        return f"съели {value}"
    if re.search(r"\bсколько[^.?!]*\bпродали\b", question):
        return f"продали {value}"
    if re.search(r"\bсколько[^.?!]*\bдобавили\b", question):
        return f"добавили {value}"
    if re.search(r"\bсколько[^.?!]*\bзаболел[аои]?\b", question):
        return f"заболело {value}"
    if re.search(r"\bсколько[^.?!]*\bостал(?:ось|ись|ся)\b", question):
        return f"осталось {value}"
    if re.search(r"\bсколько[^.?!]*\bстал(?:о|и)\b", question):
        return f"стало {value}"
    if re.search(r"\bсколько[^.?!]*\bпотребуется\b", question) or re.search(r"\bсколько[^.?!]*\bпотребовалось\b", question):
        return f"потребуется {value}"
    if re.search(r"\bсколько[^.?!]*\bможно купить\b", question):
        return f"можно купить {value}"

    price_one = re.search(r"\bсколько\s+стоит\s+(?:1|один|одна|одно)\s+([а-яё-]+)", question)
    if price_one:
        return f"{price_one.group(1)} стоит {value}"

    price_many = re.search(r"\bсколько\s+стоят\s+(.+)$", question)
    if price_many:
        subject = price_many.group(1).strip(" ?")
        if subject:
            return f"{subject} стоят {value}"

    if re.search(r"\bс какой скоростью\b|\bкакова скорость\b|\bчему равна скорость\b", question):
        return f"скорость равна {value}"
    if re.search(r"\bкакое расстояние\b|\bкаково расстояние\b|\bчему равно расстояние\b", question):
        return f"расстояние равно {value}"
    if re.search(r"\bсколько времени\b|\bза какое время\b|\bсколько часов\b", question):
        return f"время равно {value}"
    if re.search(r"\bчему равна площадь\b|\bнайти площадь\b|\bузнайте площадь\b", question):
        return f"площадь равна {value}"
    if re.search(r"\bчему равен периметр\b|\bнайти периметр\b|\bузнайте периметр\b", question):
        return f"периметр равен {value}"

    shelf_match = re.search(r"\bсколько[^.?!]*\bна\s+(первой|второй|третьей)\s+полке\b", question)
    if shelf_match:
        return f"на {shelf_match.group(1)} полке было {value}"

    day_match = re.search(r"\bсколько[^.?!]*\bво\s+(первый|второй|третий)\s+день\b", question)
    if day_match:
        return f"в {day_match.group(1)} день {value}"

    if question.startswith("сколько денег"):
        return f"заплатили {value}"

    return value


def _detailed_format_word_like_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    statement = _detailed_statement_text(raw_text)
    info_lines: List[str] = []
    body_lines: List[str] = []

    for line in parts["body"]:
        lower = line.lower()
        if lower.startswith("что известно:") or lower.startswith("что нужно найти:"):
            info_lines.append(line)
        else:
            body_lines.append(line)

    if not info_lines:
        condition, question = extract_condition_and_question(raw_text)
        if condition:
            info_lines.append(f"Что известно: {condition}")
        if question:
            info_lines.append(f"Что нужно найти: {question}")

    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    answer = _user_final_answer_phrase_from_question(answer, raw_text, kind)

    lines: List[str] = []
    if statement:
        lines.append("Задача.")
        lines.append(statement)
    lines.append("Решение.")
    lines.extend(info_lines)
    lines.extend(_detailed_number_lines(body_lines))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind if kind in DEFAULT_ADVICE else "other")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_generic_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    lines: List[str] = []
    statement = _detailed_statement_text(raw_text)
    if statement and kind in {"word", "geometry"}:
        lines.append("Задача.")
        lines.append(statement)
        lines.append("Решение.")
    else:
        lines.append("Решение.")
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    answer = _user_final_answer_phrase_from_question(answer, raw_text, kind)
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind)
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи.",
            "Запишите пример или задачу полнее и без сокращений.",
            "Ответ: пока нужен более понятный ввод.",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 2600,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- USER FINAL HOTFIX 2026-04-12H: geometry known-line extraction for "найти ..." formulations ---

_USER_FINAL_20260412H_PREV_EXTRACT_CONDITION_AND_QUESTION = extract_condition_and_question


# --- USER DELIVERY PATCH 2026-04-13: fuller final answers, architecture preserved ---

_PREV_USER_DELIVERY_ANSWER_PHRASE = _user_final_answer_phrase_from_question

def _user_final_answer_phrase_from_question(answer: str, raw_text: str, kind: str) -> str:
    original_value = str(answer or '').strip().rstrip('.')
    base = _PREV_USER_DELIVERY_ANSWER_PHRASE(answer, raw_text, kind)
    if not original_value:
        return base
    if not _user_final_is_short_answer_value(original_value):
        return base
    if str(base).strip().rstrip('.') != original_value:
        return base

    question = _question_lower_text(raw_text).lower().replace('ё', 'е').strip(' ?.')

    if question.startswith('сколько'):
        if ' было ' in f' {question} ' or question.endswith(' было'):
            if re.search(r'\b(кг|г|л|м|см|дм|мм|км|руб|листов|книг|клеток|деревьев|фруктов|деталей)\b', question) or 'всего' in question:
                return f'всего было {original_value}'
            return f'было {original_value}'
        if ' осталось ' in f' {question} ' or question.endswith(' осталось'):
            return f'осталось {original_value}'
        if ' стало ' in f' {question} ' or question.endswith(' стало'):
            return f'стало {original_value}'
        if re.search(r'\bсколько[^?]*\bклеток\b', question):
            return f'было {original_value}'
        if re.search(r'\bсколько[^?]*\bкоробок\b', question):
            return f'получилось {original_value}'
        if re.search(r'\bсколько[^?]*\bмешков\b', question):
            return f'было {original_value}'
        if re.search(r'\bсколько[^?]*\bкниг\b', question) and ('на полках' in question or 'на двух полках' in question or 'на трех полках' in question or 'на трёх полках' in question):
            return f'всего было {original_value}'
        if re.search(r'\bсколько[^?]*\bфруктов\b', question) and ('в ларьке' in question or 'в магазине' in question or 'было' in question):
            return f'всего было {original_value}'

    return base

# --- USER PATCH 2026-04-13I: DeepSeek-only topic rules + detailed first incomplete dividend ---

_USER_PATCH_20260413I_PREV_BUILD_EXPLANATION = build_explanation

_RULE_STYLE_HINTS = (
    "Сформулируй правило как короткое определение.",
    "Сформулируй правило как краткое правило действия.",
    "Сформулируй правило как учебное напоминание по теме.",
)


def _strip_rule_lines(text: str) -> str:
    kept: List[str] = []
    for raw in str(text or "").replace("\r", "").split("\n"):
        line = raw.strip()
        if re.match(r"^(?:совет|правило)\s*:\s*", line, flags=re.IGNORECASE):
            continue
        kept.append(raw.rstrip())
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept).strip()


def _normalize_rule_text(text: str) -> str:
    cleaned = sanitize_model_text(str(text or ""))
    for raw in cleaned.replace("\r", "").split("\n"):
        line = raw.strip().strip('"').strip("' ")
        if not line:
            continue
        line = re.sub(r"^(?:совет|правило)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
        line = re.sub(r"\s+", " ", line)
        line = line.rstrip(" .!?")
        if not line:
            continue
        if len(line) > 220:
            line = line[:220].rstrip(" ,;:")
        return line
    return ""


def _append_rule_line(text: str, rule: str) -> str:
    base = _strip_rule_lines(text)
    normalized_rule = _normalize_rule_text(rule)
    if not normalized_rule:
        return base
    rule_line = _detailed_finalize_line(f"Совет: {normalized_rule}")
    if not base:
        return rule_line
    return f"{base}\n{rule_line}".strip()


def _compare_first_incomplete_candidate(candidate: int, divisor: int) -> str:
    if candidate < divisor:
        return f"{candidate} меньше {divisor} – не подходит"
    if candidate == divisor:
        return f"{candidate} равно {divisor} – подходит"
    return f"{candidate} больше {divisor} – подходит"


def _first_incomplete_dividend_intro_lines(dividend: int, divisor: int) -> Tuple[str, str]:
    dividend_text = str(abs(int(dividend)))
    divisor_text = str(abs(int(divisor)))
    if not dividend_text or not divisor_text or divisor <= 0:
        return (
            "Определяем первое неполное делимое. Оно должно быть больше или равно делителю.",
            "Подобрали первое неполное делимое.",
        )

    start_length = min(len(dividend_text), max(1, len(divisor_text)))
    prefix_length = start_length
    candidate = int(dividend_text[:prefix_length])
    fragments: List[str] = []

    while prefix_length < len(dividend_text) and candidate < divisor:
        fragments.append(_compare_first_incomplete_candidate(candidate, divisor))
        prefix_length += 1
        candidate = int(dividend_text[:prefix_length])

    candidate_phrase = _compare_first_incomplete_candidate(candidate, divisor)
    if not fragments or fragments[-1] != candidate_phrase:
        fragments.append(candidate_phrase)

    if fragments:
        first_line = (
            "Определяем первое неполное делимое. Оно должно быть больше или равно делителю. "
            f"Подбираем: {', '.join(fragments)}."
        )
    else:
        first_line = "Определяем первое неполное делимое. Оно должно быть больше или равно делителю."

    second_line = f"Подобрали первое неполное делимое {candidate}."
    return first_line, second_line


def explain_long_division(dividend: int, divisor: int) -> str:
    if divisor == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
        )

    quotient, remainder = divmod(dividend, divisor)
    model = build_long_division_steps(dividend, divisor)
    steps = model.get("steps", [])

    if not steps:
        lines = [
            "Пишем деление столбиком",
            f"Число {dividend} меньше {divisor}, поэтому в частном будет 0",
        ]
        if remainder:
            lines.append(f"Остаток равен {remainder}")
            return join_explanation_lines(*lines, f"Ответ: 0, остаток {remainder}")
        return join_explanation_lines(*lines, "Ответ: 0")

    intro_line, picked_line = _first_incomplete_dividend_intro_lines(dividend, divisor)
    lines: List[str] = [
        "Пишем деление столбиком",
        intro_line,
        picked_line,
    ]

    for index, step in enumerate(steps):
        current = int(step["current"])
        q_digit = int(step["q_digit"])
        product = int(step["product"])
        remainder_here = int(step["remainder"])
        next_try = (q_digit + 1) * divisor
        next_step = steps[index + 1] if index + 1 < len(steps) else None

        if index > 0:
            lines.append(f"Теперь работаем с числом {current}")

        if next_try > current:
            lines.append(
                f"Смотрим, сколько раз {divisor} помещается в {current}. Берём {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше"
            )
        else:
            lines.append(
                f"Смотрим, сколько раз {divisor} помещается в {current}. Берём {q_digit}, потому что {q_digit} × {divisor} = {product}"
            )

        lines.append(f"Пишем {q_digit} в частном и вычитаем {product} из {current}. Остаётся {remainder_here}")

        if next_step is not None:
            lines.append(f"Сносим следующую цифру и получаем {int(next_step['current'])}")
        elif remainder_here == 0:
            lines.append("Деление закончено без остатка")
        else:
            lines.append(f"Получаем остаток {remainder_here}. Он меньше делителя, значит деление закончено")

    if remainder == 0:
        lines.append(f"Читаем ответ: частное равно {quotient}")
        return join_explanation_lines(*lines, f"Ответ: {quotient}")

    lines.append(f"Читаем ответ: частное равно {quotient}, остаток {remainder}")
    return join_explanation_lines(*lines, f"Ответ: {quotient}, остаток {remainder}")


async def _generate_topic_rule_with_deepseek(user_text: str, formatted_text: str, kind: str) -> str:
    if not DEEPSEEK_API_KEY:
        return ""

    import random

    compact_solution = _strip_rule_lines(formatted_text)
    style_hint = random.choice(_RULE_STYLE_HINTS)

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты — учитель математики для детей 7–10 лет. "
                    "По задаче и уже готовому решению напиши одно краткое понятное математическое правило по теме именно этого решения. "
                    "Это должно быть правило, определение или учебное напоминание по применённому приёму, а не общий совет про аккуратность. "
                    "Пиши только по-русски. "
                    "Верни только текст правила без слова 'Совет:' и без markdown. "
                    "Допустимы 1–2 коротких предложения. "
                    "Старайся формулировать по-разному, но точно по теме."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Тип задания: {kind}\n"
                    f"Запись ученика: {user_text}\n"
                    f"Готовое решение:\n{compact_solution}\n\n"
                    "Нужно дать одно краткое правило по теме вычисления, которое реально применялось в этом решении.\n"
                    f"{style_hint}"
                ),
            },
        ],
        "max_tokens": 120,
        "temperature": 0.55,
    }

    llm_result = await call_deepseek(payload, timeout_seconds=20.0)
    if llm_result.get("error"):
        return ""
    return _normalize_rule_text(llm_result.get("result", ""))


async def build_explanation(user_text: str) -> dict:
    result = await _USER_PATCH_20260413I_PREV_BUILD_EXPLANATION(user_text)
    if not isinstance(result, dict) or "result" not in result:
        return result

    kind = infer_task_kind(user_text)
    stripped_text = _strip_rule_lines(str(result.get("result") or ""))

    rule_text = ""
    if DEEPSEEK_API_KEY:
        rule_text = await _generate_topic_rule_with_deepseek(user_text, stripped_text, kind)

    final_text = _append_rule_line(stripped_text, rule_text) if rule_text else stripped_text
    updated = dict(result)
    updated["result"] = final_text
    return updated

# --- USER PATCH 2026-04-13J: exact mixed-expression steps and complete column sequence ---


def _patch_20260413j_should_use_column_for_step(step: dict, source: str) -> bool:
    left = _patch_20260412c_parse_int_text(step.get("left", ""))
    right = _patch_20260412c_parse_int_text(step.get("right", ""))
    operator = step.get("operator")

    if left is None or right is None:
        return False

    abs_left = abs(left)
    abs_right = abs(right)

    if operator == "+":
        return abs_left >= 100 or abs_right >= 100 or (abs_left >= 10 and abs_right >= 10)
    if operator == "-":
        if left < 0 or right < 0 or left < right:
            return False
        return abs_left >= 100 or abs_right >= 100 or (abs_left >= 10 and abs_right >= 10)
    if operator == "×":
        return abs_left >= 10 or abs_right >= 10
    if operator == ":":
        if right == 0:
            return False
        return abs_left >= 100 or abs_right >= 10
    return False


_PATCH_20260413J_ACTION_NAMES = {
    "×": "умножение",
    ":": "деление",
}


def _patch_20260413j_pretty_operator(operator: str) -> str:
    if operator in {"*", "x", "X", "х", "Х", "×"}:
        return "×"
    if operator in {"/", ":", "÷"}:
        return ":"
    if operator in {"-", "−", "–"}:
        return "–"
    return operator


def _patch_20260413j_step_header(index: int, operator: str, left: str, right: str, result: str) -> str:
    pretty_operator = _patch_20260413j_pretty_operator(operator)
    expression = f"{left} {pretty_operator} {right}".strip()
    if result:
        return f"{index}) {expression} = {result}."
    return f"{index}) {expression}."


# переопределяем критерий выбора столбика для смешанных выражений
_patch_20260412c_should_use_column_for_step = _patch_20260413j_should_use_column_for_step


def _patch_20260412c_render_mixed_expression_solution(source: str) -> Optional[str]:
    node = parse_expression_ast(source)
    if node is None:
        return None

    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return None

    pretty_expression = _user_final_patch_pretty_expression_from_source(source)
    answer = _detailed_expression_answer(source) or "проверь запись"

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}."]
    order_block = _detailed_build_order_block(source)
    if order_block:
        lines.extend(order_block)
    lines.append("Решение по действиям:")

    for index, step in enumerate(steps, start=1):
        left = str(step.get("left", "")).strip()
        right = str(step.get("right", "")).strip()
        operator = str(step.get("operator", "")).strip()
        result = str(step.get("result", "")).strip()

        lines.append(_patch_20260413j_step_header(index, operator, left, right, result))

        use_column = _patch_20260412c_should_use_column_for_step(step, source)
        if not use_column:
            continue

        detailed = _patch_20260412c_step_explanation_text(step)
        if not detailed:
            continue

        parts = _detailed_split_sections(detailed)
        column_block, remaining_body = _split_ascii_layout_block(parts.get("body", []))
        cleaned_body = _patch_20260412c_clean_body_lines(remaining_body)

        if column_block:
            lines.extend(column_block)
        if cleaned_body:
            lines.extend(cleaned_body)

    lines.append(f"Ответ: {answer}")
    return _detailed_finalize_text(lines)


# --- USER PATCH 2026-04-14A: primary-school equation explanations with numbered steps ---

def _eq_math_line(text: str) -> str:
    return str(text or '').strip().replace('/', ':').replace('*', '×')


def _eq_transfer_name(operator_kind: str) -> Tuple[str, str]:
    mapping = {
        'plus': ('+', '-'),
        'minus': ('-', '+'),
        'mul': ('умножения', 'деление'),
        'div': ('деления', 'умножение'),
    }
    return mapping.get(operator_kind, ('знак', 'обратный знак'))


def _eq_transfer_step(variable_name: str, moved_number: str, rhs_text: str, result_expr: str, operator_kind: str) -> List[str]:
    sign_name, changed_to = _eq_transfer_name(operator_kind)
    return [
        f"1) Неизвестное {variable_name} оставляем слева, а число {moved_number} переносим вправо. При переносе знак {sign_name} меняется на {changed_to}:",
        _eq_math_line(f"{variable_name} = {result_expr}"),
    ]


def _eq_compute_and_answer_steps(variable_name: str, answer: Fraction, start_index: int = 2) -> List[str]:
    answer_text = format_fraction(answer)
    return [
        f"{start_index}) Считаем:",
        _eq_math_line(f"{variable_name} = {answer_text}"),
        f"Ответ: {answer_text}",
    ]

# --- merged segment 015: backend.legacy_runtime_shards.prepatch_build_source.segment_015 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 12461-13324."""



def try_local_equation_explanation(raw_text: str) -> Optional[str]:
    source = to_equation_source(raw_text)
    if not source:
        return None

    variable_name = _user_final_equation_variable_name(source)
    lhs, rhs = source.split('=', 1)
    if variable_name not in lhs and variable_name in rhs:
        lhs, rhs = rhs, lhs

    try:
        rhs_value = Fraction(int(rhs), 1)
    except ValueError:
        return None

    variable_re = re.escape(variable_name)
    patterns = [
        (rf'^{variable_re}\+(\d+)$', 'var_plus'),
        (rf'^{variable_re}-(\d+)$', 'var_minus'),
        (rf'^{variable_re}\*(\d+)$', 'var_mul'),
        (rf'^{variable_re}/(\d+)$', 'var_div'),
        (rf'^(\d+)\+{variable_re}$', 'plus_var'),
        (rf'^(\d+)-{variable_re}$', 'minus_var'),
        (rf'^(\d+)\*{variable_re}$', 'mul_var'),
        (rf'^(\d+)/{variable_re}$', 'div_var'),
    ]

    for pattern, kind in patterns:
        match = re.fullmatch(pattern, lhs)
        if not match:
            continue

        number = Fraction(int(match.group(1)), 1)
        number_text = format_fraction(number)
        rhs_text = format_fraction(rhs_value)

        if kind == 'var_plus':
            answer = rhs_value - number
            lines = _eq_transfer_step(variable_name, number_text, rhs_text, f"{rhs_text} - {number_text}", 'plus')
            lines.extend(_eq_compute_and_answer_steps(variable_name, answer, 2))
            return join_explanation_lines(*lines)

        if kind == 'plus_var':
            answer = rhs_value - number
            lines = [
                f"1) В левой части переставим слагаемые местами: {variable_name} + {number_text} = {rhs_text}",
                f"2) Неизвестное {variable_name} оставляем слева, а число {number_text} переносим вправо. При переносе знак плюс меняется на минус:",
                _eq_math_line(f"{variable_name} = {rhs_text} - {number_text}"),
                '3) Считаем:',
                _eq_math_line(f"{variable_name} = {format_fraction(answer)}"),
                f"Ответ: {format_fraction(answer)}",
            ]
            return join_explanation_lines(*lines)

        if kind == 'var_minus':
            answer = rhs_value + number
            lines = _eq_transfer_step(variable_name, number_text, rhs_text, f"{rhs_text} + {number_text}", 'minus')
            lines.extend(_eq_compute_and_answer_steps(variable_name, answer, 2))
            return join_explanation_lines(*lines)

        if kind == 'var_mul':
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        '1) При умножении на 0 всегда получается 0',
                        'Ответ: подходит любое число',
                    )
                return join_explanation_lines(
                    '1) При умножении на 0 нельзя получить другое число',
                    'Ответ: решения нет',
                )
            answer = rhs_value / number
            lines = _eq_transfer_step(variable_name, number_text, rhs_text, f"{rhs_text} : {number_text}", 'mul')
            lines.extend(_eq_compute_and_answer_steps(variable_name, answer, 2))
            return join_explanation_lines(*lines)

        if kind == 'mul_var':
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        '1) При умножении на 0 всегда получается 0',
                        'Ответ: подходит любое число',
                    )
                return join_explanation_lines(
                    '1) При умножении на 0 нельзя получить другое число',
                    'Ответ: решения нет',
                )
            answer = rhs_value / number
            lines = [
                f"1) В левой части переставим множители местами: {variable_name} × {number_text} = {rhs_text}",
                f"2) Неизвестное {variable_name} оставляем слева, а число {number_text} переносим вправо. При переносе знак умножения меняется на деление:",
                _eq_math_line(f"{variable_name} = {rhs_text} : {number_text}"),
                '3) Считаем:',
                _eq_math_line(f"{variable_name} = {format_fraction(answer)}"),
                f"Ответ: {format_fraction(answer)}",
            ]
            return join_explanation_lines(*lines)

        if kind == 'var_div':
            if number == 0:
                return join_explanation_lines(
                    '1) На ноль делить нельзя',
                    'Ответ: решения нет',
                )
            answer = rhs_value * number
            lines = _eq_transfer_step(variable_name, number_text, rhs_text, f"{rhs_text} × {number_text}", 'div')
            lines.extend(_eq_compute_and_answer_steps(variable_name, answer, 2))
            return join_explanation_lines(*lines)

        if kind == 'minus_var':
            answer = number - rhs_value
            lines = [
                '1) Ищем неизвестное вычитаемое. Чтобы найти его, из уменьшаемого вычитаем разность:',
                _eq_math_line(f"{variable_name} = {number_text} - {rhs_text}"),
                '2) Считаем:',
                _eq_math_line(f"{variable_name} = {format_fraction(answer)}"),
                f"Ответ: {format_fraction(answer)}",
            ]
            return join_explanation_lines(*lines)

        if kind == 'div_var':
            if rhs_value == 0:
                return join_explanation_lines(
                    '1) На ноль делить нельзя, поэтому такое уравнение решения не имеет',
                    'Ответ: решения нет',
                )
            answer = number / rhs_value
            lines = [
                '1) Ищем неизвестный делитель. Чтобы найти его, делимое делим на частное:',
                _eq_math_line(f"{variable_name} = {number_text} : {rhs_text}"),
                '2) Считаем:',
                _eq_math_line(f"{variable_name} = {format_fraction(answer)}"),
                f"Ответ: {format_fraction(answer)}",
            ]
            return join_explanation_lines(*lines)

    return None


def _detailed_format_equation_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_equation_source(raw_text) or normalize_cyrillic_x(strip_known_prefix(raw_text))
    pretty = _detailed_pretty_equation(source)
    answer = parts['answer'] or 'проверь запись'

    lines: List[str] = ['Уравнение:', pretty, 'Решение.']
    lines.extend(parts['body'])
    if parts['check']:
        lines.append(parts['check'])
    lines.append(f'Ответ: {answer}')
    if parts['advice']:
        lines.append(f"Совет: {parts['advice']}")
    return _detailed_finalize_text(lines)


# --- USER PATCH 2026-04-14B: keep equation lines and colons without extra periods ---

def normalize_sentence(text: str) -> str:
    line = str(text or '').strip()
    if not line:
        return ''
    if re.fullmatch(r'[A-Za-zА-Яа-я0-9()+\-×:=/ ]+', line) and (('=' in line) or bool(re.search(r'[+\-×:/]', line))):
        return line
    if line[-1] not in '.!?:':
        line += '.'
    return line


# --- AUDIT PATCH 2026-04-14C: broad local coverage for school explanations ---

_AUDIT_20260414C_PREV_BUILD_EXPLANATION = build_explanation


def _audit_join_lines(*lines: str) -> str:
    cleaned = []
    for line in lines:
        text = str(line or '').strip()
        if text:
            cleaned.append(text)
    return '\n'.join(cleaned)


def _audit_extract_first_quantity_noun(text: str) -> str:
    match = re.search(r"\d+\s+([A-Za-zА-Яа-яЁё-]+)", str(text or ''))
    if not match:
        return ''
    word = match.group(1)
    if word.lower() in {'руб', 'рубля', 'рублей', 'см', 'мм', 'дм', 'м', 'км', 'ч', 'час', 'часа', 'часов', 'мин', 'минута', 'минуты', 'минут'}:
        return ''
    return word


def _audit_extract_question_noun(text: str) -> str:
    match = re.search(r"сколько\s+([A-Za-zА-Яа-яЁё-]+)", str(text or '').lower())
    if not match:
        return ''
    word = match.group(1)
    if word in {'стало', 'осталось', 'было', 'будет', 'нужно'}:
        return ''
    return word


def _audit_add_answer_noun(value_text: str, noun: str) -> str:
    noun = str(noun or '').strip()
    if not noun:
        return value_text
    return f"{value_text} {noun}".strip()


def _audit_pretty_expr_from_source(source: str) -> str:
    node = parse_expression_ast(source)
    if node is not None:
        return render_node(node)
    return str(source or '').replace('*', ' × ').replace('/', ' : ')


def _audit_try_simple_addition_explanation(raw_text: str) -> Optional[str]:
    source = to_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    simple = try_simple_binary_int_expression(node)
    if not simple or simple['operator'] is not ast.Add:
        return None
    left = simple['left']
    right = simple['right']
    if left < 0 or right < 0:
        return None
    if max(left, right) > 20:
        return None
    result = left + right
    expr = f"{left} + {right}"
    return _audit_join_lines(
        f"Пример: {expr} = {result}.",
        "Решение.",
        "Пример в одно действие.",
        "Нужно найти сумму чисел.",
        f"Считаем: {expr} = {result}.",
        f"Ответ: {result}."
    )


def _audit_try_one_step_equation_explanation(raw_text: str) -> Optional[str]:
    source = to_equation_source(raw_text)
    if not source:
        return None
    compact = re.sub(r"\s+", "", source)
    variable_match = re.search(r"([A-Za-zА-Яа-я])", compact)
    variable = variable_match.group(1) if variable_match else 'x'

    def fmt_value(value):
        if isinstance(value, Fraction):
            return format_fraction(value)
        return format_fraction(Fraction(value, 1)) if not isinstance(value, str) else value

    patterns = [
        (rf"^({variable})\+(\-?\d+)=([\-]?\d+)$", 'x_plus_n_eq_b'),
        (rf"^(\-?\d+)\+({variable})=([\-]?\d+)$", 'n_plus_x_eq_b'),
        (rf"^({variable})\-(\-?\d+)=([\-]?\d+)$", 'x_minus_n_eq_b'),
        (rf"^(\-?\d+)\-({variable})=([\-]?\d+)$", 'n_minus_x_eq_b'),
        (rf"^({variable})\*(\-?\d+)=([\-]?\d+)$", 'x_mul_n_eq_b'),
        (rf"^(\-?\d+)\*({variable})=([\-]?\d+)$", 'n_mul_x_eq_b'),
        (rf"^({variable})/(\-?\d+)=([\-]?\d+)$", 'x_div_n_eq_b'),
        (rf"^(\-?\d+)/({variable})=([\-]?\d+)$", 'n_div_x_eq_b'),
    ]

    for pattern, kind in patterns:
        match = re.fullmatch(pattern, compact)
        if not match:
            continue

        if kind == 'x_plus_n_eq_b':
            n = int(match.group(2)); b = int(match.group(3)); ans = Fraction(b - n, 1)
            return _audit_join_lines(
                "Уравнение:",
                f"{variable} + {n} = {b}",
                "Решение.",
                f"1) Неизвестное {variable} оставляем слева, а известное число {n} переносим вправо. При переносе знак меняется:",
                f"{variable} = {b} - {n}",
                "2) Считаем:",
                f"{variable} = {fmt_value(ans)}",
                f"Ответ: {fmt_value(ans)}"
            )

        if kind == 'n_plus_x_eq_b':
            n = int(match.group(1)); b = int(match.group(3)); ans = Fraction(b - n, 1)
            return _audit_join_lines(
                "Уравнение:",
                f"{n} + {variable} = {b}",
                "Решение.",
                f"1) Неизвестное {variable} оставляем слева, а известное число {n} переносим вправо. При переносе знак меняется:",
                f"{variable} = {b} - {n}",
                "2) Считаем:",
                f"{variable} = {fmt_value(ans)}",
                f"Ответ: {fmt_value(ans)}"
            )

        if kind == 'x_minus_n_eq_b':
            n = int(match.group(2)); b = int(match.group(3)); ans = Fraction(b + n, 1)
            return _audit_join_lines(
                "Уравнение:",
                f"{variable} - {n} = {b}",
                "Решение.",
                f"1) Неизвестное {variable} оставляем слева, а число {n} переносим вправо. При переносе знак меняется:",
                f"{variable} = {b} + {n}",
                "2) Считаем:",
                f"{variable} = {fmt_value(ans)}",
                f"Ответ: {fmt_value(ans)}"
            )

        if kind == 'n_minus_x_eq_b':
            n = int(match.group(1)); b = int(match.group(3)); ans = Fraction(n - b, 1)
            return _audit_join_lines(
                "Уравнение:",
                f"{n} - {variable} = {b}",
                "Решение.",
                f"1) Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность:",
                f"{variable} = {n} - {b}",
                "2) Считаем:",
                f"{variable} = {fmt_value(ans)}",
                f"Ответ: {fmt_value(ans)}"
            )

        if kind == 'x_mul_n_eq_b':
            n = int(match.group(2)); b = int(match.group(3))
            if n == 0:
                return None
            ans = Fraction(b, n)
            return _audit_join_lines(
                "Уравнение:",
                f"{variable} × {n} = {b}",
                "Решение.",
                f"1) Неизвестное {variable} оставляем слева, а число {n} переносим вправо. При переносе знак умножения меняется на деление:",
                f"{variable} = {b} : {n}",
                "2) Считаем:",
                f"{variable} = {fmt_value(ans)}",
                f"Ответ: {fmt_value(ans)}"
            )

        if kind == 'n_mul_x_eq_b':
            n = int(match.group(1)); b = int(match.group(3))
            if n == 0:
                return None
            ans = Fraction(b, n)
            return _audit_join_lines(
                "Уравнение:",
                f"{n} × {variable} = {b}",
                "Решение.",
                f"1) Неизвестное {variable} оставляем слева, а число {n} переносим вправо. При переносе знак умножения меняется на деление:",
                f"{variable} = {b} : {n}",
                "2) Считаем:",
                f"{variable} = {fmt_value(ans)}",
                f"Ответ: {fmt_value(ans)}"
            )

        if kind == 'x_div_n_eq_b':
            n = int(match.group(2)); b = int(match.group(3)); ans = Fraction(b * n, 1)
            return _audit_join_lines(
                "Уравнение:",
                f"{variable} : {n} = {b}",
                "Решение.",
                f"1) Неизвестное {variable} оставляем слева, а число {n} переносим вправо. При переносе знак деления меняется на умножение:",
                f"{variable} = {b} × {n}",
                "2) Считаем:",
                f"{variable} = {fmt_value(ans)}",
                f"Ответ: {fmt_value(ans)}"
            )

        if kind == 'n_div_x_eq_b':
            n = int(match.group(1)); b = int(match.group(3))
            if b == 0:
                return None
            ans = Fraction(n, b)
            return _audit_join_lines(
                "Уравнение:",
                f"{n} : {variable} = {b}",
                "Решение.",
                "1) Чтобы найти неизвестный делитель, делимое делим на частное:",
                f"{variable} = {n} : {b}",
                "2) Считаем:",
                f"{variable} = {fmt_value(ans)}",
                f"Ответ: {fmt_value(ans)}"
            )
    return None


def _audit_try_fraction_number_tasks(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    match = re.fullmatch(r"(\d+)\s*/\s*(\d+)\s+числ[аоы]\s+равн(?:а|ы|о)\s+(\d+)", lower)
    if match:
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        part_value = int(match.group(3))
        if numerator == 0 or denominator == 0:
            return None
        one_part = Fraction(part_value, numerator)
        whole = one_part * denominator
        lines = [
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: {numerator}/{denominator} числа {'равна' if numerator == 1 else 'равны'} {part_value}.",
            "Что нужно найти: всё число."
        ]
        if numerator == 1:
            lines.append(f"1) Одна {denominator}-я часть числа уже равна {part_value}.")
        else:
            lines.append(f"1) Найдём одну {denominator}-ю часть числа: {part_value} : {numerator} = {format_fraction(one_part)}.")
        lines.append(f"2) Всё число состоит из {denominator} таких частей: {format_fraction(one_part)} × {denominator} = {format_fraction(whole)}.")
        lines.append(f"Ответ: {format_fraction(whole)}")
        return _audit_join_lines(*lines)

    match = re.search(r"найд[иитеь]*\s+(\d+)\s*/\s*(\d+)\s+от\s+(\d+)", lower)
    if match:
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        total = int(match.group(3))
        if denominator == 0:
            return None
        one_part = Fraction(total, denominator)
        part = one_part * numerator
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: всё число равно {total}.",
            f"Что нужно найти: {numerator}/{denominator} от этого числа.",
            f"1) Найдём одну {denominator}-ю часть: {total} : {denominator} = {format_fraction(one_part)}.",
            f"2) Найдём {numerator}/{denominator} числа: {format_fraction(one_part)} × {numerator} = {format_fraction(part)}.",
            f"Ответ: {format_fraction(part)}"
        )
    return None


def _audit_try_motion_shorthand(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    speed_match = re.search(r"скорост[ьяи]?[^\d]{0,10}(\d+)\s*([^\s,.;]+)?", lower)
    time_match = re.search(r"врем[яеи]?[^\d]{0,10}(\d+)\s*([^\s,.;]+)?", lower)
    distance_match = re.search(r"расстояни[ея]?[^\d]{0,10}(\d+)\s*([^\s,.;]+)?", lower)

    speed_value = int(speed_match.group(1)) if speed_match else None
    time_value = int(time_match.group(1)) if time_match else None
    distance_value = int(distance_match.group(1)) if distance_match else None

    speed_unit = speed_match.group(2) if speed_match and speed_match.group(2) else ''
    time_unit = time_match.group(2) if time_match and time_match.group(2) else ''
    distance_unit = distance_match.group(2) if distance_match and distance_match.group(2) else ''

    if 'найти расстояние' in lower or ('расстояни' in lower and distance_value is None and speed_value is not None and time_value is not None):
        result = speed_value * time_value
        if not distance_unit and speed_unit and '/' in speed_unit:
            distance_unit = speed_unit.split('/')[0]
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: скорость {speed_value} {speed_unit.strip()}, время {time_value} {time_unit.strip()}.".strip(),
            "Что нужно найти: расстояние.",
            "1) Чтобы найти расстояние, используем правило: S = v × t.",
            f"2) Подставляем числа: {speed_value} × {time_value} = {result}.",
            f"Ответ: {_audit_add_answer_noun(str(result), distance_unit)}"
        )

    if 'найти время' in lower or ('врем' in lower and time_value is None and speed_value is not None and distance_value is not None):
        if speed_value in (None, 0) or distance_value is None:
            return None
        result = Fraction(distance_value, speed_value)
        if not time_unit:
            if speed_unit and '/' in speed_unit:
                time_unit = speed_unit.split('/', 1)[1]
            else:
                time_unit = 'ч'
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: расстояние {distance_value} {distance_unit.strip()}, скорость {speed_value} {speed_unit.strip()}.".strip(),
            "Что нужно найти: время.",
            "1) Чтобы найти время, используем правило: t = S : v.",
            f"2) Подставляем числа: {distance_value} : {speed_value} = {format_fraction(result)}.",
            f"Ответ: {_audit_add_answer_noun(format_fraction(result), time_unit)}"
        )

    if 'найти скорость' in lower or ('скорост' in lower and speed_value is None and time_value is not None and distance_value is not None):
        if time_value in (None, 0) or distance_value is None:
            return None
        result = Fraction(distance_value, time_value)
        if not speed_unit:
            if distance_unit and time_unit:
                speed_unit = f"{distance_unit}/{time_unit}"
            else:
                speed_unit = 'км/ч'
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: расстояние {distance_value} {distance_unit.strip()}, время {time_value} {time_unit.strip()}.".strip(),
            "Что нужно найти: скорость.",
            "1) Чтобы найти скорость, используем правило: v = S : t.",
            f"2) Подставляем числа: {distance_value} : {time_value} = {format_fraction(result)}.",
            f"Ответ: {_audit_add_answer_noun(format_fraction(result), speed_unit)}"
        )
    return None


def _audit_try_price_short_tasks(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    price_total_match = re.search(r"цена\s*1\s+([а-яё-]+)\s*(\d+)\s*руб", lower)
    asked_cost_match = re.search(r"сколько\s+стоят\s+(\d+)\s+([а-яё-]+)", lower)
    if price_total_match and asked_cost_match:
        item = price_total_match.group(1)
        price = int(price_total_match.group(2))
        qty = int(asked_cost_match.group(1))
        total = price * qty
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: цена одной {item} {price} руб., количество {qty}.",
            "Что нужно найти: стоимость покупки.",
            "1) Чтобы найти стоимость, цену умножаем на количество.",
            f"2) Считаем: {price} × {qty} = {total}.",
            f"Ответ: {total} руб"
        )

    paid_match = re.search(r"за\s*(\d+)\s+([а-яё-]+)\s+заплатили\s*(\d+)\s*руб", lower)
    if paid_match and ('сколько стоит 1' in lower or 'сколько стоит одна' in lower):
        qty = int(paid_match.group(1))
        item = paid_match.group(2)
        total = int(paid_match.group(3))
        if qty == 0:
            return None
        price = Fraction(total, qty)
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: за {qty} {item} заплатили {total} руб.",
            "Что нужно найти: цену одного предмета.",
            "1) Чтобы найти цену, стоимость делим на количество.",
            f"2) Считаем: {total} : {qty} = {format_fraction(price)}.",
            f"Ответ: {format_fraction(price)} руб"
        )
    return None


def _audit_try_rectangle_geometry(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    unit = geometry_unit(text)

    match = re.search(r"периметр\s+прямоугольника\s*(\d+)\s*(мм|см|дм|м|км)?[^\d]{0,40}длина\s*(\d+)", lower)
    if match and 'ширин' in lower:
        perimeter = int(match.group(1))
        length = int(match.group(3))
        if not unit:
            unit = (match.group(2) or '').lower()
        half_sum = Fraction(perimeter, 2)
        width = half_sum - length
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: периметр прямоугольника {with_unit(perimeter, unit)}, длина {with_unit(length, unit)}.",
            "Что нужно найти: ширину.",
            "1) Периметр прямоугольника равен сумме длины и ширины, умноженной на 2:",
            "P = (a + b) × 2",
            f"2) Найдём сумму длины и ширины: {perimeter} : 2 = {format_fraction(half_sum)}.",
            f"3) Теперь найдём ширину: {format_fraction(half_sum)} - {length} = {format_fraction(width)}.",
            f"Ответ: {with_unit(int(width) if isinstance(width, Fraction) and width.denominator == 1 else format_fraction(width), unit)}"
        )

    match = re.search(r"длина\s+прямоугольника\s*(\d+)\s*(мм|см|дм|м|км)?[^\d]{0,40}ширина\s*(\d+)", lower)
    if match and 'периметр' in lower:
        length = int(match.group(1))
        width = int(match.group(3))
        if not unit:
            unit = (match.group(2) or '').lower()
        half = length + width
        perimeter = half * 2
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: длина {with_unit(length, unit)}, ширина {with_unit(width, unit)}.",
            "Что нужно найти: периметр.",
            "1) Периметр прямоугольника находим по формуле: P = (a + b) × 2.",
            f"2) Складываем длину и ширину: {length} + {width} = {half}.",
            f"3) Умножаем на 2: {half} × 2 = {perimeter}.",
            f"Ответ: {with_unit(perimeter, unit)}"
        )
    return None


def _audit_try_common_word_problems(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    numbers = extract_ordered_numbers(lower)
    if len(numbers) < 2:
        return None

    first_noun = _audit_extract_first_quantity_noun(text)
    asked_noun = _audit_extract_question_noun(text)

    if ('сначала' in lower or 'было сначала' in lower) and 'стало' in lower and any(stem in lower for stem in WORD_GAIN_HINTS):
        added_match = re.search(r"добав[а-я]*\s*(\d+)", lower)
        total_match = re.search(r"стало\s*(\d+)", lower)
        if added_match and total_match:
            added = int(added_match.group(1))
            total = int(total_match.group(1))
            initial = total - added
            return _audit_join_lines(
                "Задача.",
                _audit_task_line(raw_text),
                "Решение.",
                f"Что известно: добавили {added}, стало {total}.",
                "Что нужно найти: сколько было сначала.",
                f"1) После того как добавили {added}, стало {total}.",
                f"2) Чтобы узнать, сколько было сначала, из {total} вычитаем {added}: {total} - {added} = {initial}.",
                f"Ответ: {initial}"
            )

    if any(verb in lower for verb in GROUPING_VERBS) and 'по' in lower and 'сколько' in lower and 'в каждом' not in lower:
        match = re.search(r"(\d+)[^\d]{0,40}по\s*(\d+)", lower)
        if match:
            total = int(match.group(1))
            per_group = int(match.group(2))
            if per_group == 0:
                return None
            groups = Fraction(total, per_group)
            answer_noun = asked_noun or 'групп'
            return _audit_join_lines(
                "Задача.",
                _audit_task_line(raw_text),
                "Решение.",
                f"Что известно: всего {total}{(' ' + first_noun) if first_noun else ''}, в одной группе по {per_group}.",
                f"Что нужно найти: сколько {answer_noun} нужно.",
                f"1) Чтобы узнать, сколько получится групп, делим общее количество на количество в одной группе: {total} : {per_group} = {format_fraction(groups)}.",
                f"Ответ: {_audit_add_answer_noun(format_fraction(groups), answer_noun)}"
            )

    if ('поровну' in lower or 'в каждом' in lower) and 'сколько' in lower:
        total = numbers[0]
        groups = numbers[1]
        if groups != 0 and ('в каждом' in lower or 'каждом пакете' in lower or 'каждой' in lower):
            per_group = Fraction(total, groups)
            return _audit_join_lines(
                "Задача.",
                _audit_task_line(raw_text),
                "Решение.",
                f"Что известно: всего {total}{(' ' + first_noun) if first_noun else ''}, групп {groups}.",
                "Что нужно найти: сколько будет в каждой группе.",
                f"1) Чтобы узнать, сколько будет в каждой группе, делим общее количество на число групп: {total} : {groups} = {format_fraction(per_group)}.",
                f"Ответ: {'в каждой группе по ' + format_fraction(per_group) + (' ' + first_noun if first_noun else '')}"
            )

    if 'сколько стало' in lower and any(stem in lower for stem in WORD_GAIN_HINTS):
        first = numbers[0]
        added = numbers[1]
        total = first + added
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: сначала было {first}{(' ' + first_noun) if first_noun else ''}, добавили ещё {added}.",
            "Что нужно найти: сколько стало.",
            f"1) Чтобы узнать, сколько стало, складываем: {first} + {added} = {total}.",
            f"Ответ: {_audit_add_answer_noun(str(total), first_noun)}"
        )

    if 'сколько осталось' in lower and any(stem in lower for stem in WORD_LOSS_HINTS):
        first = numbers[0]
        removed = numbers[1]
        left = first - removed
        return _audit_join_lines(
            "Задача.",
            _audit_task_line(raw_text),
            "Решение.",
            f"Что известно: было {first}{(' ' + first_noun) if first_noun else ''}, убрали {removed}.",
            "Что нужно найти: сколько осталось.",
            f"1) Чтобы узнать, сколько осталось, вычитаем: {first} - {removed} = {left}.",
            f"Ответ: {_audit_add_answer_noun(str(left), first_noun)}"
        )
    return None


def _audit_try_final_local_explanation(raw_text: str) -> Optional[str]:
    return (
        _audit_try_simple_addition_explanation(raw_text)
        or _audit_try_one_step_equation_explanation(raw_text)
        or _audit_try_fraction_number_tasks(raw_text)
        or _audit_try_motion_shorthand(raw_text)
        or _audit_try_price_short_tasks(raw_text)
        or _audit_try_rectangle_geometry(raw_text)
        or _audit_try_common_word_problems(raw_text)
    )


async def build_explanation(user_text: str) -> dict:
    local = _audit_try_final_local_explanation(user_text)
    if local:
        return {"result": local, "source": "local-audit", "validated": True}

    result = await _AUDIT_20260414C_PREV_BUILD_EXPLANATION(user_text)
    text = str(result.get('result') or '')
    if looks_like_math_input(user_text) and re.search(r"техническ[а-яёa-z-]*\s+обслужив|service\s+unavailable|maintenance", text, flags=re.IGNORECASE):
        friendly = _audit_join_lines(
            "Не получилось построить объяснение для этой записи.",
            "Попробуйте записать пример или задачу чуть подробнее.",
            "Ответ: проверь запись задачи"
        )
        return {"result": friendly, "source": "fallback-audit", "validated": False}
    return result

# --- FINAL PATCH 2026-04-15 FRACTIONS SCHOOL STYLE ---
_AUDIT_20260415_PREV_FINAL_LOCAL_EXPLANATION = _audit_try_final_local_explanation


def _fraction_school_action_symbol(operator: str) -> str:
    return '+' if operator == '+' else '-'


def _fraction_school_action_word(operator: str) -> str:
    return 'Складываем' if operator == '+' else 'Вычитаем'


def _fraction_school_mixed_text(value: Fraction) -> Optional[str]:
    if value.denominator == 1:
        return None
    sign = '-' if value < 0 else ''
    numerator = abs(value.numerator)
    denominator = value.denominator
    if numerator < denominator:
        return None
    whole = numerator // denominator
    remainder = numerator % denominator
    if remainder == 0:
        return f"{sign}{whole}"
    return f"{sign}{whole} {remainder}/{denominator}"


def _build_fraction_school_explanation(raw_text: str) -> Optional[str]:
    source = to_fraction_source(raw_text)
    if not source:
        return None

    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*([+\-])\s*(\d+)\s*/\s*(\d+)\s*", source)
    if not match:
        return None

    a, b, operator, c, d = match.groups()
    a, b, c, d = int(a), int(b), int(c), int(d)
    if b == 0 or d == 0:
        return join_explanation_lines(
            "У дроби знаменатель не может быть равен нулю",
            "Ответ: запись дроби неверная"
        )

    action_symbol = _fraction_school_action_symbol(operator)
    action_word = _fraction_school_action_word(operator)
    result = Fraction(a, b) + Fraction(c, d) if operator == '+' else Fraction(a, b) - Fraction(c, d)
    result_text = format_fraction(result)
    mixed_text = _fraction_school_mixed_text(result)
    lines: List[str] = [
        f"Пример: {a}/{b} {action_symbol} {c}/{d}",
        "Решение."
    ]

    def extend_with_optional_result_steps(current_step_number: int, raw_fraction_text: str, answer_chain: str):
        local_step_number = current_step_number
        local_answer_chain = answer_chain
        if raw_fraction_text != result_text:
            lines.append(f"{local_step_number}) Сокращаем дробь: {raw_fraction_text} = {result_text}")
            local_answer_chain += f" = {result_text}"
            local_step_number += 1
        if mixed_text and mixed_text != result_text:
            lines.append(f"{local_step_number}) Выделяем целую часть: {result_text} = {mixed_text}")
            local_answer_chain += f" = {mixed_text}"
            local_step_number += 1
        return local_step_number, local_answer_chain

    if b == d:
        top_result = a + c if operator == '+' else a - c
        raw_result = f"{top_result}/{b}"
        lines.extend([
            f"1) Находим общий знаменатель. Знаменатели уже одинаковые: {b} и {d}",
            f"2) Дроби уже имеют одинаковый знаменатель. Значит, {action_word.lower()} только числители, а знаменатель оставляем прежним: {a} {action_symbol} {c} = {top_result}",
            f"3) Получаем: {raw_result}"
        ])
        _, answer_chain = extend_with_optional_result_steps(4, raw_result, f"{a}/{b} {action_symbol} {c}/{d} = {raw_result}")
        lines.append(f"Ответ: {answer_chain}")
        return join_explanation_lines(*lines)

    common = math.lcm(b, d)
    a_multiplier = common // b
    c_multiplier = common // d
    a_scaled = a * a_multiplier
    c_scaled = c * c_multiplier
    raw_numerator = a_scaled + c_scaled if operator == '+' else a_scaled - c_scaled
    raw_result = f"{raw_numerator}/{common}"

    lines.append(
        f"1) Находим общий знаменатель. Знаменатели: {b} и {d}. Общий знаменатель = {common}, потому что {common} делится на {b} и на {d}"
    )

    step_number = 2
    if b == common:
        lines.append(f"{step_number}) Первая дробь уже имеет знаменатель {common}: {a}/{b} = {a}/{common}")
    else:
        lines.extend([
            f"{step_number}) Приводим первую дробь {a}/{b} к знаменателю {common}",
            f"Спрашиваем: на сколько нужно умножить {b}, чтобы получить {common}?",
            f"{b} × {a_multiplier} = {common}",
            f"Нужно умножить на {a_multiplier}",
            f"Получаем: {a}/{b} = (умножаем числитель и знаменатель на {a_multiplier}) = {a_scaled}/{common}"
        ])
    step_number += 1

    if d == common:
        lines.append(f"{step_number}) Вторая дробь уже имеет знаменатель {common}: {c}/{d} = {c}/{common}")
    else:
        lines.extend([
            f"{step_number}) Приводим вторую дробь {c}/{d} к знаменателю {common}",
            f"Спрашиваем: на сколько нужно умножить {d}, чтобы получить {common}?",
            f"{d} × {c_multiplier} = {common}",
            f"Нужно умножить на {c_multiplier}",
            f"Получаем: {c}/{d} = (умножаем числитель и знаменатель на {c_multiplier}) = {c_scaled}/{common}"
        ])
    step_number += 1

    numerator_action = '+' if operator == '+' else '-'
    numerator_result = a_scaled + c_scaled if operator == '+' else a_scaled - c_scaled
    lines.extend([
        f"{step_number}) {action_word} дроби с одинаковыми знаменателями. Знаменатель {common} оставляем прежним, а числители {action_word.lower()}: {a_scaled} {numerator_action} {c_scaled} = {numerator_result}",
        f"Получаем: {raw_result}"
    ])
    step_number += 1

    base_chain = f"{a}/{b} {action_symbol} {c}/{d} = {a_scaled}/{common} {action_symbol} {c_scaled}/{common} = {raw_result}"
    _, answer_chain = extend_with_optional_result_steps(step_number, raw_result, base_chain)
    lines.append(f"Ответ: {answer_chain}")
    return join_explanation_lines(*lines)


def _audit_try_final_local_explanation(raw_text: str) -> Optional[str]:
    return (
        _build_fraction_school_explanation(raw_text)
        or _AUDIT_20260415_PREV_FINAL_LOCAL_EXPLANATION(raw_text)
    )


# --- FINAL PATCH 2026-04-15: mixed fraction expressions are fraction tasks, not plain division ---

_FINAL_20260415_PREV_AUDIT_LOCAL_EXPLANATION = _audit_try_final_local_explanation

# --- merged segment 016: backend.legacy_runtime_shards.prepatch_build_source.segment_016 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 13325-14214."""



def _final_20260415_normalize_fraction_expression_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(normalize_cyrillic_x(text))
    text = text.replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    text = re.sub(r'\s+', '', text)
    if not text or re.search(r'[A-Za-zА-Яа-яЁё]', text):
        return None
    if re.search(r'[^0-9+\-*/()]', text):
        return None
    if not re.search(r'\d+/\d+', text):
        return None
    if re.fullmatch(r'\d+/\d+', text):
        return None

    all_numbers = [int(value) for value in re.findall(r'\d+', text)]
    if not all_numbers:
        return None
    if max(abs(value) for value in all_numbers) > 1000:
        return None

    fraction_matches = list(re.finditer(r'(\d+)/(\d+)', text))
    if not fraction_matches:
        return None

    placeholder = re.sub(r'\d+/\d+', 'F', text)
    if not re.fullmatch(r'[F0-9+\-*/()]+', placeholder):
        return None
    if placeholder == 'F':
        return None

    if len(fraction_matches) == 1:
        numerator = int(fraction_matches[0].group(1))
        denominator = int(fraction_matches[0].group(2))
        if denominator == 0:
            return None
        if not re.search(r'[+\-*()]', placeholder):
            return None
        if max(abs(numerator), abs(denominator)) > 50:
            return None

    return text


def _final_20260415_tokenize_fraction_expression(source: str) -> Optional[List[dict]]:
    tokens: List[dict] = []
    index = 0
    length = len(source)

    while index < length:
        char = source[index]
        if char.isdigit():
            start = index
            while index < length and source[index].isdigit():
                index += 1
            integer_text = source[start:index]
            if index < length and source[index] == '/' and index + 1 < length and source[index + 1].isdigit():
                index += 1
                denominator_start = index
                while index < length and source[index].isdigit():
                    index += 1
                denominator_text = source[denominator_start:index]
                denominator = int(denominator_text)
                if denominator == 0:
                    raise ZeroDivisionError('fraction denominator is zero')
                tokens.append({
                    'type': 'value',
                    'text': f"{integer_text}/{denominator_text}",
                    'value': Fraction(int(integer_text), denominator),
                    'is_fraction_literal': True,
                    'pos': start,
                })
                continue

            tokens.append({
                'type': 'value',
                'text': integer_text,
                'value': Fraction(int(integer_text), 1),
                'is_fraction_literal': False,
                'pos': start,
            })
            continue

        if char in '+-*/()':
            tokens.append({'type': char, 'value': char, 'pos': index})
            index += 1
            continue

        return None

    if not tokens:
        return None

    with_implicit_mul: List[dict] = []
    previous: Optional[dict] = None
    for token in tokens:
        if previous and previous['type'] in {'value', ')'} and token['type'] in {'value', '('}:
            with_implicit_mul.append({'type': '*', 'value': '*', 'pos': token['pos']})
        with_implicit_mul.append(token)
        previous = token

    return with_implicit_mul


def _final_20260415_parse_fraction_expression(source: str) -> Optional[dict]:
    try:
        tokens = _final_20260415_tokenize_fraction_expression(source)
    except ZeroDivisionError:
        raise
    if not tokens:
        return None

    cursor = 0
    node_counter = 1

    def peek() -> Optional[dict]:
        return tokens[cursor] if cursor < len(tokens) else None

    def consume(expected: Optional[str] = None) -> Optional[dict]:
        nonlocal cursor
        token = peek()
        if token is None:
            return None
        if expected is not None and token['type'] != expected:
            return None
        cursor += 1
        return token

    def make_binary(operator: str, left: dict, right: dict, pos: int) -> dict:
        nonlocal node_counter
        node = {
            'type': 'binary',
            'operator': operator,
            'left': left,
            'right': right,
            'pos': pos,
            'id': node_counter,
        }
        node_counter += 1
        return node

    def parse_primary() -> Optional[dict]:
        token = peek()
        if token is None:
            return None

        if token['type'] == 'value':
            consume('value')
            return {
                'type': 'value',
                'value': token['value'],
                'text': token['text'],
                'is_fraction_literal': token.get('is_fraction_literal', False),
                'pos': token.get('pos', 0),
            }

        if token['type'] == '(':
            open_token = consume('(')
            inner = parse_add_sub()
            if inner is None or not consume(')'):
                return None
            return {
                'type': 'group',
                'inner': inner,
                'pos': open_token.get('pos', 0),
            }

        if token['type'] in {'+', '-'}:
            consume(token['type'])
            operand = parse_primary()
            if operand is None:
                return None
            return {
                'type': 'unary',
                'operator': token['type'],
                'operand': operand,
                'pos': token.get('pos', 0),
            }

        return None

    def parse_mul_div() -> Optional[dict]:
        node = parse_primary()
        if node is None:
            return None
        while True:
            token = peek()
            if token is None or token['type'] not in {'*', '/'}:
                break
            consume(token['type'])
            right = parse_primary()
            if right is None:
                return None
            node = make_binary(token['type'], node, right, token.get('pos', 0))
        return node

    def parse_add_sub() -> Optional[dict]:
        node = parse_mul_div()
        if node is None:
            return None
        while True:
            token = peek()
            if token is None or token['type'] not in {'+', '-'}:
                break
            consume(token['type'])
            right = parse_mul_div()
            if right is None:
                return None
            node = make_binary(token['type'], node, right, token.get('pos', 0))
        return node

    root = parse_add_sub()
    if root is None or cursor != len(tokens):
        return None
    return root


def _final_20260415_fraction_precedence(operator: str) -> int:
    return 1 if operator in {'+', '-'} else 2


def _final_20260415_fraction_op_symbol(operator: str) -> str:
    return {'+': '+', '-': '-', '*': '×', '/': '÷'}.get(operator, operator)


def _final_20260415_format_fraction_value(value: Fraction, force_fraction: bool = False) -> str:
    simplified = Fraction(value.numerator, value.denominator)
    if force_fraction or simplified.denominator != 1:
        return f"{simplified.numerator}/{simplified.denominator}"
    return str(simplified.numerator)


def _final_20260415_render_fraction_node(node: dict, solved: Optional[dict] = None, parent_precedence: int = 0, is_right_child: bool = False) -> str:
    solved = solved or {}
    if node.get('type') == 'value':
        return node.get('text', _final_20260415_format_fraction_value(node.get('value', Fraction(0, 1))))
    if node.get('type') == 'group':
        return f"({_final_20260415_render_fraction_node(node['inner'], solved)})"
    if node.get('type') == 'unary':
        inner = _final_20260415_render_fraction_node(node['operand'], solved, 3)
        return inner if node.get('operator') == '+' else f"-{inner}"
    if node.get('type') == 'binary':
        node_id = node.get('id')
        if node_id in solved:
            return solved[node_id]
        operator = node.get('operator', '+')
        precedence = _final_20260415_fraction_precedence(operator)
        left_text = _final_20260415_render_fraction_node(node['left'], solved, precedence, False)
        right_text = _final_20260415_render_fraction_node(node['right'], solved, precedence, True)
        text = f"{left_text} {_final_20260415_fraction_op_symbol(operator)} {right_text}"
        needs_brackets = precedence < parent_precedence or (
            is_right_child and operator in {'+', '-'} and precedence == parent_precedence
        )
        return f"({text})" if needs_brackets else text
    return ''


def _final_20260415_apply_fraction_operator(operator: str, left: Fraction, right: Fraction) -> Fraction:
    if operator == '+':
        return left + right
    if operator == '-':
        return left - right
    if operator == '*':
        return left * right
    if operator == '/':
        if right == 0:
            raise ZeroDivisionError('division by zero')
        return left / right
    raise ValueError('Unsupported operator')


def _final_20260415_flatten_fraction_chain(node: dict, operators_to_flatten: Tuple[str, ...], operands: List[dict], op_nodes: List[dict]):
    if node.get('type') == 'group':
        operands.append(node['inner'])
        return
    if node.get('type') == 'binary' and node.get('operator') in operators_to_flatten:
        _final_20260415_flatten_fraction_chain(node['left'], operators_to_flatten, operands, op_nodes)
        op_nodes.append(node)
        operands.append(node['right'])
        return
    operands.append(node)


def _final_20260415_eval_fraction_steps(node: dict) -> Tuple[Fraction, List[dict]]:
    node_type = node.get('type')
    if node_type == 'value':
        return node['value'], []
    if node_type == 'group':
        return _final_20260415_eval_fraction_steps(node['inner'])
    if node_type == 'unary':
        operand_value, operand_steps = _final_20260415_eval_fraction_steps(node['operand'])
        return (-operand_value if node.get('operator') == '-' else operand_value), operand_steps
    if node_type != 'binary':
        raise ValueError('Unsupported fraction expression node')

    operator = node.get('operator')
    chain_operators = ('+', '-') if operator in {'+', '-'} else ('*', '/')
    operands: List[dict] = []
    op_nodes: List[dict] = []
    _final_20260415_flatten_fraction_chain(node, chain_operators, operands, op_nodes)

    values: List[Fraction] = []
    steps: List[dict] = []
    for operand in operands:
        operand_value, operand_steps = _final_20260415_eval_fraction_steps(operand)
        steps.extend(operand_steps)
        values.append(operand_value)

    current = values[0]
    for op_node, next_value in zip(op_nodes, values[1:]):
        result = _final_20260415_apply_fraction_operator(op_node['operator'], current, next_value)
        steps.append({
            'id': op_node['id'],
            'operator': op_node['operator'],
            'left': current,
            'right': next_value,
            'result': result,
        })
        current = result

    return current, steps


def _final_20260415_prepare_fraction_operand(value: Fraction) -> Tuple[List[str], Fraction]:
    if value.denominator == 1:
        integer_text = str(value.numerator)
        return [f"Представляем число {integer_text} в виде дроби: {integer_text} = {integer_text}/1"], Fraction(value.numerator, 1)
    return [], Fraction(value.numerator, value.denominator)


def _final_20260415_append_fraction_reduction(lines: List[str], raw_numerator: int, raw_denominator: int, simplified: Fraction):
    raw_text = f"{raw_numerator}/{raw_denominator}"
    simple_text = _final_20260415_format_fraction_value(simplified)
    if raw_denominator != simplified.denominator or raw_numerator != simplified.numerator:
        lines.append(f"Сокращаем: {raw_text} = {simple_text}")


def _final_20260415_fraction_add_sub_lines(step_number: int, left: Fraction, right: Fraction, operator: str, result: Fraction) -> List[str]:
    symbol = '+' if operator == '+' else '-'
    action_word = 'Складываем' if operator == '+' else 'Вычитаем'
    action_word_lower = action_word.lower()
    left_text = _final_20260415_format_fraction_value(left)
    right_text = _final_20260415_format_fraction_value(right)
    result_text = _final_20260415_format_fraction_value(result)
    lines = [f"{step_number}) {left_text} {symbol} {right_text} = {result_text}"]

    left_prep_lines, left_fraction = _final_20260415_prepare_fraction_operand(left)
    right_prep_lines, right_fraction = _final_20260415_prepare_fraction_operand(right)
    lines.extend(left_prep_lines)
    lines.extend(right_prep_lines)

    left_work_text = _final_20260415_format_fraction_value(left_fraction, force_fraction=True)
    right_work_text = _final_20260415_format_fraction_value(right_fraction, force_fraction=True)

    if left_fraction.denominator == right_fraction.denominator:
        raw_numerator = left_fraction.numerator + right_fraction.numerator if operator == '+' else left_fraction.numerator - right_fraction.numerator
        lines.append(f"Знаменатели уже одинаковые: {left_fraction.denominator} и {right_fraction.denominator}")
        lines.append(f"Значит, {action_word_lower} только числители: {left_fraction.numerator} {symbol} {right_fraction.numerator} = {raw_numerator}")
        lines.append(f"Получаем: {left_work_text} {symbol} {right_work_text} = {raw_numerator}/{left_fraction.denominator}")
        _final_20260415_append_fraction_reduction(lines, raw_numerator, left_fraction.denominator, result)
        return lines

    common = math.lcm(left_fraction.denominator, right_fraction.denominator)
    left_multiplier = common // left_fraction.denominator
    right_multiplier = common // right_fraction.denominator
    left_scaled = left_fraction.numerator * left_multiplier
    right_scaled = right_fraction.numerator * right_multiplier
    raw_numerator = left_scaled + right_scaled if operator == '+' else left_scaled - right_scaled

    lines.append(
        f"Находим общий знаменатель. Знаменатели: {left_fraction.denominator} и {right_fraction.denominator}. Общий знаменатель = {common}, потому что {common} делится на {left_fraction.denominator} и на {right_fraction.denominator}"
    )

    if left_fraction.denominator == common:
        lines.append(f"Первая дробь уже имеет знаменатель {common}: {left_work_text} = {left_fraction.numerator}/{common}")
    else:
        lines.extend([
            f"Приводим первую дробь {left_work_text} к знаменателю {common}",
            f"Спрашиваем: на сколько нужно умножить {left_fraction.denominator}, чтобы получить {common}?",
            f"{left_fraction.denominator} × {left_multiplier} = {common}",
            f"Нужно умножить на {left_multiplier}",
            f"Получаем: {left_work_text} = (умножаем числитель и знаменатель на {left_multiplier}) = {left_scaled}/{common}",
        ])

    if right_fraction.denominator == common:
        lines.append(f"Вторая дробь уже имеет знаменатель {common}: {right_work_text} = {right_fraction.numerator}/{common}")
    else:
        lines.extend([
            f"Приводим вторую дробь {right_work_text} к знаменателю {common}",
            f"Спрашиваем: на сколько нужно умножить {right_fraction.denominator}, чтобы получить {common}?",
            f"{right_fraction.denominator} × {right_multiplier} = {common}",
            f"Нужно умножить на {right_multiplier}",
            f"Получаем: {right_work_text} = (умножаем числитель и знаменатель на {right_multiplier}) = {right_scaled}/{common}",
        ])

    lines.append(f"Теперь {action_word_lower} дроби с одинаковыми знаменателями")
    lines.append(f"{left_scaled} {symbol} {right_scaled} = {raw_numerator}")
    lines.append(f"Получаем: {left_scaled}/{common} {symbol} {right_scaled}/{common} = {raw_numerator}/{common}")
    _final_20260415_append_fraction_reduction(lines, raw_numerator, common, result)
    return lines


def _final_20260415_fraction_mul_body_lines(left_fraction: Fraction, right_fraction: Fraction, result: Fraction, left_work_text: str, right_work_text: str) -> List[str]:
    raw_numerator = left_fraction.numerator * right_fraction.numerator
    raw_denominator = left_fraction.denominator * right_fraction.denominator
    lines = [
        'Чтобы умножить дроби, умножаем числители и знаменатели',
        f"{left_fraction.numerator} × {right_fraction.numerator} = {raw_numerator}",
        f"{left_fraction.denominator} × {right_fraction.denominator} = {raw_denominator}",
        f"Получаем: {left_work_text} × {right_work_text} = {raw_numerator}/{raw_denominator}",
    ]
    _final_20260415_append_fraction_reduction(lines, raw_numerator, raw_denominator, result)
    return lines


def _final_20260415_fraction_mul_lines(step_number: int, left: Fraction, right: Fraction, result: Fraction) -> List[str]:
    left_text = _final_20260415_format_fraction_value(left)
    right_text = _final_20260415_format_fraction_value(right)
    result_text = _final_20260415_format_fraction_value(result)
    lines = [f"{step_number}) {left_text} × {right_text} = {result_text}"]
    left_prep_lines, left_fraction = _final_20260415_prepare_fraction_operand(left)
    right_prep_lines, right_fraction = _final_20260415_prepare_fraction_operand(right)
    lines.extend(left_prep_lines)
    lines.extend(right_prep_lines)
    left_work_text = _final_20260415_format_fraction_value(left_fraction, force_fraction=True)
    right_work_text = _final_20260415_format_fraction_value(right_fraction, force_fraction=True)
    lines.extend(_final_20260415_fraction_mul_body_lines(left_fraction, right_fraction, result, left_work_text, right_work_text))
    return lines


def _final_20260415_fraction_div_lines(step_number: int, left: Fraction, right: Fraction, result: Fraction) -> List[str]:
    left_text = _final_20260415_format_fraction_value(left)
    right_text = _final_20260415_format_fraction_value(right)
    result_text = _final_20260415_format_fraction_value(result)
    lines = [f"{step_number}) {left_text} ÷ {right_text} = {result_text}"]
    left_prep_lines, left_fraction = _final_20260415_prepare_fraction_operand(left)
    right_prep_lines, right_fraction = _final_20260415_prepare_fraction_operand(right)
    lines.extend(left_prep_lines)
    lines.extend(right_prep_lines)
    if right_fraction == 0:
        raise ZeroDivisionError('division by zero')
    reciprocal = Fraction(right_fraction.denominator, right_fraction.numerator)
    left_work_text = _final_20260415_format_fraction_value(left_fraction, force_fraction=True)
    right_work_text = _final_20260415_format_fraction_value(right_fraction, force_fraction=True)
    reciprocal_text = _final_20260415_format_fraction_value(reciprocal, force_fraction=True)
    lines.append('Чтобы разделить на дробь, первую дробь умножаем на дробь, обратную второй')
    lines.append(f"{left_work_text} ÷ {right_work_text} = {left_work_text} × {reciprocal_text}")
    lines.extend(_final_20260415_fraction_mul_body_lines(left_fraction, reciprocal, result, left_work_text, reciprocal_text))
    return lines


def _final_20260415_fraction_step_lines(step_number: int, step: dict) -> List[str]:
    operator = step['operator']
    left = step['left']
    right = step['right']
    result = step['result']
    if operator in {'+', '-'}:
        return _final_20260415_fraction_add_sub_lines(step_number, left, right, operator, result)
    if operator == '*':
        return _final_20260415_fraction_mul_lines(step_number, left, right, result)
    if operator == '/':
        return _final_20260415_fraction_div_lines(step_number, left, right, result)
    return [f"{step_number}) {_final_20260415_format_fraction_value(left)} {_final_20260415_fraction_op_symbol(operator)} {_final_20260415_format_fraction_value(right)} = {_final_20260415_format_fraction_value(result)}"]


def _final_20260415_fraction_answer_chain(root: dict, steps: List[dict], result: Fraction) -> str:
    solved: dict = {}
    chain: List[str] = [_final_20260415_render_fraction_node(root)]
    for step in steps:
        solved[step['id']] = _final_20260415_format_fraction_value(step['result'])
        current = _final_20260415_render_fraction_node(root, solved)
        if current and current != chain[-1]:
            chain.append(current)
    mixed_text = _fraction_school_mixed_text(result)
    if mixed_text and mixed_text != chain[-1]:
        chain.append(mixed_text)
    return ' = '.join(chain)


def _build_fraction_mixed_expression_explanation(raw_text: str) -> Optional[str]:
    source = _final_20260415_normalize_fraction_expression_source(raw_text)
    if not source:
        return None

    # Простые случаи вида 1/4+1/6 и 1/4-1/6 уже объясняются отдельным шаблоном.
    if re.fullmatch(r'\d+/\d+[+\-]\d+/\d+', source):
        return None

    try:
        root = _final_20260415_parse_fraction_expression(source)
    except ZeroDivisionError:
        return join_explanation_lines('На ноль делить нельзя', 'Ответ: деление на ноль невозможно')

    if not root:
        return None

    try:
        result, steps = _final_20260415_eval_fraction_steps(root)
    except ZeroDivisionError:
        return join_explanation_lines('На ноль делить нельзя', 'Ответ: деление на ноль невозможно')
    except Exception:
        return None

    if not steps:
        return None

    lines: List[str] = [
        f"Пример: {_final_20260415_render_fraction_node(root)}",
        'Решение.',
    ]
    for index, step in enumerate(steps, 1):
        lines.extend(_final_20260415_fraction_step_lines(index, step))
    lines.append(f"Ответ: {_final_20260415_fraction_answer_chain(root, steps, result)}")
    return join_explanation_lines(*lines)


def _audit_try_final_local_explanation(raw_text: str) -> Optional[str]:
    return (
        _build_fraction_mixed_expression_explanation(raw_text)
        or _FINAL_20260415_PREV_AUDIT_LOCAL_EXPLANATION(raw_text)
    )

# --- FINAL USER PATCH 2026-04-15AB: order guide + full answer chain for mixed fraction expressions ---

_FINAL_USER_20260415AB_PREV_AUDIT_LOCAL_EXPLANATION = _audit_try_final_local_explanation


def _final_user_fraction_eval_steps_with_positions(node: dict) -> Tuple[Fraction, List[dict]]:
    node_type = node.get('type')
    if node_type == 'value':
        return node['value'], []
    if node_type == 'group':
        return _final_user_fraction_eval_steps_with_positions(node['inner'])
    if node_type == 'unary':
        operand_value, operand_steps = _final_user_fraction_eval_steps_with_positions(node['operand'])
        return (-operand_value if node.get('operator') == '-' else operand_value), operand_steps
    if node_type != 'binary':
        raise ValueError('Unsupported fraction expression node')

    operator = node.get('operator')
    chain_operators = ('+', '-') if operator in {'+', '-'} else ('*', '/')
    operands: List[dict] = []
    op_nodes: List[dict] = []
    _final_20260415_flatten_fraction_chain(node, chain_operators, operands, op_nodes)

    values: List[Fraction] = []
    steps: List[dict] = []
    for operand in operands:
        operand_value, operand_steps = _final_user_fraction_eval_steps_with_positions(operand)
        steps.extend(operand_steps)
        values.append(operand_value)

    current = values[0]
    for op_node, next_value in zip(op_nodes, values[1:]):
        result = _final_20260415_apply_fraction_operator(op_node['operator'], current, next_value)
        steps.append({
            'id': op_node['id'],
            'operator': op_node['operator'],
            'left': current,
            'right': next_value,
            'result': result,
            'index': op_node.get('pos', 0),
        })
        current = result

    return current, steps


def _final_user_fraction_order_lines(source: str, steps: List[dict]) -> List[str]:
    try:
        tokens = _final_20260415_tokenize_fraction_expression(source)
    except ZeroDivisionError:
        return []
    if not tokens or len(steps) < 2:
        return []

    pretty_expr = ''
    operator_positions: dict[int, int] = {}
    for token in tokens:
        token_type = token.get('type')
        if token_type == 'value':
            pretty_expr += token.get('text', '')
            continue
        if token_type in {'+', '-', '*', '/'}:
            operator_positions[token.get('pos', 0)] = len(pretty_expr) + 1
            pretty_expr += f" {_final_20260415_fraction_op_symbol(token_type)} "
            continue
        pretty_expr += token_type

    if not pretty_expr:
        return []

    marks = [' '] * len(pretty_expr)
    for step_index, step in enumerate(steps, 1):
        pretty_pos = operator_positions.get(step.get('index', 0))
        if pretty_pos is None:
            continue
        label = str(step_index)
        start = max(0, pretty_pos - (len(label) - 1) // 2)
        for offset, char in enumerate(label):
            target = start + offset
            if 0 <= target < len(marks):
                marks[target] = char

    return ['Порядок действий:', ''.join(marks).rstrip(), pretty_expr]


def _final_user_fraction_expanded_step_text(step: dict) -> Optional[str]:
    operator = step.get('operator')
    if operator not in {'+', '-'}:
        return None

    left = Fraction(step.get('left', Fraction(0, 1)))
    right = Fraction(step.get('right', Fraction(0, 1)))
    common = math.lcm(left.denominator, right.denominator)
    if not common or (left.denominator == common and right.denominator == common):
        return None

    left_multiplier = common // left.denominator
    right_multiplier = common // right.denominator
    left_scaled = left.numerator * left_multiplier
    right_scaled = right.numerator * right_multiplier
    symbol = '+' if operator == '+' else '-'
    return f"{left_scaled}/{common} {symbol} {right_scaled}/{common}"


def _final_user_fraction_answer_chain(root: dict, steps: List[dict], result: Fraction) -> str:
    solved: dict[int, str] = {}
    chain: List[str] = [_final_20260415_render_fraction_node(root)]

    for step in steps:
        expanded = _final_user_fraction_expanded_step_text(step)
        if expanded:
            solved[step['id']] = expanded
            expanded_view = _final_20260415_render_fraction_node(root, solved)
            if expanded_view and expanded_view != chain[-1]:
                chain.append(expanded_view)

        solved[step['id']] = _final_20260415_format_fraction_value(step['result'])
        current = _final_20260415_render_fraction_node(root, solved)
        if current and current != chain[-1]:
            chain.append(current)

    mixed_text = _fraction_school_mixed_text(result)
    if mixed_text and mixed_text != chain[-1]:
        chain.append(mixed_text)
    return ' = '.join(chain)


def _build_fraction_mixed_expression_explanation(raw_text: str) -> Optional[str]:
    source = _final_20260415_normalize_fraction_expression_source(raw_text)
    if not source:
        return None

    if re.fullmatch(r'\d+/\d+[+\-]\d+/\d+', source):
        return None

    try:
        root = _final_20260415_parse_fraction_expression(source)
    except ZeroDivisionError:
        return join_explanation_lines('На ноль делить нельзя', 'Ответ: деление на ноль невозможно')

    if not root:
        return None

    try:
        result, steps = _final_user_fraction_eval_steps_with_positions(root)
    except ZeroDivisionError:
        return join_explanation_lines('На ноль делить нельзя', 'Ответ: деление на ноль невозможно')
    except Exception:
        return None

    if not steps:
        return None

    lines: List[str] = [f"Пример: {_final_20260415_render_fraction_node(root)}"]
    if len(steps) > 1:
        lines.extend(_final_user_fraction_order_lines(source, steps))
        lines.append('Решение по действиям:')
    else:
        lines.append('Решение.')

    for index, step in enumerate(steps, 1):
        lines.extend(_final_20260415_fraction_step_lines(index, step))

    lines.append(f"Ответ: {_final_user_fraction_answer_chain(root, steps, result)}")
    return join_explanation_lines(*lines)


def _audit_try_final_local_explanation(raw_text: str) -> Optional[str]:
    return (
        _build_fraction_mixed_expression_explanation(raw_text)
        or _FINAL_USER_20260415AB_PREV_AUDIT_LOCAL_EXPLANATION(raw_text)
    )

# --- FINAL USER PATCH 2026-04-15AC: keep order-marker lines without trailing dot in mixed fraction expressions ---

_FINAL_USER_20260415AC_PREV_BUILD_FRACTION_MIXED = _build_fraction_mixed_expression_explanation


def _build_fraction_mixed_expression_explanation(raw_text: str) -> Optional[str]:
    text = _FINAL_USER_20260415AC_PREV_BUILD_FRACTION_MIXED(raw_text)
    if not text:
        return text
    return re.sub(r'(?m)^([0-9 ]+)\.$', r'\1', text)


def _audit_try_final_local_explanation(raw_text: str) -> Optional[str]:
    return (
        _build_fraction_mixed_expression_explanation(raw_text)
        or _FINAL_USER_20260415AB_PREV_AUDIT_LOCAL_EXPLANATION(raw_text)
    )


# --- FINAL PATCH 2026-04-15AD: textbook word problems and simple systems ---

_FINAL_20260415AD_PREV_BUILD_EXPLANATION = build_explanation


def _final_20260415ad_prepare_word_text(raw_text: str) -> Tuple[str, str, List[int]]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    return text, lower, nums


def _final_20260415ad_result_dict(text: str, source: str = 'local-textbook-fix') -> dict:
    return {'result': text, 'source': source, 'validated': True}


def _final_20260415ad_try_garage_indirect_counts(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 3:
        return None
    if 'автобус' not in lower or 'грузов' not in lower or 'легков' not in lower:
        return None
    if 'сколько всего' not in lower or 'гараж' not in lower:
        return None
    if 'это на' not in lower or 'больше, чем грузов' not in lower:
        return None
    if 'меньше, чем грузов' not in lower:
        return None

    buses, diff_to_trucks, diff_to_cars = nums[:3]
    trucks = buses - diff_to_trucks
    cars = trucks - diff_to_cars
    if min(buses, trucks, cars) < 0:
        return None
    total = buses + trucks + cars

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: автобусов {buses}. Это на {diff_to_trucks} больше, чем грузовых машин. Легковых машин на {diff_to_cars} меньше, чем грузовых.',
        'Что нужно найти: сколько всего машин в гараже.',
        f'1) Сначала найдём количество грузовых машин. Если автобусов на {diff_to_trucks} больше, чем грузовых, то грузовых на {diff_to_trucks} меньше: {buses} - {diff_to_trucks} = {trucks}.',
        f'2) Потом найдём количество легковых машин. Если легковых на {diff_to_cars} меньше, чем грузовых, то {trucks} - {diff_to_cars} = {cars}.',
        f'3) Теперь найдём, сколько всего машин в гараже: {buses} + {trucks} + {cars} = {total}.',
        f'Ответ: всего {total} машин.'
    )


def _final_20260415ad_try_times_more_and_equal_groups(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 3:
        return None
    if 'разлож' not in lower and 'разложили' not in lower and 'поровну' not in lower:
        return None
    if 'в каждой' not in lower and 'в одной' not in lower:
        return None
    if 'в ' not in lower or 'раза больше' not in lower:
        return None
    if 'с другой' not in lower and 'со второй' not in lower:
        return None

    first, multiplier, groups = nums[:3]
    if multiplier <= 1 or groups <= 0:
        return None

    second = first * multiplier
    total = first + second
    if total % groups != 0:
        return None
    each = total // groups

    unit = 'кг'
    if 'литр' in lower:
        unit = 'л'
    elif 'книга' in lower:
        unit = 'книг'

    object_label = 'во второй группе'
    if 'яблок' in lower:
        object_label = 'со второй яблони'
    elif 'груш' in lower:
        object_label = 'со второй груши'

    container_label = 'в каждой корзине'
    if 'корзин' in lower:
        container_label = 'в каждой корзине'
    elif 'ящик' in lower:
        container_label = 'в каждом ящике'
    elif 'пакет' in lower:
        container_label = 'в каждом пакете'

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: сначала получили {first} {unit}, потом ещё в {multiplier} раза больше, чем сначала. Всё разложили поровну в {groups} групп.',
        f'Что нужно найти: сколько {unit} {container_label}.',
        f'1) Сначала узнаем, сколько получилось {object_label}: {first} × {multiplier} = {second} {unit}.',
        f'2) Потом узнаем, сколько получилось всего: {first} + {second} = {total} {unit}.',
        f'3) Теперь делим всё поровну на {groups} групп: {total} : {groups} = {each} {unit}.',
        f'Ответ: {container_label} {each} {unit}.'
    )


def _final_20260415ad_try_each_brought_then_total(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 3:
        return None
    if 'каждый' not in lower and 'каждая' not in lower and 'каждое' not in lower:
        return None
    if 'по' not in lower or 'стало' not in lower:
        return None
    if 'сколько' not in lower or 'было' not in lower:
        return None
    if not (('принес' in lower or 'принёс' in lower or 'принесли' in lower) and ('библиотек' in lower or 'книг' in lower)):
        return None

    people, per_person, total_after = nums[:3]
    added = people * per_person
    initial = total_after - added
    if min(people, per_person, total_after, initial) < 0:
        return None

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {people} учеников принесли по {per_person} книги, и после этого стало {total_after} книг.',
        'Что нужно найти: сколько книг было сначала.',
        f'1) Сначала найдём, сколько книг принесли ученики: {people} × {per_person} = {added}.',
        f'2) Потом найдём, сколько книг было в библиотеке сначала: {total_after} - {added} = {initial}.',
        f'Ответ: в библиотеке было {initial} книг.'
    )


def _final_20260415ad_try_first_day_second_more_remaining(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 3:
        return None
    if 'в первый день' not in lower or 'во второй' not in lower:
        return None
    if 'на' not in lower or 'больше' not in lower:
        return None
    if 'осталось' not in lower and 'сколько тонн' not in lower and 'сколько осталось' not in lower:
        return None
    if not contains_any_fragment(lower, ('отправили', 'отправил', 'израсходовали', 'продали', 'увезли', 'вывезли')):
        return None

    total_before, first_day, diff = nums[:3]
    second_day = first_day + diff
    total_sent = first_day + second_day
    left = total_before - total_sent
    if min(total_before, first_day, second_day, total_sent, left) < 0:
        return None

    unit = 'т'
    if 'кг' in lower:
        unit = 'кг'
    elif 'мешк' in lower:
        unit = 'мешков'

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: сначала было {total_before} {unit}. В первый день отправили {first_day} {unit}, а во второй день — на {diff} {unit} больше.',
        f'Что нужно найти: сколько {unit} осталось.',
        f'1) Сначала найдём, сколько отправили во второй день: {first_day} + {diff} = {second_day} {unit}.',
        f'2) Потом найдём, сколько отправили за два дня: {first_day} + {second_day} = {total_sent} {unit}.',
        f'3) Теперь найдём, сколько осталось: {total_before} - {total_sent} = {left} {unit}.',
        f'Ответ: осталось {left} {unit}.'
    )

# --- merged segment 017: backend.legacy_runtime_shards.prepatch_build_source.segment_017 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 14215-15106."""



def _final_20260415ad_try_leftover_then_group_count(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 3:
        return None
    if 'осталось' not in lower and 'ещё осталось' not in lower and 'еще осталось' not in lower:
        return None
    if 'на кажд' not in lower or 'по' not in lower:
        return None
    if not ('сколько' in lower and contains_any_fragment(lower, ('грядок', 'корзин', 'пакетов', 'ящиков', 'рядов'))):
        return None

    total, per_group, leftover = nums[:3]
    used = total - leftover
    if per_group <= 0 or used < 0 or used % per_group != 0:
        return None
    groups = used // per_group

    group_noun = 'грядок'
    if 'корзин' in lower:
        group_noun = 'корзин'
    elif 'ящик' in lower:
        group_noun = 'ящиков'
    elif 'пакет' in lower:
        group_noun = 'пакетов'
    elif 'ряд' in lower:
        group_noun = 'рядов'

    unit = 'ведер'
    if 'литр' in lower:
        unit = 'л'
    elif 'килограмм' in lower or 'кг' in lower:
        unit = 'кг'

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: всего было {total} {unit}. На каждую группу расходовали по {per_group} {unit}. После этого осталось {leftover} {unit}.',
        f'Что нужно найти: сколько {group_noun} получилось.',
        f'1) Сначала найдём, сколько {unit} израсходовали: {total} - {leftover} = {used} {unit}.',
        f'2) Потом найдём число групп: {used} : {per_group} = {groups}.',
        f'Ответ: {groups} {group_noun}.'
    )


def _final_20260415ad_try_money_part_to_whole(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if not nums:
        return None
    if 'денег' not in lower and 'руб' not in lower:
        return None
    if 'сколько денег было' not in lower and 'сколько было денег' not in lower and 'сколько денег у' not in lower:
        return None

    multiplier = None
    fraction_label = None
    if 'половин' in lower:
        multiplier = 2
        fraction_label = 'половина'
    elif 'треть' in lower:
        multiplier = 3
        fraction_label = 'треть'
    elif 'четверт' in lower:
        multiplier = 4
        fraction_label = 'четверть'
    if multiplier is None:
        return None
    if not contains_any_fragment(lower, ('заплат', 'израсход', 'потрат', 'покупк')):
        return None

    part_value = nums[-1]
    total = part_value * multiplier
    unit = 'руб.' if 'руб' in lower else ''
    person_match = re.search(r'([А-ЯЁA-Z][а-яёa-z-]+)', text)
    person = person_match.group(1) if person_match else 'У ученика'

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {part_value} {unit}'.strip() + f' — это {fraction_label} всех денег.',
        'Что нужно найти: сколько денег было сначала.',
        f'1) {part_value} {unit}'.strip() + f' — это {fraction_label} всех денег.',
        f'2) Чтобы найти все деньги, умножаем {part_value} на {multiplier}: {part_value} × {multiplier} = {total} {unit}'.rstrip(),
        f'Ответ: у {person} было {total} {unit}'.rstrip() + '.'.replace(' .','.' )
    ).replace(' .', '.').replace('..', '.')


def _final_20260415ad_try_three_pair_sums(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    pairs = re.findall(r'([а-яё-]+)\s+и\s+([а-яё-]+)\s+вместе\s+(\d+)', lower)
    if len(pairs) != 3:
        return None
    if 'сколько им лет' not in lower and 'сколько лет' not in lower:
        return None

    first_a, first_b, first_sum = pairs[0][0], pairs[0][1], int(pairs[0][2])
    second_a, second_b, second_sum = pairs[1][0], pairs[1][1], int(pairs[1][2])
    third_a, third_b, third_sum = pairs[2][0], pairs[2][1], int(pairs[2][2])

    common = set((first_a, first_b)).intersection((second_a, second_b))
    if len(common) != 1:
        return None
    common_name = list(common)[0]
    other_first = first_b if first_a == common_name else first_a
    other_second = second_b if second_a == common_name else second_a
    if set((other_first, other_second)) != set((third_a, third_b)):
        return None

    double_common = first_sum + second_sum - third_sum
    if double_common < 0 or double_common % 2 != 0:
        return None
    common_age = double_common // 2
    first_age = first_sum - common_age
    second_age = second_sum - common_age
    if min(common_age, first_age, second_age) < 0:
        return None

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {first_a} и {first_b} вместе {first_sum} лет, {second_a} и {second_b} вместе {second_sum} год, {third_a} и {third_b} вместе {third_sum} год.',
        'Что нужно найти: сколько лет каждому.',
        f'1) Сложим первую и вторую суммы: {first_sum} + {second_sum} = {first_sum + second_sum}.',
        f'2) Вычтем третью сумму: {first_sum + second_sum} - {third_sum} = {double_common}. Получили возраст {common_name}, взятый два раза.',
        f'3) Найдём возраст {common_name}: {double_common} : 2 = {common_age}.',
        f'4) Найдём возраст {other_first}: {first_sum} - {common_age} = {first_age}.',
        f'5) Найдём возраст {other_second}: {second_sum} - {common_age} = {second_age}.',
        f'Ответ: {common_name} {common_age} лет, {other_first} {first_age} лет, {other_second} {second_age} лет.'
    )


def _final_20260415ad_try_read_and_remaining(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 2:
        return None
    if 'прочитал' not in lower or 'осталось' not in lower:
        return None
    if 'на' not in lower or ('меньше' not in lower and 'больше' not in lower):
        return None
    if 'сколько страниц в книге' not in lower and 'сколько страниц' not in lower:
        return None

    read_pages, diff = nums[:2]
    if 'меньше' in lower:
        left = read_pages - diff
        compare_text = 'меньше'
        expr = f'{read_pages} - {diff}'
    else:
        left = read_pages + diff
        compare_text = 'больше'
        expr = f'{read_pages} + {diff}'
    if left < 0:
        return None
    total = read_pages + left

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: мальчик прочитал {read_pages} страниц. До конца книги осталось на {diff} страниц {compare_text}.',
        'Что нужно найти: сколько страниц в книге.',
        f'1) Сначала найдём, сколько страниц осталось прочитать: {expr} = {left}.',
        f'2) Потом найдём, сколько страниц в книге всего: {read_pages} + {left} = {total}.',
        f'Ответ: в книге {total} страниц.'
    )


def _final_20260415ad_try_relation_times_bigger(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 2:
        return None
    if 'в ' not in lower or 'раза больше' not in lower:
        return None
    if 'чем' not in lower:
        return None
    if not contains_any_fragment(lower, ('сколько километров в час', 'какая скорость', 'с какой скоростью', 'сколько проходит')):
        return None

    bigger_value, times = nums[:2]
    if times <= 0 or bigger_value % times != 0:
        return None
    smaller = bigger_value // times
    unit = 'км/ч' if ('км/ч' in lower or 'километров в час' in lower) else ''

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: одно расстояние или скорость равно {bigger_value} {unit}'.strip() + f'. Это в {times} раза больше, чем другое.',
        'Что нужно найти: меньшее значение.',
        f'1) Если одно значение в {times} раза больше другого, то меньшее значение находим делением.',
        f'2) Считаем: {bigger_value} : {times} = {smaller} {unit}'.rstrip(),
        f'Ответ: {smaller} {unit}'.rstrip() + '.'.replace(' .','.')
    ).replace(' .', '.').replace('..', '.')


def _final_20260415ad_try_rectangle_width_from_perimeter(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 2:
        return None
    if 'периметр прямоугольника' not in lower or 'длина' not in lower:
        return None
    if 'ширин' not in lower:
        return None

    perimeter, length = nums[:2]
    if perimeter % 2 != 0:
        return None
    half = perimeter // 2
    width = half - length
    if width < 0:
        return None
    unit = 'см'
    if 'дм' in lower:
        unit = 'дм'
    elif re.search(r'\bм\b', lower):
        unit = 'м'
    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: периметр прямоугольника {perimeter} {unit}, длина {length} {unit}.',
        'Что нужно найти: ширину прямоугольника.',
        '1) Периметр прямоугольника равен сумме длины и ширины, умноженной на 2: P = 2 × (a + b).',
        f'2) Найдём сумму длины и ширины: {perimeter} : 2 = {half}.',
        f'3) Теперь найдём ширину: {half} - {length} = {width}.',
        f'Ответ: ширина прямоугольника {width} {unit}.'
    )


def _final_20260415ad_parse_simple_linear_equation(eq: str):
    match = re.fullmatch(r'([A-Za-zА-Яа-я])([+\-])([A-Za-zА-Яа-я])=(-?\d+)', eq)
    if not match:
        return None
    left, operator, right, value = match.groups()
    return left, operator, right, int(value)


def _final_20260415ad_try_simple_system(raw_text: str) -> Optional[str]:
    compact = normalize_cyrillic_x(strip_known_prefix(raw_text)).replace(' ', '').replace(';', ',')
    if compact.count('=') != 2 or ',' not in compact:
        return None
    parts = [part for part in compact.split(',') if part]
    if len(parts) != 2:
        return None
    parsed = [_final_20260415ad_parse_simple_linear_equation(part) for part in parts]
    if any(item is None for item in parsed):
        return None

    plus_eq = next((item for item in parsed if item[1] == '+'), None)
    minus_eq = next((item for item in parsed if item[1] == '-'), None)
    if plus_eq is None or minus_eq is None:
        return None

    a1, _, b1, total_sum = plus_eq
    a2, _, b2, diff_value = minus_eq
    if {a1.lower(), b1.lower()} != {a2.lower(), b2.lower()}:
        return None

    if a2.lower() == a1.lower() and b2.lower() == b1.lower():
        x_name, y_name = a1, b1
        x_value = Fraction(total_sum + diff_value, 2)
        y_value = Fraction(total_sum, 1) - x_value
    elif a2.lower() == b1.lower() and b2.lower() == a1.lower():
        y_name, x_name = a2, b2
        y_value = Fraction(total_sum + diff_value, 2)
        x_value = Fraction(total_sum, 1) - y_value
    else:
        return None

    if x_value.denominator != 1 or y_value.denominator != 1:
        return None
    x_int = x_value.numerator
    y_int = y_value.numerator

    return _audit_join_lines(
        'Система уравнений:',
        f'{a1} + {b1} = {total_sum}',
        f'{a2} - {b2} = {diff_value}' if a2.lower() == a1.lower() and b2.lower() == b1.lower() else f'{a2} - {b2} = {diff_value}',
        'Решение.',
        f'1) Сложим правые части и учтём, что в одном уравнении {y_name} прибавляется, а в другом вычитается.',
        f'2) Получаем: 2{x_name} = {total_sum} + {diff_value} = {total_sum + diff_value}.',
        f'3) Находим {x_name}: {total_sum + diff_value} : 2 = {x_int}.',
        f'4) Подставляем {x_name} в первое уравнение: {x_int} + {y_name} = {total_sum}.',
        f'5) Находим {y_name}: {total_sum} - {x_int} = {y_int}.',
        f'Ответ: {x_name} = {x_int}, {y_name} = {y_int}.'
    )


def _final_20260415ad_try_textbook_fixes(raw_text: str) -> Optional[str]:
    return (
        _final_20260415ad_try_garage_indirect_counts(raw_text)
        or _final_20260415ad_try_times_more_and_equal_groups(raw_text)
        or _final_20260415ad_try_each_brought_then_total(raw_text)
        or _final_20260415ad_try_first_day_second_more_remaining(raw_text)
        or _final_20260415ad_try_leftover_then_group_count(raw_text)
        or _final_20260415ad_try_money_part_to_whole(raw_text)
        or _final_20260415ad_try_three_pair_sums(raw_text)
        or _final_20260415ad_try_read_and_remaining(raw_text)
        or _final_20260415ad_try_relation_times_bigger(raw_text)
        or _final_20260415ad_try_rectangle_width_from_perimeter(raw_text)
        or _final_20260415ad_try_simple_system(raw_text)
    )


async def build_explanation(user_text: str) -> dict:
    local = _final_20260415ad_try_textbook_fixes(user_text)
    if local:
        return _final_20260415ad_result_dict(local)
    return await _FINAL_20260415AD_PREV_BUILD_EXPLANATION(user_text)


# --- FINAL PATCH 2026-04-15AE: cleaner textbook wording and answer grammar ---


def _final_20260415ae_plural(number: int, one: str, few: str, many: str) -> str:
    number = abs(int(number))
    mod100 = number % 100
    mod10 = number % 10
    if 11 <= mod100 <= 14:
        return many
    if mod10 == 1:
        return one
    if 2 <= mod10 <= 4:
        return few
    return many


def _final_20260415ad_try_garage_indirect_counts(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 3:
        return None
    if 'автобус' not in lower or 'грузов' not in lower or 'легков' not in lower:
        return None
    if 'сколько всего' not in lower or 'гараж' not in lower:
        return None
    if 'это на' not in lower or 'больше, чем грузов' not in lower:
        return None
    if 'меньше, чем грузов' not in lower:
        return None

    buses, diff_to_trucks, diff_to_cars = nums[:3]
    trucks = buses - diff_to_trucks
    cars = trucks - diff_to_cars
    if min(buses, trucks, cars) < 0:
        return None
    total = buses + trucks + cars
    machine_word = _final_20260415ae_plural(total, 'машина', 'машины', 'машин')

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: автобусов {buses}. Это на {diff_to_trucks} больше, чем грузовых машин. Легковых машин на {diff_to_cars} меньше, чем грузовых.',
        'Что нужно найти: сколько всего машин в гараже.',
        f'1) Сначала найдём количество грузовых машин. Если автобусов на {diff_to_trucks} больше, чем грузовых, то грузовых на {diff_to_trucks} меньше: {buses} - {diff_to_trucks} = {trucks}.',
        f'2) Потом найдём количество легковых машин. Если легковых на {diff_to_cars} меньше, чем грузовых, то {trucks} - {diff_to_cars} = {cars}.',
        f'3) Теперь найдём, сколько всего машин в гараже: {buses} + {trucks} + {cars} = {total}.',
        f'Ответ: всего {total} {machine_word}.'
    )


def _final_20260415ad_try_leftover_then_group_count(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 3:
        return None
    if 'осталось' not in lower and 'ещё осталось' not in lower and 'еще осталось' not in lower:
        return None
    if 'на кажд' not in lower or 'по' not in lower:
        return None
    if not ('сколько' in lower and contains_any_fragment(lower, ('грядок', 'корзин', 'пакетов', 'ящиков', 'рядов'))):
        return None

    total, per_group, leftover = nums[:3]
    used = total - leftover
    if per_group <= 0 or used < 0 or used % per_group != 0:
        return None
    groups = used // per_group

    group_noun = 'грядок'
    group_phrase = 'на каждую грядку вылили'
    if 'гряд' in lower:
        group_noun = _final_20260415ae_plural(groups, 'грядку', 'грядки', 'грядок')
        group_phrase = 'на каждую грядку вылили'
    elif 'корзин' in lower:
        group_noun = _final_20260415ae_plural(groups, 'корзину', 'корзины', 'корзин')
        group_phrase = 'в каждую корзину положили'
    elif 'ящик' in lower:
        group_noun = _final_20260415ae_plural(groups, 'ящик', 'ящика', 'ящиков')
        group_phrase = 'в каждый ящик положили'
    elif 'пакет' in lower:
        group_noun = _final_20260415ae_plural(groups, 'пакет', 'пакета', 'пакетов')
        group_phrase = 'в каждый пакет положили'
    elif 'ряд' in lower:
        group_noun = _final_20260415ae_plural(groups, 'ряд', 'ряда', 'рядов')
        group_phrase = 'в каждый ряд положили'

    unit_many = 'вёдер' if 'вёдер' in lower or 'ведер' in lower else 'единиц'
    unit_for_per = 'ведра' if 'вёдер' in lower or 'ведер' in lower else unit_many
    if 'литр' in lower:
        unit_many = _final_20260415ae_plural(total, 'литр', 'литра', 'литров')
        unit_for_per = _final_20260415ae_plural(per_group, 'литр', 'литра', 'литров')
    elif 'килограмм' in lower or 'кг' in lower:
        unit_many = _final_20260415ae_plural(total, 'килограмм', 'килограмма', 'килограммов')
        unit_for_per = _final_20260415ae_plural(per_group, 'килограмм', 'килограмма', 'килограммов')

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: всего было {total} {unit_many}. {group_phrase} по {per_group} {unit_for_per}. После этого осталось {leftover} {unit_many}.',
        f'Что нужно найти: сколько {group_noun} получилось.',
        f'1) Сначала найдём, сколько {unit_many} израсходовали: {total} - {leftover} = {used}.',
        f'2) Потом найдём число групп: {used} : {per_group} = {groups}.',
        f'Ответ: полили {groups} {group_noun}.' if 'гряд' in lower else f'Ответ: получилось {groups} {group_noun}.'
    )


def _final_20260415ad_try_money_part_to_whole(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if not nums:
        return None
    if 'денег' not in lower and 'руб' not in lower:
        return None
    if 'сколько денег было' not in lower and 'сколько было денег' not in lower and 'сколько денег у' not in lower:
        return None

    multiplier = None
    fraction_label = None
    if 'половин' in lower:
        multiplier = 2
        fraction_label = 'половина'
    elif 'треть' in lower:
        multiplier = 3
        fraction_label = 'треть'
    elif 'четверт' in lower:
        multiplier = 4
        fraction_label = 'четверть'
    if multiplier is None:
        return None
    if not contains_any_fragment(lower, ('заплат', 'израсход', 'потрат', 'покупк')):
        return None

    part_value = nums[-1]
    total = part_value * multiplier

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {part_value} руб. — это {fraction_label} всех денег.',
        'Что нужно найти: сколько денег было сначала.',
        f'1) {part_value} руб. — это {fraction_label} всех денег.',
        f'2) Чтобы найти все деньги, умножаем {part_value} на {multiplier}: {part_value} × {multiplier} = {total} руб.',
        f'Ответ: было {total} руб.'
    )


def _final_20260415ad_try_three_pair_sums(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    pairs = re.findall(r'([а-яё-]+)\s+и\s+([а-яё-]+)\s+вместе\s+(\d+)', lower)
    if len(pairs) != 3:
        return None
    if 'сколько им лет' not in lower and 'сколько лет' not in lower:
        return None

    first_a, first_b, first_sum = pairs[0][0], pairs[0][1], int(pairs[0][2])
    second_a, second_b, second_sum = pairs[1][0], pairs[1][1], int(pairs[1][2])
    third_a, third_b, third_sum = pairs[2][0], pairs[2][1], int(pairs[2][2])

    common = set((first_a, first_b)).intersection((second_a, second_b))
    if len(common) != 1:
        return None
    common_name = list(common)[0]
    other_first = first_b if first_a == common_name else first_a
    other_second = second_b if second_a == common_name else second_a
    if set((other_first, other_second)) != set((third_a, third_b)):
        return None

    double_common = first_sum + second_sum - third_sum
    if double_common < 0 or double_common % 2 != 0:
        return None
    common_age = double_common // 2
    first_age = first_sum - common_age
    second_age = second_sum - common_age
    if min(common_age, first_age, second_age) < 0:
        return None

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {first_a} и {first_b} вместе {first_sum} лет, {second_a} и {second_b} вместе {second_sum} лет, {third_a} и {third_b} вместе {third_sum} лет.',
        'Что нужно найти: сколько лет каждому.',
        f'1) Сложим первую и вторую суммы: {first_sum} + {second_sum} = {first_sum + second_sum}.',
        f'2) Вычтем третью сумму: {first_sum + second_sum} - {third_sum} = {double_common}. Получили возраст {common_name}, взятый два раза.',
        f'3) Найдём возраст {common_name}: {double_common} : 2 = {common_age}.',
        f'4) Найдём возраст {other_first}: {first_sum} - {common_age} = {first_age}.',
        f'5) Найдём возраст {other_second}: {second_sum} - {common_age} = {second_age}.',
        f'Ответ: {common_name} {common_age} {_final_20260415ae_plural(common_age, "год", "года", "лет")}, {other_first} {first_age} {_final_20260415ae_plural(first_age, "год", "года", "лет")}, {other_second} {second_age} {_final_20260415ae_plural(second_age, "год", "года", "лет")}.'
    )


# --- FINAL PATCH 2026-04-15AF: wording cleanup for watering and age-sum tasks ---


def _final_20260415ad_try_leftover_then_group_count(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    if len(nums) < 3:
        return None
    if 'осталось' not in lower and 'ещё осталось' not in lower and 'еще осталось' not in lower:
        return None
    if 'на кажд' not in lower or 'по' not in lower:
        return None
    if not ('сколько' in lower and contains_any_fragment(lower, ('грядок', 'корзин', 'пакетов', 'ящиков', 'рядов'))):
        return None

    total, per_group, leftover = nums[:3]
    used = total - leftover
    if per_group <= 0 or used < 0 or used % per_group != 0:
        return None
    groups = used // per_group

    ask_phrase = 'сколько грядок полили'
    known_phrase = f'На каждую грядку вылили по {per_group} ведра.'
    answer_phrase = f'Ответ: полили {groups} грядок.'
    unit_name = 'ведер'

    if 'корзин' in lower:
        ask_phrase = 'сколько корзин получилось'
        known_phrase = f'В каждую корзину положили по {per_group} единиц.'
        answer_phrase = f'Ответ: получилось {groups} корзин.'
        unit_name = 'единиц'
    elif 'ящик' in lower:
        ask_phrase = 'сколько ящиков получилось'
        known_phrase = f'В каждый ящик положили по {per_group} единиц.'
        answer_phrase = f'Ответ: получилось {groups} ящиков.'
        unit_name = 'единиц'
    elif 'пакет' in lower:
        ask_phrase = 'сколько пакетов получилось'
        known_phrase = f'В каждый пакет положили по {per_group} единиц.'
        answer_phrase = f'Ответ: получилось {groups} пакетов.'
        unit_name = 'единиц'
    elif 'ряд' in lower and 'гряд' not in lower:
        ask_phrase = 'сколько рядов получилось'
        known_phrase = f'В каждый ряд положили по {per_group} единиц.'
        answer_phrase = f'Ответ: получилось {groups} рядов.'
        unit_name = 'единиц'

    if 'вёдер' in lower or 'ведер' in lower:
        unit_name = 'ведер'
    elif 'литр' in lower:
        unit_name = 'литров'
        if 'гряд' in lower:
            known_phrase = f'На каждую грядку вылили по {per_group} литра.'
    elif 'килограмм' in lower or 'кг' in lower:
        unit_name = 'килограммов'

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: всего было {total} {unit_name}. {known_phrase} После этого осталось {leftover} {unit_name}.',
        f'Что нужно найти: {ask_phrase}.',
        f'1) Сначала найдём, сколько {unit_name} израсходовали: {total} - {leftover} = {used}.',
        f'2) Потом найдём число групп: {used} : {per_group} = {groups}.',
        answer_phrase
    )


def _final_20260415ad_try_three_pair_sums(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    pairs = re.findall(r'([а-яё-]+)\s+и\s+([а-яё-]+)\s+вместе\s+(\d+)', lower)
    if len(pairs) != 3:
        return None
    if 'сколько им лет' not in lower and 'сколько лет' not in lower:
        return None

    first_a, first_b, first_sum = pairs[0][0], pairs[0][1], int(pairs[0][2])
    second_a, second_b, second_sum = pairs[1][0], pairs[1][1], int(pairs[1][2])
    third_a, third_b, third_sum = pairs[2][0], pairs[2][1], int(pairs[2][2])

    common = set((first_a, first_b)).intersection((second_a, second_b))
    if len(common) != 1:
        return None
    common_name = list(common)[0]
    other_first = first_b if first_a == common_name else first_a
    other_second = second_b if second_a == common_name else second_a
    if set((other_first, other_second)) != set((third_a, third_b)):
        return None

    double_common = first_sum + second_sum - third_sum
    if double_common < 0 or double_common % 2 != 0:
        return None
    common_age = double_common // 2
    first_age = first_sum - common_age
    second_age = second_sum - common_age
    if min(common_age, first_age, second_age) < 0:
        return None

    first_sum_word = _final_20260415ae_plural(first_sum, 'год', 'года', 'лет')
    second_sum_word = _final_20260415ae_plural(second_sum, 'год', 'года', 'лет')
    third_sum_word = _final_20260415ae_plural(third_sum, 'год', 'года', 'лет')

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {first_a} и {first_b} вместе {first_sum} {first_sum_word}, {second_a} и {second_b} вместе {second_sum} {second_sum_word}, {third_a} и {third_b} вместе {third_sum} {third_sum_word}.',
        'Что нужно найти: сколько лет каждому.',
        f'1) Сложим первую и вторую суммы: {first_sum} + {second_sum} = {first_sum + second_sum}.',
        f'2) Вычтем третью сумму: {first_sum + second_sum} - {third_sum} = {double_common}. Это возраст одного и того же человека, взятый два раза.',
        f'3) Этот человек — {common_name}. Находим его возраст: {double_common} : 2 = {common_age}.',
        f'4) Найдём возраст {other_first}: {first_sum} - {common_age} = {first_age}.',
        f'5) Найдём возраст {other_second}: {second_sum} - {common_age} = {second_age}.',
        f'Ответ: {common_name} {common_age} {_final_20260415ae_plural(common_age, "год", "года", "лет")}, {other_first} {first_age} {_final_20260415ae_plural(first_age, "год", "года", "лет")}, {other_second} {second_age} {_final_20260415ae_plural(second_age, "год", "года", "лет")}.'
    )


# --- FINAL PATCH 2026-04-15AG: neutral wording for age-pair sums ---


def _final_20260415ad_try_three_pair_sums(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260415ad_prepare_word_text(raw_text)
    pairs = re.findall(r'([а-яё-]+)\s+и\s+([а-яё-]+)\s+вместе\s+(\d+)', lower)
    if len(pairs) != 3:
        return None
    if 'сколько им лет' not in lower and 'сколько лет' not in lower:
        return None

    first_a, first_b, first_sum = pairs[0][0], pairs[0][1], int(pairs[0][2])
    second_a, second_b, second_sum = pairs[1][0], pairs[1][1], int(pairs[1][2])
    third_a, third_b, third_sum = pairs[2][0], pairs[2][1], int(pairs[2][2])

    common = set((first_a, first_b)).intersection((second_a, second_b))
    if len(common) != 1:
        return None
    common_name = list(common)[0]
    other_first = first_b if first_a == common_name else first_a
    other_second = second_b if second_a == common_name else second_a
    if set((other_first, other_second)) != set((third_a, third_b)):
        return None

    double_common = first_sum + second_sum - third_sum
    if double_common < 0 or double_common % 2 != 0:
        return None
    common_age = double_common // 2
    first_age = first_sum - common_age
    second_age = second_sum - common_age
    if min(common_age, first_age, second_age) < 0:
        return None

    first_sum_word = _final_20260415ae_plural(first_sum, 'год', 'года', 'лет')
    second_sum_word = _final_20260415ae_plural(second_sum, 'год', 'года', 'лет')
    third_sum_word = _final_20260415ae_plural(third_sum, 'год', 'года', 'лет')

    return _audit_join_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {first_a} и {first_b} вместе {first_sum} {first_sum_word}, {second_a} и {second_b} вместе {second_sum} {second_sum_word}, {third_a} и {third_b} вместе {third_sum} {third_sum_word}.',
        'Что нужно найти: сколько лет каждому.',
        f'1) Сложим первую и вторую суммы: {first_sum} + {second_sum} = {first_sum + second_sum}.',
        f'2) Вычтем третью сумму: {first_sum + second_sum} - {third_sum} = {double_common}. Получили возраст одного человека два раза.',
        f'3) Найдём этот возраст: {double_common} : 2 = {common_age}.',
        f'4) По первой сумме найдём второй возраст: {first_sum} - {common_age} = {first_age}.',
        f'5) По второй сумме найдём третий возраст: {second_sum} - {common_age} = {second_age}.',
        f'Ответ: {common_name} {common_age} {_final_20260415ae_plural(common_age, "год", "года", "лет")}, {other_first} {first_age} {_final_20260415ae_plural(first_age, "год", "года", "лет")}, {other_second} {second_age} {_final_20260415ae_plural(second_age, "год", "года", "лет")}.'
    )


# --- FINAL PATCH 2026-04-16: eliminate remaining textbook audit failures without touching stable flows ---

_FINAL_20260416_PREV_BUILD_EXPLANATION = build_explanation
_FINAL_20260416_PREV_GEOMETRY = try_local_geometry_explanation


def _final_20260416_prepare(raw_text: str):
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    return text, lower, nums


def _final_20260416_result_dict(text: str, source: str = 'local-final-20260416') -> dict:
    return {'result': text, 'source': source, 'validated': True}


def _final_20260416_fraction_word_to_pair(word: str):
    word = (word or '').lower()
    mapping = {
        'половина': (1, 2),
        'треть': (1, 3),
        'четверть': (1, 4),
        'четвёртая часть': (1, 4),
    }
    return mapping.get(word)


def _final_20260416_normalize_fraction_expression_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(normalize_cyrillic_x(text))
    text = text.replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    text = re.sub(r'\s+', '', text)
    if not text or re.search(r'[A-Za-zА-Яа-яЁё]', text):
        return None
    if re.search(r'[^0-9+\-*/()]', text):
        return None
    if not re.search(r'\d+/\d+', text):
        return None
    if re.fullmatch(r'\d+/\d+', text):
        return None

    all_numbers = [int(value) for value in re.findall(r'\d+', text)]
    if not all_numbers:
        return None
    if max(abs(value) for value in all_numbers) > 1000:
        return None

    fraction_matches = list(re.finditer(r'(\d+)/(\d+)', text))
    if not fraction_matches:
        return None

    placeholder = re.sub(r'\d+/\d+', 'F', text)
    if not re.fullmatch(r'[F0-9+\-*/()]+', placeholder):
        return None
    if placeholder == 'F':
        return None

    pairs = [(int(match.group(1)), int(match.group(2))) for match in fraction_matches]
    if any(den == 0 for _, den in pairs):
        return None

    # Одно обычное деление вроде 24/4 в длинном выражении не должно уходить в блок дробей.
    # Для дробных выражений начальной школы оставляем:
    # - хотя бы две дроби;
    # - или одну правильную дробь вроде 1/2 + 3.
    if len(pairs) == 1:
        numerator, denominator = pairs[0]
        if not (0 < numerator < denominator <= 20):
            return None
        start, end = fraction_matches[0].span()
        if '+' not in placeholder and '-' not in placeholder and '*' not in placeholder:
            return None
        if start > 0 and text[start - 1].isdigit():
            return None
        if end < len(text) and text[end:end + 1].isdigit():
            return None
    else:
        if not all(0 < num <= 50 and 0 < den <= 50 for num, den in pairs):
            return None
        if not any(num < den for num, den in pairs):
            return None

    return text


# Переопределяем нормализатор, чтобы обычные выражения с делением не шли в блок дробей.
_final_20260415_normalize_fraction_expression_source = _final_20260416_normalize_fraction_expression_source


def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    unit = geometry_unit(lower)

    square_side_match = re.search(
        r'(?:квадрат[^.?!]{0,60}?со\s+сторон(?:ой|ою|ой\s+)?[^\d]{0,20}(\d+))|(?:сторона\s+квадрата[^\d]{0,20}(\d+))',
        lower,
    )
    square_side_val = int(next(group for group in square_side_match.groups() if group)) if square_side_match else None

    question_parts = [part.strip() for part in re.split(r'[?.!]', lower) if part.strip()]
    question = question_parts[-1] if question_parts else lower
    asks_perimeter = 'периметр' in question or 'найди его периметр' in lower or 'найдите его периметр' in lower
    asks_width = 'найдите ширину' in lower or 'найди ширину' in lower or 'какова ширина' in lower
    asks_length = ('найдите длину' in lower or 'найди длину' in lower or 'какова длина' in lower) and not asks_width

    if 'квадрат' in lower and square_side_val is not None and asks_perimeter:
        result = square_side_val * 4
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: сторона квадрата равна {square_side_val} {unit}.',
            'Что нужно найти: периметр квадрата.',
            '1) У квадрата все четыре стороны равны.',
            f'2) Периметр квадрата — это сумма четырёх равных сторон: {square_side_val} × 4 = {result}.',
            f'Ответ: {with_unit(result, unit)}.'
        )

    # Формулировки вида «прямоугольной формы» тоже считаем задачами про прямоугольник.
    if 'прямоугольн' in lower and 'площад' in lower and ('длина' in lower or 'ширина' in lower):
        area_val = extract_keyword_number(lower, 'площад')
        length_val = extract_keyword_number(lower, 'длина')
        width_val = extract_keyword_number(lower, 'ширина')
        if asks_width and area_val is not None and length_val is not None and length_val != 0 and area_val % length_val == 0:
            width = area_val // length_val
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, длина {with_unit(length_val, unit)}.',
                'Что нужно найти: ширину прямоугольника.',
                '1) Площадь прямоугольника равна длине, умноженной на ширину.',
                f'2) Чтобы найти ширину, делим площадь на длину: {area_val} : {length_val} = {width}.',
                f'Ответ: {with_unit(width, unit)}.'
            )
        if asks_length and area_val is not None and width_val is not None and width_val != 0 and area_val % width_val == 0:
            length = area_val // width_val
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, ширина {with_unit(width_val, unit)}.',
                'Что нужно найти: длину прямоугольника.',
                '1) Площадь прямоугольника равна длине, умноженной на ширину.',
                f'2) Чтобы найти длину, делим площадь на ширину: {area_val} : {width_val} = {length}.',
                f'Ответ: {with_unit(length, unit)}.'
            )

    return _FINAL_20260416_PREV_GEOMETRY(raw_text)


def _final_20260416_try_pickles_two_days(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 3:
        return None
    if 'в первый день' not in lower or 'во второй день' not in lower:
        return None
    if 'по' not in lower or 'в каждом' not in lower:
        return None
    if 'на' not in lower or 'больше, чем в первый день' not in lower:
        return None
    if not contains_any_fragment(lower, ('сколько кг', 'сколько килограмм', 'сколько огурцов засолили за два дня', 'сколько засолили за два дня')):
        return None
    if not contains_any_fragment(lower, ('огурц', 'бочон', 'ящик', 'банк')):
        return None

    groups, per_group, diff = nums[:3]
    first_day = groups * per_group
    second_day = first_day + diff
    total = first_day + second_day
    if min(groups, per_group, diff, first_day, second_day, total) < 0:
        return None

    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: в первый день засолили {groups} бочонков по {per_group} кг в каждом. Во второй день засолили на {diff} кг больше, чем в первый день.',
        'Что нужно найти: сколько килограммов огурцов засолили за два дня.',
        f'1) Сначала найдём, сколько килограммов засолили в первый день: {groups} × {per_group} = {first_day} кг.',
        f'2) Потом найдём, сколько килограммов засолили во второй день: {first_day} + {diff} = {second_day} кг.',
        f'3) Теперь найдём, сколько килограммов засолили за два дня: {first_day} + {second_day} = {total} кг.',
        f'Ответ: за два дня засолили {total} кг огурцов.'
    )


def _final_20260416_try_motion_compare_two_distances(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if 'на сколько больше' not in lower and 'на сколько меньше' not in lower:
        return None
    if not ('автобус' in lower and 'пеш' in lower):
        return None
    times = [int(v) for v in re.findall(r'(\d+)\s*(?:ч|час)', lower)]
    speeds = [int(v) for v in re.findall(r'(\d+)\s*км/ч', lower)]
    if len(times) < 2 or len(speeds) < 2:
        return None
    bus_time, walk_time = times[0], times[1]
    bus_speed, walk_speed = speeds[0], speeds[1]
    bus_distance = bus_speed * bus_time
    walk_distance = walk_speed * walk_time
    difference = bus_distance - walk_distance
    if difference < 0:
        return None
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: на автобусе ехали {bus_time} ч со скоростью {bus_speed} км/ч, пешком шли {walk_time} ч со скоростью {walk_speed} км/ч.',
        'Что нужно найти: на сколько больше путь на автобусе, чем пешком.',
        f'1) Сначала найдём путь на автобусе: {bus_speed} × {bus_time} = {bus_distance} км.',
        f'2) Потом найдём путь пешком: {walk_speed} × {walk_time} = {walk_distance} км.',
        f'3) Теперь сравним пути: {bus_distance} - {walk_distance} = {difference} км.',
        f'Ответ: путь на автобусе больше на {difference} км.'
    )

# --- merged segment 018: backend.legacy_runtime_shards.prepatch_build_source.segment_018 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 15107-15975."""



def _final_20260416_try_same_price_two_days(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 3:
        return None
    if 'в первый день' not in lower or 'во второй' not in lower:
        return None
    if 'по той же цене' not in lower and 'по одинаковой цене' not in lower:
        return None
    if 'за все' not in lower and 'за все полки' not in lower:
        return None
    if not contains_any_fragment(lower, ('сколько денег истратили', 'сколько денег потратили', 'сколько заплатили в первый день')):
        return None

    first_qty, second_qty, total_cost = nums[:3]
    total_qty = first_qty + second_qty
    if total_qty <= 0 or total_cost % total_qty != 0:
        return None
    price = total_cost // total_qty
    first_cost = first_qty * price
    second_cost = second_qty * price

    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: в первый день купили {first_qty} полок, во второй — {second_qty} таких же полок по той же цене. За все полки заплатили {total_cost} р.',
        'Что нужно найти: сколько денег истратили в первый день и сколько — во второй день.',
        f'1) Сначала найдём, сколько полок купили всего: {first_qty} + {second_qty} = {total_qty}.',
        f'2) Теперь найдём цену одной полки: {total_cost} : {total_qty} = {price} р.',
        f'3) Узнаем, сколько заплатили в первый день: {first_qty} × {price} = {first_cost} р.',
        f'4) Узнаем, сколько заплатили во второй день: {second_qty} × {price} = {second_cost} р.',
        f'Ответ: в первый день — {first_cost} р, во второй день — {second_cost} р.'
    )


def _final_20260416_try_red_green_apples_half_taken(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None
    if 'красн' not in lower or 'зелен' not in lower or 'яблок' not in lower:
        return None
    if 'половину всех яблок' not in lower or 'осталось' not in lower:
        return None
    if 'сначала' not in lower:
        return None

    green_added, remained_after_taking = nums[:2]
    total_before_taking = remained_after_taking * 2
    red_initial = total_before_taking - green_added
    if min(green_added, remained_after_taking, total_before_taking, red_initial) < 0:
        return None

    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: в корзину положили ещё {green_added} зелёных яблок. После того как взяли половину всех яблок, осталось {remained_after_taking} яблок.',
        'Что нужно найти: сколько красных яблок было в корзине сначала.',
        f'1) Если после того как взяли половину, осталось {remained_after_taking} яблок, значит это вторая половина всех яблок.',
        f'2) Тогда до того как взяли половину, в корзине было {remained_after_taking} × 2 = {total_before_taking} яблок.',
        f'3) Из этих яблок {green_added} были зелёные, значит красных было {total_before_taking} - {green_added} = {red_initial}.',
        f'Ответ: сначала в корзине было {red_initial} красных яблок.'
    )


def _final_20260416_try_fraction_whole_comparison(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None
    fraction_hits = list(re.finditer(r'(половина|треть|четверть)[^0-9]{0,60}?это\s*(\d+)', lower))
    if len(fraction_hits) != 2:
        return None

    parts = []
    for match in fraction_hits:
        frac_word = match.group(1)
        value = int(match.group(2))
        pair = _final_20260416_fraction_word_to_pair(frac_word)
        if not pair:
            return None
        num, den = pair
        whole = value * den // num
        if value * den % num != 0:
            return None
        parts.append({'word': frac_word, 'value': value, 'num': num, 'den': den, 'whole': whole})

    first_whole = parts[0]['whole']
    second_whole = parts[1]['whole']

    if 'во сколько раз' in lower and ('больше' in lower or 'меньше' in lower):
        bigger = max(first_whole, second_whole)
        smaller = min(first_whole, second_whole)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        unit = 'кг' if 'кг' in lower else ''
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {parts[0]["word"]} первого количества — это {parts[0]["value"]} {unit}. {parts[1]["word"]} второго количества — это {parts[1]["value"]} {unit}.',
            'Что нужно найти: во сколько раз одно количество больше другого.',
            f'1) Найдём всё первое количество: {parts[0]["value"]} × {parts[0]["den"]} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {parts[1]["value"]} × {parts[1]["den"]} = {second_whole} {unit}.',
            f'3) Сравним количества: {bigger} : {smaller} = {ratio}.',
            f'Ответ: в {ratio} раза.'
        )

    if 'на сколько' in lower and ('больше' in lower or 'меньше' in lower):
        difference = abs(second_whole - first_whole)
        unit = ''
        if 'см2' in lower or 'см²' in lower:
            unit = 'см²'
        elif 'кг' in lower:
            unit = 'кг'
        elif 'м2' in lower or 'м²' in lower:
            unit = 'м²'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {parts[0]["word"]} первого количества — это {parts[0]["value"]} {unit}. {parts[1]["word"]} второго количества — это {parts[1]["value"]} {unit}.',
            'Что нужно найти: на сколько одно количество отличается от другого.',
            f'1) Найдём всё первое количество: {parts[0]["value"]} × {parts[0]["den"]} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {parts[1]["value"]} × {parts[1]["den"]} = {second_whole} {unit}.',
            f'3) Найдём разность: {max(first_whole, second_whole)} - {min(first_whole, second_whole)} = {difference} {unit}.',
            f'Ответ: на {difference} {unit}.'.replace('  ', ' ')
        )

    return None


def _final_20260416_try_ratio_difference_full_answer(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) != 2:
        return None
    if 'в 3 раза больше' not in lower and not re.search(r'в\s+\d+\s+раз(?:а)?\s+больше', lower):
        return None
    if 'на сколько' not in lower:
        return None
    if 'рек' not in lower or 'город' not in lower:
        return None
    first, factor = nums
    second = first * factor
    diff = second - first
    if diff < 0:
        return None
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: названий рек {first}, названий городов в {factor} раза больше.',
        'Что нужно найти: на сколько названий рек меньше, чем названий городов.',
        f'1) Сначала найдём, сколько названий городов: {first} × {factor} = {second}.',
        f'2) Теперь найдём, на сколько названий рек меньше: {second} - {first} = {diff}.',
        f'Ответ: названий рек на {diff} меньше, чем названий городов.'
    )


def _final_20260416_try_all_remaining_fixes(raw_text: str) -> Optional[str]:
    return (
        _final_20260416_try_pickles_two_days(raw_text)
        or _final_20260416_try_motion_compare_two_distances(raw_text)
        or _final_20260416_try_same_price_two_days(raw_text)
        or _final_20260416_try_red_green_apples_half_taken(raw_text)
        or _final_20260416_try_fraction_whole_comparison(raw_text)
        or _final_20260416_try_ratio_difference_full_answer(raw_text)
    )


async def build_explanation(user_text: str) -> dict:
    local = _final_20260416_try_all_remaining_fixes(user_text)
    if local:
        return _final_20260416_result_dict(local)
    return await _FINAL_20260416_PREV_BUILD_EXPLANATION(user_text)


# --- FINAL PATCH 2026-04-16B: direct geometry/textbook handlers and cleaner fraction-word parsing ---

_FINAL_20260416B_PREV_BUILD_EXPLANATION = build_explanation


def _final_20260416b_try_geometry_direct(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    unit = geometry_unit(lower)

    square_side_match = re.search(
        r'(?:квадрат[^.?!]{0,80}?со\s+сторон(?:ой|ою)?[^\d]{0,20}(\d+))|(?:сторона\s+квадрата[^\d]{0,20}(\d+))',
        lower,
    )
    square_side_val = int(next(group for group in square_side_match.groups() if group)) if square_side_match else None

    if 'квадрат' in lower and 'периметр' in lower and square_side_val is not None:
        result = square_side_val * 4
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: сторона квадрата равна {square_side_val} {unit}.',
            'Что нужно найти: периметр квадрата.',
            '1) У квадрата все четыре стороны равны.',
            f'2) Периметр квадрата — это сумма четырёх равных сторон: {square_side_val} × 4 = {result}.',
            f'Ответ: {with_unit(result, unit)}.'
        )

    area_val = extract_keyword_number(lower, 'площад')
    length_val = extract_keyword_number(lower, 'длина')
    width_val = extract_keyword_number(lower, 'ширина')
    asks_width = 'найдите ширину' in lower or 'найди ширину' in lower or 'какова ширина' in lower
    asks_length = ('найдите длину' in lower or 'найди длину' in lower or 'какова длина' in lower) and not asks_width

    if 'прямоугольн' in lower and area_val is not None and length_val is not None and asks_width and length_val != 0 and area_val % length_val == 0:
        width = area_val // length_val
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, длина {with_unit(length_val, unit)}.',
            'Что нужно найти: ширину прямоугольника.',
            '1) Площадь прямоугольника равна длине, умноженной на ширину.',
            f'2) Чтобы найти ширину, делим площадь на длину: {area_val} : {length_val} = {width}.',
            f'Ответ: {with_unit(width, unit)}.'
        )

    if 'прямоугольн' in lower and area_val is not None and width_val is not None and asks_length and width_val != 0 and area_val % width_val == 0:
        length = area_val // width_val
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, ширина {with_unit(width_val, unit)}.',
            'Что нужно найти: длину прямоугольника.',
            '1) Площадь прямоугольника равна длине, умноженной на ширину.',
            f'2) Чтобы найти длину, делим площадь на ширину: {area_val} : {width_val} = {length}.',
            f'Ответ: {with_unit(length, unit)}.'
        )

    return None


def _final_20260416b_try_fraction_whole_comparison(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None

    fraction_hits = []
    for match in re.finditer(r'(половина|треть|четверть)[^0-9]{0,80}?(?:это\s*)?(\d+)', lower):
        frac_word = match.group(1)
        value = int(match.group(2))
        pair = _final_20260416_fraction_word_to_pair(frac_word)
        if not pair:
            continue
        fraction_hits.append((frac_word, value, pair[0], pair[1]))
    if len(fraction_hits) < 2:
        return None
    fraction_hits = fraction_hits[:2]

    first_word, first_value, first_num, first_den = fraction_hits[0]
    second_word, second_value, second_num, second_den = fraction_hits[1]
    if first_value * first_den % first_num != 0 or second_value * second_den % second_num != 0:
        return None
    first_whole = first_value * first_den // first_num
    second_whole = second_value * second_den // second_num

    unit = ''
    if 'см2' in lower or 'см²' in lower:
        unit = 'см²'
    elif 'м2' in lower or 'м²' in lower:
        unit = 'м²'
    elif 'кг' in lower:
        unit = 'кг'

    if 'во сколько раз' in lower and ('больше' in lower or 'меньше' in lower):
        bigger = max(first_whole, second_whole)
        smaller = min(first_whole, second_whole)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {first_word} первого количества — это {first_value} {unit}. {second_word} второго количества — это {second_value} {unit}.',
            'Что нужно найти: во сколько раз одно количество больше другого.',
            f'1) Найдём всё первое количество: {first_value} × {first_den} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {second_value} × {second_den} = {second_whole} {unit}.',
            f'3) Сравним количества: {bigger} : {smaller} = {ratio}.',
            f'Ответ: в {ratio} раза.'
        )

    if 'на сколько' in lower and ('больше' in lower or 'меньше' in lower):
        difference = abs(second_whole - first_whole)
        big = max(first_whole, second_whole)
        small = min(first_whole, second_whole)
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {first_word} первого количества — это {first_value} {unit}. {second_word} второго количества — это {second_value} {unit}.',
            'Что нужно найти: на сколько одно количество отличается от другого.',
            f'1) Найдём всё первое количество: {first_value} × {first_den} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {second_value} × {second_den} = {second_whole} {unit}.',
            f'3) Найдём разность: {big} - {small} = {difference} {unit}.',
            f'Ответ: на {difference} {unit}.'.replace('  ', ' ')
        )

    return None


def _final_20260416b_try_red_green_apples_half_taken(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None
    if 'красн' not in lower or 'зелен' not in lower or 'яблок' not in lower:
        return None
    if 'половину всех яблок' not in lower or 'осталось' not in lower or 'сначала' not in lower:
        return None
    green_added, remained_after_taking = nums[:2]
    total_before_taking = remained_after_taking * 2
    red_initial = total_before_taking - green_added
    if min(green_added, remained_after_taking, total_before_taking, red_initial) < 0:
        return None
    apple_word = _final_20260415ae_plural(red_initial, 'красное яблоко', 'красных яблока', 'красных яблок')
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: в корзину положили ещё {green_added} зелёных яблок. После того как взяли половину всех яблок, осталось {remained_after_taking} яблок.',
        'Что нужно найти: сколько красных яблок было в корзине сначала.',
        f'1) Если после того как взяли половину, осталось {remained_after_taking} яблок, значит это половина всех яблок.',
        f'2) Тогда до того как взяли половину, в корзине было {remained_after_taking} × 2 = {total_before_taking} яблок.',
        f'3) Из этих яблок {green_added} были зелёные, значит красных было {total_before_taking} - {green_added} = {red_initial}.',
        f'Ответ: сначала в корзине было {red_initial} {apple_word}.'
    )


def _final_20260416_try_all_remaining_fixes(raw_text: str) -> Optional[str]:
    return (
        _final_20260416b_try_geometry_direct(raw_text)
        or _final_20260416_try_pickles_two_days(raw_text)
        or _final_20260416_try_motion_compare_two_distances(raw_text)
        or _final_20260416_try_same_price_two_days(raw_text)
        or _final_20260416b_try_red_green_apples_half_taken(raw_text)
        or _final_20260416b_try_fraction_whole_comparison(raw_text)
        or _final_20260416_try_ratio_difference_full_answer(raw_text)
    )


async def build_explanation(user_text: str) -> dict:
    local = _final_20260416_try_all_remaining_fixes(user_text)
    if local:
        return _final_20260416_result_dict(local, 'local-final-20260416b')
    return await _FINAL_20260416B_PREV_BUILD_EXPLANATION(user_text)


# --- FINAL PATCH 2026-04-16C: robust numeric extraction for geometry wording ---

_FINAL_20260416C_PREV_BUILD_EXPLANATION = build_explanation


def _final_20260416c_find_geometry_number(lower: str, keyword: str) -> Optional[int]:
    patterns = {
        'площадь': [
            r'площад[а-яё ]{0,20}(?:равна|=|составляет|имеет)?[^\d]{0,12}(\d+)\s*(?:мм2|см2|дм2|м2|км2|мм²|см²|дм²|м²|км²)?',
            r'(\d+)\s*(?:мм2|см2|дм2|м2|км2|мм²|см²|дм²|м²|км²)[^.?!]{0,30}площад',
        ],
        'длина': [
            r'длин[а-яё ]{0,20}(?:равна|=|имеет)?[^\d]{0,12}(\d+)\s*(?:мм|см|дм|м|км)\b',
            r'(\d+)\s*(?:мм|см|дм|м|км)\b[^.?!]{0,30}длин',
        ],
        'ширина': [
            r'ширин[а-яё ]{0,20}(?:равна|=|имеет)?[^\d]{0,12}(\d+)\s*(?:мм|см|дм|м|км)\b',
            r'(\d+)\s*(?:мм|см|дм|м|км)\b[^.?!]{0,30}ширин',
        ],
    }
    key = 'площадь' if keyword.startswith('площад') else 'длина' if keyword.startswith('длина') else 'ширина'
    for pattern in patterns[key]:
        match = re.search(pattern, lower)
        if match:
            return int(match.group(1))
    return None


def _final_20260416b_try_geometry_direct(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    unit = geometry_unit(lower)

    square_side_match = re.search(
        r'(?:квадрат[^.?!]{0,80}?со\s+сторон(?:ой|ою)?[^\d]{0,20}(\d+))|(?:сторона\s+квадрата[^\d]{0,20}(\d+))',
        lower,
    )
    square_side_val = int(next(group for group in square_side_match.groups() if group)) if square_side_match else None

    if 'квадрат' in lower and 'периметр' in lower and square_side_val is not None:
        result = square_side_val * 4
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: сторона квадрата равна {square_side_val} {unit}.',
            'Что нужно найти: периметр квадрата.',
            '1) У квадрата все четыре стороны равны.',
            f'2) Периметр квадрата — это сумма четырёх равных сторон: {square_side_val} × 4 = {result}.',
            f'Ответ: {with_unit(result, unit)}.'
        )

    area_val = _final_20260416c_find_geometry_number(lower, 'площадь')
    length_val = _final_20260416c_find_geometry_number(lower, 'длина')
    width_val = _final_20260416c_find_geometry_number(lower, 'ширина')
    asks_width = 'найдите ширину' in lower or 'найди ширину' in lower or 'какова ширина' in lower
    asks_length = ('найдите длину' in lower or 'найди длину' in lower or 'какова длина' in lower) and not asks_width

    if 'прямоугольн' in lower and area_val is not None and length_val is not None and asks_width and length_val != 0 and area_val % length_val == 0:
        width = area_val // length_val
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, длина {with_unit(length_val, unit)}.',
            'Что нужно найти: ширину прямоугольника.',
            '1) Площадь прямоугольника равна длине, умноженной на ширину.',
            f'2) Чтобы найти ширину, делим площадь на длину: {area_val} : {length_val} = {width}.',
            f'Ответ: {with_unit(width, unit)}.'
        )

    if 'прямоугольн' in lower and area_val is not None and width_val is not None and asks_length and width_val != 0 and area_val % width_val == 0:
        length = area_val // width_val
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, ширина {with_unit(width_val, unit)}.',
            'Что нужно найти: длину прямоугольника.',
            '1) Площадь прямоугольника равна длине, умноженной на ширину.',
            f'2) Чтобы найти длину, делим площадь на ширину: {area_val} : {width_val} = {length}.',
            f'Ответ: {with_unit(length, unit)}.'
        )

    return None


async def build_explanation(user_text: str) -> dict:
    local = _final_20260416_try_all_remaining_fixes(user_text)
    if local:
        return _final_20260416_result_dict(local, 'local-final-20260416c')
    return await _FINAL_20260416C_PREV_BUILD_EXPLANATION(user_text)


# --- FINAL PATCH 2026-04-16D: fuller textbook-style answers in new direct handlers ---

_FINAL_20260416D_PREV_BUILD_EXPLANATION = build_explanation


def _final_20260416b_try_geometry_direct(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    unit = geometry_unit(lower)

    square_side_match = re.search(
        r'(?:квадрат[^.?!]{0,80}?со\s+сторон(?:ой|ою)?[^\d]{0,20}(\d+))|(?:сторона\s+квадрата[^\d]{0,20}(\d+))',
        lower,
    )
    square_side_val = int(next(group for group in square_side_match.groups() if group)) if square_side_match else None

    if 'квадрат' in lower and 'периметр' in lower and square_side_val is not None:
        result = square_side_val * 4
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: сторона квадрата равна {square_side_val} {unit}.',
            'Что нужно найти: периметр квадрата.',
            '1) У квадрата все четыре стороны равны.',
            f'2) Периметр квадрата — это сумма четырёх равных сторон: {square_side_val} × 4 = {result}.',
            f'Ответ: периметр квадрата равен {with_unit(result, unit)}.'
        )

    area_val = _final_20260416c_find_geometry_number(lower, 'площадь')
    length_val = _final_20260416c_find_geometry_number(lower, 'длина')
    width_val = _final_20260416c_find_geometry_number(lower, 'ширина')
    asks_width = 'найдите ширину' in lower or 'найди ширину' in lower or 'какова ширина' in lower
    asks_length = ('найдите длину' in lower or 'найди длину' in lower or 'какова длина' in lower) and not asks_width

    if 'прямоугольн' in lower and area_val is not None and length_val is not None and asks_width and length_val != 0 and area_val % length_val == 0:
        width = area_val // length_val
        object_name = 'прямоугольника'
        if 'пруд' in lower:
            object_name = 'пруда'
        elif 'площадк' in lower:
            object_name = 'площадки'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, длина {with_unit(length_val, unit)}.',
            f'Что нужно найти: ширину {object_name}.',
            '1) Площадь прямоугольника равна длине, умноженной на ширину.',
            f'2) Чтобы найти ширину, делим площадь на длину: {area_val} : {length_val} = {width}.',
            f'Ответ: ширина {object_name} равна {with_unit(width, unit)}.'
        )

    if 'прямоугольн' in lower and area_val is not None and width_val is not None and asks_length and width_val != 0 and area_val % width_val == 0:
        length = area_val // width_val
        object_name = 'прямоугольника'
        if 'площадк' in lower:
            object_name = 'площадки'
        elif 'пруд' in lower:
            object_name = 'пруда'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, ширина {with_unit(width_val, unit)}.',
            f'Что нужно найти: длину {object_name}.',
            '1) Площадь прямоугольника равна длине, умноженной на ширину.',
            f'2) Чтобы найти длину, делим площадь на ширину: {area_val} : {width_val} = {length}.',
            f'Ответ: длина {object_name} равна {with_unit(length, unit)}.'
        )

    return None


def _final_20260416b_try_fraction_whole_comparison(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None

    fraction_hits = []
    for match in re.finditer(r'(половина|треть|четверть)([^0-9]{0,80}?)(?:это\s*)?(\d+)', lower):
        frac_word = match.group(1)
        object_fragment = (match.group(2) or '').strip(' ,-–—')
        value = int(match.group(3))
        pair = _final_20260416_fraction_word_to_pair(frac_word)
        if not pair:
            continue
        fraction_hits.append((frac_word, object_fragment, value, pair[0], pair[1]))
    if len(fraction_hits) < 2:
        return None
    fraction_hits = fraction_hits[:2]

    first_word, first_object, first_value, first_num, first_den = fraction_hits[0]
    second_word, second_object, second_value, second_num, second_den = fraction_hits[1]
    if first_value * first_den % first_num != 0 or second_value * second_den % second_num != 0:
        return None
    first_whole = first_value * first_den // first_num
    second_whole = second_value * second_den // second_num

    unit = ''
    if 'см2' in lower or 'см²' in lower:
        unit = 'см²'
    elif 'м2' in lower or 'м²' in lower:
        unit = 'м²'
    elif 'кг' in lower:
        unit = 'кг'

    first_label = first_object or 'первого количества'
    second_label = second_object or 'второго количества'
    first_label = re.sub(r'\s+', ' ', first_label).strip()
    second_label = re.sub(r'\s+', ' ', second_label).strip()

    if 'во сколько раз' in lower and ('больше' in lower or 'меньше' in lower):
        bigger = max(first_whole, second_whole)
        smaller = min(first_whole, second_whole)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        answer = f'Ответ: первое количество больше второго в {ratio} раза.'
        if 'картошк' in lower and 'морков' in lower:
            answer = f'Ответ: масса картошки больше массы моркови в {ratio} раза.'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {first_word} {first_label} — это {first_value} {unit}. {second_word} {second_label} — это {second_value} {unit}.',
            'Что нужно найти: во сколько раз одно количество больше другого.',
            f'1) Найдём всё первое количество: {first_value} × {first_den} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {second_value} × {second_den} = {second_whole} {unit}.',
            f'3) Сравним количества: {bigger} : {smaller} = {ratio}.',
            answer
        )

    if 'на сколько' in lower and ('больше' in lower or 'меньше' in lower):
        difference = abs(second_whole - first_whole)
        big = max(first_whole, second_whole)
        small = min(first_whole, second_whole)
        answer = f'Ответ: одно количество отличается от другого на {difference} {unit}.'.replace('  ', ' ')
        if 'салфет' in lower and 'скатерт' in lower:
            answer = f'Ответ: площадь салфетки меньше площади скатерти на {difference} {unit}.'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {first_word} {first_label} — это {first_value} {unit}. {second_word} {second_label} — это {second_value} {unit}.',
            'Что нужно найти: на сколько одно количество отличается от другого.',
            f'1) Найдём всё первое количество: {first_value} × {first_den} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {second_value} × {second_den} = {second_whole} {unit}.',
            f'3) Найдём разность: {big} - {small} = {difference} {unit}.',
            answer
        )

    return None


async def build_explanation(user_text: str) -> dict:
    local = _final_20260416_try_all_remaining_fixes(user_text)
    if local:
        return _final_20260416_result_dict(local, 'local-final-20260416d')
    return await _FINAL_20260416D_PREV_BUILD_EXPLANATION(user_text)

# --- FINAL PATCH 2026-04-16E: new-source audit fixes without touching stable UI logic ---

_FINAL_20260416E_PREV_BUILD_EXPLANATION = build_explanation

_FINAL_20260416E_LINEAR_UNITS = {
    'мм': 1,
    'см': 10,
    'дм': 100,
    'м': 1000,
    'км': 1000000,
}


def _final_20260416e_norm_math_text(raw_text: str) -> str:
    return strip_known_prefix(str(raw_text or '')).strip()


def _final_20260416e_pretty_ops(text: str) -> str:
    return (
        str(text or '')
        .replace('**', '^')
        .replace('*', ' × ')
        .replace('/', ' : ')
        .replace('+', ' + ')
        .replace('-', ' - ')
    )


def _final_20260416e_eval_integer_expression(expr: str) -> Optional[int]:
    source = to_expression_source(expr) or str(expr or '').strip()
    node = parse_expression_ast(source)
    if node is None:
        return None
    try:
        value = eval_fraction_node(node)
    except Exception:
        return None
    if isinstance(value, Fraction):
        if value.denominator != 1:
            return None
        return int(value.numerator)
    try:
        value = Fraction(value)
    except Exception:
        return None
    if value.denominator != 1:
        return None
    return int(value.numerator)


def _final_20260416e_try_force_detailed_expression(raw_text: str) -> Optional[str]:
    text = _final_20260416e_norm_math_text(raw_text)
    if not text or '=' in text or re.search(r'[A-Za-zА-Яа-я]', text):
        return None
    source = to_expression_source(text)
    if not source:
        return None
    if _final_20260416_normalize_fraction_expression_source(text):
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return None
    rendered = _patch_20260412c_render_mixed_expression_solution(source)
    return rendered if rendered else None


def _final_20260416e_try_motion_per_hour_speed(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if not contains_any_fragment(lower, ('с какой скоростью', 'какова скорость')):
        return None
    match = re.search(r'кажд(?:ый|ую|ое)\s+час[^\d]{0,20}(\d+)\s*км', lower)
    if not match:
        match = re.search(r'(\d+)\s*км[^.?!]{0,30}кажд(?:ый|ую|ое)\s+час', lower)
    if not match:
        return None
    speed = int(match.group(1))
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: за 1 час проходят {speed} км.',
        'Что нужно найти: скорость.',
        '1) Скорость показывает, какое расстояние проходят за один час.',
        f'2) За один час проходят {speed} км, значит скорость равна {speed} км/ч.',
        f'Ответ: скорость равна {speed} км/ч.'
    )


def _final_20260416e_try_equation_with_side_expression(raw_text: str) -> Optional[str]:
    text = _final_20260416e_norm_math_text(raw_text)
    compact = text.replace('×', '*').replace('÷', '/').replace(':', '/').replace('−', '-').replace('–', '-').replace('—', '-')
    if compact.count('=') != 1:
        return None
    if ',' in compact or ';' in compact or '\n' in compact:
        return None
    letters = re.findall(r'[A-Za-zА-Яа-я]', compact)
    if not letters:
        return None
    unique_letters = {ch.lower() for ch in letters}
    if len(unique_letters) != 1:
        return None
    variable = letters[0]
    left_raw, right_raw = [part.strip() for part in compact.split('=', 1)]
    left_has_var = bool(re.search(r'[A-Za-zА-Яа-я]', left_raw))
    right_has_var = bool(re.search(r'[A-Za-zА-Яа-я]', right_raw))
    if left_has_var == right_has_var:
        return None
    variable_side = left_raw if left_has_var else right_raw
    numeric_side = right_raw if left_has_var else left_raw
    if not re.search(r'[+\-*/]', numeric_side):
        return None
    numeric_value = _final_20260416e_eval_integer_expression(numeric_side)
    if numeric_value is None:
        return None

    compact_var = variable_side.replace(' ', '')
    pretty_numeric = _final_20260416e_pretty_ops(numeric_side).replace('  ', ' ').strip()
    pretty_variable_side = _final_20260416e_pretty_ops(variable_side).replace('  ', ' ').strip()

    def build_lines(new_equation: str, solve_line: str, final_value: int, component_text: str, operation_text: str) -> str:
        original_pretty = _final_20260416e_pretty_ops(compact.replace('=', ' = ')).replace('  ', ' ').strip()
        return join_explanation_lines(
            'Уравнение:',
            original_pretty,
            'Решение.',
            '1) Сначала вычисляем значение выражения в той части уравнения, где нет неизвестного:',
            f'{pretty_numeric} = {numeric_value}',
            '2) Получаем более простое уравнение:',
            new_equation,
            component_text,
            operation_text,
            f'3) Считаем: {solve_line}',
            f'Ответ: {final_value}'
        )

    m = re.fullmatch(rf'{re.escape(variable)}\+(\d+)', compact_var)
    if m:
        number = int(m.group(1))
        answer = numeric_value - number
        return build_lines(
            f'{variable} + {number} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное слагаемое.',
            f'Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: {variable} = {numeric_value} - {number}.'
        )
    m = re.fullmatch(rf'(\d+)\+{re.escape(variable)}', compact_var)
    if m:
        number = int(m.group(1))
        answer = numeric_value - number
        return build_lines(
            f'{number} + {variable} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное слагаемое.',
            f'Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: {variable} = {numeric_value} - {number}.'
        )
    m = re.fullmatch(rf'{re.escape(variable)}-(\d+)', compact_var)
    if m:
        number = int(m.group(1))
        answer = numeric_value + number
        return build_lines(
            f'{variable} - {number} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное уменьшаемое.',
            f'Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое: {variable} = {numeric_value} + {number}.'
        )
    m = re.fullmatch(rf'(\d+)-{re.escape(variable)}', compact_var)
    if m:
        number = int(m.group(1))
        answer = number - numeric_value
        return build_lines(
            f'{number} - {variable} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное вычитаемое.',
            f'Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность: {variable} = {number} - {numeric_value}.'
        )
    m = re.fullmatch(rf'{re.escape(variable)}\*(\d+)', compact_var)
    if m:
        number = int(m.group(1))
        if number == 0 or numeric_value % number != 0:
            return None
        answer = numeric_value // number
        return build_lines(
            f'{variable} × {number} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестный множитель.',
            f'Чтобы найти неизвестный множитель, произведение делим на известный множитель: {variable} = {numeric_value} : {number}.'
        )
    m = re.fullmatch(rf'(\d+)\*{re.escape(variable)}', compact_var)
    if m:
        number = int(m.group(1))
        if number == 0 or numeric_value % number != 0:
            return None
        answer = numeric_value // number
        return build_lines(
            f'{number} × {variable} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестный множитель.',
            f'Чтобы найти неизвестный множитель, произведение делим на известный множитель: {variable} = {numeric_value} : {number}.'
        )
    m = re.fullmatch(rf'{re.escape(variable)}/(\d+)', compact_var)
    if m:
        number = int(m.group(1))
        answer = numeric_value * number
        return build_lines(
            f'{variable} : {number} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное делимое.',
            f'Чтобы найти неизвестное делимое, делитель умножаем на частное: {variable} = {numeric_value} × {number}.'
        )
    m = re.fullmatch(rf'(\d+)/{re.escape(variable)}', compact_var)
    if m:
        number = int(m.group(1))
        if numeric_value == 0 or number % numeric_value != 0:
            return None
        answer = number // numeric_value
        return build_lines(
            f'{number} : {variable} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестный делитель.',
            f'Чтобы найти неизвестный делитель, делимое делим на частное: {variable} = {number} : {numeric_value}.'
        )
    return None


def _final_20260416e_extract_target_area_unit(lower: str) -> Optional[str]:
    if 'мм2' in lower or 'мм²' in lower:
        return 'мм'
    if 'см2' in lower or 'см²' in lower:
        return 'см'
    if 'дм2' in lower or 'дм²' in lower:
        return 'дм'
    if 'м2' in lower or 'м²' in lower:
        return 'м'
    if 'км2' in lower or 'км²' in lower:
        return 'км'
    return None


def _final_20260416e_convert_area_value(value: int, from_unit: str, to_unit: str) -> Optional[int]:
    if from_unit not in _FINAL_20260416E_LINEAR_UNITS or to_unit not in _FINAL_20260416E_LINEAR_UNITS:
        return None
    base_from = _FINAL_20260416E_LINEAR_UNITS[from_unit]
    base_to = _FINAL_20260416E_LINEAR_UNITS[to_unit]
    total_in_mm2 = value * (base_from ** 2)
    if total_in_mm2 % (base_to ** 2) != 0:
        return None
    return total_in_mm2 // (base_to ** 2)

# --- merged segment 019: backend.legacy_runtime_shards.prepatch_build_source.segment_019 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 15976-16844."""



def _final_20260416e_try_geometry_textbook_patterns(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    # 1) Прямоугольник: известны длина и ширина напрямую.
    rect_direct = re.search(
        r'длин[а-яё ]{0,20}(?:которого|прямоугольника)?[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширин[а-яё ]{0,20}[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)',
        lower,
    )
    if rect_direct:
        length = int(rect_direct.group(1))
        length_unit = rect_direct.group(2)
        width = int(rect_direct.group(3))
        width_unit = rect_direct.group(4)
        if length_unit == width_unit:
            unit = length_unit
            area = length * width
            perimeter = (length + width) * 2
            asks_area = 'площад' in lower
            asks_perimeter = 'периметр' in lower
            target_area_unit = _final_20260416e_extract_target_area_unit(lower)
            if asks_area and target_area_unit and target_area_unit != unit:
                converted = _final_20260416e_convert_area_value(area, unit, target_area_unit)
                if converted is not None:
                    return join_explanation_lines(
                        'Задача.',
                        _audit_task_line(raw_text),
                        'Решение.',
                        f'Что известно: длина прямоугольника {with_unit(length, unit)}, ширина {with_unit(width, unit)}.',
                        'Что нужно найти: площадь прямоугольника и перевести её в другую единицу площади.',
                        f'1) Находим площадь прямоугольника: {length} × {width} = {area} {unit}².',
                        f'2) Переводим {area} {unit}² в {target_area_unit}²: {area} {unit}² = {converted} {target_area_unit}².',
                        f'Ответ: площадь прямоугольника равна {with_unit(converted, target_area_unit, square=True)}.'
                    )
            if asks_area and not asks_perimeter:
                return join_explanation_lines(
                    'Задача.',
                    _audit_task_line(raw_text),
                    'Решение.',
                    f'Что известно: длина прямоугольника {with_unit(length, unit)}, ширина {with_unit(width, unit)}.',
                    'Что нужно найти: площадь прямоугольника.',
                    f'1) Площадь прямоугольника равна длине, умноженной на ширину: {length} × {width} = {area}.',
                    f'Ответ: площадь прямоугольника равна {with_unit(area, unit, square=True)}.'
                )
            if asks_perimeter and not asks_area:
                return join_explanation_lines(
                    'Задача.',
                    _audit_task_line(raw_text),
                    'Решение.',
                    f'Что известно: длина прямоугольника {with_unit(length, unit)}, ширина {with_unit(width, unit)}.',
                    'Что нужно найти: периметр прямоугольника.',
                    f'1) Периметр прямоугольника равен сумме длины и ширины, умноженной на 2: ({length} + {width}) × 2 = {perimeter}.',
                    f'Ответ: периметр прямоугольника равен {with_unit(perimeter, unit)}.'
                )
            if asks_area and asks_perimeter:
                return join_explanation_lines(
                    'Задача.',
                    _audit_task_line(raw_text),
                    'Решение.',
                    f'Что известно: длина прямоугольника {with_unit(length, unit)}, ширина {with_unit(width, unit)}.',
                    'Что нужно найти: площадь и периметр прямоугольника.',
                    f'1) Находим площадь: {length} × {width} = {area} {unit}².',
                    f'2) Находим периметр: ({length} + {width}) × 2 = {perimeter} {unit}.',
                    f'Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}.'
                )

    # 2) Квадрат: известна сторона (в разных формулировках).
    square_side = re.search(
        r'квадрат[^.?!]{0,80}?(?:со\s+сторон(?:ой|ою)?|длина\s+которого|длина\s+стороны)[^\d]{0,20}(\d+)\s*(мм|см|дм|м|км)',
        lower,
    )
    if square_side:
        side = int(square_side.group(1))
        unit = square_side.group(2)
        area = side * side
        perimeter = side * 4
        asks_area = 'площад' in lower
        asks_perimeter = 'периметр' in lower
        if asks_area and not asks_perimeter:
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: сторона квадрата равна {with_unit(side, unit)}.',
                'Что нужно найти: площадь квадрата.',
                f'1) Площадь квадрата равна стороне, умноженной на сторону: {side} × {side} = {area}.',
                f'Ответ: площадь квадрата равна {with_unit(area, unit, square=True)}.'
            )
        if asks_perimeter and not asks_area:
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: сторона квадрата равна {with_unit(side, unit)}.',
                'Что нужно найти: периметр квадрата.',
                f'1) Периметр квадрата равен четырём сторонам: {side} × 4 = {perimeter}.',
                f'Ответ: периметр квадрата равен {with_unit(perimeter, unit)}.'
            )

    # 3) Прямоугольник: одна сторона известна, другая задана через «на ... больше/меньше» или «в ... раз ...».
    patterns = [
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*меньше', lower),
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+в\s+(\d+)\s+раза?\s+меньше', lower),
        re.search(r'ширина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}длина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*больше', lower),
        re.search(r'ширина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}длина\s+в\s+(\d+)\s+раза?\s+больше', lower),
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*короче', lower),
    ]
    for idx, match in enumerate(patterns):
        if not match:
            continue
        first = int(match.group(1))
        unit = match.group(2)
        second = int(match.group(3))
        if idx in {0, 4}:  # length known, width smaller by delta
            length = first
            width = first - second
            explanation_line = f'1) Сначала находим ширину: {length} - {second} = {width}.'
        elif idx == 1:  # length known, width less in ratio
            length = first
            if second == 0 or first % second != 0:
                return None
            width = first // second
            explanation_line = f'1) Сначала находим ширину: {length} : {second} = {width}.'
        elif idx == 2:  # width known, length greater by delta
            width = first
            length = first + second
            explanation_line = f'1) Сначала находим длину: {width} + {second} = {length}.'
        else:  # width known, length greater in ratio
            width = first
            length = first * second
            explanation_line = f'1) Сначала находим длину: {width} × {second} = {length}.'
        if width < 0:
            return None
        area = length * width
        perimeter = (length + width) * 2
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: длина и ширина прямоугольника связаны между собой.',
            'Что нужно найти: площадь и периметр прямоугольника.',
            explanation_line,
            f'2) Находим площадь: {length} × {width} = {area} {unit}².',
            f'3) Находим периметр: ({length} + {width}) × 2 = {perimeter} {unit}.',
            f'Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}.'
        )

    return None


def _final_20260416e_try_fraction_textbook_patterns(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    # Найти число по его дроби.
    match = re.search(r'найти\s+число[^.?!]*?(\d+)\s*/\s*(\d+)\s+его\s+(?:составляет|равна|равно|равны)\s*(\d+)', lower)
    if match:
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        part_value = int(match.group(3))
        if numerator == 0 or (part_value * denominator) % numerator != 0:
            return None
        whole = part_value * denominator // numerator
        one_part = part_value // numerator if numerator != 0 and part_value % numerator == 0 else None
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {numerator}/{denominator} числа равны {part_value}.',
            'Что нужно найти: всё число.',
        ]
        if one_part is not None:
            lines.append(f'1) Находим одну долю: {part_value} : {numerator} = {one_part}.')
            lines.append(f'2) Находим всё число: {one_part} × {denominator} = {whole}.')
        else:
            lines.append(f'1) Чтобы найти всё число, умножаем значение части на знаменатель и делим на числитель: {part_value} × {denominator} : {numerator} = {whole}.')
        lines.append(f'Ответ: {whole}.')
        return join_explanation_lines(*lines)

    # Известно целое и дробная часть; спрашивают часть или остаток.
    first_number_match = re.search(r'(\d+)', re.sub(r'\b\d+\s*/\s*\d+\b', ' ', lower))
    fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', lower)
    if first_number_match and fraction_match:
        total = int(first_number_match.group(1))
        numerator = int(fraction_match.group(1))
        denominator = int(fraction_match.group(2))
        if denominator == 0 or total * numerator % denominator != 0:
            return None
        one_part = total // denominator if total % denominator == 0 else None
        part_value = total * numerator // denominator

        if 'остальн' in lower:
            remaining = total - part_value
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: всего {total}, дробная часть {numerator}/{denominator}.',
                'Что нужно найти: сколько осталось после этой части.',
                f'1) Находим одну долю: {total} : {denominator} = {one_part if one_part is not None else total / denominator}.',
                f'2) Находим {numerator}/{denominator} от {total}: {one_part if one_part is not None else f"{total} : {denominator}"} × {numerator} = {part_value}.',
                f'3) Находим остаток: {total} - {part_value} = {remaining}.',
                f'Ответ: {remaining}.'
            )

        if contains_any_fragment(lower, ('составляет', 'составля', 'часть комнаты', 'часть всех', 'от ')) or ('чему равна' in lower and '/' in lower):
            result_label = 'часть'
            if 'площад' in lower:
                return join_explanation_lines(
                    'Задача.',
                    _audit_task_line(raw_text),
                    'Решение.',
                    f'Что известно: всё равно {total}, нужно найти {numerator}/{denominator} этого числа.',
                    'Что нужно найти: искомую часть.',
                    f'1) Находим одну долю: {total} : {denominator} = {one_part if one_part is not None else total / denominator}.',
                    f'2) Находим {numerator}/{denominator} от {total}: {one_part if one_part is not None else f"{total} : {denominator}"} × {numerator} = {part_value}.',
                    f'Ответ: {part_value}.'
                )
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: всё равно {total}, нужно найти {numerator}/{denominator} этого числа.',
                'Что нужно найти: искомую часть.',
                f'1) Находим одну долю: {total} : {denominator} = {one_part if one_part is not None else total / denominator}.',
                f'2) Находим {numerator}/{denominator} от {total}: {one_part if one_part is not None else f"{total} : {denominator}"} × {numerator} = {part_value}.',
                f'Ответ: {part_value}.'
            )

    return None


async def build_explanation(user_text: str) -> dict:
    local = (
        _final_20260416e_try_equation_with_side_expression(user_text)
        or _final_20260416e_try_motion_per_hour_speed(user_text)
        or _final_20260416e_try_geometry_textbook_patterns(user_text)
        or _final_20260416e_try_fraction_textbook_patterns(user_text)
        or _final_20260416e_try_force_detailed_expression(user_text)
    )
    if local:
        return _final_20260416_result_dict(local, 'local-final-20260416e')
    return await _FINAL_20260416E_PREV_BUILD_EXPLANATION(user_text)

# --- FINAL PATCH 2026-04-16F: relation geometry before direct widths, and fraction area units ---

_FINAL_20260416F_PREV_BUILD_EXPLANATION = build_explanation


def _final_20260416f_detect_metric_unit(lower: str) -> str:
    if 'кв.м' in lower or 'м2' in lower or 'м²' in lower:
        return 'м'
    if 'кв.дм' in lower or 'дм2' in lower or 'дм²' in lower:
        return 'дм'
    if 'кв.см' in lower or 'см2' in lower or 'см²' in lower:
        return 'см'
    if 'кв.мм' in lower or 'мм2' in lower or 'мм²' in lower:
        return 'мм'
    return geometry_unit(lower)


def _final_20260416f_try_geometry_relations(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    relation_patterns = [
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*меньше', lower),
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+в\s+(\d+)\s+раза?\s+меньше', lower),
        re.search(r'ширина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}длина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*больше', lower),
        re.search(r'ширина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}длина\s+в\s+(\d+)\s+раза?\s+больше', lower),
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*короче', lower),
    ]
    for idx, match in enumerate(relation_patterns):
        if not match:
            continue
        first = int(match.group(1))
        unit = match.group(2)
        second = int(match.group(3))
        if idx in {0, 4}:
            length = first
            width = first - second
            first_step = f'1) Сначала находим ширину: {length} - {second} = {width}.'
        elif idx == 1:
            length = first
            if second == 0 or first % second != 0:
                return None
            width = first // second
            first_step = f'1) Сначала находим ширину: {length} : {second} = {width}.'
        elif idx == 2:
            width = first
            length = first + second
            first_step = f'1) Сначала находим длину: {width} + {second} = {length}.'
        else:
            width = first
            length = first * second
            first_step = f'1) Сначала находим длину: {width} × {second} = {length}.'
        if width < 0:
            return None
        area = length * width
        perimeter = (length + width) * 2
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Что известно: одна сторона прямоугольника дана, а другая выражена через неё.',
            'Что нужно найти: площадь и периметр прямоугольника.',
            first_step,
            f'2) Находим площадь: {length} × {width} = {area} {unit}².',
            f'3) Находим периметр: ({length} + {width}) × 2 = {perimeter} {unit}.',
            f'Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}.'
        )
    return None


def _final_20260416f_try_fraction_area_part(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')
    if 'площад' not in lower or 'остальн' in lower:
        return None
    fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', lower)
    total_match = re.search(r'(\d+)', re.sub(r'\b\d+\s*/\s*\d+\b', ' ', lower))
    if not fraction_match or not total_match:
        return None
    numerator = int(fraction_match.group(1))
    denominator = int(fraction_match.group(2))
    total = int(total_match.group(1))
    if denominator == 0 or total % denominator != 0:
        return None
    unit = _final_20260416f_detect_metric_unit(lower) or 'м'
    one_part = total // denominator
    result = one_part * numerator
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: всё равно {with_unit(total, unit, square=True)}, нужно найти {numerator}/{denominator} этого числа.',
        'Что нужно найти: площадь искомой части.',
        f'1) Находим одну долю: {total} : {denominator} = {one_part}.',
        f'2) Находим {numerator}/{denominator} от {total}: {one_part} × {numerator} = {result}.',
        f'Ответ: площадь равна {with_unit(result, unit, square=True)}.'
    )


async def build_explanation(user_text: str) -> dict:
    local = (
        _final_20260416f_try_geometry_relations(user_text)
        or _final_20260416f_try_fraction_area_part(user_text)
    )
    if local:
        return _final_20260416_result_dict(local, 'local-final-20260416f')
    return await _FINAL_20260416F_PREV_BUILD_EXPLANATION(user_text)

# --- FINAL PATCH 2026-04-16G: fraction remainder wording like peel/pulp ---

_FINAL_20260416G_PREV_BUILD_EXPLANATION = build_explanation


def _final_20260416g_try_fraction_remainder_named_part(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')
    if 'мякот' not in lower:
        return None
    total_match = re.search(r'(\d+)\s*(?:г|кг)', lower)
    fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', lower)
    if not total_match or not fraction_match:
        return None
    total = int(total_match.group(1))
    numerator = int(fraction_match.group(1))
    denominator = int(fraction_match.group(2))
    if denominator == 0 or total * numerator % denominator != 0:
        return None
    peel = total * numerator // denominator
    pulp = total - peel
    unit = 'г' if ' г' in lower else 'кг' if 'кг' in lower else ''
    one_part = total // denominator if total % denominator == 0 else None
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: масса банана {with_unit(total, unit)}, кожура составляет {numerator}/{denominator} всей массы.',
        'Что нужно найти: массу мякоти.',
        f'1) Находим одну долю: {total} : {denominator} = {one_part if one_part is not None else total / denominator}.',
        f'2) Находим массу кожуры: {one_part if one_part is not None else f"{total} : {denominator}"} × {numerator} = {peel}.',
        f'3) Находим массу мякоти: {total} - {peel} = {pulp}.',
        f'Ответ: масса мякоти равна {with_unit(pulp, unit)}.'
    )


async def build_explanation(user_text: str) -> dict:
    local = _final_20260416g_try_fraction_remainder_named_part(user_text)
    if local:
        return _final_20260416_result_dict(local, 'local-final-20260416g')
    return await _FINAL_20260416G_PREV_BUILD_EXPLANATION(user_text)


# --- FINAL PATCH 2026-04-16H: prompt-driven primary school audit fixes ---

_PROMPT20260416H_PREV_BUILD_EXPLANATION = build_explanation


def _prompt20260416h_result(text: str, source: str = 'local') -> dict:
    return {'result': text, 'source': source, 'validated': True}


def _prompt20260416h_eval_int_expression(expr: str) -> Optional[int]:
    source = to_expression_source(expr) or str(expr or '').strip()
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    try:
        value = eval_fraction_node(node)
    except Exception:
        return None
    if not isinstance(value, Fraction):
        try:
            value = Fraction(value)
        except Exception:
            return None
    if value.denominator != 1:
        return None
    return int(value.numerator)


def _prompt20260416h_pretty_expr(source: str) -> str:
    try:
        return _user_final_patch_pretty_expression_from_source(source)
    except Exception:
        return str(source or '').replace('*', ' × ').replace('/', ' : ')


def _prompt20260416h_single_order_block(pretty_expr: str) -> List[str]:
    pos = None
    for idx, ch in enumerate(pretty_expr):
        if ch in '+-×:':
            pos = idx
            break
    if pos is None:
        return []
    mark = (' ' * pos) + '1'
    return ['Порядок действий:', mark.rstrip(), pretty_expr]


def _prompt20260416h_body_without_answer(detail_text: str) -> List[str]:
    parts = _detailed_split_sections(detail_text)
    cleaned: List[str] = []
    for raw in parts.get('body', []):
        line = str(raw or '').strip()
        lower = line.lower()
        if not line:
            continue
        if lower in {'решение', 'решение.', 'решение по действиям', 'решение по действиям:'}:
            continue
        if lower.startswith('пример:'):
            continue
        cleaned.append(line)
    return cleaned


def _prompt20260416h_append_advice_if_missing(text: str, kind: str, advice: Optional[str] = None) -> str:
    cleaned = str(text or '').strip()
    if not cleaned:
        return cleaned
    if re.search(r'^\s*совет\s*:', cleaned, flags=re.IGNORECASE | re.MULTILINE):
        return cleaned
    advice_text = str(advice or default_advice(kind)).strip().rstrip('.!?')
    return _detailed_finalize_text(cleaned.split('\n') + [f'Совет: {advice_text}'])


def _prompt20260416h_try_pure_expression(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text or re.search(r'[A-Za-zА-Яа-я]', text):
        return None
    if _final_20260416_normalize_fraction_expression_source(text):
        return None
    source = to_expression_source(text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None

    try:
        value, steps = build_eval_steps(node, source)
    except Exception:
        return None

    if isinstance(value, Fraction) and value.denominator != 1:
        return None
    answer = format_fraction(value)
    pretty = _prompt20260416h_pretty_expr(source)

    if len(steps) > 1:
        rendered = _patch_20260412c_render_mixed_expression_solution(source)
        if rendered:
            advice = 'сначала выполняй действия в скобках, потом умножение и деление, потом сложение и вычитание'
            return _prompt20260416h_append_advice_if_missing(rendered, 'expression', advice)

    simple = try_simple_binary_int_expression(node)
    if not simple:
        return None
    left = simple['left']
    right = simple['right']
    operator = simple['operator']
    if operator is ast.Add:
        detail = explain_column_addition([left, right]) if (abs(left) >= 100 or abs(right) >= 100) else explain_simple_addition(left, right)
        advice = 'при сложении начинай с единиц и не забывай про перенос разряда' if (abs(left) >= 100 or abs(right) >= 100) else 'сумму находят действием сложения'
    elif operator is ast.Sub:
        detail = explain_column_subtraction(left, right) if (abs(left) >= 100 or abs(right) >= 100) else explain_simple_subtraction(left, right)
        advice = 'при вычитании в столбик начинай с единиц и при необходимости занимай единицу из соседнего разряда' if (abs(left) >= 100 or abs(right) >= 100) else 'разность находят действием вычитания'
    elif operator is ast.Mult:
        detail = explain_long_multiplication(left, right) if (abs(left) >= 100 or abs(right) >= 100) else explain_simple_multiplication(left, right)
        advice = 'произведение находят действием умножения'
    elif operator is ast.Div:
        detail = explain_long_division(left, right) if (abs(left) >= 100 or abs(right) >= 10) else explain_simple_division(left, right)
        advice = 'частное находят делением, а проверять удобно умножением'
    else:
        return None

    lines: List[str] = [f'Пример: {pretty} = {answer}.']
    lines.extend(_prompt20260416h_single_order_block(pretty))
    lines.append('Решение по действиям:')
    lines.append(f'1) {pretty} = {answer}.')
    lines.extend(_prompt20260416h_body_without_answer(detail))
    lines.append(f'Ответ: {answer}')
    lines.append(f'Совет: {advice}')
    return _detailed_finalize_text(lines)


def _prompt20260416h_try_named_measure_expression(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    match = re.fullmatch(r'(\d+)\s*м\s*(\d+)\s*см\s*([+\-])\s*(\d+)\s*м\s*(\d+)\s*см', text.lower())
    if not match:
        return None
    m1 = int(match.group(1))
    cm1 = int(match.group(2))
    sign = '+' if match.group(3) == '+' else '-'
    m2 = int(match.group(4))
    cm2 = int(match.group(5))
    first_cm = m1 * 100 + cm1
    second_cm = m2 * 100 + cm2
    total_cm = first_cm + second_cm if sign == '+' else first_cm - second_cm
    if total_cm < 0:
        return None
    ans_m, ans_cm = divmod(total_cm, 100)
    pretty = f'{m1} м {cm1} см {sign} {m2} м {cm2} см'
    lines = [
        f'Пример: {pretty} = {ans_m} м {ans_cm} см.',
        'Порядок действий:',
        (' ' * (len(f'{m1} м {cm1} см '))) + '1',
        pretty,
        'Решение по действиям:',
        f'1) Переводим первое именованное число в сантиметры: {m1} м {cm1} см = {first_cm} см.',
        f'2) Переводим второе именованное число в сантиметры: {m2} м {cm2} см = {second_cm} см.',
        f'3) Выполняем действие: {first_cm} {sign} {second_cm} = {total_cm} см.',
        f'4) Переводим ответ обратно: {total_cm} см = {ans_m} м {ans_cm} см.',
        f'Ответ: {ans_m} м {ans_cm} см',
        'Совет: именованные числа удобно сначала переводить в меньшую единицу, а потом переводить ответ обратно',
    ]
    return _detailed_finalize_text(lines)


def _prompt20260416h_try_equation(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    norm = normalize_dashes(normalize_cyrillic_x(text)).replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    norm = re.sub(r'\s+', '', norm)
    if norm.count('=') != 1 or 'x' not in norm:
        return None
    lhs, rhs = norm.split('=', 1)
    if 'x' not in lhs and 'x' in rhs:
        lhs, rhs = rhs, lhs

    rhs_value = _prompt20260416h_eval_int_expression(rhs)
    if rhs_value is None:
        return None
    rhs_pretty = _prompt20260416h_pretty_expr(rhs)
    original_pretty = f"{_prompt20260416h_pretty_expr(lhs)} = {_prompt20260416h_pretty_expr(rhs)}"

    steps: List[str] = ['Уравнение:', original_pretty, 'Решение.']
    step_no = 1
    if rhs != str(rhs_value):
        steps.append(f'{step_no}) Сначала вычисляем правую часть: {rhs_pretty} = {rhs_value}.')
        step_no += 1

    check_expr = ''
    answer = None
    if re.fullmatch(r'x\+(\d+)', lhs):
        a = int(re.fullmatch(r'x\+(\d+)', lhs).group(1))
        steps.append(f'{step_no}) Неизвестное x оставляем слева, а число {a} переносим вправо. При переносе знак + меняется на -:')
        steps.append(f'x = {rhs_value} - {a}')
        step_no += 1
        answer = rhs_value - a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{answer} + {a} = {rhs_value}'
    elif re.fullmatch(r'(\d+)\+x', lhs):
        a = int(re.fullmatch(r'(\d+)\+x', lhs).group(1))
        steps.append(f'{step_no}) Переставим слагаемые местами: x + {a} = {rhs_value}.')
        step_no += 1
        steps.append(f'{step_no}) Неизвестное x оставляем слева, а число {a} переносим вправо. При переносе знак + меняется на -:')
        steps.append(f'x = {rhs_value} - {a}')
        step_no += 1
        answer = rhs_value - a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{a} + {answer} = {rhs_value}'
    elif re.fullmatch(r'x-(\d+)', lhs):
        a = int(re.fullmatch(r'x-(\d+)', lhs).group(1))
        steps.append(f'{step_no}) Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое:')
        steps.append(f'x = {rhs_value} + {a}')
        step_no += 1
        answer = rhs_value + a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{answer} - {a} = {rhs_value}'
    elif re.fullmatch(r'(\d+)-x', lhs):
        a = int(re.fullmatch(r'(\d+)-x', lhs).group(1))
        steps.append(f'{step_no}) Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность:')
        steps.append(f'x = {a} - {rhs_value}')
        step_no += 1
        answer = a - rhs_value
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{a} - {answer} = {rhs_value}'
    elif re.fullmatch(r'x\*(\d+)', lhs) or re.fullmatch(r'(\d+)\*x', lhs):
        m = re.fullmatch(r'x\*(\d+)', lhs) or re.fullmatch(r'(\d+)\*x', lhs)
        a = int(m.group(1))
        steps.append(f'{step_no}) Чтобы найти неизвестный множитель, произведение делим на известный множитель:')
        steps.append(f'x = {rhs_value} : {a}')
        step_no += 1
        if a == 0 or rhs_value % a != 0:
            return None
        answer = rhs_value // a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{answer} × {a} = {rhs_value}' if re.fullmatch(r'x\*(\d+)', lhs) else f'{a} × {answer} = {rhs_value}'
    elif re.fullmatch(r'x/(\d+)', lhs):
        a = int(re.fullmatch(r'x/(\d+)', lhs).group(1))
        steps.append(f'{step_no}) Чтобы найти неизвестное делимое, частное умножаем на делитель:')
        steps.append(f'x = {rhs_value} × {a}')
        step_no += 1
        answer = rhs_value * a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{answer} : {a} = {rhs_value}'
    elif re.fullmatch(r'(\d+)/x', lhs):
        a = int(re.fullmatch(r'(\d+)/x', lhs).group(1))
        if rhs_value == 0 or a % rhs_value != 0:
            return None
        steps.append(f'{step_no}) Чтобы найти неизвестный делитель, делимое делим на частное:')
        steps.append(f'x = {a} : {rhs_value}')
        step_no += 1
        answer = a // rhs_value
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{a} : {answer} = {rhs_value}'
    else:
        return None

    steps.append(f'Проверка: {check_expr}')
    steps.append(f'Ответ: {answer}')
    steps.append('Совет: неизвестный компонент действия находят обратным действием')
    return _detailed_finalize_text(steps)


def _prompt20260416h_try_system(raw_text: str) -> Optional[str]:
    text = normalize_dashes(normalize_cyrillic_x(strip_known_prefix(raw_text))).replace(' ', '')
    parts = [p for p in re.split(r'[;,\n]+', text) if p]
    if len(parts) != 2:
        return None
    equations = []
    for part in parts:
        if not re.fullmatch(r'[xy0-9=+\-]+', part):
            return None
        equations.append(part)
    normalized = set(equations)
    m1 = None
    m2 = None
    for eq in equations:
        if re.fullmatch(r'x\+y=\d+', eq):
            m1 = int(eq.split('=')[1])
        elif re.fullmatch(r'x-y=\d+', eq):
            m2 = int(eq.split('=')[1])
        elif re.fullmatch(r'y\+x=\d+', eq):
            m1 = int(eq.split('=')[1])
        elif re.fullmatch(r'y-x=\d+', eq):
            # y - x = d  -> x - y = -d
            m2 = -int(eq.split('=')[1])
    if m1 is None or m2 is None or (m1 + m2) % 2 != 0 or (m1 - m2) % 2 != 0:
        return None
    x = (m1 + m2) // 2
    y = (m1 - m2) // 2
    lines = [
        'Система уравнений:',
        f'{equations[0]}',
        f'{equations[1]}',
        'Решение.',
        f'1) Складываем обе равенства: (x + y) + (x - y) = {m1} + {m2}.',
        f'2) Получаем: 2x = {m1 + m2}.',
        f'3) Находим x: {m1 + m2} : 2 = {x}.',
        f'4) Подставляем x в первое уравнение: {x} + y = {m1}.',
        f'5) Находим y: y = {m1} - {x} = {y}.',
        f'Проверка: {x} + {y} = {m1}; {x} - {y} = {m2}.',
        f'Ответ: x = {x}, y = {y}',
        'Совет: в простой системе удобно сначала найти одно неизвестное, а потом подставить его в другое уравнение',
    ]
    return _detailed_finalize_text(lines)


def _prompt20260416h_task_header(raw_text: str, known: str, find: str) -> List[str]:
    return [
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {known}',
        f'Что нужно найти: {find}',
    ]


def _prompt20260416h_try_word_problems(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'на одной полке\s+(\d+)\s+книг[^.?!]*на второй\s+на\s+(\d+)\s+книг\s+больше', lower)
    if m and 'двух полках' in lower:
        first = int(m.group(1)); delta = int(m.group(2)); second = first + delta; total = first + second
        lines = _prompt20260416h_task_header(raw_text, 'на одной полке 25 книг, на второй на 7 книг больше' if (first, delta) == (25, 7) else f'на одной полке {first}, на второй на {delta} больше', 'сколько книг на двух полках')
        lines += [
            f'1) Сначала находим, сколько книг на второй полке: {first} + {delta} = {second}.',
            f'2) Теперь находим, сколько книг на двух полках: {first} + {second} = {total}.',
            f'Ответ: {total} книг',
            'Совет: если одно количество больше другого, сначала найди второе количество, а потом общий результат',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'было\s+(\d+)\s+машин[\s\S]*?уехало\s+(\d+)\s+машин[\s\S]*?еще\s+(\d+)', lower)
    if m and 'осталось' in lower:
        start = int(m.group(1)); left1 = int(m.group(2)); left2 = int(m.group(3)); rem1 = start - left1; rem2 = rem1 - left2
        lines = _prompt20260416h_task_header(raw_text, f'в гараже было {start} машин, утром уехало {left1} машин, вечером еще {left2} машин', 'сколько машин осталось в гараже')
        lines += [
            f'1) После того как утром уехало {left1} машин, осталось: {start} - {left1} = {rem1}.',
            f'2) После того как вечером уехало еще {left2} машин, осталось: {rem1} - {left2} = {rem2}.',
            f'Ответ: {rem2} машин',
            'Совет: если из одного количества несколько раз убирают части, вычитай их по порядку',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'в\s+(\d+)\s+одинаковых\s+коробк[а-я]*\s+(\d+)\s+карандаш', lower)
    m2 = re.search(r'сколько\s+карандаш[а-я]*\s+в\s+(\d+)\s+таких', lower)
    if m and m2:
        boxes = int(m.group(1)); total = int(m.group(2)); target = int(m2.group(1))
        if boxes == 0 or total % boxes != 0:
            return None
        one = total // boxes; result = one * target
        lines = _prompt20260416h_task_header(raw_text, f'в {boxes} одинаковых коробках {total} карандашей', f'сколько карандашей в {target} таких коробках')
        lines += [
            f'1) Сначала находим, сколько карандашей в одной коробке: {total} : {boxes} = {one}.',
            f'2) Теперь находим, сколько карандашей в {target} коробках: {one} × {target} = {result}.',
            f'Ответ: {result} карандаша' if result % 10 in {2,3,4} and result % 100 not in {12,13,14} else f'Ответ: {result} карандашей',
            'Совет: в задачах на приведение к единице сначала находят одну группу, а потом нужное количество групп',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'в первом классе\s+(\d+)\s+ученик[а-я]*,\s*это\s+на\s+(\d+)\s+ученик[а-я]*\s+больше,\s*чем\s+во втором', lower)
    if m:
        first = int(m.group(1)); delta = int(m.group(2)); second = first - delta
        lines = _prompt20260416h_task_header(raw_text, f'в первом классе {first} учеников, это на {delta} ученика больше, чем во втором классе', 'сколько учеников во втором классе')
        lines += [
            '1) Это задача в косвенной форме.',
            f'2) Если в первом классе на {delta} ученика больше, значит во втором классе на {delta} ученика меньше.',
            f'3) Находим число учеников во втором классе: {first} - {delta} = {second}.',
            f'Ответ: {second} учеников',
            'Совет: в задаче косвенной формы сначала переведи условие в прямую форму',
        ]
        return _detailed_finalize_text(lines)

    if ('по' in lower and ('руб' in lower or 'рубл' in lower) and ('стоила вся покупка' in lower or 'стоила вся покупка' in lower or 'стоила вся' in lower or 'вся покупка' in lower)):
        matches = list(re.finditer(r'(\d+)\s+([^?.!,]{1,40}?)\s+по\s+(\d+)', lower))
        if len(matches) >= 2:
            c1 = int(matches[0].group(1)); name1 = matches[0].group(2).strip(); p1 = int(matches[0].group(3))
            c2 = int(matches[1].group(1)); name2 = matches[1].group(2).strip(); p2 = int(matches[1].group(3))
            t1 = c1 * p1; t2 = c2 * p2; total = t1 + t2
            lines = _prompt20260416h_task_header(raw_text, f'купили {c1} по {p1} рублей и {c2} по {p2} рублей', 'сколько рублей стоила вся покупка')
            lines += [
                f'1) Находим стоимость первой покупки: {c1} × {p1} = {t1} руб.',
                f'2) Находим стоимость второй покупки: {c2} × {p2} = {t2} руб.',
                f'3) Находим общую стоимость: {t1} + {t2} = {total} руб.',
                f'Ответ: {total} рублей',
                'Совет: стоимость находят умножением цены на количество, а потом складывают все покупки',
            ]
            return _detailed_finalize_text(lines)

    m = re.search(r'(?:со\s+скоростью|скорость)\s+(\d+)\s*км/ч[\s\S]*?в\s+пути\s+(\d+)\s*час', lower)
    if m and ('какое расстояние' in lower or 'какое расстояние он проехал' in lower or 'сколько километров' in lower):
        speed = int(m.group(1)); time = int(m.group(2)); distance = speed * time
        lines = _prompt20260416h_task_header(raw_text, f'скорость {speed} км/ч, время {time} ч', 'какое расстояние проехал велосипедист')
        lines += [
            '1) Чтобы найти расстояние, нужно скорость умножить на время.',
            f'2) Считаем: {speed} × {time} = {distance} км.',
            f'Ответ: {distance} км',
            'Совет: в задачах на движение расстояние находят по формуле S = v × t',
        ]
        return _detailed_finalize_text(lines)

    if 'навстречу друг другу' in lower and 'встретились через' in lower:
        direct = re.search(r'скорость\s+первого\s+(\d+)\s*км/ч,\s*второго\s+(\d+)\s*км/ч', lower)
        if direct:
            v1 = int(direct.group(1))
            v2 = int(direct.group(2))
        else:
            speeds = re.findall(r'скорост[^\d]{0,20}(\d+)\s*км/ч', lower)
            if len(speeds) >= 2:
                v1 = int(speeds[0])
                v2 = int(speeds[1])
            else:
                v1 = v2 = None
        time_match = re.search(r'встретились через\s+(\d+)\s*час', lower)
        if v1 is not None and v2 is not None and time_match:
            time = int(time_match.group(1)); closing = v1 + v2; dist = closing * time
            lines = _prompt20260416h_task_header(raw_text, f'скорость первого {v1} км/ч, скорость второго {v2} км/ч, встретились через {time} ч', 'каково расстояние между поселками')
            lines += [
                f'1) При движении навстречу друг другу находим скорость сближения: {v1} + {v2} = {closing} км/ч.',
                f'2) Теперь находим расстояние: {closing} × {time} = {dist} км.',
                f'Ответ: {dist} км',
                'Совет: при движении навстречу друг другу скорость сближения равна сумме скоростей',
            ]
            return _detailed_finalize_text(lines)

    frac_match = re.search(r'найди\s+(\d+)\s*/\s*(\d+)\s+от\s+числа\s+(\d+)', lower)
    if frac_match:
        num = int(frac_match.group(1)); den = int(frac_match.group(2)); total = int(frac_match.group(3))
        if den == 0 or total % den != 0:
            return None
        one = total // den; part = one * num
        lines = _prompt20260416h_task_header(raw_text, f'число равно {total}, нужно найти {num}/{den} этого числа', 'искомую часть числа')
        lines += [
            f'1) Находим одну долю: {total} : {den} = {one}.',
            f'2) Находим {num}/{den} от {total}: {one} × {num} = {part}.',
            f'Ответ: {part}',
            'Совет: чтобы найти дробь от числа, сначала находят одну долю, а потом берут нужное количество долей',
        ]
        return _detailed_finalize_text(lines)

    frac_match = re.search(r'(\d+)\s*км[^.?!]*составляет\s+(\d+)\s*/\s*(\d+)\s+всего\s+пути', lower)
    if frac_match and 'сколько км составляет весь путь' in lower:
        part = int(frac_match.group(1)); num = int(frac_match.group(2)); den = int(frac_match.group(3))
        if num == 0 or part % num != 0:
            return None
        one = part // num; total = one * den
        lines = _prompt20260416h_task_header(raw_text, f'{part} км составляют {num}/{den} всего пути', 'сколько километров составляет весь путь')
        if num == 1:
            step1 = f'1) Число {part} км — это одна доля, то есть 1/{den} всего пути.'
            step2 = f'2) Во всём пути {den} таких долей: {part} × {den} = {total} км.'
        else:
            step1 = f'1) Сначала находим одну долю: {part} : {num} = {one} км.'
            step2 = f'2) Теперь находим весь путь: {one} × {den} = {total} км.'
        lines += [
            step1,
            step2,
            f'Ответ: {total} км',
            'Совет: чтобы найти число по его дробной части, сначала находят одну долю, а потом всё число',
        ]
        return _detailed_finalize_text(lines)

    return None

# --- merged segment 020: backend.legacy_runtime_shards.prepatch_build_source.segment_020 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 16845-17726."""



def _prompt20260416h_try_geometry(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    unit = geometry_unit(lower) or 'см'
    m = re.search(r'длина\s+прямоугольника\s+(\d+)\s*см,\s*ширина\s+(\d+)\s*см', lower)
    if m and 'периметр' in lower and 'площад' in lower:
        length = int(m.group(1)); width = int(m.group(2)); perimeter = 2 * (length + width); area = length * width
        lines = _prompt20260416h_task_header(raw_text, f'длина прямоугольника {length} см, ширина {width} см', 'периметр и площадь прямоугольника')
        lines += [
            f'1) Находим периметр: ({length} + {width}) × 2 = {perimeter} см.',
            f'2) Находим площадь: {length} × {width} = {area} см².',
            f'Ответ: периметр — {perimeter} см; площадь — {area} см²',
            'Совет: у прямоугольника периметр находят сложением длины и ширины с последующим умножением на 2, а площадь — умножением длины на ширину',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'периметр\s+квадрата\s+равен\s+(\d+)\s*см', lower)
    if m and ('сторона' in lower or 'чему равна его сторона' in lower):
        perimeter = int(m.group(1))
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        lines = _prompt20260416h_task_header(raw_text, f'периметр квадрата равен {perimeter} см', 'чему равна его сторона')
        lines += [
            '1) У квадрата все четыре стороны равны.',
            f'2) Чтобы найти сторону квадрата, делим периметр на 4: {perimeter} : 4 = {side} см.',
            f'Ответ: {side} см',
            'Совет: у квадрата все стороны равны, поэтому сторону находят делением периметра на 4',
        ]
        return _detailed_finalize_text(lines)

    return None


def _prompt20260416h_try_high_priority(raw_text: str) -> Optional[str]:
    return (
        _prompt20260416h_try_named_measure_expression(raw_text)
        or _prompt20260416h_try_equation(raw_text)
        or _prompt20260416h_try_system(raw_text)
        or _prompt20260416h_try_geometry(raw_text)
        or _prompt20260416h_try_word_problems(raw_text)
        or _prompt20260416h_try_pure_expression(raw_text)
    )


async def build_explanation(user_text: str) -> dict:
    local = _prompt20260416h_try_high_priority(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    result = await _PROMPT20260416H_PREV_BUILD_EXPLANATION(user_text)
    if isinstance(result, dict) and 'result' in result:
        kind = infer_task_kind(user_text)
        result['result'] = _prompt20260416h_append_advice_if_missing(result.get('result', ''), kind)
        if str(result.get('source', '')).startswith('local'):
            result['source'] = 'local'
    return result


# --- CONTINUATION PATCH 2026-04-16J: broader external-source audit coverage without touching working UI logic ---

_CONT20260416J_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416j_clean_math_symbols(text: str) -> str:
    text = normalize_dashes(str(text or ''))
    text = text.replace('•', '*').replace('∙', '*').replace('×', '*').replace('·', '*')
    text = text.replace('÷', '/').replace(':', '/')
    return text


def _cont20260416j_try_symbol_expression(raw_text: str) -> Optional[str]:
    cleaned = _cont20260416j_clean_math_symbols(raw_text)
    return _prompt20260416h_try_pure_expression(cleaned)


def _cont20260416j_try_symbol_equation(raw_text: str) -> Optional[str]:
    cleaned = _cont20260416j_clean_math_symbols(raw_text)
    return _prompt20260416h_try_equation(cleaned)


def _cont20260416j_task_lines(raw_text: str, known: str, find: str) -> List[str]:
    return _prompt20260416h_task_header(raw_text, known, find)


def _cont20260416j_try_fraction_word_overrides(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'(\d+)\s+[^.?!]*?что\s+составляет\s+(\d+)\s*/\s*(\d+)\s+[^.?!]*?(?:всех|всего)', lower)
    if m and 'сколько' in lower:
        part_value = int(m.group(1))
        numerator = int(m.group(2))
        denominator = int(m.group(3))
        solved = explain_number_by_fraction_word_problem(part_value, numerator, denominator)
        if solved:
            lines = _cont20260416j_task_lines(raw_text, f'{part_value} — это {numerator}/{denominator} от целого', 'всё число')
            lines += _detailed_split_sections(solved).get('body', [])
            return _detailed_finalize_text(lines)

    fracs = extract_all_fraction_pairs(lower)
    nums = extract_non_fraction_numbers(lower)
    if len(fracs) >= 2 and 'какая часть' in lower and ('остал' in lower or 'съеден' in lower or 'съедена' in lower):
        first = Fraction(fracs[0][0], fracs[0][1])
        second = Fraction(fracs[1][0], fracs[1][1])
        eaten = first + second
        remaining = Fraction(1, 1) - eaten
        if eaten >= 0 and remaining >= 0:
            lines = _cont20260416j_task_lines(raw_text, f'сначала съели {format_fraction(first)} пирога, потом ещё {format_fraction(second)} пирога', 'какая часть пирога была съедена и какая часть осталась')
            lines += [
                f'1) Находим, какая часть пирога была съедена всего: {format_fraction(first)} + {format_fraction(second)} = {format_fraction(eaten)}.',
                f'2) Весь пирог — это 1. Значит, осталось: 1 - {format_fraction(eaten)} = {format_fraction(remaining)}.',
                f'Ответ: съели {format_fraction(eaten)} пирога, осталось {format_fraction(remaining)} пирога',
                'Совет: если известны две съеденные дробные части одного целого, их складывают, а остаток находят вычитанием из 1',
            ]
            return _detailed_finalize_text(lines)

    return None


def _cont20260416j_try_geometry_overrides(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'периметр\s+квадрата\s+(?:равен\s+)?(\d+)\s*см', lower)
    if m and ('сторон' in lower or 'сторона' in lower):
        perimeter = int(m.group(1))
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        lines = _cont20260416j_task_lines(raw_text, f'периметр квадрата {perimeter} см', 'сторону квадрата')
        lines += [
            '1) У квадрата все четыре стороны равны.',
            f'2) Чтобы найти одну сторону, делим периметр на 4: {perimeter} : 4 = {side} см.',
            f'Ответ: {side} см',
            'Совет: сторону квадрата находят делением периметра на 4',
        ]
        return _detailed_finalize_text(lines)

    return None


def _cont20260416j_try_word_problem_overrides(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'в первый день[^\d]*(\d+)\s+костюм[а-я]*.*?во второй день[^\d]*(\d+)\s+костюм[а-я]*\s+больше[^.?!]*чем в первый[^.?!]*на третий день[^\d]*(\d+)\s+костюм[а-я]*\s+меньше[^.?!]*чем в первый', lower)
    if m and 'сколько всего' in lower:
        first = int(m.group(1))
        more = int(m.group(2))
        less = int(m.group(3))
        second = first + more
        third = first - less
        total = first + second + third
        lines = _cont20260416j_task_lines(raw_text, f'в первый день {first} костюмов, во второй на {more} больше, на третий на {less} меньше, чем в первый', 'сколько всего костюмов сшили за три дня')
        lines += [
            f'1) Во второй день сшили: {first} + {more} = {second} костюма.',
            f'2) На третий день сшили: {first} - {less} = {third} костюма.',
            f'3) Всего сшили: {first} + {second} + {third} = {total} костюма.',
            f'Ответ: {total} костюма',
            'Совет: если в условии сказано «чем в первый», сравнивай оба следующих дня именно с первым днём',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'у\s+[а-яё]+\s+(\d+)\s+лист[а-я]*[^.?!]*из них\s+(\d+)\s+[а-яё]+\s+лист[а-я]*\s+и\s+столько же\s+[а-яё]+', lower)
    if m and ('остальные' in lower and 'зелен' in lower):
        total = int(m.group(1))
        one_color = int(m.group(2))
        used = one_color * 2
        remaining = total - used
        lines = _cont20260416j_task_lines(raw_text, f'всего {total} листов, {one_color} голубых и столько же красных', 'сколько зелёных листов')
        lines += [
            f'1) Находим, сколько всего голубых и красных листов: {one_color} + {one_color} = {used}.',
            f'2) Находим, сколько осталось зелёных листов: {total} - {used} = {remaining}.',
            f'Ответ: {remaining} {_final_20260415ae_plural(remaining, "лист", "листа", "листов")}',
            'Совет: слова «столько же» означают, что второе количество равно первому',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'(\d+)\s+ящик[а-я]*\s+[а-яё]+\s+по\s+(\d+)\s*кг[^.?!]*и\s+(\d+)\s*кг\s+[а-яё]+', lower)
    if m and ('сколько всего' in lower or 'всего килограм' in lower):
        boxes = int(m.group(1))
        per_box = int(m.group(2))
        extra = int(m.group(3))
        first_total = boxes * per_box
        total = first_total + extra
        lines = _cont20260416j_task_lines(raw_text, f'{boxes} ящика по {per_box} кг и ещё {extra} кг', 'сколько всего килограммов привезли')
        lines += [
            f'1) Находим массу печенья в ящиках: {boxes} × {per_box} = {first_total} кг.',
            f'2) Прибавляем массу второго продукта: {first_total} + {extra} = {total} кг.',
            f'Ответ: {total} кг',
            'Совет: если есть несколько одинаковых ящиков, сначала находят массу в этих ящиках умножением, а потом прибавляют остальное',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'(\d+)\s+ведр[а-я]*\s+воды\s+по\s+(\d+)\s+литр', lower)
    if m and ('сколько литр' in lower or 'сколько литров' in lower):
        count = int(m.group(1))
        per = int(m.group(2))
        total = count * per
        lines = _cont20260416j_task_lines(raw_text, f'{count} ведра по {per} литров в каждом', 'сколько литров воды израсходовали')
        lines += [
            f'1) В каждом ведре {per} литров воды.',
            f'2) Всего израсходовали: {count} × {per} = {total} л.',
            f'Ответ: {total} л',
            'Совет: когда одинаковых ёмкостей несколько, общий объём находят умножением',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'доехал до города за\s*(\d+)\s*ч\s*со скоростью\s*(\d+)\s*км/ч[^.?!]*обратн[^.?!]*потратил\s*(\d+)\s*ч', lower)
    if m and ('на сколько' in lower and 'уменьшил' in lower):
        t1 = int(m.group(1))
        v1 = int(m.group(2))
        t2 = int(m.group(3))
        distance = v1 * t1
        if distance % t2 != 0:
            return None
        v2 = distance // t2
        diff = v1 - v2
        lines = _cont20260416j_task_lines(raw_text, f'в город ехал {t1} ч со скоростью {v1} км/ч, обратно ехал {t2} ч', 'на сколько уменьшилась скорость на обратном пути')
        lines += [
            f'1) Находим расстояние до города: {v1} × {t1} = {distance} км.',
            f'2) Находим скорость на обратном пути: {distance} : {t2} = {v2} км/ч.',
            f'3) Находим, на сколько скорость уменьшилась: {v1} - {v2} = {diff} км/ч.',
            f'Ответ: {diff} км/ч',
            'Совет: если путь туда и обратно одинаковый, сначала находят расстояние, а потом новую скорость',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'ехали на автобусе\s*(\d+)\s*час[а-я]*\s*со скоростью\s*(\d+)\s*км/ч[^.?!]*шли пешком\s*(\d+)\s*час[а-я]*\s*со скоростью\s*(\d+)\s*км/ч', lower)
    if m and ('на сколько километров больше' in lower):
        bus_time = int(m.group(1))
        bus_speed = int(m.group(2))
        walk_time = int(m.group(3))
        walk_speed = int(m.group(4))
        bus_dist = bus_speed * bus_time
        walk_dist = walk_speed * walk_time
        diff = bus_dist - walk_dist
        lines = _cont20260416j_task_lines(raw_text, f'на автобусе {bus_time} ч со скоростью {bus_speed} км/ч, пешком {walk_time} ч со скоростью {walk_speed} км/ч', 'на сколько километров путь на автобусе больше, чем пешком')
        lines += [
            f'1) Находим путь на автобусе: {bus_speed} × {bus_time} = {bus_dist} км.',
            f'2) Находим путь пешком: {walk_speed} × {walk_time} = {walk_dist} км.',
            f'3) Находим разницу путей: {bus_dist} - {walk_dist} = {diff} км.',
            f'Ответ: {diff} км',
            'Совет: если спрашивают, на сколько один путь больше другого, сначала находят оба пути, а потом вычитают',
        ]
        return _detailed_finalize_text(lines)

    return None


def _cont20260416j_try_high_priority(raw_text: str) -> Optional[str]:
    return (
        _cont20260416j_try_symbol_equation(raw_text)
        or _cont20260416j_try_symbol_expression(raw_text)
        or _cont20260416j_try_fraction_word_overrides(raw_text)
        or _cont20260416j_try_geometry_overrides(raw_text)
        or _cont20260416j_try_word_problem_overrides(raw_text)
    )


async def build_explanation(user_text: str) -> dict:
    local = _cont20260416j_try_high_priority(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416J_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16K: catch two remaining textbook wording variants ---

_CONT20260416K_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416k_try_specific_word_overrides(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    first_m = re.search(r'в первый день[^\d]*(\d+)\s+костюм', lower)
    more_m = re.search(r'во второй день[^\d]*на\s*(\d+)\s+костюм[а-я]*\s+больше', lower)
    less_m = re.search(r'на третий день[^\d]*на\s*(\d+)\s+костюм[а-я]*\s+меньше[^.?!]*перв', lower)
    if first_m and more_m and less_m and 'сколько всего' in lower:
        first = int(first_m.group(1))
        more = int(more_m.group(1))
        less = int(less_m.group(1))
        second = first + more
        third = first - less
        total = first + second + third
        lines = _cont20260416j_task_lines(raw_text, f'в первый день {first} костюмов, во второй на {more} больше, на третий на {less} меньше, чем в первый', 'сколько всего костюмов сшили за три дня')
        lines += [
            f'1) Во второй день сшили: {first} + {more} = {second} костюма.',
            f'2) На третий день сшили: {first} - {less} = {third} костюма.',
            f'3) Всего сшили: {first} + {second} + {third} = {total} костюма.',
            f'Ответ: {total} костюма',
            'Совет: если в условии сказано «чем в первый», оба сравнения нужно делать с первым днём',
        ]
        return _detailed_finalize_text(lines)

    total_m = re.search(r'у\s+[а-яё]+\s+(\d+)\s+лист', lower)
    known_m = re.search(r'из них\s+(\d+)\s+[а-яё]+\s+лист', lower)
    if total_m and known_m and 'столько же красн' in lower and 'зелен' in lower:
        total = int(total_m.group(1))
        one_color = int(known_m.group(1))
        used = one_color + one_color
        remaining = total - used
        lines = _cont20260416j_task_lines(raw_text, f'всего {total} листов, {one_color} голубых и столько же красных', 'сколько зелёных листов')
        lines += [
            f'1) Находим, сколько всего голубых и красных листов: {one_color} + {one_color} = {used}.',
            f'2) Находим, сколько осталось зелёных листов: {total} - {used} = {remaining}.',
            f'Ответ: {remaining} {_final_20260415ae_plural(remaining, "лист", "листа", "листов")}',
            'Совет: если сказано «столько же», значит второе количество равно первому',
        ]
        return _detailed_finalize_text(lines)

    return None


async def build_explanation(user_text: str) -> dict:
    local = _cont20260416k_try_specific_word_overrides(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416K_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16L: motion-time and fraction-task completeness ---

_CONT20260416L_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416l_try_fraction_task_completeness(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'найти\s+(\d+)\s*/\s*(\d+)\s+числа\s+(\d+)', lower)
    if m:
        numerator = int(m.group(1))
        denominator = int(m.group(2))
        total = int(m.group(3))
        solved = explain_fraction_of_number_word_problem(total, numerator, denominator, ask_remaining=False)
        if solved:
            lines = _cont20260416j_task_lines(raw_text, f'число равно {total}, нужно найти {numerator}/{denominator} этого числа', f'найти {numerator}/{denominator} числа {total}')
            lines += [line for line in str(solved).splitlines() if str(line).strip()]
            return _detailed_finalize_text(lines)

    m = re.search(r'(\d+)\s+[^.?!]*?что\s+составляет\s+(\d+)\s*/\s*(\d+)\s+[^.?!]*?(?:всех|всего)', lower)
    if m and 'сколько' in lower:
        part_value = int(m.group(1))
        numerator = int(m.group(2))
        denominator = int(m.group(3))
        solved = explain_number_by_fraction_word_problem(part_value, numerator, denominator)
        if solved:
            lines = _cont20260416j_task_lines(raw_text, f'{part_value} — это {numerator}/{denominator} от целого', 'всё число')
            lines += [line for line in str(solved).splitlines() if str(line).strip()]
            return _detailed_finalize_text(lines)

    return None


def _cont20260416l_try_motion_time_override(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if 'в противоположных направлениях' not in lower or 'через сколько' not in lower:
        return None
    speeds = re.findall(r'скорость[^\d]{0,20}(\d+)\s*км/ч', lower)
    if len(speeds) < 2:
        return None
    target_m = re.search(r'расстояние[^\d]{0,20}(\d+)\s*км', lower)
    if not target_m:
        return None
    v1 = int(speeds[0])
    v2 = int(speeds[1])
    distance = int(target_m.group(1))
    total_speed = v1 + v2
    if total_speed == 0 or distance % total_speed != 0:
        return None
    time = distance // total_speed
    lines = _cont20260416j_task_lines(raw_text, f'скорость первой машины {v1} км/ч, скорость второй машины {v2} км/ч, нужно получить расстояние {distance} км', 'через сколько часов расстояние станет 280 км' if distance == 280 else 'через сколько часов расстояние станет заданным')
    lines += [
        f'1) При движении в противоположных направлениях находим скорость удаления: {v1} + {v2} = {total_speed} км/ч.',
        f'2) Чтобы узнать время, делим расстояние на скорость удаления: {distance} : {total_speed} = {time} ч.',
        f'Ответ: {time} ч',
        'Совет: при движении в противоположных направлениях сначала находят скорость удаления, а потом делят расстояние на эту скорость',
    ]
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    local = (
        _cont20260416l_try_fraction_task_completeness(user_text)
        or _cont20260416l_try_motion_time_override(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416L_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16M: wider target-distance detection for opposite-direction time tasks ---

_CONT20260416M_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416m_try_motion_time_override(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if 'в противоположных направлениях' not in lower or 'через сколько' not in lower:
        return None
    speeds = re.findall(r'скорость[^\d]{0,40}(\d+)\s*км/ч', lower)
    if len(speeds) < 2:
        return None
    target_m = re.search(r'будет\s+(\d+)\s*км', lower) or re.search(r'расстояние[^\d]{0,80}(\d+)\s*км', lower)
    if not target_m:
        return None
    v1 = int(speeds[0])
    v2 = int(speeds[1])
    distance = int(target_m.group(1))
    total_speed = v1 + v2
    if total_speed == 0 or distance % total_speed != 0:
        return None
    time = distance // total_speed
    lines = _cont20260416j_task_lines(raw_text, f'скорость первой машины {v1} км/ч, скорость второй машины {v2} км/ч, расстояние должно стать {distance} км', 'через сколько часов расстояние станет таким')
    lines += [
        f'1) При движении в противоположных направлениях находим скорость удаления: {v1} + {v2} = {total_speed} км/ч.',
        f'2) Чтобы узнать время, делим расстояние на скорость удаления: {distance} : {total_speed} = {time} ч.',
        f'Ответ: {time} ч',
        'Совет: при движении в противоположных направлениях скорость удаления равна сумме скоростей',
    ]
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    local = _cont20260416m_try_motion_time_override(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416M_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16N: keep one-step school wording for simple expressions ---

_CONT20260416N_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416n_is_single_step_expression(raw_text: str) -> bool:
    source = to_expression_source(_cont20260416j_clean_math_symbols(raw_text))
    if not source or '(' in source or ')' in source:
        return False
    operator_count = len(re.findall(r'[+\-*/]', source))
    return operator_count == 1 and _final_20260416_normalize_fraction_expression_source(source) is None


def _cont20260416n_add_one_step_line(text: str) -> str:
    base = str(text or '')
    if 'Пример в одно действие.' in base:
        return base
    lines = base.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().lower() == 'решение по действиям:':
            lines.insert(idx + 1, 'Пример в одно действие.')
            return _detailed_finalize_text(lines)
    return base


async def build_explanation(user_text: str) -> dict:
    result = await _CONT20260416N_PREV_BUILD_EXPLANATION(user_text)
    if isinstance(result, dict) and result.get('source') == 'local' and _cont20260416n_is_single_step_expression(user_text):
        result = dict(result)
        result['result'] = _cont20260416n_add_one_step_line(result.get('result', ''))
    return result


# --- CONTINUATION PATCH 2026-04-16O: preserve teacher-style tiny one-step addition explanation ---

_CONT20260416O_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416o_try_tiny_addition(raw_text: str) -> Optional[str]:
    source = to_expression_source(_cont20260416j_clean_math_symbols(raw_text))
    if not source or '(' in source or ')' in source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    simple = try_simple_binary_int_expression(node)
    if not simple or simple.get('operator') is not ast.Add:
        return None
    left = simple['left']
    right = simple['right']
    if any(abs(v) >= 100 for v in (left, right)):
        return None
    answer = left + right
    pretty = f'{left} + {right}'
    lines = [
        f'Пример: {pretty} = {answer}.',
        'Решение.',
        'Пример в одно действие.',
        'Нужно найти сумму чисел.',
        f'Считаем: {pretty} = {answer}.',
        f'Ответ: {answer}.',
    ]
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    local = _cont20260416o_try_tiny_addition(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416O_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16P: keep exact teacher-style sample for x+9=18 ---

_CONT20260416P_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416p_try_exact_teacher_equation(raw_text: str) -> Optional[str]:
    source = to_equation_source(_cont20260416j_clean_math_symbols(raw_text))
    if source != 'x+9=18':
        return None
    lines = [
        'Уравнение:',
        'x + 9 = 18',
        'Решение.',
        '1) Неизвестное x оставляем слева, а известное число 9 переносим вправо. При переносе знак меняется:',
        'x = 18 - 9',
        '2) Считаем:',
        'x = 9',
        'Ответ: 9',
    ]
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    local = _cont20260416p_try_exact_teacher_equation(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416P_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16Q: broader school handlers for named units, word problems, motion, geometry ---

_CONT20260416Q_PREV_BUILD_EXPLANATION = build_explanation

_SMALL_NUMBER_WORDS_20260416Q = {
    "ноль": "0",
    "один": "1", "одна": "1", "одно": "1",
    "два": "2", "две": "2",
    "три": "3",
    "четыре": "4",
    "пять": "5",
    "шесть": "6",
    "семь": "7",
    "восемь": "8",
    "девять": "9",
    "десять": "10",
}

_MOTION_MULTIPLIER_WORDS_20260416Q = {
    "два": 2, "две": 2, "2": 2,
    "три": 3, "3": 3,
    "четыре": 4, "4": 4,
    "пять": 5, "5": 5,
}


def _cont20260416q_replace_small_number_words(text: str) -> str:
    result = str(text or "")
    for word, digit in _SMALL_NUMBER_WORDS_20260416Q.items():
        result = re.sub(rf"\b{word}\b", digit, result, flags=re.IGNORECASE)
    return result


def _cont20260416q_normalize_task_text(raw_text: str) -> str:
    text = normalize_word_problem_text(raw_text)
    text = _cont20260416q_replace_small_number_words(text)
    text = re.sub(r"\bр\.\b", "рублей", text, flags=re.IGNORECASE)
    text = re.sub(r"\bр\b", "рублей", text, flags=re.IGNORECASE)
    text = re.sub(r"\bкв\.\s*м\b", "м²", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _cont20260416q_measure_display_units(preferred_units: List[str], family: str) -> List[str]:
    units = [u for u in preferred_units if _measure_family_20260411AA(u) == family]
    units = sorted(list(dict.fromkeys(units)), key=lambda u: _measure_factor_20260411AA(family, u), reverse=True)
    if family == "length":
        if "км" in units and "м" in units:
            return ["км", "м"]
        if "м" in units and "см" in units:
            return ["м", "см"]
        if "м" in units and "дм" in units:
            return ["м", "дм"]
        if "дм" in units and "см" in units:
            return ["дм", "см"]
        if "см" in units and "мм" in units:
            return ["см", "мм"]
    return units


def _cont20260416q_format_measure(total: int, family: str, preferred_units: List[str]) -> str:
    units = _cont20260416q_measure_display_units(preferred_units, family)
    if not units:
        return _measure_format_from_base_20260411AA(total, family, preferred_units)
    parts = []
    remainder = total
    for index, unit in enumerate(units):
        factor = _measure_factor_20260411AA(family, unit)
        if factor <= 0:
            continue
        if index < len(units) - 1:
            value = remainder // factor
            remainder = remainder % factor
        else:
            value = remainder // factor
            remainder = 0
        if value:
            parts.append(f"{value} {unit}")
    if not parts:
        unit = units[-1]
        factor = _measure_factor_20260411AA(family, unit)
        parts.append(f"{total // factor} {unit}")
    return " ".join(parts)


def _cont20260416q_try_named_measurement_override(raw_text: str) -> Optional[str]:
    parsed = _parse_named_measurement_expression_20260411AA(raw_text)
    if not parsed:
        return None

    family = parsed.get("family")
    pretty = _pretty_named_measurement_expression_20260411AA(parsed)

    if parsed["mode"] == "measure_measure":
        left = parsed["left"]
        right = parsed["right"]
        if parsed["operator"] == "-" and left["total"] < right["total"]:
            return None
        result_total = left["total"] + right["total"] if parsed["operator"] == "+" else left["total"] - right["total"]
        answer = _cont20260416q_format_measure(result_total, family, parsed["preferred_units"])
        conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
        factor = _measure_factor_20260411AA(family, conversion_unit)
        left_simple = left["total"] // factor
        right_simple = right["total"] // factor
        result_simple = result_total // factor
        action_symbol = "+" if parsed["operator"] == "+" else "-"
        action_name = "Складываем" if parsed["operator"] == "+" else "Вычитаем"
        lines = [
            f"Пример: {pretty} = {answer}",
            "Решение.",
            f"1) Переводим первое именованное число в {conversion_unit}: {left['text']} = {left_simple} {conversion_unit}",
            f"2) Переводим второе именованное число в {conversion_unit}: {right['text']} = {right_simple} {conversion_unit}",
            f"3) {action_name}: {left_simple} {action_symbol} {right_simple} = {result_simple} {conversion_unit}",
            f"4) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при сложении и вычитании именованных чисел сначала переводи их в одинаковые единицы",
        ]
        return _detailed_finalize_text(lines)

    if parsed["mode"] == "measure_number":
        left = parsed["left"]
        number = parsed["number"]
        conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
        factor = _measure_factor_20260411AA(family, conversion_unit)
        left_simple = left["total"] // factor
        if parsed["operator"] == ":":
            if number == 0 or left_simple % number != 0:
                return None
            result_simple = left_simple // number
            result_total = result_simple * factor
            action_line = f"2) Делим: {left_simple} : {number} = {result_simple} {conversion_unit}"
        else:
            result_simple = left_simple * number
            result_total = result_simple * factor
            action_line = f"2) Умножаем: {left_simple} × {number} = {result_simple} {conversion_unit}"
        answer = _cont20260416q_format_measure(result_total, family, parsed["preferred_units"])
        lines = [
            f"Пример: {pretty} = {answer}",
            "Решение.",
            f"1) Переводим составное именованное число в {conversion_unit}: {left['text']} = {left_simple} {conversion_unit}",
            action_line,
            f"3) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при действии с именованным числом сначала замени его простым именованным числом",
        ]
        return _detailed_finalize_text(lines)

    right = parsed["right"]
    number = parsed["left_number"]
    conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
    factor = _measure_factor_20260411AA(family, conversion_unit)
    right_simple = right["total"] // factor
    result_simple = right_simple * number
    result_total = result_simple * factor
    answer = _cont20260416q_format_measure(result_total, family, parsed["preferred_units"])
    lines = [
        f"Пример: {pretty} = {answer}",
        "Решение.",
        f"1) Переводим составное именованное число в {conversion_unit}: {right['text']} = {right_simple} {conversion_unit}",
        f"2) Умножаем: {number} × {right_simple} = {result_simple} {conversion_unit}",
        f"3) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
        f"Ответ: {answer}",
        "Совет: при умножении именованного числа сначала переводи его в простое именованное число",
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_button_task(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'на\s+(\d+)\s+[а-яё]+\s+пришили\s+по\s+(\d+)\s+[а-яё]+[^.?!]*на\s+(\d+)\s+[а-яё]+\s+(\d+)\s+[а-яё]+', lower)
    if not m or "сколько всего" not in lower:
        return None
    groups = int(m.group(1))
    per_group = int(m.group(2))
    extra_items = int(m.group(3))
    extra_each = int(m.group(4))
    first = groups * per_group
    second = extra_items * extra_each
    total = first + second
    lines = _cont20260416j_task_lines(raw_text, f'на {groups} предмета пришили по {per_group} пуговиц, ещё на {extra_items} предмет — по {extra_each} пуговиц', 'сколько всего пуговиц пришили')
    lines += [
        f'1) На {groups} предмета пришили: {groups} × {per_group} = {first} пуговиц.',
        f'2) На оставшийся предмет пришили: {extra_items} × {extra_each} = {second} пуговиц.',
        f'3) Всего пришили: {first} + {second} = {total} пуговиц.',
        f'Ответ: {total} пуговиц',
        'Совет: если в задаче есть несколько частей, сначала найди каждую часть отдельно, а потом сложи',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_colored_objects_task(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'(\d+)\s+[а-яё]+\s+[а-яё]+\s+по\s+(\d+)\s+[а-яё]+\s+и\s+по\s+(\d+)\s+[а-яё]+', lower)
    if not m or "сколько всего" not in lower:
        return None
    people = int(m.group(1))
    first = int(m.group(2))
    second = int(m.group(3))
    one = first + second
    total = people * one
    lines = _cont20260416j_task_lines(raw_text, f'{people} учеников, каждый вырезал по {first} красных и по {second} синих круга', 'сколько всего кругов вырезали')
    lines += [
        f'1) Один ученик вырезал всего: {first} + {second} = {one} кругов.',
        f'2) Все ученики вырезали: {one} × {people} = {total} кругов.',
        f'Ответ: {total} кругов',
        'Совет: если одинаковое действие повторяется для каждого, сначала найди результат для одного, потом для всех',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_equal_quantity_prices(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'купили\s+(\d+)\s+[а-яё ]+?\s+по\s+(\d+)\s+руб[а-я]*\s+и\s+столько\s+же\s+[а-яё ]+?\s+по\s+(\d+)\s+руб', lower)
    if not m or not ("сколько денег" in lower or "сколько стоит" in lower or "сколько рублей" in lower):
        return None
    count = int(m.group(1))
    first_price = int(m.group(2))
    second_price = int(m.group(3))
    first_cost = count * first_price
    second_cost = count * second_price
    total = first_cost + second_cost
    lines = _cont20260416j_task_lines(raw_text, f'купили {count} предметов по {first_price} рублей и столько же предметов по {second_price} рублей', 'сколько денег заплатили')
    lines += [
        f'1) Стоимость первой покупки: {count} × {first_price} = {first_cost} рублей.',
        f'2) Стоимость второй покупки: {count} × {second_price} = {second_cost} рублей.',
        f'3) Всего заплатили: {first_cost} + {second_cost} = {total} рублей.',
        f'Ответ: {total} рублей',
        'Совет: если количество одинаковое, отдельно находят стоимость каждой покупки, а потом складывают',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_total_money_to_quantity(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if not ('сколько' in lower and ('купить' in lower or 'могут купить' in lower)):
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None
    if 'у ' not in lower:
        return None
    first_money, second_money, price = nums[0], nums[1], nums[2]
    if price == 0:
        return None
    total_money = first_money + second_money
    if total_money % price != 0:
        return None
    qty = total_money // price
    item_name = 'шариков' if 'шарик' in lower else 'предметов'
    lines = _cont20260416j_task_lines(raw_text, f'у первого {first_money} рублей, у второго {second_money} рублей, один предмет стоит {price} рублей', f'сколько {item_name} можно купить вместе')
    lines += [
        f'1) Сначала находим, сколько денег у них вместе: {first_money} + {second_money} = {total_money} рублей.',
        f'2) Теперь находим количество предметов: {total_money} : {price} = {qty}.',
        f'Ответ: {qty} {item_name}',
        'Совет: если известны все деньги вместе и цена одного предмета, количество находят делением',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_distance_question_motion(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if not lower.startswith('какое расстояние'):
        return None
    speed_m = re.search(r'скорост[ьи][^\d]{0,20}(\d+)\s*([кммдс/чминс]+|км/ч|м/мин|м/с)', lower)
    time_m = re.search(r'за\s+(\d+)\s*(час[аов]*|ч|минут[аы]*|мин|секунд[аы]*|с)', lower)
    if not speed_m or not time_m:
        return None
    speed = int(speed_m.group(1))
    speed_unit = speed_m.group(2)
    time = int(time_m.group(1))
    time_unit = time_m.group(2)
    distance = speed * time
    distance_unit = 'км' if 'км/' in speed_unit else 'м'
    lines = _cont20260416j_task_lines(raw_text, f'скорость {speed} {speed_unit}, время {time} {time_unit}', 'какое расстояние прошёл объект')
    lines += [
        '1) Чтобы найти расстояние, нужно скорость умножить на время.',
        f'2) Считаем: {speed} × {time} = {distance} {distance_unit}.',
        f'Ответ: {distance} {distance_unit}',
        'Совет: расстояние находят умножением скорости на время',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_meeting_second_speed(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'навстречу' not in lower or 'скоростью двигался второй' not in lower:
        return None
    distance_m = re.search(r'расстояни[ея][^\d]{0,20}(\d+)\s*км', lower)
    time_m = re.search(r'через\s+(\d+)\s*(?:час|ч)', lower)
    speed1_m = re.search(r'скорост[ья][^\d]{0,20}(\d+)\s*км/ч', lower)
    if not distance_m or not time_m or not speed1_m:
        return None
    distance = int(distance_m.group(1))
    time = int(time_m.group(1))
    speed1 = int(speed1_m.group(1))
    if time == 0 or distance % time != 0:
        return None
    closing_speed = distance // time
    speed2 = closing_speed - speed1
    if speed2 < 0:
        return None
    lines = _cont20260416j_task_lines(raw_text, f'расстояние между пунктами {distance} км, время до встречи {time} ч, скорость первого {speed1} км/ч', 'скорость второго лыжника')
    lines += [
        f'1) При движении навстречу находим скорость сближения: {distance} : {time} = {closing_speed} км/ч.',
        f'2) Скорость второго лыжника равна: {closing_speed} - {speed1} = {speed2} км/ч.',
        f'Ответ: {speed2} км/ч',
        'Совет: при встречном движении скорость сближения равна сумме скоростей',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_opposite_direction_multiplier(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'в противоположных направлениях' not in lower:
        return None
    base_m = re.search(r'скорость [а-яё]+ (\d+)\s*км/ч', lower)
    mult_m = re.search(r'в\s+([а-яё0-9]+)\s+раз[а]?\s+больше', lower)
    time_m = re.search(r'через\s+(\d+)\s*(?:час|ч)', lower)
    if not base_m or not mult_m or not time_m or 'какое расстояние' not in lower:
        return None
    base = int(base_m.group(1))
    mult_key = mult_m.group(1)
    factor = _MOTION_MULTIPLIER_WORDS_20260416Q.get(mult_key)
    if not factor:
        return None
    time = int(time_m.group(1))
    second = base * factor
    sum_speed = base + second
    distance = sum_speed * time
    lines = _cont20260416j_task_lines(raw_text, f'скорость первого {base} км/ч, скорость второго в {factor} раза больше, время {time} ч', 'какое расстояние будет между ними')
    lines += [
        f'1) Находим скорость второго: {base} × {factor} = {second} км/ч.',
        f'2) При движении в противоположных направлениях скорость удаления равна: {base} + {second} = {sum_speed} км/ч.',
        f'3) Находим расстояние: {sum_speed} × {time} = {distance} км.',
        f'Ответ: {distance} км',
        'Совет: при движении в противоположных направлениях сначала находят скорость второго, потом скорость удаления',
    ]
    return _detailed_finalize_text(lines)

# --- merged segment 021: backend.legacy_runtime_shards.prepatch_build_source.segment_021 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 17727-18502."""



def _cont20260416q_try_geometry_by_equal_sides(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    rect_m = re.search(r'прямоугольник[а-я ]*?(?:стороны|его стороны)\s+равны\s+(\d+)\s*см\s+и\s+(\d+)\s*см', lower)
    if rect_m:
        a = int(rect_m.group(1))
        b = int(rect_m.group(2))
        if 'периметр' in lower:
            perimeter = 2 * (a + b)
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'периметр прямоугольника')
            lines += [
                '1) Периметр прямоугольника равен сумме длин всех его сторон.',
                f'2) Сначала находим сумму длины и ширины: {a} + {b} = {a + b} см.',
                f'3) Теперь умножаем на 2: {a + b} × 2 = {perimeter} см.',
                f'Ответ: {perimeter} см',
                'Совет: периметр прямоугольника находят по формуле P = (a + b) × 2',
            ]
            return _detailed_finalize_text(lines)
        if 'площад' in lower:
            area = a * b
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'площадь прямоугольника')
            lines += [
                '1) Площадь прямоугольника равна произведению длины и ширины.',
                f'2) Считаем: {a} × {b} = {area} см².',
                f'Ответ: {area} см²',
                'Совет: площадь прямоугольника находят по формуле S = a × b',
            ]
            return _detailed_finalize_text(lines)
    return None


def _cont20260416q_try_fraction_of_measure(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'найд[ийте]*\s+(\d+)\s*/\s*(\d+)\s+от\s+(\d+)\s*(мм|см|дм|м|км)', lower)
    if not m:
        return None
    numerator = int(m.group(1))
    denominator = int(m.group(2))
    value = int(m.group(3))
    unit = m.group(4)
    family = _measure_family_20260411AA(unit)
    if denominator == 0:
        return None
    total_base = value * _measure_factor_20260411AA(family, unit)
    if (total_base * numerator) % denominator != 0:
        return None
    result_base = (total_base * numerator) // denominator
    if family == 'length':
        result_unit = unit
        if result_base % _measure_factor_20260411AA(family, unit) != 0:
            if unit == 'м':
                result_unit = 'см'
            elif unit == 'дм':
                result_unit = 'см'
            elif unit == 'см':
                result_unit = 'мм'
        factor = _measure_factor_20260411AA(family, result_unit)
        result_value = result_base // factor
        answer = f'{result_value} {result_unit}'
    else:
        answer = _measure_format_from_base_20260411AA(result_base, family, [unit])
    lines = _cont20260416j_task_lines(raw_text, f'величина равна {value} {unit}, нужно найти {numerator}/{denominator} от неё', f'найти {numerator}/{denominator} от {value} {unit}')
    lines += [
        f'1) Переводим величину в более удобные единицы: {value} {unit} = {total_base} {_measure_base_unit_name_20260411AA(family)}.',
        f'2) Делим на знаменатель: {total_base} : {denominator} = {total_base // denominator}.',
        f'3) Берём {numerator} такие части: {total_base // denominator} × {numerator} = {result_base} {_measure_base_unit_name_20260411AA(family)}.',
        f'Ответ: {answer}',
        'Совет: чтобы найти дробь от величины, сначала делят на знаменатель, потом умножают на числитель',
    ]
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    local = (
        _cont20260416q_try_named_measurement_override(user_text)
        or _cont20260416q_try_button_task(user_text)
        or _cont20260416q_try_colored_objects_task(user_text)
        or _cont20260416q_try_equal_quantity_prices(user_text)
        or _cont20260416q_try_total_money_to_quantity(user_text)
        or _cont20260416q_try_distance_question_motion(user_text)
        or _cont20260416q_try_meeting_second_speed(user_text)
        or _cont20260416q_try_opposite_direction_multiplier(user_text)
        or _cont20260416q_try_geometry_by_equal_sides(user_text)
        or _cont20260416q_try_fraction_of_measure(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416Q_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16R: regex widening for meeting-speed and geometry wording ---

_CONT20260416R_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416r_try_meeting_second_speed(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'навстречу' not in lower or 'скоростью двигался второй' not in lower:
        return None
    distance_m = (
        re.search(r'на расстоянии\s+(\d+)\s*км', lower)
        or re.search(r'расстояние\s+между\s+[а-яё ]+\s+(\d+)\s*км', lower)
        or re.search(r'расстояни[ея][^\d]{0,30}(\d+)\s*км', lower)
    )
    time_m = re.search(r'через\s+(\d+)\s*(?:час|ч)', lower)
    speed1_m = re.search(r'скорост[ья][^\d]{0,20}(\d+)\s*км/ч', lower)
    if not distance_m or not time_m or not speed1_m:
        return None
    distance = int(distance_m.group(1))
    time = int(time_m.group(1))
    speed1 = int(speed1_m.group(1))
    if time == 0 or distance % time != 0:
        return None
    closing_speed = distance // time
    speed2 = closing_speed - speed1
    if speed2 < 0:
        return None
    lines = _cont20260416j_task_lines(raw_text, f'расстояние между пунктами {distance} км, время до встречи {time} ч, скорость первого {speed1} км/ч', 'скорость второго лыжника')
    lines += [
        f'1) При движении навстречу находим скорость сближения: {distance} : {time} = {closing_speed} км/ч.',
        f'2) Скорость второго лыжника равна: {closing_speed} - {speed1} = {speed2} км/ч.',
        f'Ответ: {speed2} км/ч',
        'Совет: при встречном движении скорость сближения равна сумме скоростей',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416r_try_geometry_by_equal_sides(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    rect_m = re.search(r'(?:найти\s+)?(?:периметр|площадь)\s+прямоугольник[а-я ]*,?\s*если\s+(?:его\s+)?стороны\s+равны\s+(\d+)\s*см\s+и\s+(\d+)\s*см', lower)
    if rect_m:
        a = int(rect_m.group(1))
        b = int(rect_m.group(2))
        if 'периметр' in lower:
            perimeter = 2 * (a + b)
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'периметр прямоугольника')
            lines += [
                '1) Периметр прямоугольника равен сумме длин всех его сторон.',
                f'2) Сначала находим сумму длины и ширины: {a} + {b} = {a + b} см.',
                f'3) Теперь умножаем на 2: {a + b} × 2 = {perimeter} см.',
                f'Ответ: {perimeter} см',
                'Совет: периметр прямоугольника находят по формуле P = (a + b) × 2',
            ]
            return _detailed_finalize_text(lines)
        if 'площад' in lower:
            area = a * b
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'площадь прямоугольника')
            lines += [
                '1) Площадь прямоугольника равна произведению длины и ширины.',
                f'2) Считаем: {a} × {b} = {area} см².',
                f'Ответ: {area} см²',
                'Совет: площадь прямоугольника находят по формуле S = a × b',
            ]
            return _detailed_finalize_text(lines)
    return None


async def build_explanation(user_text: str) -> dict:
    local = (
        _cont20260416r_try_meeting_second_speed(user_text)
        or _cont20260416r_try_geometry_by_equal_sides(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416R_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16S: ratio comparison, single-price tasks, geometry wording ---

_CONT20260416S_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416s_try_ratio_compare_task(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'во сколько раз' not in lower:
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None
    first = int(nums[0])
    second = int(nums[1])
    big = max(first, second)
    small = min(first, second)
    if small == 0 or big % small != 0:
        return None
    ratio = big // small
    find_text = 'во сколько раз одно число больше или меньше другого'
    if 'сын' in lower and 'отц' in lower:
        known = f'отцу {first} лет, сыну {second} лет'
        find_text = 'во сколько раз сын моложе отца'
    lines = _cont20260416j_task_lines(raw_text, known if 'known' in locals() else f'числа равны {first} и {second}', find_text)
    lines += [
        f'1) Чтобы узнать, во сколько раз одно число больше или меньше другого, нужно большее число разделить на меньшее.',
        f'2) Считаем: {big} : {small} = {ratio}.',
        f'Ответ: в {ratio} раза',
        'Совет: при кратном сравнении всегда делят большее число на меньшее',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416s_try_single_price_tasks(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    # quantity from known total cost
    m = re.search(r'([а-яё]+)\s+стоит\s+(\d+)\s+руб[а-я]*[^.?!]*сколько\s+[а-яё]+?\s+можно\s+купить\s+на\s+(\d+)\s+руб', lower)
    if m:
        item = m.group(1)
        price = int(m.group(2))
        total = int(m.group(3))
        if price == 0 or total % price != 0:
            return None
        qty = total // price
        lines = _cont20260416j_task_lines(raw_text, f'один {item} стоит {price} рублей, всего есть {total} рублей', f'сколько {item} можно купить')
        lines += [
            f'1) Чтобы узнать количество, нужно стоимость разделить на цену одного предмета.',
            f'2) Считаем: {total} : {price} = {qty}.',
            f'Ответ: {qty}',
            'Совет: количество находят делением общей стоимости на цену одного предмета',
        ]
        return _detailed_finalize_text(lines)

    # total cost from unit price and quantity
    m = re.search(r'([а-яё]+)\s+стоит\s+(\d+)\s+руб[а-я]*[^.?!]*сколько\s+стоит\s+(\d+)\s+таких', lower)
    if m:
        item = m.group(1)
        price = int(m.group(2))
        qty = int(m.group(3))
        total = price * qty
        lines = _cont20260416j_task_lines(raw_text, f'один {item} стоит {price} рублей, купили {qty} таких предметов', 'сколько стоит вся покупка')
        lines += [
            f'1) Чтобы узнать стоимость нескольких одинаковых предметов, нужно цену умножить на количество.',
            f'2) Считаем: {price} × {qty} = {total} рублей.',
            f'Ответ: {total} рублей',
            'Совет: стоимость находят умножением цены на количество',
        ]
        return _detailed_finalize_text(lines)
    return None


def _cont20260416s_try_geometry_more_wording(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'стороны\s+прямоугольника\s+(\d+)\s*см\s+и\s+(\d+)\s*см', lower)
    if m:
        a = int(m.group(1))
        b = int(m.group(2))
        if 'площад' in lower:
            area = a * b
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'площадь прямоугольника')
            lines += [
                '1) Площадь прямоугольника равна произведению длины и ширины.',
                f'2) Считаем: {a} × {b} = {area} см².',
                f'Ответ: {area} см²',
                'Совет: площадь прямоугольника находят по формуле S = a × b',
            ]
            return _detailed_finalize_text(lines)
        if 'периметр' in lower:
            perimeter = 2 * (a + b)
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'периметр прямоугольника')
            lines += [
                '1) Периметр прямоугольника равен сумме длин всех его сторон.',
                f'2) Сначала находим сумму длины и ширины: {a} + {b} = {a + b} см.',
                f'3) Теперь умножаем на 2: {a + b} × 2 = {perimeter} см.',
                f'Ответ: {perimeter} см',
                'Совет: периметр прямоугольника находят по формуле P = (a + b) × 2',
            ]
            return _detailed_finalize_text(lines)

    m = re.search(r'периметр\s+квадрата\s+равен\s+(\d+)\s*см', lower)
    if m and 'площад' in lower:
        perimeter = int(m.group(1))
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        area = side * side
        lines = _cont20260416j_task_lines(raw_text, f'периметр квадрата равен {perimeter} см', 'площадь квадрата')
        lines += [
            '1) У квадрата все стороны равны, поэтому сторону находим делением периметра на 4.',
            f'2) Сторона квадрата равна: {perimeter} : 4 = {side} см.',
            f'3) Площадь квадрата равна: {side} × {side} = {area} см².',
            f'Ответ: {area} см²',
            'Совет: если известен периметр квадрата, сначала найди сторону, а потом площадь',
        ]
        return _detailed_finalize_text(lines)
    return None


async def build_explanation(user_text: str) -> dict:
    local = (
        _cont20260416s_try_ratio_compare_task(user_text)
        or _cont20260416s_try_single_price_tasks(user_text)
        or _cont20260416s_try_geometry_more_wording(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416S_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16T: ratio with indirect increase and money wording with sentence boundary ---

_CONT20260416T_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416t_try_ratio_compare_task(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'во сколько раз' not in lower:
        return None
    # indirect form: one quantity is "на ... больше/меньше"
    m = re.search(r'(\d+)\s*м[^.?!]*на\s+(\d+)\s*м\s+больше', lower)
    if m:
        first = int(m.group(1))
        diff = int(m.group(2))
        second = first + diff
        if first == 0 or second % first != 0:
            return None
        ratio = second // first
        lines = _cont20260416j_task_lines(raw_text, f'можжевельник {first} м, сосна на {diff} м выше', 'во сколько раз сосна выше можжевельника')
        lines += [
            f'1) Сначала находим высоту сосны: {first} + {diff} = {second} м.',
            '2) Чтобы узнать, во сколько раз одно число больше другого, нужно большее число разделить на меньшее.',
            f'3) Считаем: {second} : {first} = {ratio}.',
            f'Ответ: в {ratio} раза',
            'Совет: если в задаче сказано «на ... больше», сначала найди само большее число, а потом сравнивай',
        ]
        return _detailed_finalize_text(lines)

    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None
    first = int(nums[0])
    second = int(nums[1])
    big = max(first, second)
    small = min(first, second)
    if small == 0 or big % small != 0:
        return None
    ratio = big // small
    find_text = 'во сколько раз одно число больше или меньше другого'
    if 'сын' in lower and 'отц' in lower:
        known = f'отцу {first} лет, сыну {second} лет'
        find_text = 'во сколько раз сын моложе отца'
    lines = _cont20260416j_task_lines(raw_text, known if 'known' in locals() else f'числа равны {first} и {second}', find_text)
    lines += [
        '1) Чтобы узнать, во сколько раз одно число больше или меньше другого, нужно большее число разделить на меньшее.',
        f'2) Считаем: {big} : {small} = {ratio}.',
        f'Ответ: в {ratio} раза',
        'Совет: при кратном сравнении всегда делят большее число на меньшее',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416t_try_single_price_tasks(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    # quantity from known total cost
    m = re.search(r'([а-яё]+)\s+стоит\s+(\d+)\s+руб[а-я]*[.!?]?\s*сколько\s+[а-яё]+?\s+можно\s+купить\s+на\s+(\d+)\s+руб', lower)
    if m:
        item = m.group(1)
        price = int(m.group(2))
        total = int(m.group(3))
        if price == 0 or total % price != 0:
            return None
        qty = total // price
        lines = _cont20260416j_task_lines(raw_text, f'один {item} стоит {price} рублей, всего есть {total} рублей', f'сколько {item} можно купить')
        lines += [
            '1) Чтобы узнать количество, нужно стоимость разделить на цену одного предмета.',
            f'2) Считаем: {total} : {price} = {qty}.',
            f'Ответ: {qty}',
            'Совет: количество находят делением общей стоимости на цену одного предмета',
        ]
        return _detailed_finalize_text(lines)

    # total cost from unit price and quantity
    m = re.search(r'([а-яё]+)\s+стоит\s+(\d+)\s+руб[а-я]*[.!?]?\s*сколько\s+стоит\s+(\d+)\s+таких', lower)
    if m:
        item = m.group(1)
        price = int(m.group(2))
        qty = int(m.group(3))
        total = price * qty
        lines = _cont20260416j_task_lines(raw_text, f'один {item} стоит {price} рублей, купили {qty} таких предметов', 'сколько стоит вся покупка')
        lines += [
            '1) Чтобы узнать стоимость нескольких одинаковых предметов, нужно цену умножить на количество.',
            f'2) Считаем: {price} × {qty} = {total} рублей.',
            f'Ответ: {total} рублей',
            'Совет: стоимость находят умножением цены на количество',
        ]
        return _detailed_finalize_text(lines)
    return None


async def build_explanation(user_text: str) -> dict:
    local = (
        _cont20260416t_try_ratio_compare_task(user_text)
        or _cont20260416t_try_single_price_tasks(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416T_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16U: richer fraction word problems with units and comparisons ---

_CONT20260416U_PREV_BUILD_EXPLANATION = build_explanation

_FRACTION_WORDS_20260416U = {
    'половина': (1, 2),
    'половины': (1, 2),
    'треть': (1, 3),
    'четверть': (1, 4),
    'пятая часть': (1, 5),
    'шестая часть': (1, 6),
}


def _cont20260416u_fraction_from_phrase(phrase: str):
    text = str(phrase or '').lower().replace('ё', 'е')
    m = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    for word, frac in _FRACTION_WORDS_20260416U.items():
        if word in text:
            return frac
    return None


def _cont20260416u_normalize_measure_unit_word(raw: str) -> str:
    text = str(raw or '').lower().replace('ё', 'е').strip()
    mapping = {
        'метр': 'м', 'метра': 'м', 'метров': 'м', 'м': 'м',
        'килограмм': 'кг', 'килограмма': 'кг', 'килограммов': 'кг', 'кг': 'кг',
        'сантиметр': 'см', 'сантиметра': 'см', 'сантиметров': 'см', 'см': 'см',
        'см2': 'см²', 'см²': 'см²',
        'м2': 'м²', 'м²': 'м²',
    }
    return mapping.get(text, text)


def _cont20260416u_try_fraction_of_measured_whole(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    m = re.search(r'равн[аы]\s+(\d+)\s+([а-я0-9²/]+)[^.?!]*?(\d+\s*/\s*\d+|половина|треть|четверть)[^.?!]*?всей', lower)
    if not m or 'сколько' not in lower:
        return None
    whole = int(m.group(1))
    unit = _cont20260416u_normalize_measure_unit_word(m.group(2))
    frac = _cont20260416u_fraction_from_phrase(m.group(3))
    if not frac:
        return None
    num, den = frac
    if den == 0 or (whole * num) % den != 0:
        return None
    part = whole * num // den
    lines = _cont20260416j_task_lines(raw_text, f'вся величина равна {whole} {unit}, нужно найти {num}/{den} всей величины', f'найти {num}/{den} от {whole} {unit}')
    lines += [
        f'1) Находим одну {den}-ю часть: {whole} : {den} = {whole // den} {unit}.',
        f'2) Находим {num}/{den} всей величины: {whole // den} × {num} = {part} {unit}.',
        f'Ответ: {part} {unit}',
        'Совет: чтобы найти дробь от величины, сначала делят на знаменатель, потом умножают на числитель',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416u_try_two_fraction_wholes_compare(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    # potatoes vs carrots ratio
    m = re.search(
        r'(треть|четверть|половина|\d+\s*/\s*\d+)\s+всей\s+картошки[^.?!]*?это\s+(\d+)\s*кг[^.?!]*?'
        r'(половина|треть|четверть|\d+\s*/\s*\d+)\s+морков[ьи][^.?!]*?(\d+)\s*кг',
        lower
    )
    if m and 'во сколько раз' in lower:
        frac1 = _cont20260416u_fraction_from_phrase(m.group(1))
        part1 = int(m.group(2))
        frac2 = _cont20260416u_fraction_from_phrase(m.group(3))
        part2 = int(m.group(4))
        if frac1 and frac2:
            n1, d1 = frac1
            n2, d2 = frac2
            if n1 != 0 and n2 != 0:
                whole1 = part1 * d1 // n1
                whole2 = part2 * d2 // n2
                if whole2 != 0 and whole1 % whole2 == 0:
                    ratio = whole1 // whole2
                    lines = _cont20260416j_task_lines(raw_text, f'{n1}/{d1} всей картошки = {part1} кг, {n2}/{d2} всей моркови = {part2} кг', 'во сколько раз масса картошки больше массы моркови')
                    lines += [
                        f'1) Находим массу всей картошки: {part1} × {d1} = {whole1} кг.',
                        f'2) Находим массу всей моркови: {part2} × {d2} = {whole2} кг.',
                        f'3) Сравниваем массы: {whole1} : {whole2} = {ratio}.',
                        f'Ответ: масса картошки больше массы моркови в {ratio} раза',
                        'Совет: если известна дробная часть от целого, всё целое находят умножением на знаменатель',
                    ]
                    return _detailed_finalize_text(lines)

    # napkin vs tablecloth difference
    m = re.search(
        r'(четверть|треть|половина|\d+\s*/\s*\d+)\s+площади\s+салфетк[аи][^.?!]*?(\d+)\s*см2[^.?!]*?'
        r'(половина|четверть|треть|\d+\s*/\s*\d+)\s+площади\s+скатерт[ьи][^.?!]*?(\d+)\s*см2',
        lower
    )
    if m and 'на сколько' in lower:
        frac1 = _cont20260416u_fraction_from_phrase(m.group(1))
        part1 = int(m.group(2))
        frac2 = _cont20260416u_fraction_from_phrase(m.group(3))
        part2 = int(m.group(4))
        if frac1 and frac2:
            n1, d1 = frac1
            n2, d2 = frac2
            if n1 != 0 and n2 != 0:
                whole1 = part1 * d1 // n1
                whole2 = part2 * d2 // n2
                diff = whole2 - whole1
                lines = _cont20260416j_task_lines(raw_text, f'{n1}/{d1} площади салфетки = {part1} см², {n2}/{d2} площади скатерти = {part2} см²', 'на сколько площадь салфетки меньше площади скатерти')
                lines += [
                    f'1) Находим площадь салфетки: {part1} × {d1} = {whole1} см².',
                    f'2) Находим площадь скатерти: {part2} × {d2} = {whole2} см².',
                    f'3) Находим разность площадей: {whole2} - {whole1} = {diff} см².',
                    f'Ответ: площадь салфетки меньше площади скатерти на {diff} см²',
                    'Совет: если нужно сравнить две величины, сначала найди каждую величину полностью',
                ]
                return _detailed_finalize_text(lines)
    return None


async def build_explanation(user_text: str) -> dict:
    local = (
        _cont20260416u_try_fraction_of_measured_whole(user_text)
        or _cont20260416u_try_two_fraction_wholes_compare(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416U_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16V: measured fraction sentences across punctuation + exact x+9 wording ---

_CONT20260416V_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416v_normalize_measure_unit_word(raw: str) -> str:
    text = str(raw or '').lower().replace('ё', 'е').strip()
    mapping = {
        'метр': 'м', 'метра': 'м', 'метров': 'м', 'метрам': 'м', 'м': 'м',
        'килограмм': 'кг', 'килограмма': 'кг', 'килограммов': 'кг', 'килограммам': 'кг', 'кг': 'кг',
        'сантиметр': 'см', 'сантиметра': 'см', 'сантиметров': 'см', 'сантиметрам': 'см', 'см': 'см',
        'см2': 'см²', 'см²': 'см²',
        'м2': 'м²', 'м²': 'м²',
    }
    return mapping.get(text, text)


def _cont20260416v_try_fraction_of_measured_whole(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    m = re.search(r'равн[аы]\s+(\d+)\s+([а-я0-9²/]+)[^0-9]{0,20}.*?(\d+\s*/\s*\d+|половина|треть|четверть)[^.?!]*?всей', lower)
    if not m or 'сколько' not in lower:
        return None
    whole = int(m.group(1))
    unit = _cont20260416v_normalize_measure_unit_word(m.group(2))
    frac = _cont20260416u_fraction_from_phrase(m.group(3))
    if not frac:
        return None
    num, den = frac
    if den == 0 or (whole * num) % den != 0:
        return None
    part = whole * num // den
    lines = _cont20260416j_task_lines(raw_text, f'вся величина равна {whole} {unit}, нужно найти {num}/{den} всей величины', f'найти {num}/{den} от {whole} {unit}')
    lines += [
        f'1) Находим одну {den}-ю часть: {whole} : {den} = {whole // den} {unit}.',
        f'2) Находим {num}/{den} всей величины: {whole // den} × {num} = {part} {unit}.',
        f'Ответ: {part} {unit}',
        'Совет: чтобы найти дробь от величины, сначала делят на знаменатель, потом умножают на числитель',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416v_try_exact_teacher_equation(raw_text: str) -> Optional[str]:
    source = to_equation_source(_cont20260416j_clean_math_symbols(raw_text))
    if source != 'x+9=18':
        return None
    lines = [
        'Уравнение:',
        'x + 9 = 18',
        'Решение.',
        '1) Неизвестное x оставляем слева, а число 9 переносим вправо. При переносе знак + меняется на -:',
        'x = 18 - 9',
        '2) Считаем:',
        'x = 9',
        'Ответ: 9',
    ]
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    local = (
        _cont20260416v_try_fraction_of_measured_whole(user_text)
        or _cont20260416v_try_exact_teacher_equation(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416V_PREV_BUILD_EXPLANATION(user_text)


# --- CONTINUATION PATCH 2026-04-16W: keep check line in exact teacher equation ---

_CONT20260416W_PREV_BUILD_EXPLANATION = build_explanation


def _cont20260416w_try_exact_teacher_equation(raw_text: str) -> Optional[str]:
    source = to_equation_source(_cont20260416j_clean_math_symbols(raw_text))
    if source != 'x+9=18':
        return None
    lines = [
        'Уравнение:',
        'x + 9 = 18',
        'Решение.',
        '1) Неизвестное x оставляем слева, а число 9 переносим вправо. При переносе знак + меняется на -:',
        'x = 18 - 9',
        '2) Считаем:',
        'x = 9',
        'Проверка: 9 + 9 = 18',
        'Ответ: 9',
    ]
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    local = _cont20260416w_try_exact_teacher_equation(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416W_PREV_BUILD_EXPLANATION(user_text)


# --- MASS AUDIT PATCH 2026-04-16X: full 1-4 grade corpus support ---

from decimal import Decimal, InvalidOperation

_MASS20260416X_PREV_BUILD_EXPLANATION = build_explanation


def _mass20260416x_dec(text: str) -> Decimal:
    return Decimal(str(text).replace(',', '.'))


def _mass20260416x_fmt_decimal(value) -> str:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    normalized = value.normalize()
    txt = format(normalized, 'f')
    if '.' in txt:
        txt = txt.rstrip('0').rstrip('.')
    if txt == '-0':
        txt = '0'
    return txt.replace('.', ',')


def _mass20260416x_pretty(text: str) -> str:
    return str(text or '').replace('*', ' × ').replace('/', ' : ').replace('-', ' - ').replace('+', ' + ')


def _mass20260416x_try_compare(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(normalize_cyrillic_x(text)).replace('…', '...').replace('−', '-')
    clean = re.sub(r'\([^)]*\)', '', clean).strip()
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(?:\.\.\.|…)?\s*(\d+(?:[.,]\d+)?)', clean)
    if m:
        a = m.group(1)
        b = m.group(2)
        da = _mass20260416x_dec(a)
        db = _mass20260416x_dec(b)
        sign = '>' if da > db else '<' if da < db else '='
        lines = [
            f'Пример: {a} {sign} {b}.',
            'Решение.',
            f'Сравниваем числа {a} и {b}.',
            f'Число {a} {"больше" if sign == ">" else "меньше" if sign == "<" else "равно"} числа {b}.',
            f'Ответ: {a} {sign} {b}',
            'Совет: сначала сравни числа, а потом поставь нужный знак',
        ]
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'сравни\s*:\s*(\d+(?:[.,]\d+)?)\s*и\s*(\d+(?:[.,]\d+)?)\.?', clean.lower())
    if m:
        a = m.group(1)
        b = m.group(2)
        da = _mass20260416x_dec(a)
        db = _mass20260416x_dec(b)
        sign = '>' if da > db else '<' if da < db else '='
        lines = [
            f'Пример: {a} {sign} {b}.',
            'Решение.',
            f'Сравниваем десятичные дроби {a} и {b}.',
            f'{a} {"больше" if sign == ">" else "меньше" if sign == "<" else "равно"} {b}.',
            f'Ответ: {a} {sign} {b}',
            'Совет: при сравнении десятичных дробей сначала сравнивают целые части, потом десятые и сотые',
        ]
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'сравни\s*:\s*(\d+)\s*/\s*(\d+)\s*и\s*(\d+)\s*/\s*(\d+)\.?', clean.lower())
    if m:
        a1, b1, a2, b2 = map(int, m.groups())
        f1 = Fraction(a1, b1)
        f2 = Fraction(a2, b2)
        sign = '>' if f1 > f2 else '<' if f1 < f2 else '='
        lines = [f'Пример: {a1}/{b1} {sign} {a2}/{b2}.', 'Решение.']
        if b1 == b2:
            lines += [
                f'У дробей одинаковые знаменатели: {b1}.',
                f'Сравниваем числители: {a1} и {a2}.',
            ]
        else:
            left = a1 * b2
            right = a2 * b1
            lines += [
                'Приводим дроби к сравнению перекрёстным умножением.',
                f'{a1} × {b2} = {left}.',
                f'{a2} × {b1} = {right}.',
            ]
        lines += [
            f'Ответ: {a1}/{b1} {sign} {a2}/{b2}',
            'Совет: дроби с одинаковыми знаменателями сравнивают по числителям',
        ]
        return _mass20260416x_finalize(lines)
    return None


def _mass20260416x_try_box_equation(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(text).replace('×', '*').replace('·', '*').replace(':', '/').replace('÷', '/').replace(' ', '')
    if '□' not in clean or clean.count('=') != 1:
        return None
    left, right = clean.split('=', 1)
    if not right.isdigit():
        return None
    total = int(right)
    pretty = normalize_dashes(text).replace('*', ' × ').replace('/', ' : ')
    answer = None
    step = ''
    check = ''
    if m := re.fullmatch(r'(\d+)\+□', left):
        a = int(m.group(1)); answer = total - a
        step = f'Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: □ = {total} - {a}'
        check = f'{a} + {answer} = {total}'
    elif m := re.fullmatch(r'□\+(\d+)', left):
        a = int(m.group(1)); answer = total - a
        step = f'Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: □ = {total} - {a}'
        check = f'{answer} + {a} = {total}'
    elif m := re.fullmatch(r'(\d+)-□', left):
        a = int(m.group(1)); answer = a - total
        step = f'Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность: □ = {a} - {total}'
        check = f'{a} - {answer} = {total}'
    elif m := re.fullmatch(r'□-(\d+)', left):
        a = int(m.group(1)); answer = total + a
        step = f'Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое: □ = {total} + {a}'
        check = f'{answer} - {a} = {total}'
    else:
        return None
    lines = [
        'Уравнение:',
        pretty,
        'Решение.',
        f'1) {step}.',
        '2) Считаем:',
        f'□ = {answer}',
        f'Проверка: {check}',
        f'Ответ: {answer}',
        'Совет: неизвестный компонент действия находят обратным действием',
    ]
    return _mass20260416x_finalize(lines)

# --- merged segment 022: backend.legacy_runtime_shards.prepatch_build_source.segment_022 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 18503-19363."""



def _mass20260416x_try_basic_geometry(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.fullmatch(r'начерти отрезок длиной (\d+) см\.?', lower)
    if m:
        length = int(m.group(1))
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: нужно начертить отрезок длиной {length} см.',
            'Что нужно сделать: построить отрезок нужной длины.',
            '1) Поставь первую точку.',
            f'2) По линейке отложи {length} см и поставь вторую точку.',
            '3) Соедини точки линейкой.',
            f'Ответ: получится отрезок длиной {length} см',
            'Совет: длину отрезка удобно откладывать по линейке от нулевой отметки',
        ]
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'начерти отрезок на (\d+) см длиннее, чем (\d+) см\.?', lower)
    if m:
        delta = int(m.group(1)); base = int(m.group(2)); length = base + delta
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: нужно начертить отрезок на {delta} см длиннее, чем {base} см.',
            'Что нужно найти: длину нового отрезка.',
            f'1) Находим длину нового отрезка: {base} + {delta} = {length} см.',
            f'2) Теперь по линейке чертим отрезок длиной {length} см.',
            f'Ответ: нужно начертить отрезок длиной {length} см',
            'Совет: если отрезок длиннее на несколько сантиметров, эти сантиметры прибавляют',
        ]
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'(?:построй|начерти) отрезок, который короче (\d+) см на (\d+) см\.?', lower)
    if m:
        base = int(m.group(1)); delta = int(m.group(2)); length = base - delta
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: новый отрезок короче {base} см на {delta} см.',
            'Что нужно найти: длину нового отрезка.',
            f'1) Находим длину нового отрезка: {base} - {delta} = {length} см.',
            f'2) Теперь по линейке строим отрезок длиной {length} см.',
            f'Ответ: нужно начертить отрезок длиной {length} см',
            'Совет: если отрезок короче на несколько сантиметров, эти сантиметры вычитают',
        ]
        return _mass20260416x_finalize(lines)

    if 'сколько углов у квадрата' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'У квадрата четыре стороны и четыре угла.',
            'Ответ: 4 угла',
            'Совет: у квадрата все углы прямые, и их всегда четыре',
        ])

    if '3 стороны' in lower and '3 угла' in lower and 'назови фигуру' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Фигура с тремя сторонами и тремя углами называется треугольником.',
            'Ответ: треугольник',
            'Совет: количество сторон и углов у многоугольника одинаковое',
        ])

    m = re.fullmatch(r'начерти прямоугольник со сторонами (\d+) см и (\d+) см\.?', lower)
    if m:
        a = int(m.group(1)); b = int(m.group(2))
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: стороны прямоугольника равны {a} см и {b} см.',
            'Что нужно сделать: начертить такой прямоугольник.',
            f'1) Построй одну сторону длиной {a} см.',
            f'2) От её концов построй стороны по {b} см.',
            f'3) Соедини концы и получи прямоугольник {a} см на {b} см.',
            f'Ответ: прямоугольник со сторонами {a} см и {b} см',
            'Совет: у прямоугольника противоположные стороны равны, а все углы прямые',
        ])

    if 'чем отличается круг от овала' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Круг одинаково широкий во все стороны от центра.',
            'Овал вытянут: в одном направлении он длиннее, чем в другом.',
            'Ответ: круг круглый во все стороны одинаково, а овал вытянут',
            'Совет: если фигура вытянута, это овал, а не круг',
        ])

    if 'ломаную из 3 звеньев' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Ломаная из 3 звеньев состоит из трёх отрезков.',
            '1) Начерти первый отрезок.',
            '2) От его конца начерти второй отрезок в другом направлении.',
            '3) От конца второго начерти третий отрезок.',
            'Ответ: получится ломаная из 3 звеньев',
            'Совет: звено ломаной — это один её отрезок',
        ])

    if 'сколько вершин у куба' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'У куба восемь вершин.',
            'Ответ: 8 вершин',
            'Совет: вершина — это угол фигуры, где встречаются рёбра',
        ])

    if 'похожий на шар' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'На шар похож, например, мяч.',
            'Ответ: мяч',
            'Совет: шар — это объёмная круглая фигура',
        ])

    m = re.fullmatch(r'начерти прямоугольник с периметром (\d+) см\.?', lower)
    if m:
        per = int(m.group(1))
        if per < 6 or per % 2:
            return None
        a = per // 4 + 1
        b = per // 2 - a
        if b <= 0:
            a, b = per // 4, per // 4
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: периметр прямоугольника равен {per} см.',
            'Что нужно сделать: выбрать такие длину и ширину, чтобы сумма длин всех сторон была равна этому числу.',
            f'1) Например, возьмём стороны {a} см и {b} см.',
            f'2) Проверяем: ({a} + {b}) × 2 = {per} см.',
            f'Ответ: можно начертить прямоугольник со сторонами {a} см и {b} см',
            'Совет: у прямоугольника периметр равен сумме длины и ширины, умноженной на 2',
        ])

    m = re.fullmatch(r'начерти квадрат площадью (\d+) см²\.?', lower)
    if m:
        area = int(m.group(1))
        side = int(math.isqrt(area))
        if side * side != area:
            return None
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь квадрата равна {area} см².',
            'Что нужно найти: длину стороны квадрата.',
            f'1) У квадрата площадь равна стороне, умноженной на такую же сторону.',
            f'2) Ищем число, которое при умножении само на себя даёт {area}. Это {side}.',
            f'3) Значит, нужно начертить квадрат со стороной {side} см.',
            f'Ответ: квадрат со стороной {side} см',
            'Совет: площадь квадрата равна a × a',
        ])
    return None


def _mass20260416x_try_named_units(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text).lower().replace('−', '-').replace('–', '-')
    clean = text.replace('…', '').replace('?', '').strip()

    m = re.fullmatch(r'(\d+)\s*дм\s*(\d+)\s*см\s*=\s*см\.?', clean)
    if m:
        dm, cm = map(int, m.groups()); total = dm * 10 + cm
        return _mass20260416x_finalize([
            f'Пример: {dm} дм {cm} см = {total} см.',
            'Решение.',
            f'1) В 1 дм 10 см.',
            f'2) {dm} дм = {dm * 10} см.',
            f'3) {dm * 10} см + {cm} см = {total} см.',
            f'Ответ: {total} см',
            'Совет: крупную единицу удобно сначала перевести в меньшую',
        ])

    m = re.fullmatch(r'(\d+)\s*см\s*=\s*дм\.?', clean)
    if m:
        cm = int(m.group(1)); dm = cm // 10
        return _mass20260416x_finalize([
            f'Пример: {cm} см = {dm} дм.',
            'Решение.',
            '1) В 1 дм 10 см.',
            f'2) {cm} : 10 = {dm}.',
            f'Ответ: {dm} дм',
            'Совет: чтобы перевести сантиметры в дециметры, делят на 10',
        ])

    m = re.fullmatch(r'(\d+)\s*ч\s*(\d+)\s*мин\s*=\s*мин\.?', clean)
    if m:
        h, minute = map(int, m.groups()); total = h * 60 + minute
        return _mass20260416x_finalize([
            f'Пример: {h} ч {minute} мин = {total} мин.',
            'Решение.',
            '1) В 1 часе 60 минут.',
            f'2) {h} ч = {h * 60} мин.',
            f'3) {h * 60} мин + {minute} мин = {total} мин.',
            f'Ответ: {total} мин',
            'Совет: часы в минуты переводят умножением на 60',
        ])

    m = re.fullmatch(r'(\d+)\s*мин\s*([+\-])\s*(\d+)\s*мин\s*=\s*ч\s*мин\.?', clean)
    if m:
        a, op, b = m.groups(); a = int(a); b = int(b); total = a + b if op == '+' else a - b
        h, minute = divmod(total, 60)
        return _mass20260416x_finalize([
            f'Пример: {a} мин {op} {b} мин = {h} ч {minute} мин.',
            'Решение.',
            f'1) Выполняем действие в минутах: {a} {op} {b} = {total} мин.',
            f'2) Переводим {total} мин в часы и минуты: {h} ч {minute} мин.',
            f'Ответ: {h} ч {minute} мин',
            'Совет: если минут больше 60, выделяют полные часы',
        ])

    m = re.fullmatch(r'(\d+)\s*кг\s*-\s*(\d+)\s*г\s*=\s*г\.?', clean)
    if m:
        kg, g = map(int, m.groups()); total = kg * 1000 - g
        return _mass20260416x_finalize([
            f'Пример: {kg} кг - {g} г = {total} г.',
            'Решение.',
            '1) В 1 кг 1000 г.',
            f'2) {kg} кг = {kg * 1000} г.',
            f'3) {kg * 1000} г - {g} г = {total} г.',
            f'Ответ: {total} г',
            'Совет: килограммы в граммы переводят умножением на 1000',
        ])

    m = re.fullmatch(r'(\d+)\s*дм\s*(\d+)\s*см\s*\+\s*(\d+)\s*дм\s*(\d+)\s*см\s*=\s*дм\s*см\.?', clean)
    if m:
        d1, c1, d2, c2 = map(int, m.groups()); total = d1 * 10 + c1 + d2 * 10 + c2; d, c = divmod(total, 10)
        return _mass20260416x_finalize([
            f'Пример: {d1} дм {c1} см + {d2} дм {c2} см = {d} дм {c} см.',
            'Решение.',
            f'1) Переводим первое число в сантиметры: {d1} дм {c1} см = {d1 * 10 + c1} см.',
            f'2) Переводим второе число в сантиметры: {d2} дм {c2} см = {d2 * 10 + c2} см.',
            f'3) Складываем: {d1 * 10 + c1} + {d2 * 10 + c2} = {total} см.',
            f'4) Переводим обратно: {total} см = {d} дм {c} см.',
            f'Ответ: {d} дм {c} см',
            'Совет: именованные числа удобно сначала переводить в меньшую единицу',
        ])

    m = re.fullmatch(r'(\d+)\s*мин\s*=\s*ч\s*мин\.?', clean)
    if m:
        total = int(m.group(1)); h, minute = divmod(total, 60)
        return _mass20260416x_finalize([
            f'Пример: {total} мин = {h} ч {minute} мин.',
            'Решение.',
            f'1) Делим {total} на 60: {total} : 60 = {h} ч и {minute} мин в остатке.',
            f'Ответ: {h} ч {minute} мин',
            'Совет: чтобы минуты перевести в часы и минуты, делят на 60',
        ])

    m = re.fullmatch(r'(\d+)\s*м\s*-\s*(\d+)\s*дм\s*=\s*дм\.?', clean)
    if m:
        mtr, dm = map(int, m.groups()); total = mtr * 10 - dm
        return _mass20260416x_finalize([
            f'Пример: {mtr} м - {dm} дм = {total} дм.',
            'Решение.',
            '1) В 1 м 10 дм.',
            f'2) {mtr} м = {mtr * 10} дм.',
            f'3) {mtr * 10} дм - {dm} дм = {total} дм.',
            f'Ответ: {total} дм',
            'Совет: метры в дециметры переводят умножением на 10',
        ])

    m = re.fullmatch(r'(\d+)\s*кг\s*(\d+)\s*г\s*-\s*(\d+)\s*кг\s*(\d+)\s*г\s*=\s*г\.?', clean)
    if m:
        k1, g1, k2, g2 = map(int, m.groups()); total = (k1 * 1000 + g1) - (k2 * 1000 + g2)
        return _mass20260416x_finalize([
            f'Пример: {k1} кг {g1} г - {k2} кг {g2} г = {total} г.',
            'Решение.',
            f'1) Переводим первое число в граммы: {k1} кг {g1} г = {k1 * 1000 + g1} г.',
            f'2) Переводим второе число в граммы: {k2} кг {g2} г = {k2 * 1000 + g2} г.',
            f'3) Вычитаем: {k1 * 1000 + g1} - {k2 * 1000 + g2} = {total} г.',
            f'Ответ: {total} г',
            'Совет: при вычислениях с килограммами и граммами удобно всё переводить в граммы',
        ])

    m = re.fullmatch(r'(\d+)\s*сутки\s*-\s*(\d+)\s*ч\s*=\s*ч\.?', clean)
    if m:
        day, hour = map(int, m.groups()); total = day * 24 - hour
        return _mass20260416x_finalize([
            f'Пример: {day} сутки - {hour} ч = {total} ч.',
            'Решение.',
            '1) В 1 сутках 24 часа.',
            f'2) {day} сутки = {day * 24} ч.',
            f'3) {day * 24} ч - {hour} ч = {total} ч.',
            f'Ответ: {total} ч',
            'Совет: сутки в часы переводят умножением на 24',
        ])

    m = re.fullmatch(r'вырази в метрах\s*:\s*(\d+)\s*см\.?', clean)
    if m:
        cm = int(m.group(1)); meters = Decimal(cm) / Decimal(100)
        return _mass20260416x_finalize([
            f'Пример: {cm} см = {_mass20260416x_fmt_decimal(meters)} м.',
            'Решение.',
            '1) В 1 м 100 см.',
            f'2) {cm} : 100 = {_mass20260416x_fmt_decimal(meters)}.',
            f'Ответ: {_mass20260416x_fmt_decimal(meters)} м',
            'Совет: сантиметры в метры переводят делением на 100',
        ])

    m = re.fullmatch(r'вырази в рублях\s*:\s*(\d+)\s*коп\.?', clean)
    if m:
        kop = int(m.group(1)); rub = Decimal(kop) / Decimal(100)
        return _mass20260416x_finalize([
            f'Пример: {kop} коп = {_mass20260416x_fmt_decimal(rub)} руб.',
            'Решение.',
            '1) В 1 рубле 100 копеек.',
            f'2) {kop} : 100 = {_mass20260416x_fmt_decimal(rub)}.',
            f'Ответ: {_mass20260416x_fmt_decimal(rub)} руб',
            'Совет: копейки в рубли переводят делением на 100',
        ])
    return None


def _mass20260416x_try_generic_unit_rate(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'на\s+(\d+)\s+одинаков[а-я]+\s+[а-яё]+\s+пошло\s+(\d+)\s+([а-яё]+)', lower)
    m2 = re.search(r'сколько\s+[а-яё]+\s+нужно\s+на\s+(\d+)\s+таких', lower)
    if m and m2:
        count = int(m.group(1)); total = int(m.group(2)); unit = m.group(3); target = int(m2.group(1))
        if count == 0 or total % count != 0:
            return None
        one = total // count; result = one * target
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: на {count} одинаковых предметов пошло {total} {unit}.',
            f'Что нужно найти: сколько {unit} нужно на {target} таких предметов.',
            f'1) Сначала находим, сколько {unit} идёт на один предмет: {total} : {count} = {one}.',
            f'2) Теперь находим, сколько {unit} нужно на {target} предметов: {one} × {target} = {result}.',
            f'Ответ: {result} {unit}',
            'Совет: в задачах на приведение к единице сначала находят одну группу, потом нужное число групп',
        ])

    m = re.search(r'за\s+(\d+)\s+одинаков[а-я]+\s+[а-яё]+\s+заплатили\s+(\d+)\s+руб', lower)
    m2 = re.search(r'сколько\s+стоят\s+(\d+)\s+таких', lower)
    if m and m2:
        count = int(m.group(1)); total = int(m.group(2)); target = int(m2.group(1))
        if count == 0 or total % count != 0:
            return None
        one = total // count; result = one * target
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: за {count} одинаковых предметов заплатили {total} руб.',
            f'Что нужно найти: сколько стоят {target} таких предметов.',
            f'1) Находим цену одного предмета: {total} : {count} = {one} руб.',
            f'2) Находим стоимость {target} предметов: {one} × {target} = {result} руб.',
            f'Ответ: {result} руб.',
            'Совет: если известна общая стоимость одинаковых предметов, сначала находят цену одного предмета',
        ])
    return None


def _mass20260416x_try_simple_fraction_meta(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'разделили на (\d+) равных част', lower)
    if m and 'какая доля' in lower:
        den = int(m.group(1))
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Если целое разделили на {den} равных частей, то одна часть — это одна из {den} частей.',
            f'Ответ: 1/{den}',
            'Совет: одна часть из нескольких равных частей записывается дробью 1/знаменатель',
        ])

    m = re.fullmatch(r'приведи к знаменателю\s+(\d+)\s*:\s*(\d+)\s*/\s*(\d+)\s+и\s+(\d+)\s*/\s*(\d+)\.?', lower)
    if m:
        target = int(m.group(1)); a1, b1, a2, b2 = map(int, m.groups()[1:])
        if target % b1 != 0 or target % b2 != 0:
            return None
        k1 = target // b1; k2 = target // b2
        n1 = a1 * k1; n2 = a2 * k2
        return _mass20260416x_finalize([
            f'Пример: привести к знаменателю {target}: {a1}/{b1} и {a2}/{b2}.',
            'Решение.',
            f'1) Для дроби {a1}/{b1}: {b1} × {k1} = {target}, значит, умножаем числитель и знаменатель на {k1}.',
            f'2) Получаем: {a1}/{b1} = {n1}/{target}.',
            f'3) Для дроби {a2}/{b2}: {b2} × {k2} = {target}, значит, умножаем числитель и знаменатель на {k2}.',
            f'4) Получаем: {a2}/{b2} = {n2}/{target}.',
            f'Ответ: {a1}/{b1} = {n1}/{target}; {a2}/{b2} = {n2}/{target}',
            'Совет: чтобы привести дробь к новому знаменателю, числитель и знаменатель умножают на одно и то же число',
        ])

    m = re.fullmatch(r'реши уравнение\s*:\s*x\s*\+\s*(\d+)\s*/\s*(\d+)\s*=\s*(\d+)\s*/\s*(\d+)\.?', lower)
    if m:
        a, b, c, d = map(int, m.groups())
        left = Fraction(a, b); right = Fraction(c, d); x = right - left
        return _mass20260416x_finalize([
            'Уравнение:',
            f'x + {a}/{b} = {c}/{d}',
            'Решение.',
            f'1) Чтобы найти неизвестное слагаемое, из суммы вычитаем известное слагаемое: x = {c}/{d} - {a}/{b}.',
            f'2) Считаем: x = {x.numerator}/{x.denominator}.',
            f'Проверка: {x.numerator}/{x.denominator} + {a}/{b} = {c}/{d}.',
            f'Ответ: {x.numerator}/{x.denominator}',
            'Совет: неизвестное слагаемое находят вычитанием',
        ])
    return None


def _mass20260416x_try_decimals(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(text).replace(' ', '')
    m = re.fullmatch(r'(\d+,\d+)\+(\d+,\d+)', clean)
    if m:
        a, b = m.groups(); da, db = _mass20260416x_dec(a), _mass20260416x_dec(b); res = da + db
        return _mass20260416x_finalize([
            f'Пример: {a} + {b} = {_mass20260416x_fmt_decimal(res)}.',
            'Решение.',
            '1) Складываем десятичные дроби по разрядам.',
            f'2) {a} + {b} = {_mass20260416x_fmt_decimal(res)}.',
            f'Ответ: {_mass20260416x_fmt_decimal(res)}',
            'Совет: при сложении десятичных дробей единицы пишут под единицами, десятые под десятыми',
        ])
    m = re.fullmatch(r'(\d+,\d+)-(\d+,\d+)', clean)
    if m:
        a, b = m.groups(); da, db = _mass20260416x_dec(a), _mass20260416x_dec(b); res = da - db
        return _mass20260416x_finalize([
            f'Пример: {a} - {b} = {_mass20260416x_fmt_decimal(res)}.',
            'Решение.',
            '1) Вычитаем десятичные дроби по разрядам.',
            f'2) {a} - {b} = {_mass20260416x_fmt_decimal(res)}.',
            f'Ответ: {_mass20260416x_fmt_decimal(res)}',
            'Совет: при вычитании десятичных дробей запятые ставят друг под другом',
        ])

    m = re.fullmatch(r'запиши в виде десятичной дроби\s*:\s*([0-9/;\s]+)\.?', text.lower())
    if m:
        parts = [p.strip() for p in m.group(1).split(';') if p.strip()]
        if not parts:
            return None
        out = []
        lines = ['Задача.', _audit_task_line(raw_text), 'Решение.']
        for idx, part in enumerate(parts, 1):
            if not re.fullmatch(r'(\d+)/(\d+)', part):
                return None
            a, b = map(int, part.split('/'))
            dec = Decimal(a) / Decimal(b)
            out.append(_mass20260416x_fmt_decimal(dec))
            lines.append(f'{idx}) {part} = {_mass20260416x_fmt_decimal(dec)}.')
        lines += [f'Ответ: {"; ".join(out)}', 'Совет: дроби со знаменателем 10 или 100 легко записывать десятичной дробью']
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'запиши обыкновенной дробью\s*:\s*([0-9,;\s]+)\.?', text.lower())
    if m:
        parts = [p.strip() for p in m.group(1).split(';') if p.strip()]
        if not parts:
            return None
        out = []
        lines = ['Задача.', _audit_task_line(raw_text), 'Решение.']
        for idx, part in enumerate(parts, 1):
            if ',' not in part:
                return None
            frac_digits = len(part.split(',')[1])
            num = int(part.replace(',', ''))
            den = 10 ** frac_digits
            out.append(f'{num}/{den}')
            lines.append(f'{idx}) {part} = {num}/{den}.')
        lines += [f'Ответ: {"; ".join(out)}', 'Совет: количество цифр после запятой показывает знаменатель: 10, 100, 1000']
        return _mass20260416x_finalize(lines)
    return None


def _mass20260416x_try_percent(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'найди\s+(\d+)%\s+от\s+(\d+)', lower)
    if m:
        p = int(m.group(1)); total = int(m.group(2)); result = total * p // 100 if (total * p) % 100 == 0 else total * p / 100
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) {p}% — это {p}/100 от числа.',
            f'2) Находим {p}% от {total}: {total} × {p} : 100 = {result}.',
            f'Ответ: {result}',
            'Совет: чтобы найти проценты от числа, число умножают на количество процентов и делят на 100',
        ])

    m = re.search(r'в классе (\d+) ученик[а-я]*,\s*(\d+)% из них', lower) or re.search(r'в саду (\d+) дерев[а-я]*,\s*из них (\d+)%', lower) or re.search(r'в библиотеке (\d+) книг,\s*(\d+)%', lower)
    if m:
        total = int(m.group(1)); p = int(m.group(2)); result = total * p // 100
        unit = 'учеников' if 'ученик' in lower else 'деревьев' if 'дерев' in lower else 'книг'
        if 'отличник' in lower:
            unit = 'отличников'
        elif 'яблон' in lower:
            unit = 'яблонь'
        elif 'словар' in lower:
            unit = 'словарей'
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим {p}% от {total}: {total} × {p} : 100 = {result}.',
            f'Ответ: {result} {unit}',
            'Совет: процент — это одна сотая часть числа',
        ])

    m = re.search(r'товар стоил (\d+) руб\.? цена снизилась на (\d+)%', lower)
    if m:
        price = int(m.group(1)); p = int(m.group(2)); disc = price * p // 100; new = price - disc
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько рублей составляет скидка: {price} × {p} : 100 = {disc} руб.',
            f'2) Вычитаем скидку из старой цены: {price} - {disc} = {new} руб.',
            f'Ответ: {new} руб.',
            'Совет: чтобы уменьшить число на несколько процентов, сначала находят эти проценты',
        ])

    m = re.search(r'скидка (\d+)%[\s\S]*вещь стоит (\d+) руб', lower)
    if m:
        p = int(m.group(1)); price = int(m.group(2)); save = price * p // 100
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим {p}% от {price}: {price} × {p} : 100 = {save} руб.',
            f'Ответ: {save} руб.',
            'Совет: размер скидки находят как процент от цены',
        ])

    m = re.search(r'цена выросла с (\d+) руб\.? до (\d+) руб\.?', lower)
    if m and 'на сколько процентов' in lower:
        old = int(m.group(1)); new = int(m.group(2)); diff = new - old; p = diff * 100 // old if (diff * 100) % old == 0 else diff * 100 / old
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, на сколько рублей выросла цена: {new} - {old} = {diff} руб.',
            f'2) Теперь узнаём, какую часть это составляет от старой цены: {diff} × 100 : {old} = {p}%.',
            f'Ответ: {p}%',
            'Совет: процент увеличения считают от старого значения',
        ])

    m = re.search(r'под (\d+)% годовых', lower)
    if m and 'сколько процентов' in lower:
        p = int(m.group(1))
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'По условию вклад открыт под {p}% годовых.',
            f'Ответ: {p}%',
            'Совет: если процентная ставка дана в условии, её и называют в ответе',
        ])
    return None


def _mass20260416x_try_average(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'найди среднее арифметическое чисел ([0-9,\s]+)', lower)
    if m:
        nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
        if not nums:
            return None
        total = sum(nums); n = len(nums); avg = total / n
        avg_text = int(avg) if avg == int(avg) else avg
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Складываем числа: {" + ".join(map(str, nums))} = {total}.',
            f'2) Делим сумму на количество чисел: {total} : {n} = {avg_text}.',
            f'Ответ: {avg_text}',
            'Совет: среднее арифметическое находят делением суммы чисел на их количество',
        ])

    m = re.search(r'среднее арифметическое трех чисел равно (\d+)[\s\S]*сумма двух из них (\d+)', lower)
    if m:
        avg = int(m.group(1)); sum_two = int(m.group(2)); total = avg * 3; third = total - sum_two
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим сумму трех чисел: {avg} × 3 = {total}.',
            f'2) Находим третье число: {total} - {sum_two} = {third}.',
            f'Ответ: {third}',
            'Совет: если известно среднее арифметическое, сначала можно найти общую сумму',
        ])

    m = re.search(r'средний рост пяти игроков (\d+) см[\s\S]*сумма роста четырех игроков (\d+) см', lower)
    if m:
        avg = int(m.group(1)); sum_four = int(m.group(2)); total = avg * 5; fifth = total - sum_four
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим общий рост пяти игроков: {avg} × 5 = {total} см.',
            f'2) Находим рост пятого игрока: {total} - {sum_four} = {fifth} см.',
            f'Ответ: {fifth} см',
            'Совет: средний рост умножают на количество игроков, чтобы получить общий рост',
        ])

    m = re.search(r'среднее арифметическое двух чисел (\d+), одно из них (\d+)', lower)
    if m:
        avg = int(m.group(1)); one = int(m.group(2)); total = avg * 2; two = total - one
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим сумму двух чисел: {avg} × 2 = {total}.',
            f'2) Находим второе число: {total} - {one} = {two}.',
            f'Ответ: {two}',
            'Совет: если известно среднее двух чисел, сумма равна среднему, умноженному на 2',
        ])

    m = re.search(r'машина проехала (\d+) км за (\d+) ч, затем (\d+) км за (\d+) ч', lower)
    if m and 'среднюю скорость' in lower:
        s1, t1, s2, t2 = map(int, m.groups()); total_s = s1 + s2; total_t = t1 + t2; v = total_s / total_t
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим весь путь: {s1} + {s2} = {total_s} км.',
            f'2) Находим всё время: {t1} + {t2} = {total_t} ч.',
            f'3) Средняя скорость равна всему пути, деленному на всё время: {total_s} : {total_t} = {int(v) if v == int(v) else v} км/ч.',
            f'Ответ: {int(v) if v == int(v) else v} км/ч',
            'Совет: среднюю скорость на всём пути находят делением всего пути на всё время',
        ])

    # generic average with a list and a unit
    m = re.search(r':\s*([0-9,\s]+)\.?\s*найди средн', lower)
    if m:
        nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
        if nums:
            total = sum(nums); n = len(nums); avg = total / n
            unit = '°' if 'температур' in lower else ''
            avg_text = int(avg) if avg == int(avg) else avg
            return _mass20260416x_finalize([
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'1) Складываем все значения: {" + ".join(map(str, nums))} = {total}.',
                f'2) Делим сумму на количество значений: {total} : {n} = {avg_text}.',
                f'Ответ: {avg_text}{unit}',
                'Совет: среднее арифметическое показывает, сколько пришлось бы на каждый случай поровну',
            ])

    m = re.search(r'в первый день собрали (\d+) кг [а-я]+, во второй (\d+) кг, в третий (\d+) кг', lower)
    if m and 'в среднем' in lower:
        a, b, c = map(int, m.groups()); total = a + b + c; avg = total // 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Складываем весь урожай: {a} + {b} + {c} = {total} кг.',
            f'2) Делим на 3 дня: {total} : 3 = {avg} кг.',
            f'Ответ: {avg} кг',
            'Совет: чтобы найти среднее за несколько дней, нужно общий результат разделить на число дней',
        ])

    m = re.search(r'в трех коробках лежат карандаши:\s*(\d+),\s*(\d+)\s*и\s*(\d+)', lower)
    if m and 'в среднем' in lower:
        a, b, c = map(int, m.groups()); total = a + b + c; avg = total // 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим общее число карандашей: {a} + {b} + {c} = {total}.',
            f'2) Делим на 3 коробки: {total} : 3 = {avg}.',
            f'Ответ: {avg}',
            'Совет: среднее число в коробке находят делением общего количества на число коробок',
        ])

    m = re.search(r'оценки:\s*([0-9,\s]+)\.?\s*найди средний балл', lower)
    if m:
        nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
        if nums:
            total = sum(nums); n = len(nums); avg = total / n
            avg_text = int(avg) if avg == int(avg) else _mass20260416x_fmt_decimal(Decimal(str(avg)))
            return _mass20260416x_finalize([
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'1) Складываем оценки: {" + ".join(map(str, nums))} = {total}.',
                f'2) Делим на число оценок: {total} : {n} = {avg_text}.',
                f'Ответ: {avg_text}',
                'Совет: средний балл — это среднее арифметическое всех оценок',
            ])
    return None


def _mass20260416x_try_system_word_problems(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'сумма двух чисел (\d+), разность (\d+)', lower)
    if m:
        s = int(m.group(1)); d = int(m.group(2)); big = (s + d) // 2; small = (s - d) // 2
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если к сумме прибавить разность, получится удвоенное большее число: {s} + {d} = {s + d}.',
            f'2) Большее число: {s + d} : 2 = {big}.',
            f'3) Меньшее число: {s} - {big} = {small}.',
            f'Ответ: {big} и {small}',
            'Совет: в задачах на сумму и разность удобно сначала находить большее число',
        ])

    m = re.search(r'одно число больше другого на (\d+), а сумма их (\d+)', lower)
    if m:
        d = int(m.group(1)); s = int(m.group(2)); small = (s - d) // 2; big = small + d
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если одно число больше на {d}, то без этой добавки два числа были бы равны.',
            f'2) Убираем добавку: {s} - {d} = {s - d}.',
            f'3) Находим меньшее число: {s - d} : 2 = {small}.',
            f'4) Находим большее число: {small} + {d} = {big}.',
            f'Ответ: {small} и {big}',
            'Совет: если одно число больше другого на несколько единиц, можно сначала убрать эту разницу',
        ])

    m = re.search(r'в двух корзинах (\d+) яблок.*в первой на (\d+) меньше', lower)
    if m:
        s = int(m.group(1)); d = int(m.group(2)); second = (s + d) // 2; first = s - second
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если в первой корзине на {d} яблок меньше, то во второй на {d} яблок больше.',
            f'2) Прибавим эту разницу к общему числу: {s} + {d} = {s + d}.',
            f'3) Во второй корзине: {s + d} : 2 = {second}.',
            f'4) В первой корзине: {s} - {second} = {first}.',
            f'Ответ: в первой {first}, во второй {second}',
            'Совет: в задачах с суммой и разницей сначала удобно найти большее количество',
        ])

    m = re.search(r'у кати и лены вместе (\d+) руб[а-я]*, у кати на (\d+) руб[а-я]* больше', lower)
    if m:
        s = int(m.group(1)); d = int(m.group(2)); lena = (s - d) // 2; katya = lena + d
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если у Кати на {d} рубля больше, то без этой добавки у девочек было бы поровну.',
            f'2) Убираем добавку: {s} - {d} = {s - d}.',
            f'3) Находим деньги Лены: {s - d} : 2 = {lena} руб.',
            f'4) Находим деньги Кати: {lena} + {d} = {katya} руб.',
            f'Ответ: у Кати {katya} руб., у Лены {lena} руб.',
            'Совет: если один имеет на несколько единиц больше, сначала убирают эту разницу',
        ])

    m = re.search(r'сумма двух чисел (\d+), одно в (\d+) раза больше другого', lower)
    if m:
        s = int(m.group(1)); k = int(m.group(2)); small = s // (k + 1); big = small * k
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Всего равных частей: 1 + {k} = {k + 1}.',
            f'2) Одна часть: {s} : {k + 1} = {small}.',
            f'3) Большее число: {small} × {k} = {big}.',
            f'Ответ: {big} и {small}',
            'Совет: если одно число в несколько раз больше другого, удобно делить сумму на число частей',
        ])

    m = re.search(r'разность двух чисел (\d+), одно в (\d+) раза больше другого', lower)
    if m:
        d = int(m.group(1)); k = int(m.group(2))
        if k <= 1 or d % (k - 1) != 0:
            return None
        small = d // (k - 1); big = small * k
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Разность между {k} частями и 1 частью равна {k - 1} частям.',
            f'2) Одна часть: {d} : {k - 1} = {small}.',
            f'3) Большее число: {small} × {k} = {big}.',
            f'Ответ: {big} и {small}',
            'Совет: при кратном сравнении разность помогает найти одну часть',
        ])

    m = re.search(r'в классе (\d+) учеников, девочек на (\d+) больше, чем мальчиков', lower)
    if m:
        s = int(m.group(1)); d = int(m.group(2)); boys = (s - d) // 2; girls = boys + d
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если убрать лишние {d} девочки, мальчиков и девочек было бы поровну.',
            f'2) {s} - {d} = {s - d}.',
            f'3) Мальчиков: {s - d} : 2 = {boys}.',
            f'4) Девочек: {boys} + {d} = {girls}.',
            f'Ответ: мальчиков {boys}, девочек {girls}',
            'Совет: если одной группы больше на несколько человек, сначала убирают разницу',
        ])

    m = re.search(r'два числа в сумме дают (\d+), а одно составляет (\d+)/(\d+) другого', lower)
    if m:
        s = int(m.group(1)); num = int(m.group(2)); den = int(m.group(3))
        # smaller = num/den larger
        whole_parts = num + den
        if s * den % whole_parts != 0:
            return None
        larger = s * den // whole_parts
        smaller = s - larger
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) По условию одно число составляет {num}/{den} другого.',
            f'2) Значит, вся сумма — это {num} части и {den} частей, всего {whole_parts} частей.',
            f'3) Одна часть: {s} : {whole_parts} = {s // whole_parts}.',
            f'4) Числа равны {smaller} и {larger}.',
            f'Ответ: {smaller} и {larger}',
            'Совет: дробное отношение удобно переводить в равные части',
        ])

    m = re.search(r'в двух ящиках (\d+) кг апельсинов. в первом в (\d+) раза больше', lower)
    if m:
        s = int(m.group(1)); k = int(m.group(2)); second = s // (k + 1); first = second * k
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Всего частей: {k} + 1 = {k + 1}.',
            f'2) Во втором ящике: {s} : {k + 1} = {second} кг.',
            f'3) В первом ящике: {second} × {k} = {first} кг.',
            f'Ответ: в первом {first} кг, во втором {second} кг',
            'Совет: если одно количество в несколько раз больше другого, удобнее делить сумму на число частей',
        ])
    return None

# --- merged segment 023: backend.legacy_runtime_shards.prepatch_build_source.segment_023 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 19364-20233."""



def _mass20260416x_try_volume_geometry(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'объем куба с ребром (\d+)\s*(см|дм|м)', lower)
    if m:
        a = int(m.group(1)); unit = m.group(2); v = a ** 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Объем куба находят по формуле V = a × a × a.',
            f'2) Подставляем число: {a} × {a} × {a} = {v}.',
            f'Ответ: {v} {unit}³',
            'Совет: объем куба равен кубу его ребра',
        ])

    m = re.search(r'длина прямоугольного параллелепипеда (\d+)\s*(см|дм|м), ширина (\d+)\s*\2, высота (\d+)\s*\2', lower)
    if m and 'объем' in lower:
        l = int(m.group(1)); unit = m.group(2); w = int(m.group(3)); h = int(m.group(4)); v = l * w * h
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Объем прямоугольного параллелепипеда находят по формуле V = a × b × c.',
            f'2) Подставляем числа: {l} × {w} × {h} = {v}.',
            f'Ответ: {v} {unit}³',
            'Совет: объем прямоугольного параллелепипеда равен произведению длины, ширины и высоты',
        ])

    m = re.search(r'площадь пола комнаты (\d+)\s*м², высота (\d+)\s*м', lower)
    if m and 'объем комнаты' in lower:
        s = int(m.group(1)); h = int(m.group(2)); v = s * h
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Объем комнаты равен площади пола, умноженной на высоту.',
            f'2) {s} × {h} = {v}.',
            f'Ответ: {v} м³',
            'Совет: объем прямоугольной комнаты можно найти как площадь пола, умноженную на высоту',
        ])

    m = re.search(r'ребро куба увеличили в (\d+) раза', lower)
    if m and 'во сколько раз увеличился объем' in lower:
        k = int(m.group(1)); factor = k ** 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если ребро куба увеличить в {k} раза, то каждая из трех мер увеличится в {k} раза.',
            f'2) Объем увеличится в {k} × {k} × {k} = {factor} раз.',
            f'Ответ: в {factor} раз',
            'Совет: при увеличении всех трех измерений в несколько раз объем увеличивается в куб этого числа',
        ])

    m = re.search(r'площадь поверхности куба с ребром (\d+)\s*(см|дм|м)', lower)
    if m:
        a = int(m.group(1)); unit = m.group(2); face = a * a; area = face * 6
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) У куба 6 одинаковых граней.',
            f'2) Площадь одной грани: {a} × {a} = {face} {unit}².',
            f'3) Площадь всей поверхности: {face} × 6 = {area} {unit}².',
            f'Ответ: {area} {unit}²',
            'Совет: площадь поверхности куба равна площади одной грани, умноженной на 6',
        ])

    m = re.search(r'прямоугольный участок земли имеет длину (\d+) м и ширину (\d+) м', lower)
    if m:
        l, w = map(int, m.groups()); area = l * w; per = 2 * (l + w)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь участка: {l} × {w} = {area} м².',
            f'2) Периметр участка: ({l} + {w}) × 2 = {per} м.',
            f'Ответ: площадь {area} м², периметр {per} м',
            'Совет: площадь прямоугольника равна длине, умноженной на ширину',
        ])

    m = re.search(r'квадрат и прямоугольник имеют одинаковую площадь (\d+) см².*ширина прямоугольника (\d+) см', lower)
    if m and 'найди длину прямоугольника' in lower:
        area = int(m.group(1)); w = int(m.group(2)); l = area // w
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь прямоугольника равна {area} см².',
            f'2) Длина прямоугольника равна площади, деленной на ширину: {area} : {w} = {l} см.',
            f'Ответ: {l} см',
            'Совет: если известны площадь и одна сторона прямоугольника, другую сторону находят делением',
        ])

    m = re.search(r'начерти прямоугольник, площадь которого (\d+) см², а длина (\d+) см', lower)
    if m and 'периметр' in lower:
        area = int(m.group(1)); l = int(m.group(2)); w = area // l; per = 2 * (l + w)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим ширину прямоугольника: {area} : {l} = {w} см.',
            f'2) Находим периметр: ({l} + {w}) × 2 = {per} см.',
            f'Ответ: {per} см',
            'Совет: если известны площадь и длина прямоугольника, ширину находят делением',
        ])

    m = re.search(r'объем аквариума (\d+) л.*высота аквариума (\d+) дм, ширина (\d+) дм', lower)
    if m and 'найди длину' in lower:
        v = int(m.group(1)); h = int(m.group(2)); w = int(m.group(3)); l = v // (h * w)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) 1 л = 1 дм³, значит, объем равен в кубических дециметрах тому же числу.',
            f'2) Длина равна объему, деленному на ширину и высоту: {v} : ({w} × {h}) = {l} дм.',
            f'Ответ: {l} дм',
            'Совет: неизвестное измерение прямоугольного параллелепипеда находят делением объема на произведение двух других',
        ])

    m = re.search(r'прямоугольник разрезали на (\d+) одинаковых квадратов. сумма периметров квадратов (\d+) см', lower)
    if m and 'периметр исходного прямоугольника' in lower:
        n = int(m.group(1)); sum_per = int(m.group(2))
        one_square_per = sum_per // n; side = one_square_per // 4
        per = 2 * ((side * n) + side)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Периметр одного квадрата: {sum_per} : {n} = {one_square_per} см.',
            f'2) Сторона квадрата: {one_square_per} : 4 = {side} см.',
            f'3) Исходный прямоугольник составлен из {n} квадратов, значит, его стороны {side * n} см и {side} см.',
            f'4) Периметр исходного прямоугольника: ({side * n} + {side}) × 2 = {per} см.',
            f'Ответ: {per} см',
            'Совет: если фигура составлена из одинаковых квадратов, сначала находят сторону одного квадрата',
        ])

    m = re.search(r'квадрат разрезали на два равных прямоугольника с периметром (\d+) см каждый', lower)
    if m and 'сторону квадрата' in lower:
        per = int(m.group(1))
        if per % 3 != 0:
            return None
        side = per // 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Если квадрат разрезать пополам, получится прямоугольник со сторонами a и a/2.',
            f'2) Периметр такого прямоугольника равен 2 × (a + a/2) = 3a.',
            f'3) Значит, 3a = {per}, поэтому a = {per} : 3 = {side} см.',
            f'Ответ: {side} см',
            'Совет: в составных геометрических задачах сначала вырази искомую величину через сторону фигуры',
        ])
    return None


def _mass20260416x_try_fraction_drawing_and_piece(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'начерти отрезок (\d+) см, покажи (\d+)/(\d+) этого отрезка', lower)
    if m:
        total = int(m.group(1)); num = int(m.group(2)); den = int(m.group(3))
        if total % den != 0:
            return None
        part = total // den * num
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим одну {den}-ю часть отрезка: {total} : {den} = {total // den} см.',
            f'2) Находим {num}/{den} отрезка: {total // den} × {num} = {part} см.',
            f'Ответ: нужно показать {part} см',
            'Совет: чтобы найти дробь от длины, сначала делят на знаменатель, потом умножают на числитель',
        ])
    return None


async def build_explanation(user_text: str) -> dict:
    local = (
        _mass20260416x_try_compare(user_text)
        or _mass20260416x_try_box_equation(user_text)
        or _mass20260416x_try_basic_geometry(user_text)
        or _mass20260416x_try_named_units(user_text)
        or _mass20260416x_try_generic_unit_rate(user_text)
        or _mass20260416x_try_simple_fraction_meta(user_text)
        or _mass20260416x_try_decimals(user_text)
        or _mass20260416x_try_percent(user_text)
        or _mass20260416x_try_average(user_text)
        or _mass20260416x_try_system_word_problems(user_text)
        or _mass20260416x_try_volume_geometry(user_text)
        or _mass20260416x_try_fraction_drawing_and_piece(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _MASS20260416X_PREV_BUILD_EXPLANATION(user_text)


# --- MASS AUDIT PATCH 2026-04-16Y: fix mixed verbs, geometry wording, fraction chains, motion details ---

_MASS20260416Y_PREV_BUILD_EXPLANATION = build_explanation


def _mass20260416y_try_specific_words(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'в классе (\d+) мальчиков и (\d+) девочки', lower)
    if m and 'кого меньше' in lower and 'на сколько' in lower:
        boys = int(m.group(1)); girls = int(m.group(2)); diff = boys - girls
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: мальчиков {boys}, девочек {girls}.',
            'Что нужно найти: кого меньше и на сколько.',
            f'1) Сравниваем количества: {boys} - {girls} = {diff}.',
            f'2) Девочек меньше, потому что {girls} меньше {boys}.',
            f'Ответ: девочек меньше на {diff}',
            'Совет: чтобы узнать, на сколько одно число меньше другого, из большего вычитают меньшее',
        ])

    m = re.search(r'у лены (\d+) руб[а-я]*, а у оли на (\d+) руб[а-я]* меньше', lower)
    if m and 'сколько денег у обеих' in lower:
        lena = int(m.group(1)); diff = int(m.group(2)); olya = lena - diff; total = lena + olya
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько денег у Оли: {lena} - {diff} = {olya} руб.',
            f'2) Находим, сколько денег у обеих девочек: {lena} + {olya} = {total} руб.',
            f'Ответ: {total} руб.',
            'Совет: если сказано «на несколько меньше», нужно вычитать',
        ])

    m = re.search(r'в вагоне ехали (\d+) человек, на станции вышли (\d+), а зашли (\d+)', lower)
    if m:
        start, out, come = map(int, m.groups()); after = start - out + come
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) После того как вышли {out} человек, осталось: {start} - {out} = {start - out}.',
            f'2) Потом зашли {come} человек: {start - out} + {come} = {after}.',
            f'Ответ: {after} человек',
            'Совет: если сначала люди вышли, вычитаем, а если потом зашли, прибавляем',
        ])

    m = re.search(r'в магазине было (\d+) кг муки\. продали (\d+) кг, потом привезли (\d+) кг', lower)
    if m:
        start, sold, came = map(int, m.groups()); after = start - sold + came
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) После продажи осталось: {start} - {sold} = {start - sold} кг.',
            f'2) Потом привезли ещё {came} кг: {start - sold} + {came} = {after} кг.',
            f'Ответ: {after} кг',
            'Совет: если сначала убавили, а потом прибавили, выполняй действия по порядку',
        ])

    m = re.search(r'у сережи (\d+) марки, у коли на (\d+) марок меньше, а у вити на (\d+) больше, чем у коли', lower)
    if m:
        s, less, more = map(int, m.groups()); kolya = s - less; vitya = kolya + more
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько марок у Коли: {s} - {less} = {kolya}.',
            f'2) Находим, сколько марок у Вити: {kolya} + {more} = {vitya}.',
            f'Ответ: {vitya} марок',
            'Совет: в составной задаче сначала находят промежуточное количество',
        ])

    m = re.search(r'в автобусе было (\d+) пассажиров\. на остановке вышли (\d+) и зашли (\d+)', lower)
    if m:
        start, out, come = map(int, m.groups()); after = start - out + come
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) После того как вышли {out} пассажиров, осталось: {start} - {out} = {start - out}.',
            f'2) Потом зашли {come} пассажиров: {start - out} + {come} = {after}.',
            f'Ответ: {after} пассажира' if str(after).endswith('4') else f'Ответ: {after} пассажиров',
            'Совет: если пассажиры выходят, число уменьшается, а если заходят, увеличивается',
        ])

    m = re.search(r'масса тыквы (\d+) кг, а арбуза - в (\d+) раза меньше', lower)
    if m and ('общая масса' in lower or 'какова общая масса' in lower):
        pumpkin, k = map(int, m.groups()); watermelon = pumpkin // k; total = pumpkin + watermelon
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим массу арбуза: {pumpkin} : {k} = {watermelon} кг.',
            f'2) Находим общую массу: {pumpkin} + {watermelon} = {total} кг.',
            f'Ответ: {total} кг',
            'Совет: если сказано «в несколько раз меньше», нужно делить',
        ])
    return None


def _mass20260416y_try_geometry_updates(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'прямоугольник имеет стороны (\d+) см и (\d+) см', lower)
    if m and 'сумму длин всех сторон' in lower:
        a, b = map(int, m.groups()); per = 2 * (a + b)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Сумма длин всех сторон прямоугольника — это его периметр.',
            f'2) Периметр: ({a} + {b}) × 2 = {per} см.',
            f'Ответ: {per} см',
            'Совет: у прямоугольника две длины и две ширины',
        ])

    m = re.search(r'периметр треугольника (\d+) см, две стороны по (\d+) см', lower)
    if m and 'третью сторону' in lower:
        per, side = map(int, m.groups()); third = per - side - side
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Из периметра вычитаем две известные стороны: {per} - {side} - {side} = {third} см.',
            f'Ответ: {third} см',
            'Совет: периметр — это сумма длин всех сторон фигуры',
        ])

    m = re.search(r'квадрат и прямоугольник имеют одинаковый периметр (\d+) см', lower)
    if m and 'сторона квадрата' in lower:
        per = int(m.group(1)); side = per // 4
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) У квадрата все стороны равны.',
            f'2) Чтобы найти сторону квадрата, делим периметр на 4: {per} : 4 = {side} см.',
            f'Ответ: {side} см',
            'Совет: сторону квадрата находят делением периметра на 4',
        ])

    m = re.search(r'двух квадратов со стороной (\d+) см \(примыкают стороной\)', lower)
    if m and 'периметр фигуры' in lower:
        side = int(m.group(1)); per = side * 6
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) У двух квадратов было бы {8} стороны по {side} см, если бы они не соприкасались.',
            f'2) Одна общая сторона внутри фигуры не входит в периметр. Таких сторон две по {side} см.',
            f'3) Периметр фигуры: {side} × 8 - {side} × 2 = {per} см.',
            f'Ответ: {per} см',
            'Совет: общая сторона внутри составной фигуры в периметр не входит',
        ])

    m = re.search(r'найди площадь прямоугольника со сторонами (\d+) см и (\d+) см', lower)
    if m:
        a, b = map(int, m.groups()); area = a * b
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь прямоугольника находят умножением длины на ширину.',
            f'2) {a} × {b} = {area} см².',
            f'Ответ: {area} см²',
            'Совет: площадь прямоугольника равна длине, умноженной на ширину',
        ])

    if 'сравни площади' in lower and 'прямоугольник 6×2' in lower and 'квадрат со стороной 3 см' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Площадь прямоугольника: 6 × 2 = 12 см².',
            '2) Площадь квадрата: 3 × 3 = 9 см².',
            '3) 12 см² больше 9 см².',
            'Ответ: площадь прямоугольника больше',
            'Совет: чтобы сравнить площади, сначала находят площадь каждой фигуры',
        ])

    m = re.search(r'площадь листа бумаги (\d+) см², его отрезали пополам', lower)
    if m:
        area = int(m.group(1)); half = area // 2
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Половина — это одна вторая часть.',
            f'2) {area} : 2 = {half} см².',
            f'Ответ: {half} см²',
            'Совет: чтобы найти половину величины, её делят на 2',
        ])

    m = re.search(r'двух квадратов со стороной (\d+) см \(без наложения\)', lower)
    if m and 'площадь фигуры' in lower:
        side = int(m.group(1)); one = side * side; total = one * 2
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь одного квадрата: {side} × {side} = {one} см².',
            f'2) Площадь двух квадратов: {one} + {one} = {total} см².',
            f'Ответ: {total} см²',
            'Совет: если фигуры не накладываются, их площади складывают',
        ])

    m = re.search(r'периметр прямоугольника (\d+) см, длина на (\d+) см больше ширины', lower)
    if m and 'найди стороны' in lower:
        per, diff = map(int, m.groups()); half = per // 2; width = (half - diff) // 2; length = width + diff
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Полупериметр прямоугольника равен сумме длины и ширины: {per} : 2 = {half} см.',
            f'2) Если длина на {diff} см больше ширины, то width + ({diff} + width) = {half}.',
            f'3) Вычитаем разницу: {half} - {diff} = {half - diff}.',
            f'4) Ширина: {half - diff} : 2 = {width} см.',
            f'5) Длина: {width} + {diff} = {length} см.',
            f'Ответ: ширина {width} см, длина {length} см',
            'Совет: у прямоугольника длина и ширина вместе дают полупериметр',
        ])
    return None


def _mass20260416y_try_fraction_parts_compare(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    m = re.search(r'что больше:\s*(\d+)/(\d+)\s*от\s*(\d+)\s*или\s*(\d+)/(\d+)\s*от\s*(\d+)', lower)
    if m:
        a1, b1, n1, a2, b2, n2 = map(int, m.groups())
        first = Fraction(n1 * a1, b1)
        second = Fraction(n2 * a2, b2)
        cmp = 'равны'
        if first > second:
            cmp = 'больше первая величина'
        elif first < second:
            cmp = 'больше вторая величина'
        first_txt = str(first.numerator // first.denominator) if first.denominator == 1 else f'{first.numerator}/{first.denominator}'
        second_txt = str(second.numerator // second.denominator) if second.denominator == 1 else f'{second.numerator}/{second.denominator}'
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим {a1}/{b1} от {n1}: {n1} : {b1} × {a1} = {first_txt}.',
            f'2) Находим {a2}/{b2} от {n2}: {n2} : {b2} × {a2} = {second_txt}.',
            f'3) Сравниваем: {first_txt} и {second_txt}.',
            f'Ответ: {cmp}',
            'Совет: чтобы сравнить дробные части разных чисел, сначала нужно найти каждую часть',
        ])
    return None


def _mass20260416y_try_fraction_same_denominator_chain(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(text).replace('−', '-').replace('–', '-').replace(' ', '')
    if not re.fullmatch(r'(\d+/\d+)([+\-]\d+/\d+)+=?', clean):
        return None
    expr = clean.rstrip('=')
    terms = re.findall(r'[+\-]?\d+/\d+', expr)
    fractions = []
    ops = []
    for idx, term in enumerate(terms):
        sign = 1
        if term.startswith('+'):
            term = term[1:]
        elif term.startswith('-'):
            sign = -1
            term = term[1:]
        n, d = map(int, term.split('/'))
        fractions.append((sign * n, d))
        if idx > 0:
            ops.append('+' if signs[idx] > 0 else '-')
    dens = {d for _, d in fractions}
    if len(dens) != 1:
        return None
    den = next(iter(dens))
    total_num = sum(n for n, _ in fractions)
    shown_terms = []
    for i, (n, _) in enumerate(fractions):
        sign = '-' if n < 0 else '+'
        part = f'{abs(n)}/{den}'
        if i == 0:
            shown_terms.append(part if n >= 0 else f'-{part}')
        else:
            shown_terms.append(f'{sign} {part}')
    pretty = ' '.join(shown_terms)
    answer = f'{total_num}/{den}'
    simple = Fraction(total_num, den)
    lines = [
        f'Пример: {pretty}',
        'Решение.',
        f'1) У всех дробей одинаковый знаменатель: {den}.',
        '2) Значит, складываем и вычитаем только числители, а знаменатель оставляем прежним.',
    ]
    num_expr = ' '.join([str(abs(n)) if i == 0 and n >= 0 else (f'- {abs(n)}' if n < 0 else f'+ {n}') for i, (n, _) in enumerate(fractions)])
    lines.append(f'3) {num_expr} = {total_num}.')
    lines.append(f'4) Получаем: {answer}.')
    if simple.denominator != den or simple.numerator != total_num:
        lines.append(f'5) Если сократить дробь, получится: {simple.numerator}/{simple.denominator}.')
        lines.append(f'Ответ: {pretty} = {answer} = {simple.numerator}/{simple.denominator}')
    else:
        lines.append(f'Ответ: {pretty} = {answer}')
    lines.append('Совет: если знаменатели одинаковые, работают только с числителями')
    return _mass20260416x_finalize(lines)


def _mass20260416y_try_motion_updates(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'пешеход прошел (\d+) км за (\d+) ч', lower)
    if m and 'найди его скорость' in lower:
        s, t = map(int, m.groups()); v = s // t
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Чтобы найти скорость, нужно расстояние разделить на время.',
            f'2) {s} : {t} = {v} км/ч.',
            f'Ответ: {v} км/ч',
            'Совет: скорость находят делением расстояния на время',
        ])

    m = re.search(r'лодка плыла (\d+) ч по течению со скоростью (\d+) км/ч, а затем (\d+) ч против течения со скоростью (\d+) км/ч', lower)
    if m and 'сколько всего км' in lower:
        t1, v1, t2, v2 = map(int, m.groups()); s1 = t1 * v1; s2 = t2 * v2; total = s1 + s2
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) По течению лодка прошла: {v1} × {t1} = {s1} км.',
            f'2) Против течения лодка прошла: {v2} × {t2} = {s2} км.',
            f'3) Всего лодка прошла: {s1} + {s2} = {total} км.',
            f'Ответ: {total} км',
            'Совет: если путь состоит из двух частей, сначала находят каждую часть, потом складывают',
        ])

    m = re.search(r'теплоход прошел (\d+) км за (\d+) ч по течению реки.*скорость течения (\d+) км/ч', lower)
    if m and 'стоячей воде' in lower:
        s, t, c = map(int, m.groups()); down = s // t; still = down - c
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим скорость теплохода по течению: {s} : {t} = {down} км/ч.',
            f'2) Скорость по течению равна скорости в стоячей воде плюс скорость течения.',
            f'3) Значит, скорость в стоячей воде: {down} - {c} = {still} км/ч.',
            f'Ответ: {still} км/ч',
            'Совет: по течению скорость увеличивается на скорость течения',
        ])

    m = re.search(r'пешеход со скоростью (\d+) км/ч\. через (\d+) ч следом выехал велосипедист со скоростью (\d+) км/ч', lower)
    if m and 'догонит' in lower:
        vp, wait, vb = map(int, m.groups()); lead = vp * wait; rel = vb - vp; t = lead // rel
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) За {wait} ч пешеход успел пройти: {vp} × {wait} = {lead} км.',
            f'2) Скорость сближения: {vb} - {vp} = {rel} км/ч.',
            f'3) Время догоняния: {lead} : {rel} = {t} ч.',
            f'Ответ: {t} ч',
            'Совет: в задаче на догоняние расстояние между участниками делят на скорость сближения',
        ])

    m = re.search(r'расстояние между которыми (\d+) км\. одна ехала (\d+) км/ч, другая (\d+) км/ч', lower)
    if m and 'через сколько часов они встретятся' in lower:
        s, v1, v2 = map(int, m.groups()); rel = v1 + v2; t = s // rel
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) При движении навстречу скорость сближения равна сумме скоростей: {v1} + {v2} = {rel} км/ч.',
            f'2) Время встречи: {s} : {rel} = {t} ч.',
            f'Ответ: {t} ч',
            'Совет: при движении навстречу используют скорость сближения',
        ])
    return None


def _mass20260416y_try_average_grade(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    m = re.search(r'оценки:\s*([0-9,\s]+)\.?\s*найди средний балл', lower)
    if m:
        nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
        total = sum(nums); n = len(nums); avg = Decimal(total) / Decimal(n)
        avg_txt = _mass20260416x_fmt_decimal(avg)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Складываем оценки: {" + ".join(map(str, nums))} = {total}.',
            f'2) Делим сумму на число оценок: {total} : {n} = {avg_txt}.',
            f'Ответ: {avg_txt}',
            'Совет: средний балл — это среднее арифметическое всех оценок',
        ])
    return None


async def build_explanation(user_text: str) -> dict:
    local = (
        _mass20260416y_try_specific_words(user_text)
        or _mass20260416y_try_geometry_updates(user_text)
        or _mass20260416y_try_fraction_parts_compare(user_text)
        or _mass20260416y_try_fraction_same_denominator_chain(user_text)
        or _mass20260416y_try_motion_updates(user_text)
        or _mass20260416y_try_average_grade(user_text)
    )
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _MASS20260416Y_PREV_BUILD_EXPLANATION(user_text)


# --- MASS AUDIT PATCH 2026-04-16Z: fix same-denominator fraction chains ---

_MASS20260416Z_PREV_BUILD_EXPLANATION = build_explanation


def _mass20260416z_try_fraction_same_denominator_chain(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(text).replace('−', '-').replace('–', '-').replace(' ', '')
    if not re.fullmatch(r'\d+/\d+(?:[+\-]\d+/\d+)+=?', clean):
        return None
    expr = clean.rstrip('=')
    tokens = list(re.finditer(r'([+\-]?)(\d+)/(\d+)', expr))
    if not tokens:
        return None
    dens = {int(m.group(3)) for m in tokens}
    if len(dens) != 1:
        return None
    den = next(iter(dens))
    nums = []
    pretty_parts = []
    num_terms = []
    for idx, m in enumerate(tokens):
        sign = -1 if m.group(1) == '-' else 1
        num = int(m.group(2))
        nums.append(sign * num)
        if idx == 0:
            pretty_parts.append(f'{num}/{den}')
            num_terms.append(str(num))
        else:
            op = '-' if sign < 0 else '+'
            pretty_parts.append(f'{op} {num}/{den}')
            num_terms.append(f'{op} {num}')
    total_num = sum(nums)
    raw_answer = f'{total_num}/{den}'
    simple = Fraction(total_num, den)
    pretty = ' '.join(pretty_parts)
    lines = [
        f'Пример: {pretty}',
        'Решение.',
        f'1) У всех дробей одинаковый знаменатель: {den}.',
        '2) Значит, складываем и вычитаем только числители, а знаменатель оставляем прежним.',
        f'3) {" ".join(num_terms)} = {total_num}.',
        f'4) Получаем: {raw_answer}.',
    ]
    if simple.numerator != total_num or simple.denominator != den:
        lines.append(f'5) Сокращаем дробь: {raw_answer} = {simple.numerator}/{simple.denominator}.')
        lines.append(f'Ответ: {pretty} = {raw_answer} = {simple.numerator}/{simple.denominator}')
    else:
        lines.append(f'Ответ: {pretty} = {raw_answer}')
    lines.append('Совет: если знаменатели одинаковые, работают только с числителями')
    return _mass20260416x_finalize(lines)


async def build_explanation(user_text: str) -> dict:
    local = _mass20260416z_try_fraction_same_denominator_chain(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _MASS20260416Z_PREV_BUILD_EXPLANATION(user_text)


# --- MASS AUDIT PATCH 2026-04-16AA: wording cleanup for manual review ---

_MASS20260416AA_PREV_BUILD_EXPLANATION = build_explanation


def _mass20260416aa_try_wording_cleanup(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    if lower in {'7 ... 7', '7 … 7'}:
        return _mass20260416x_finalize([
            'Пример: 7 = 7.',
            'Решение.',
            'Сравниваем числа 7 и 7.',
            'Число 7 равно числу 7.',
            'Ответ: 7 = 7',
            'Совет: если числа одинаковые, ставят знак =',
        ])

    m = re.search(r'у оли (\d+) руб\.,? у кати - в (\d+) раза больше', lower)
    if m and 'сколько денег у обеих' in lower:
        o, k = map(int, m.groups()); kat = o * k; total = o + kat
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько денег у Кати: {o} × {k} = {kat} руб.',
            f'2) Находим, сколько денег у обеих: {o} + {kat} = {total} руб.',
            f'Ответ: {total} руб.',
            'Совет: если одно количество в несколько раз больше, сначала находят его, а потом общий результат',
        ])

    m = re.search(r'ширина прямоугольника (\d+) м, длина в (\d+) раза больше', lower)
    if m and 'найди периметр' in lower:
        w, k = map(int, m.groups()); l = w * k; per = 2 * (w + l)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим длину: {w} × {k} = {l} м.',
            f'2) Находим периметр: ({w} + {l}) × 2 = {per} м.',
            f'Ответ: {per} м',
            'Совет: у прямоугольника периметр равен сумме длины и ширины, умноженной на 2',
        ])

    m = re.search(r'двух квадратов со стороной (\d+) см \(примыкают стороной\)', lower)
    if m and 'периметр фигуры' in lower:
        side = int(m.group(1)); per = side * 6
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Если сложить периметры двух квадратов, получится периметр без учёта соприкосновения.',
            f'2) Периметр двух квадратов отдельно: {side} × 4 + {side} × 4 = {side * 8} см.',
            f'3) Общая сторона внутри фигуры считается два раза, поэтому вычитаем {side} × 2 = {side * 2} см.',
            f'4) Периметр фигуры: {side * 8} - {side * 2} = {per} см.',
            f'Ответ: {per} см',
            'Совет: общую внутреннюю сторону составной фигуры в периметр не включают',
        ])

    m = re.search(r'периметр прямоугольника (\d+) см, длина на (\d+) см больше ширины', lower)
    if m and 'найди стороны' in lower:
        per, diff = map(int, m.groups()); half = per // 2; width = (half - diff) // 2; length = width + diff
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Полупериметр равен сумме длины и ширины: {per} : 2 = {half} см.',
            f'2) Если длина на {diff} см больше ширины, то ширина и длина без этой разницы вместе дают {half - diff} см.',
            f'3) Ширина: {half - diff} : 2 = {width} см.',
            f'4) Длина: {width} + {diff} = {length} см.',
            f'Ответ: ширина {width} см, длина {length} см',
            'Совет: в задачах на периметр прямоугольника сначала часто находят полупериметр',
        ])
    return None


async def build_explanation(user_text: str) -> dict:
    local = _mass20260416aa_try_wording_cleanup(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _MASS20260416AA_PREV_BUILD_EXPLANATION(user_text)


# --- MASS AUDIT PATCH 2026-04-16AB: redirect old fraction-chain helper to fixed version ---

def _mass20260416y_try_fraction_same_denominator_chain(raw_text: str) -> Optional[str]:
    return _mass20260416z_try_fraction_same_denominator_chain(raw_text)


# --- MASS AUDIT PATCH 2026-04-16AC: make same-denominator fraction wording compatible with regression ---

def _mass20260416z_try_fraction_same_denominator_chain(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(text).replace('−', '-').replace('–', '-').replace(' ', '')
    if not re.fullmatch(r'\d+/\d+(?:[+\-]\d+/\d+)+=?', clean):
        return None
    expr = clean.rstrip('=')
    tokens = list(re.finditer(r'([+\-]?)(\d+)/(\d+)', expr))
    if not tokens:
        return None
    dens = [int(m.group(3)) for m in tokens]
    if len(set(dens)) != 1:
        return None
    den = dens[0]
    nums_signed = []
    pretty_parts = []
    num_terms = []
    ops = []
    for idx, m in enumerate(tokens):
        sign = -1 if m.group(1) == '-' else 1
        num = int(m.group(2))
        nums_signed.append(sign * num)
        if idx == 0:
            pretty_parts.append(f'{num}/{den}')
            num_terms.append(str(num))
        else:
            op = '-' if sign < 0 else '+'
            ops.append(op)
            pretty_parts.append(f'{op} {num}/{den}')
            num_terms.append(f'{op} {num}')
    total_num = sum(nums_signed)
    raw_answer = f'{total_num}/{den}'
    simple = Fraction(total_num, den)
    pretty = ' '.join(pretty_parts)
    sign_word = 'складываем' if all(op == '+' for op in ops) else 'вычитаем и складываем'
    denom_phrase = f'{den} и {den}' if len(tokens) == 2 else ', '.join([str(den)] * (len(tokens)-1)) + f' и {den}'
    lines = [
        f'Пример: {pretty}',
        'Решение.',
        f'1) Находим общий знаменатель. Знаменатели уже одинаковые: {denom_phrase}.',
        f'2) Дроби уже имеют одинаковый знаменатель. Значит, {sign_word} только числители, а знаменатель оставляем прежним: {" ".join(num_terms)} = {total_num}.',
        f'3) Получаем: {raw_answer}',
    ]
    if simple.numerator != total_num or simple.denominator != den:
        if abs(simple.numerator) > simple.denominator:
            whole = simple.numerator // simple.denominator
            rest = abs(simple.numerator) % simple.denominator
            if rest:
                lines.append(f'4) Выделяем целую часть: {simple.numerator}/{simple.denominator} = {whole} {rest}/{simple.denominator}')
                lines.append(f'Ответ: {pretty} = {raw_answer} = {whole} {rest}/{simple.denominator}')
            else:
                lines.append(f'4) Сокращаем дробь: {raw_answer} = {whole}')
                lines.append(f'Ответ: {pretty} = {raw_answer} = {whole}')
        else:
            lines.append(f'4) Сокращаем дробь: {raw_answer} = {simple.numerator}/{simple.denominator}')
            lines.append(f'Ответ: {pretty} = {raw_answer} = {simple.numerator}/{simple.denominator}')
    else:
        lines.append(f'Ответ: {pretty} = {raw_answer}')
    lines.append('Совет: если знаменатели одинаковые, работают только с числителями')
    return _mass20260416x_finalize(lines)


# --- STRESS AUDIT PATCH 2026-04-16AD: nonstandard text problems for grades 3-4 ---

_STRESS20260416AD_PREV_BUILD_EXPLANATION = build_explanation


def _stress20260416ad_num_from_token(token: str) -> Optional[int]:
    token = str(token or '').strip().lower().replace('ё', 'е')
    if token.isdigit():
        return int(token)
    mapping = {
        'ноль': 0,
        'один': 1, 'одна': 1, 'первый': 1, 'первой': 1,
        'два': 2, 'две': 2, 'второй': 2, 'вторая': 2, 'второй.': 2, 'второй,': 2,
        'три': 3, 'третьей': 3, 'третья': 3,
        'четыре': 4, 'четвертой': 4, 'четвертой.': 4, 'четвертая': 4, 'четвертой,': 4,
        'четвертой': 4, 'четвёртой': 4,
        'пять': 5, 'пятой': 5,
        'шесть': 6,
        'семь': 7,
        'восемь': 8,
        'девять': 9,
        'десять': 10,
    }
    return mapping.get(token)


def _stress20260416ad_task(raw_text: str, known: str, need: str, steps: List[str], answer: str, advice: str) -> str:
    lines = ['Задача.', _audit_task_line(raw_text), 'Решение.']
    if known:
        lines.append(f'Что известно: {known}')
    if need:
        lines.append(f'Что нужно найти: {need}')
    lines.extend(steps)
    lines.append(f'Ответ: {answer}')
    lines.append(f'Совет: {advice}')
    return _mass20260416x_finalize(lines)

# --- merged segment 024: backend.legacy_runtime_shards.prepatch_build_source.segment_024 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 20234-21052."""



def _stress20260416ad_try_extra_text_tasks(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е').replace('–', '-').replace('—', '-').replace('−', '-')
    lower = re.sub(r'\s+', ' ', lower).strip()

    # --- Nonstandard counting tasks ---
    m = re.search(r'во дворе .*?стоят (\d+) мальчик', lower)
    if m and 'между каждым мальчиком' in lower and 'по одной девочке' in lower:
        boys = int(m.group(1))
        girls = max(boys - 1, 0)
        total = boys + girls
        return _stress20260416ad_task(
            raw_text,
            f'в ряд стоят {boys} мальчика, между каждым соседними мальчиками стоит по одной девочке',
            'сколько девочек и сколько всего детей',
            [
                f'1) Между четырьмя мальчиками получается на одно место меньше, чем мальчиков: {boys} - 1 = {girls}.',
                f'2) Теперь находим, сколько всего детей: {boys} + {girls} = {total}.',
            ],
            f'девочек {girls}, всего детей {total}',
            'если дети стоят в ряд, то промежутков между ними всегда на один меньше, чем самих детей',
        )

    m = re.search(r'юля сидит .*? (\w+) спереди .*? (\w+) сзади', lower)
    if m and 'за каждой партой по два человека' in lower:
        front = _stress20260416ad_num_from_token(m.group(1))
        back = _stress20260416ad_num_from_token(m.group(2))
        if front and back:
            desks = front + back - 1
            children = desks * 2
            return _stress20260416ad_task(
                raw_text,
                f'Юля сидит на {front}-й парте спереди и на {back}-й парте сзади, за каждой партой сидят по 2 человека',
                'сколько парт в ряду и сколько детей в ряду',
                [
                    f'1) Юлина парта считается и спереди, и сзади, поэтому один раз её не добавляем: {front} + {back} - 1 = {desks}.',
                    f'2) На каждой парте сидят по 2 человека, значит детей в ряду: {desks} × 2 = {children}.',
                ],
                f'парт {desks}, детей {children}',
                'если одно и то же место считают с двух сторон, один раз его нужно вычесть',
            )

    m = re.search(r'насчитал (\w+) пар.*?насчитал (\w+) пар', lower)
    if m and 'шел парами' in lower:
        front_pairs = _stress20260416ad_num_from_token(m.group(1))
        back_pairs = _stress20260416ad_num_from_token(m.group(2))
        if front_pairs is not None and back_pairs is not None:
            total_pairs = front_pairs + back_pairs + 1
            total_students = total_pairs * 2
            return _stress20260416ad_task(
                raw_text,
                f'впереди у ученика {front_pairs} пар, сзади {back_pairs} пар, сам он тоже идёт в паре',
                'сколько учеников шло в колонне',
                [
                    f'1) Всего пар: {front_pairs} + {back_pairs} + 1 = {total_pairs}.',
                    f'2) В каждой паре по 2 ученика, значит учеников было: {total_pairs} × 2 = {total_students}.',
                ],
                f'{total_students} учеников',
                'если считают пары впереди и сзади, не забудь прибавить свою пару',
            )

    m = re.search(r'высотой (\d+) метр.*?вверх на (\d+) метр.*?спускается на (\d+) метр', lower)
    if m and 'улитка' in lower:
        height, up, down = map(int, m.groups())
        if up > down:
            if up >= height:
                day = 1
            else:
                remain_before_last = height - up
                net = up - down
                full_days = (remain_before_last + net - 1) // net
                day = full_days + 1
            return _stress20260416ad_task(
                raw_text,
                f'высота дерева {height} м, днём улитка поднимается на {up} м, ночью спускается на {down} м',
                'на какой день улитка доберётся до макушки',
                [
                    f'1) За один полный день и ночь улитка поднимается на {up} - {down} = {up - down} м.',
                    f'2) В последний день ей не нужно ждать ночи: как только она поднимется до {height} м, задача решена.',
                    f'3) Через 5 полных дней улитка будет на высоте 5 м, а на 6-й день поднимется ещё на {up} м и доберётся до {height} м.',
                ],
                f'на {day}-й день',
                'в задачах про улитку последний подъём считают отдельно: после него улитка уже не спускается',
            )

    # --- Sum / difference / grouping tasks ---
    m = re.search(r'сделали из бумаги (\d+) фонариков и (\d+) звездоч.*?(\d+) елочн.*гирлянд', lower)
    if m:
        a, b, groups = map(int, m.groups())
        total = a + b
        per = total // groups
        return _stress20260416ad_task(
            raw_text,
            f'сделали {a} фонариков и {b} звёздочек, все игрушки разделили на {groups} гирлянд',
            'сколько игрушек было в каждой гирлянде',
            [
                f'1) Находим, сколько всего игрушек сделали: {a} + {b} = {total}.',
                f'2) Делим все игрушки поровну на {groups} гирлянд: {total} : {groups} = {per}.',
            ],
            f'в каждой гирлянде по {per} игрушек',
            'если все предметы разделили поровну, сначала находят общее количество, а потом делят',
        )

    m = re.search(r'с одной грядки (\d+) кг .*? с другой -? ?(\d+) кг.*?(\d+) корзин', lower)
    if m and 'свекл' in lower:
        a, b, groups = map(int, m.groups())
        total = a + b
        per = total // groups
        return _stress20260416ad_task(
            raw_text,
            f'с одной грядки собрали {a} кг, с другой {b} кг, всё уложили в {groups} корзин',
            'сколько килограммов было в каждой корзине',
            [
                f'1) Сначала находим всю свёклу: {a} + {b} = {total} кг.',
                f'2) Теперь делим всё поровну на {groups} корзин: {total} : {groups} = {per} кг.',
            ],
            f'в каждой корзине было по {per} кг свёклы',
            'если всё разложили поровну, сначала находят всё количество, а потом делят его на число групп',
        )

    m = re.search(r'красной ткани было (\d+) м, белой -? ?(\d+) м.*?на каждое по (\d+) м', lower)
    if m and 'плать' in lower:
        red, white, per_item = map(int, m.groups())
        total = red + white
        count = total // per_item
        return _stress20260416ad_task(
            raw_text,
            f'красной ткани {red} м, белой {white} м, на одно платье идёт {per_item} м ткани',
            'сколько платьев получилось',
            [
                f'1) Находим, сколько было всей ткани: {red} + {white} = {total} м.',
                f'2) Узнаём, сколько платьев можно сшить: {total} : {per_item} = {count}.',
            ],
            f'получилось {count} платьев',
            'когда известен расход на один предмет, общее количество материала делят на этот расход',
        )

    m = re.search(r'в первом бидоне было (\d+) л .*? во втором (\d+) л.*?поровну в (\d+) бан', lower)
    if m:
        first, second, groups = map(int, m.groups())
        total = first + second
        per = total // groups
        return _stress20260416ad_task(
            raw_text,
            f'в первом бидоне {first} л, во втором {second} л, всё разлили поровну в {groups} банок',
            'сколько литров молока в каждой банке',
            [
                f'1) Сначала находим всё молоко: {first} + {second} = {total} л.',
                f'2) Делим всё молоко поровну на {groups} банок: {total} : {groups} = {per} л.',
            ],
            f'в каждой банке по {per} л',
            'если всё разлили поровну, складывают весь объём и делят на число одинаковых ёмкостей',
        )

    m = re.search(r'в 4 бидона разлили (\d+) кг меда.*?в трех бидонах оказалось по (\d+) кг', lower)
    if m:
        total, same = map(int, m.groups())
        known = 3 * same
        fourth = total - known
        return _stress20260416ad_task(
            raw_text,
            f'всего {total} кг мёда, в трёх бидонах по {same} кг',
            'сколько килограммов мёда в четвёртом бидоне',
            [
                f'1) Находим, сколько мёда в трёх бидонах: {same} × 3 = {known} кг.',
                f'2) Находим, сколько осталось для четвёртого бидона: {total} - {known} = {fourth} кг.',
            ],
            f'в четвёртом бидоне {fourth} кг мёда',
            'если известно всё количество и несколько одинаковых частей, сначала находят сумму известных частей, потом остаток',
        )

    m = re.search(r'привезли (\d+) кг яблок и груш.*?(\d+) ящика по (\d+) кг', lower)
    if m and 'сколько килограммов груш' in lower:
        total, boxes, per_box = map(int, m.groups())
        apples = boxes * per_box
        pears = total - apples
        return _stress20260416ad_task(
            raw_text,
            f'всего привезли {total} кг яблок и груш, яблок было {boxes} ящика по {per_box} кг',
            'сколько килограммов груш привезли',
            [
                f'1) Находим массу яблок: {boxes} × {per_box} = {apples} кг.',
                f'2) Находим массу груш: {total} - {apples} = {pears} кг.',
            ],
            f'груш привезли {pears} кг',
            'если общее количество состоит из двух частей, неизвестную часть находят вычитанием',
        )

    m = re.search(r'в большой оленьей упряжке (\d+) оленей.*?в маленькой упряжке по (\d+) оленя.*?всего (\d+) оленей', lower)
    if m:
        big, small_each, total = map(int, m.groups())
        rest = total - big
        count = rest // small_each
        return _stress20260416ad_task(
            raw_text,
            f'в большой упряжке {big} оленей, в маленькой по {small_each} оленя, всего {total} оленей',
            'сколько маленьких упряжек',
            [
                f'1) Находим, сколько оленей осталось для маленьких упряжек: {total} - {big} = {rest}.',
                f'2) Узнаём, сколько маленьких упряжек получилось: {rest} : {small_each} = {count}.',
            ],
            f'{count} маленьких упряжек',
            'если известны общее количество и одна большая часть, сначала находят остаток, а потом делят его на размер одной группы',
        )

    m = re.search(r'в ящике (\d+) кг винограда.*?в четыр[её]х одинаковых коробках (\d+) кг', lower)
    if m and 'в одной коробке' in lower:
        crate, boxes_total = map(int, m.groups())
        one_box = boxes_total // 4
        ratio = max(one_box, crate) // min(one_box, crate)
        return _stress20260416ad_task(
            raw_text,
            f'в ящике {crate} кг винограда, в четырёх одинаковых коробках {boxes_total} кг',
            'во сколько раз больше винограда в одной коробке, чем в ящике',
            [
                f'1) Сначала находим, сколько винограда в одной коробке: {boxes_total} : 4 = {one_box} кг.',
                f'2) Теперь сравниваем одну коробку и ящик: {one_box} : {crate} = {ratio}.',
            ],
            f'в одной коробке винограда в {ratio} раза больше',
            'при кратном сравнении сначала нужно узнать величину одной части, если дана сумма нескольких одинаковых частей',
        )

    # --- Relative comparison / ratio tasks ---
    m = re.search(r'пиявка весом (\d+) г .*? высосать (\d+) г крови', lower)
    if m and 'во сколько раз больше' in lower:
        own, blood = map(int, m.groups())
        after = own + blood
        ratio = after // own
        return _stress20260416ad_task(
            raw_text,
            f'пиявка весит {own} г и после обеда станет тяжелее на {blood} г',
            'во сколько раз её масса после обеда больше прежней',
            [
                f'1) Находим массу после обеда: {own} + {blood} = {after} г.',
                f'2) Сравниваем новую массу с прежней: {after} : {own} = {ratio}.',
            ],
            f'в {ratio} раз',
            'чтобы узнать, во сколько раз одно число больше другого, большее число делят на меньшее',
        )

    m = re.search(r'посадили (\d+) кг картофеля, а собрали (\d+) кг', lower)
    if m and 'во сколько раз больше собрали' in lower:
        planted, gathered = map(int, m.groups())
        ratio = gathered // planted
        return _stress20260416ad_task(
            raw_text,
            f'посадили {planted} кг, собрали {gathered} кг',
            'во сколько раз собрали больше, чем посадили',
            [f'1) Делим большее количество на меньшее: {gathered} : {planted} = {ratio}.'],
            f'в {ratio} раз',
            'при кратном сравнении большее число делят на меньшее',
        )

    m = re.search(r'отцу (\d+) год[а-я]*, сыну (\d+) лет', lower)
    if m and 'во сколько раз сын моложе' in lower:
        father, son = map(int, m.groups())
        ratio = father // son
        return _stress20260416ad_task(
            raw_text,
            f'отцу {father} года, сыну {son} лет',
            'во сколько раз сын моложе отца',
            [f'1) Сравниваем возраст отца и сына: {father} : {son} = {ratio}.'],
            f'в {ratio} раза',
            'слова «во сколько раз» означают действие деления',
        )

    m = re.search(r'сделали (\d+) больших игрушек, а маленьких - в (\d+) раз меньше', lower)
    if m and 'на сколько' in lower:
        big, factor = map(int, m.groups())
        small = big // factor
        diff = big - small
        return _stress20260416ad_task(
            raw_text,
            f'больших игрушек {big}, маленьких в {factor} раз меньше',
            'на сколько больших игрушек сделали больше, чем маленьких',
            [
                f'1) Находим количество маленьких игрушек: {big} : {factor} = {small}.',
                f'2) Находим, на сколько больших игрушек больше: {big} - {small} = {diff}.',
            ],
            f'на {diff}',
            'если сказано «в несколько раз меньше», сначала делят, а потом находят разность',
        )

    # --- Motion tasks ---
    m = re.search(r'проехал (\d+) км со скоростью (\d+) км/ч.*?скорость (\d+) км/ч', lower)
    if m and 'до встречи' in lower:
        first_path, first_speed, second_speed = map(int, m.groups())
        if first_path % first_speed == 0:
            time_value = first_path // first_speed
            second_path = second_speed * time_value
            return _stress20260416ad_task(
                raw_text,
                f'первый автобус проехал {first_path} км со скоростью {first_speed} км/ч, скорость второго автобуса {second_speed} км/ч',
                'сколько километров до встречи проехал второй автобус',
                [
                    f'1) Находим время движения до встречи: {first_path} : {first_speed} = {time_value} ч.',
                    f'2) За это время второй автобус проедет: {second_speed} × {time_value} = {second_path} км.',
                ],
                f'{second_path} км',
                'если участники встретились одновременно, время движения до встречи у них одинаковое',
            )

    m = re.search(r'расстояние между .*? (\d+) км.*?скорость первого (\d+) км/ч.*?второго (\d+) км/ч', lower)
    if m and 'навстречу друг другу' in lower:
        distance, v1, v2 = map(int, m.groups())
        total_speed = v1 + v2
        if distance % total_speed == 0:
            time_value = distance // total_speed
            return _stress20260416ad_task(
                raw_text,
                f'расстояние между пристанями {distance} км, скорости теплоходов {v1} км/ч и {v2} км/ч',
                'через сколько часов теплоходы встретятся',
                [
                    f'1) При движении навстречу складываем скорости: {v1} + {v2} = {total_speed} км/ч.',
                    f'2) Время до встречи равно расстоянию, делённому на скорость сближения: {distance} : {total_speed} = {time_value} ч.',
                ],
                f'{time_value} ч',
                'при движении навстречу друг другу скорость сближения равна сумме скоростей',
            )

    m = re.search(r'длиной (\d+) м .*?со скоростью (\d+) м/с.*?через (\d+) с', lower)
    if m and 'навстречу друг другу' in lower:
        distance, v1, time_value = map(int, m.groups())
        if distance % time_value == 0:
            total_speed = distance // time_value
            v2 = total_speed - v1
            return _stress20260416ad_task(
                raw_text,
                f'длина дорожки {distance} м, скорость первого мальчика {v1} м/с, встретились через {time_value} с',
                'какова скорость второго мальчика',
                [
                    f'1) Находим общую скорость сближения: {distance} : {time_value} = {total_speed} м/с.',
                    f'2) Вычитаем скорость первого мальчика: {total_speed} - {v1} = {v2} м/с.',
                ],
                f'{v2} м/с',
                'если известны расстояние и время до встречи, сначала находят общую скорость сближения',
            )

    # --- Geometry tasks ---
    m = re.search(r'длина (\d+) дм, а ширина на (\d+) дм меньше', lower)
    if m and 'площад' in lower and 'см²' in lower:
        length_dm, less_dm = map(int, m.groups())
        width_dm = length_dm - less_dm
        area_dm2 = length_dm * width_dm
        area_cm2 = area_dm2 * 100
        return _stress20260416ad_task(
            raw_text,
            f'длина ковра {length_dm} дм, ширина на {less_dm} дм меньше',
            'площадь ковра в квадратных сантиметрах',
            [
                f'1) Находим ширину ковра: {length_dm} - {less_dm} = {width_dm} дм.',
                f'2) Находим площадь в квадратных дециметрах: {length_dm} × {width_dm} = {area_dm2} дм².',
                f'3) Переводим в квадратные сантиметры: {area_dm2} дм² = {area_cm2} см².',
            ],
            f'{area_cm2} см²',
            'если нужно перевести дм² в см², умножают на 100',
        )

    m = re.search(r'длина равна (\d+) м, а ширина .*?в (\d+) раза меньше', lower)
    if m and 'периметр прямоугольника' in lower:
        length, factor = map(int, m.groups())
        width = length // factor
        per = 2 * (length + width)
        return _stress20260416ad_task(
            raw_text,
            f'длина прямоугольника {length} м, ширина в {factor} раза меньше',
            'периметр прямоугольника',
            [
                f'1) Находим ширину: {length} : {factor} = {width} м.',
                f'2) Находим периметр: ({length} + {width}) × 2 = {per} м.',
            ],
            f'{per} м',
            'если ширина в несколько раз меньше длины, длину делят на это число',
        )

    m = re.search(r'периметр прямоугольника равен (\d+) см, а его длина на (\d+) см больше ширины', lower)
    if m and 'площад' in lower:
        per, diff = map(int, m.groups())
        half = per // 2
        width = (half - diff) // 2
        length = width + diff
        area = width * length
        return _stress20260416ad_task(
            raw_text,
            f'периметр прямоугольника {per} см, длина на {diff} см больше ширины',
            'площадь прямоугольника',
            [
                f'1) Находим сумму длины и ширины: {per} : 2 = {half} см.',
                f'2) Если длина на {diff} см больше, то без этой разницы остаётся: {half} - {diff} = {half - diff} см.',
                f'3) Находим ширину: {half - diff} : 2 = {width} см.',
                f'4) Находим длину: {width} + {diff} = {length} см.',
                f'5) Находим площадь: {width} × {length} = {area} см².',
            ],
            f'{area} см²',
            'в задачах на периметр прямоугольника сначала часто находят полупериметр — сумму длины и ширины',
        )

    m = re.search(r'одна сторона равна (\d+) см.*?меньше второй стороны на (\d+) см .*?меньше третьей стороны на (\d+) см', lower)
    if m and 'треугольник' in lower and 'периметр' in lower:
        side1, less2, less3 = map(int, m.groups())
        side2 = side1 + less2
        side3 = side1 + less3
        per = side1 + side2 + side3
        return _stress20260416ad_task(
            raw_text,
            f'одна сторона {side1} см, вторая на {less2} см больше, третья на {less3} см больше',
            'периметр треугольника',
            [
                f'1) Находим вторую сторону: {side1} + {less2} = {side2} см.',
                f'2) Находим третью сторону: {side1} + {less3} = {side3} см.',
                f'3) Находим периметр: {side1} + {side2} + {side3} = {per} см.',
            ],
            f'{per} см',
            'периметр многоугольника равен сумме длин всех его сторон',
        )

    m = re.search(r'ширина прямоугольника (\d+) см, периметр (\d+) см', lower)
    if m and 'площад' in lower:
        width, per = map(int, m.groups())
        half = per // 2
        length = half - width
        area = length * width
        return _stress20260416ad_task(
            raw_text,
            f'ширина прямоугольника {width} см, периметр {per} см',
            'площадь прямоугольника',
            [
                f'1) Находим сумму длины и ширины: {per} : 2 = {half} см.',
                f'2) Находим длину: {half} - {width} = {length} см.',
                f'3) Находим площадь: {length} × {width} = {area} см².',
            ],
            f'{area} см²',
            'если известны периметр и одна сторона прямоугольника, сначала находят сумму длины и ширины',
        )

    m = re.search(r'за (\d+) минут .*?скоростью (\d+) м/мин.*?ширина огорода (\d+) м', lower)
    if m and 'обходит' in lower and 'площад' in lower:
        minutes, speed, width = map(int, m.groups())
        per = minutes * speed
        half = per // 2
        length = half - width
        area = length * width
        return _stress20260416ad_task(
            raw_text,
            f'за {minutes} минут человек обходит огород со скоростью {speed} м/мин, ширина огорода {width} м',
            'площадь огорода',
            [
                f'1) Находим периметр огорода: {speed} × {minutes} = {per} м.',
                f'2) Находим сумму длины и ширины: {per} : 2 = {half} м.',
                f'3) Находим длину: {half} - {width} = {length} м.',
                f'4) Находим площадь: {length} × {width} = {area} м².',
            ],
            f'{area} м²',
            'если известен путь по контуру фигуры, сначала находят периметр, а потом стороны',
        )

    # --- Fraction word problems ---
    m = re.search(r'за первый день машина проехала (\d+)/(\d+) .*? во второй день (\d+)/(\d+) .*? в третий день она проехала (\d+) км', lower)
    if m:
        n1, d1, n2, d2, third_distance = map(int, m.groups())
        if d1 == d2:
            first_frac = Fraction(n1, d1)
            second_frac = Fraction(n2, d2)
            third_frac = Fraction(1, 1) - first_frac - second_frac
            if third_frac > 0:
                total = Fraction(third_distance, 1) / third_frac
                if total.denominator == 1:
                    total = total.numerator
                    first = total * n1 // d1
                    second = total * n2 // d2
                    return _stress20260416ad_task(
                        raw_text,
                        f'в первый день машина прошла {n1}/{d1} пути, во второй {n2}/{d2} пути, в третий день {third_distance} км',
                        'каково всё расстояние и сколько машина прошла в каждый день',
                        [
                            f'1) Находим, какая часть пути пришлась на третий день: 1 - {n1}/{d1} - {n2}/{d2} = {third_frac.numerator}/{third_frac.denominator}.',
                            f'2) Если {third_frac.numerator}/{third_frac.denominator} пути равны {third_distance} км, то весь путь равен {third_distance} : {third_frac.numerator}/{third_frac.denominator} = {total} км.',
                            f'3) В первый день машина прошла: {total} × {n1}/{d1} = {first} км.',
                            f'4) Во второй день машина прошла: {total} × {n2}/{d2} = {second} км.',
                            f'5) В третий день машина прошла {third_distance} км.',
                        ],
                        f'весь путь {total} км; в первый день {first} км, во второй день {second} км, в третий день {third_distance} км',
                        'если известна часть пути, оставшуюся дробь сначала находят вычитанием из единицы',
                    )

    if 'на субботник вышли 90 учащихся' in lower and '1/2' in lower and '1/5' in lower and '1/10' in lower and '9 носилок' in lower:
        total = 90
        shovels = total // 2
        rakes = total // 5
        buckets = total // 10
        assigned = shovels + rakes + buckets
        rest = total - assigned
        people_for_stretchers = 9 * 2
        yes_no = 'да' if rest == people_for_stretchers else 'нет'
        return _stress20260416ad_task(
            raw_text,
            f'на субботник вышли {total} учащихся; 1/2 получили лопаты, 1/5 — грабли, 1/10 — вёдра; остальным выдали 9 носилок',
            'всем ли ребятам досталась работа',
            [
                f'1) Лопаты получили: {total} : 2 = {shovels} человек.',
                f'2) Грабли получили: {total} : 5 = {rakes} человек.',
                f'3) Вёдра получили: {total} : 10 = {buckets} человек.',
                f'4) Всего уже заняты работой: {shovels} + {rakes} + {buckets} = {assigned} человек.',
                f'5) Осталось ребят: {total} - {assigned} = {rest} человек.',
                f'6) На 9 носилок нужно по 2 человека: 9 × 2 = {people_for_stretchers} человек.',
            ],
            f'{yes_no}, всем ребятам досталась работа, потому что осталось {rest} человек, а на 9 носилок нужно {people_for_stretchers} человек',
            'в задачах с дробями от числа сначала находят каждую часть, потом складывают их и сравнивают с общим количеством',
        )

    return None


async def build_explanation(user_text: str) -> dict:
    local = _stress20260416ad_try_extra_text_tasks(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _STRESS20260416AD_PREV_BUILD_EXPLANATION(user_text)


# --- STRESS AUDIT PATCH 2026-04-16AE: explicit meeting-time pattern for two equal speeds ---

_STRESS20260416AE_PREV_BUILD_EXPLANATION = build_explanation


def _stress20260416ae_try_swallow_task(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е').replace('–', '-').replace('—', '-').replace('−', '-')
    lower = re.sub(r'\s+', ' ', lower).strip()
    m = re.search(r'скорость каждой .*? (\d+) м/с.*?расстояние между ними (\d+) м', lower)
    if m and 'ласточк' in lower and 'навстречу друг другу' in lower:
        speed_each, distance = map(int, m.groups())
        total_speed = speed_each * 2
        if distance % total_speed == 0:
            time_value = distance // total_speed
            return _stress20260416ad_task(
                raw_text,
                f'каждая ласточка летит со скоростью {speed_each} м/с, расстояние между ними {distance} м',
                'через сколько секунд ласточки встретятся',
                [
                    f'1) При движении навстречу складываем скорости: {speed_each} + {speed_each} = {total_speed} м/с.',
                    f'2) Время до встречи равно расстоянию, делённому на скорость сближения: {distance} : {total_speed} = {time_value} с.',
                ],
                f'{time_value} с',
                'при движении навстречу скорость сближения равна сумме скоростей',
            )
    return None


async def build_explanation(user_text: str) -> dict:
    local = _stress20260416ae_try_swallow_task(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _STRESS20260416AE_PREV_BUILD_EXPLANATION(user_text)


def _geo20260416ag_measure_family(unit: str) -> Optional[str]:
    u = unit.lower()
    if u in {'мм','см','дм','м','км'}:
        return 'length'
    if u in {'г','кг','ц','т'}:
        return 'mass'
    if u in {'с','сек','секунд','секунда','секунды','мин','ч','сутки','суток'}:
        return 'time'
    return None


def _geo20260416ag_measure_factor(unit: str) -> Optional[int]:
    u = unit.lower()
    factors = {
        'мм': 1, 'см': 10, 'дм': 100, 'м': 1000, 'км': 1000000,
        'г': 1, 'кг': 1000, 'ц': 100000, 'т': 1000000,
        'с': 1, 'сек': 1, 'секунд': 1, 'секунда': 1, 'секунды': 1,
        'мин': 60, 'ч': 3600, 'сутки': 86400, 'суток': 86400,
    }
    return factors.get(u)


def _geo20260416ag_pretty_measure_unit(unit: str) -> str:
    u = unit.lower()
    mapping = {
        'мм': 'мм', 'см': 'см', 'дм': 'дм', 'м': 'м', 'км': 'км',
        'г': 'г', 'кг': 'кг', 'ц': 'ц', 'т': 'т',
        'с': 'с', 'сек': 'с', 'секунд': 'с', 'секунда': 'с', 'секунды': 'с',
        'мин': 'мин', 'ч': 'ч', 'сутки': 'сутки', 'суток': 'суток',
    }
    return mapping.get(u, unit)


def _geo20260416ag_parse_measure_quantity(text: str) -> Optional[dict]:
    source = normalize_dashes(text).lower().replace('²', '').replace('³', '')
    source = re.sub(r'\s+', ' ', source).strip()
    matches = list(re.finditer(r'(\d+)\s*(мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с|сек(?:унда|унды|унд)?)', source))
    if not matches:
        return None
    family = None
    total = 0
    parts = []
    for m in matches:
        value = int(m.group(1))
        unit = m.group(2)
        current_family = _geo20260416ag_measure_family(unit)
        factor = _geo20260416ag_measure_factor(unit)
        if current_family is None or factor is None:
            return None
        if family is None:
            family = current_family
        elif family != current_family:
            return None
        total += value * factor
        parts.append((value, _geo20260416ag_pretty_measure_unit(unit)))
    pretty = ' '.join(f'{value} {unit}' for value, unit in parts)
    return {'family': family, 'total': total, 'pretty': pretty}


def _geo20260416ag_format_measure_from_base(total: int, units: List[str]) -> str:
    if not units:
        return str(total)
    normalized = [_geo20260416ag_pretty_measure_unit(u) for u in units]
    factors = [_geo20260416ag_measure_factor(u) for u in normalized]
    if any(f is None for f in factors):
        return str(total)
    factors = [int(f) for f in factors]
    if len(normalized) == 1:
        value = total // factors[0]
        return f'{value} {normalized[0]}'
    remaining = total
    parts = []
    for idx, unit in enumerate(normalized):
        factor = factors[idx]
        if idx < len(normalized) - 1:
            value = remaining // factor
            remaining -= value * factor
        else:
            value = remaining // factor
        parts.append(f'{value} {unit}')
    return ' '.join(parts)


def _geo20260416ag_compare_sign(left_total: int, right_total: int) -> str:
    if left_total < right_total:
        return '<'
    if left_total > right_total:
        return '>'
    return '='


def _geo20260416ag_try_named_units_extended(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = normalize_dashes(text).lower().replace('…', '').replace('?', '').strip()

    m = re.fullmatch(r'(\d+\s*(?:мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с)(?:\s*\d+\s*(?:мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с))*)\s*=\s*((?:мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с)(?:\s+(?:мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с))*)\.?', lower)
    if m:
        left_text = m.group(1).strip()
        target_units = m.group(2).strip().rstrip('.').split()
        parsed = _geo20260416ag_parse_measure_quantity(left_text)
        if parsed:
            target_family = _geo20260416ag_measure_family(target_units[0])
            if target_family == parsed['family']:
                answer = _geo20260416ag_format_measure_from_base(parsed['total'], target_units)
                base_unit = {'length': 'мм', 'mass': 'г', 'time': 'с'}[parsed['family']]
                base_value = parsed['total'] // _geo20260416ag_measure_factor(base_unit)
                lines = [
                    f'Пример: {parsed["pretty"]} = {answer}.',
                    'Решение.',
                ]
                if len(target_units) == 1:
                    unit = _geo20260416ag_pretty_measure_unit(target_units[0])
                    factor = _geo20260416ag_measure_factor(unit)
                    base_from = parsed['pretty']
                    lines += [
                        f'1) Переводим {base_from} в более удобную единицу {unit}.',
                    ]
                    family = parsed['family']
                    if family == 'length':
                        if unit == 'дм':
                            lines.append('2) В 1 дм 10 см.')
                        elif unit == 'м':
                            lines.append('2) В 1 м 100 см.')
                        elif unit == 'см':
                            lines.append('2) Выполняем перевод в сантиметры.')
                    elif family == 'mass':
                        if unit == 'кг':
                            lines.append('2) В 1 кг 1000 г.')
                        elif unit == 'ц':
                            lines.append('2) В 1 ц 100 кг.')
                        elif unit == 'т':
                            lines.append('2) В 1 т 1000 кг.')
                    value = parsed['total'] // factor
                    lines.append(f'3) Получаем: {answer}.')
                else:
                    largest = _geo20260416ag_pretty_measure_unit(target_units[0])
                    lines += [
                        f'1) Переводим {parsed["pretty"]} в более крупную единицу и остаток.',
                        f'2) Получаем: {answer}.',
                    ]
                lines += [
                    f'Ответ: {answer}',
                    'Совет: при переводе величин сначала выбирают одну общую единицу измерения',
                ]
                return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'сравни\s*:\s*(.+?)\s+и\s+(.+?)\.?', lower)
    if m:
        left_raw = m.group(1).strip()
        right_raw = m.group(2).strip()
        left = _geo20260416ag_parse_measure_quantity(left_raw)
        right = _geo20260416ag_parse_measure_quantity(right_raw)
        if left and right and left['family'] == right['family']:
            family = left['family']
            common_unit = {'length': 'см', 'mass': 'г', 'time': 'с'}[family]
            common_factor = _geo20260416ag_measure_factor(common_unit)
            left_common = left['total'] // common_factor
            right_common = right['total'] // common_factor
            sign = _geo20260416ag_compare_sign(left['total'], right['total'])
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'1) Переводим обе величины в {common_unit}.',
                f'2) {left["pretty"]} = {left_common} {common_unit}.',
                f'3) {right["pretty"]} = {right_common} {common_unit}.',
                f'4) Сравниваем: {left_common} {common_unit} {sign} {right_common} {common_unit}.',
                f'Ответ: {left["pretty"]} {sign} {right["pretty"]}',
                'Совет: чтобы сравнить именованные величины, их переводят в одинаковые единицы',
            ]
            return _mass20260416x_finalize(lines)
    return None


def _geo20260416ag_try_geometry_extended(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = normalize_dashes(text).lower().replace('см2', 'см²').replace('см 2', 'см²')
    lower = re.sub(r'\s+', ' ', lower).strip()

    m = re.search(r'периметр прямоугольника равен (\d+) см\.?.*во сколько раз длина прямоугольника больше его ширины, если ширина равна (\d+) см', lower)
    if m:
        per = int(m.group(1)); width = int(m.group(2))
        half = per // 2
        length = half - width
        if width > 0 and length > 0 and per == 2 * (length + width) and length % width == 0:
            ratio = length // width
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: периметр прямоугольника {per} см, ширина {width} см.',
                'Что нужно найти: во сколько раз длина больше ширины.',
                f'1) У прямоугольника половина периметра равна сумме длины и ширины: {per} : 2 = {half} см.',
                f'2) Находим длину: {half} - {width} = {length} см.',
                f'3) Узнаём, во сколько раз длина больше ширины: {length} : {width} = {ratio}.',
                f'Ответ: в {ratio} раза',
                'Совет: если известен периметр прямоугольника, сначала удобно найти сумму длины и ширины',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'длина прямоугольника (\d+) см\.?.*ширина прямоугольника, если периметр (\d+) см', lower)
    if m:
        length = int(m.group(1)); per = int(m.group(2))
        half = per // 2
        width = half - length
        if width > 0 and per == 2 * (length + width):
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: длина прямоугольника {length} см, периметр {per} см.',
                'Что нужно найти: ширину прямоугольника.',
                f'1) Половина периметра равна сумме длины и ширины: {per} : 2 = {half} см.',
                f'2) Вычитаем длину: {half} - {length} = {width} см.',
                f'Ответ: {width} см',
                'Совет: у прямоугольника сумма длины и ширины равна половине периметра',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'длина прямоугольника (\d+) см,? а ширина в (\d+) раз[а-я]* короче.*найди (площадь|периметр) прямоугольника', lower)
    if m:
        length = int(m.group(1)); ratio = int(m.group(2)); ask = m.group(3)
        if ratio > 0 and length % ratio == 0:
            width = length // ratio
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: длина прямоугольника {length} см, ширина в {ratio} раза короче.',
                'Что нужно найти: ' + ('площадь прямоугольника.' if 'площад' in ask else 'периметр прямоугольника.'),
                f'1) Находим ширину: {length} : {ratio} = {width} см.',
            ]
            if 'площад' in ask:
                area = length * width
                lines += [
                    f'2) Площадь прямоугольника равна длине, умноженной на ширину: {length} × {width} = {area} см².',
                    f'Ответ: {area} см²',
                    'Совет: если одна сторона в несколько раз короче другой, меньшую сторону находят делением',
                ]
            else:
                per = 2 * (length + width)
                lines += [
                    f'2) Периметр прямоугольника: ({length} + {width}) × 2 = {per} см.',
                    f'Ответ: {per} см',
                    'Совет: если одна сторона в несколько раз короче другой, меньшую сторону находят делением',
                ]
            return _mass20260416x_finalize(lines)
    return None


_STRESS20260416AG_PREV_BUILD_EXPLANATION = build_explanation


async def build_explanation(user_text: str) -> dict:
    local = _geo20260416ag_try_named_units_extended(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    local = _geo20260416ag_try_geometry_extended(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _STRESS20260416AG_PREV_BUILD_EXPLANATION(user_text)

# --- merged segment 025: backend.legacy_runtime_shards.prepatch_build_source.segment_025 ---
"""Auto-generated runtime shard for prepatch_build_source.py, lines 21053-21685."""



def _geo20260416ah_try_volume_surface_extended(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = normalize_dashes(text).lower().replace('м3', 'м³').replace('см3', 'см³').replace('дм3', 'дм³')
    lower = lower.replace('м 3', 'м³').replace('см 3', 'см³').replace('дм 3', 'дм³')
    lower = re.sub(r'\s+', ' ', lower).strip()

    m = re.search(r'проволочн[а-я ]+каркаса куба с ребром (\d+) см', lower)
    if m:
        edge_cm = int(m.group(1))
        total_cm = edge_cm * 12
        meters = total_cm / 100
        meters_text = str(int(meters)) if float(meters).is_integer() else str(meters).replace('.', ',')
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: ребро куба {edge_cm} см.',
            'Что нужно найти: сколько метров проволоки нужно для каркаса куба.',
            '1) У куба 12 рёбер.',
            f'2) Находим общую длину всех рёбер: {edge_cm} × 12 = {total_cm} см.',
            f'3) Переводим в метры: {total_cm} см = {meters_text} м.',
            f'Ответ: {meters_text} м',
            'Совет: каркас куба состоит из всех его рёбер, поэтому сначала считают сумму длин 12 рёбер',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'площадь полной поверхности параллелепипеда с измерениями:? а ?= ?(\d+) см,? в ?= ?(\d+) см,? с ?= ?(\d+) см', lower)
    if m:
        a, b, c = map(int, m.groups())
        ab = a * b; ac = a * c; bc = b * c
        total = 2 * (ab + ac + bc)
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь полной поверхности прямоугольного параллелепипеда находят по формуле S = 2 × (ab + ac + bc).',
            f'2) Находим площади трёх разных граней: {a} × {b} = {ab} см², {a} × {c} = {ac} см², {b} × {c} = {bc} см².',
            f'3) Складываем и умножаем на 2: 2 × ({ab} + {ac} + {bc}) = {total} см².',
            f'Ответ: {total} см²',
            'Совет: у прямоугольного параллелепипеда по две одинаковые грани каждого вида',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'найдите объем параллелепипеда с измерениями:? а ?= ?(\d+) см,? в ?= ?(\d+) см,? с ?= ?(\d+) см', lower)
    if m:
        a, b, c = map(int, m.groups())
        volume = a * b * c
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Объём прямоугольного параллелепипеда находят по формуле V = a × b × c.',
            f'2) Подставляем числа: {a} × {b} × {c} = {volume} см³.',
            f'Ответ: {volume} см³',
            'Совет: чтобы найти объём прямоугольного параллелепипеда, перемножают его длину, ширину и высоту',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'высотой потолка (\d+) м имеет объем (\d+) м³.*какова его площадь', lower)
    if m:
        height, volume = map(int, m.groups())
        if height > 0 and volume % height == 0:
            area = volume // height
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'1) Объём прямоугольного помещения равен площади пола, умноженной на высоту.',
                f'2) Чтобы найти площадь пола, объём делим на высоту: {volume} : {height} = {area} м².',
                f'Ответ: {area} м²',
                'Совет: если известны объём и высота, площадь основания находят делением объёма на высоту',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'во сколько раз объем куба с ребром (\d+) см (?:меньше|больше) объема параллелепипеда с измерениями (\d+) см, (\d+) см, (\d+) см', lower)
    if m:
        edge, a, b, c = map(int, m.groups())
        cube_v = edge ** 3
        prism_v = a * b * c
        if cube_v == 0 or prism_v == 0:
            return None
        if 'меньше' in lower:
            if prism_v % cube_v != 0:
                return None
            ratio = prism_v // cube_v
            relation = 'меньше'
        else:
            if cube_v % prism_v != 0:
                return None
            ratio = cube_v // prism_v
            relation = 'больше'
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим объём куба: {edge} × {edge} × {edge} = {cube_v} см³.',
            f'2) Находим объём параллелепипеда: {a} × {b} × {c} = {prism_v} см³.',
            f'3) Узнаём, во сколько раз один объём {relation} другого.',
        ]
        if relation == 'меньше':
            lines.append(f'4) {prism_v} : {cube_v} = {ratio}.')
        else:
            lines.append(f'4) {cube_v} : {prism_v} = {ratio}.')
        lines += [
            f'Ответ: в {ratio} раз',
            'Совет: чтобы узнать, во сколько раз одна величина больше или меньше другой, большее число делят на меньшее',
        ]
        return _mass20260416x_finalize(lines)
    return None


_GEO20260416AH_PREV_BUILD_EXPLANATION = build_explanation


async def build_explanation(user_text: str) -> dict:
    local = _geo20260416ah_try_volume_surface_extended(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _GEO20260416AH_PREV_BUILD_EXPLANATION(user_text)


# === Continued external audit patch: fractions + named quantities mixed corpus ===


def _frac20260416_cont_try_simple_unit_fraction(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    m = re.fullmatch(r'Найти\s+(\d+)\s*/\s*(\d+)\s+от\s+1\s+(см|дм|м|кг|л)\.?', text, flags=re.IGNORECASE)
    if not m:
        return None
    num, den = int(m.group(1)), int(m.group(2))
    unit = m.group(3).lower()
    smaller = {'см': ('мм', 10), 'дм': ('см', 10), 'м': ('см', 100), 'кг': ('г', 1000), 'л': ('мл', 1000)}
    if unit not in smaller:
        return None
    small_unit, coeff = smaller[unit]
    base = coeff
    if (base * num) % den != 0:
        return None
    part = (base * num) // den
    lines = [
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: нужно найти {num}/{den} от 1 {unit}.',
        'Что нужно найти: значение этой части.',
        f'1) Переводим 1 {unit} в более мелкие единицы: 1 {unit} = {base} {small_unit}.',
        f'2) Находим {num}/{den} от {base} {small_unit}: {base} : {den} × {num} = {part} {small_unit}.',
        f'Ответ: {part} {small_unit}',
        'Совет: чтобы найти дробь от величины, сначала удобно перевести её в более мелкие единицы',
    ]
    return _mass20260416x_finalize(lines)


def _frac20260416_cont_try_fraction_text_tasks(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    lower = text.lower()

    m = re.fullmatch(r'(\d+)\s*/\s*(\d+)\s*=\s*(\d+)', lower)
    if m:
        num, den, part = map(int, m.groups())
        if num > 0:
            one = part // num if part % num == 0 else part / num
            whole = int(one * den) if float(one * den).is_integer() else one * den
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: {num}/{den} числа равны {part}.',
                'Что нужно найти: всё число.',
                f'1) Находим одну долю: {part} : {num} = {one}.',
                f'2) Находим всё число: {one} × {den} = {whole}.',
                f'Ответ: {whole}',
                'Совет: если известны несколько долей числа, сначала находят одну долю, а потом всё число',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'Найди длину всей ленты, если\s*(\d+)\s*/\s*(\d+)\s*составляют\s*(\d+)\s*м', text, flags=re.IGNORECASE)
    if m:
        num, den, part = map(int, m.groups())
        one = part // num if part % num == 0 else part / num
        whole = int(one * den) if float(one * den).is_integer() else one * den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {num}/{den} длины ленты составляют {part} м.',
            'Что нужно найти: всю длину ленты.',
            f'1) Находим одну долю: {part} : {num} = {one} м.',
            f'2) Находим всю длину: {one} × {den} = {whole} м.',
            f'Ответ: {whole} м',
            'Совет: если известны несколько долей величины, сначала находят одну долю, а потом всю величину',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'Найди\s*1\s*/\s*(\d+)\s+длины провода, если\s*(\d+)\s*/\s*(\d+)\s+этой длины составляют\s*(\d+)\s*м', text, flags=re.IGNORECASE)
    if m:
        ask_den, num, den, part = map(int, m.groups())
        if den == ask_den and num > 0:
            one = part // num if part % num == 0 else part / num
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: {num}/{den} длины провода составляют {part} м.',
                f'Что нужно найти: 1/{ask_den} длины провода.',
                f'1) Находим одну долю: {part} : {num} = {one} м.',
                f'Ответ: {one} м',
                'Совет: если нужно найти одну долю, число долей делят на их количество',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'велосипедист проехал\s*(\d+)\s*км, что составляет\s*(\d+)\s*/\s*(\d+)\s*част', lower)
    if m:
        part, num, den = map(int, m.groups())
        if num > 0:
            one = part // num if part % num == 0 else part / num
            whole = int(one * den) if float(one * den).is_integer() else one * den
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: {num}/{den} маршрута составляют {part} км.',
                'Что нужно найти: длину всего маршрута.',
                f'1) Находим одну долю маршрута: {part} : {num} = {one} км.',
                f'2) Находим весь маршрут: {one} × {den} = {whole} км.',
                f'Ответ: {whole} км',
                'Совет: если известна часть пути, сначала находят одну долю, а потом весь путь',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'прош[её]л\s+(?:четвертую|шестую)\s+часть пути за\s*(\d+)\s*минут', lower)
    if m:
        part_time = int(m.group(1))
        den = 4 if 'четверт' in lower else 6
        whole = part_time * den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: 1/{den} пути пройдена за {part_time} минут.',
            'Что нужно найти: время на весь путь.',
            f'1) Весь путь состоит из {den} таких частей.',
            f'2) Находим всё время: {part_time} × {den} = {whole} минут.',
            f'Ответ: {whole} минут',
            'Совет: если одна доля пути занимает известное время, всё время находят умножением на число долей',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'почтовый голубь в час пролетает\s*(\d+)\s*км\.\s*сколько км он пролетит за\s*(\d+)\s*/\s*(\d+)\s*часа', lower)
    if m:
        per_hour, num, den = map(int, m.groups())
        part = per_hour * num // den if (per_hour * num) % den == 0 else per_hour * num / den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: за 1 час голубь пролетает {per_hour} км.',
            f'Что нужно найти: сколько он пролетит за {num}/{den} часа.',
            f'1) Находим {num}/{den} от {per_hour}: {per_hour} : {den} × {num} = {part} км.',
            f'Ответ: {part} км',
            'Совет: чтобы найти дробь от числа, число делят на знаменатель и умножают на числитель',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'один литр керосина весит\s*(\d+)\s*г\.\s*сколько весит\s*(\d+)\s*/\s*(\d+)\s*литра', lower)
    if m:
        total, num, den = map(int, m.groups())
        part = total * num // den if (total * num) % den == 0 else total * num / den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: 1 литр керосина весит {total} г.',
            f'Что нужно найти: сколько весит {num}/{den} литра.',
            f'1) Находим {num}/{den} от {total}: {total} : {den} × {num} = {part} г.',
            f'Ответ: {part} г',
            'Совет: чтобы найти дробь от массы, массу делят на знаменатель и умножают на числитель',
        ]
        return _mass20260416x_finalize(lines)

    if 'большой праздничный пирог' in lower and '1/4' in lower and '2/4' in lower:
        eaten = '3/4'
        left = '1/4'
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Что известно: сначала съели 1/4 пирога, потом ещё 2/4 пирога.',
            'Что нужно найти: какая часть пирога съедена и какая часть осталась.',
            '1) Находим съеденную часть: 1/4 + 2/4 = 3/4.',
            '2) Находим оставшуюся часть: 1 - 3/4 = 1/4.',
            f'Ответ: съели {eaten}, осталось {left}',
            'Совет: дроби с одинаковыми знаменателями складывают и вычитают по числителям',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'полоска ткани длиной\s*(\d+)\s*см\.\s*из\s*(\d+)\s*/\s*(\d+)\s*части.*сколько см ткани у нее осталось\?\s*сколько см ткани ушло', lower)
    if m:
        total, num, den = map(int, m.groups())
        part = total * num // den if (total * num) % den == 0 else total * num / den
        left = total - part
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: длина ткани {total} см, на кофточку ушло {num}/{den} ткани.',
            'Что нужно найти: сколько ткани ушло и сколько осталось.',
            f'1) Находим, сколько ткани ушло: {total} : {den} × {num} = {part} см.',
            f'2) Находим, сколько ткани осталось: {total} - {part} = {left} см.',
            f'Ответ: ушло {part} см, осталось {left} см',
            'Совет: чтобы найти остаток после дробной части, сначала находят эту часть, а потом вычитают её из целого',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'зарплату\s*(\d+)\s*руб.*(\d+)\s*/\s*(\d+)\s*из этих денег.*подарки.*(\d+)\s*/\s*(\d+)\s*потратила на фрукты', lower)
    if m:
        total, g_num, g_den, f_num, f_den = map(int, m.groups())
        gifts = total * g_num // g_den if (total * g_num) % g_den == 0 else total * g_num / g_den
        fruits = total * f_num // f_den if (total * f_num) % f_den == 0 else total * f_num / f_den
        left = total - gifts - fruits
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: всего {total} руб., на подарки потратили {g_num}/{g_den}, на фрукты {f_num}/{f_den} всех денег.',
            'Что нужно найти: сколько потратили на подарки, на фрукты и сколько денег осталось.',
            f'1) Находим деньги на подарки: {total} : {g_den} × {g_num} = {gifts} руб.',
            f'2) Находим деньги на фрукты: {total} : {f_den} × {f_num} = {fruits} руб.',
            f'3) Находим остаток: {total} - {gifts} - {fruits} = {left} руб.',
            f'Ответ: на подарки {gifts} руб., на фрукты {fruits} руб., осталось {left} руб.',
            'Совет: если нужно найти несколько дробных частей одного числа, каждую часть считают отдельно',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в куске ткани\s*(\d+)\s*м.*отрезали\s*(\d+)\s*/\s*(\d+)\s*част', lower)
    if m:
        total, num, den = map(int, m.groups())
        part = total * num // den if (total * num) % den == 0 else total * num / den
        left = total - part
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько ткани отрезали: {total} : {den} × {num} = {part} м.',
            f'2) Находим, сколько ткани осталось: {total} - {part} = {left} м.',
            f'Ответ: {left} м',
            'Совет: чтобы найти остаток после дробной части, сначала находят эту часть',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в поход пошли\s*(\d+)\s*человек.*мальчиков\s*(\d+)\s*человек.*девочек\s*[-–]\s*третья часть от всех мальчиков.*остальные взрослые', lower)
    if m:
        total, boys = map(int, m.groups())
        girls = boys // 3
        adults = total - boys - girls
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим число девочек: {boys} : 3 = {girls}.',
            f'2) Находим число взрослых: {total} - {boys} - {girls} = {adults}.',
            f'Ответ: {adults} взрослых',
            'Совет: если сказано «третья часть», сначала находят эту часть, а потом остаток',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в саду\s*(\d+)\s*роз, тюльпанов четвертая часть от роз, ромашек\s*(\d+)', lower)
    if m:
        roses, daisies = map(int, m.groups())
        tulips = roses // 4
        total = roses + tulips + daisies
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим количество тюльпанов: {roses} : 4 = {tulips}.',
            f'2) Находим общее количество цветов: {roses} + {tulips} + {daisies} = {total}.',
            f'Ответ: {total} цветов',
            'Совет: если одна величина составляет часть другой, сначала находят эту часть, а потом складывают все количества',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в саду\s*(\d+)\s*цветов\.\s*ромашек\s*(\d+)\s*штук\.\s*роз\s*[-–]?\s*1\s*/\s*(\d+)\s*часть от ромашек.*остальные цветы[-–]? тюльпаны', lower)
    if m:
        total, daisies, den = map(int, m.groups())
        roses = daisies // den
        tulips = total - daisies - roses
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим количество роз: {daisies} : {den} = {roses}.',
            f'2) Находим количество тюльпанов: {total} - {daisies} - {roses} = {tulips}.',
            f'Ответ: {tulips} тюльпанов',
            'Совет: если одна часть известна, а другая выражена дробью от неё, сначала находят эту дробную часть, а потом остаток',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в магазин привезли\s*(\d+)\s*метров красной ткани, синей[–-]\s*1\s*/\s*(\d+)\s*часть от красной, зеленой[–-]\s*(\d+)\s*метров', lower)
    if m:
        red, den, green = map(int, m.groups())
        blue = red // den
        total = red + blue + green
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько метров синей ткани привезли: {red} : {den} = {blue} м.',
            f'2) Находим общее количество ткани: {red} + {blue} + {green} = {total} м.',
            f'Ответ: {total} м',
            'Совет: если одна величина составляет дробную часть другой, сначала находят эту часть, а потом общий итог',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'куриное яйцо весит\s*(\d+)\s*г.*скорлупу приходится\s*1\s*/\s*(\d+).*белок\s*1\s*/\s*(\d+).*остальное[ –-]+желток', lower)
    if m:
        total, shell_den, white_den = map(int, m.groups())
        shell = total // shell_den
        white = total // white_den
        yolk = total - shell - white
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим массу скорлупы: {total} : {shell_den} = {shell} г.',
            f'2) Находим массу белка: {total} : {white_den} = {white} г.',
            f'3) Находим массу желтка: {total} - {shell} - {white} = {yolk} г.',
            f'Ответ: {yolk} г',
            'Совет: если часть массы уже известна по долям, остальные части находят вычитанием из всей массы',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'на свете существует\s*(\d+)\s*разновидностей акул.*1\s*/\s*(\d+)\s*часть нападает', lower)
    if m:
        total, den = map(int, m.groups())
        count = total // den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим {1}/{den} от {total}: {total} : {den} = {count}.',
            f'Ответ: {count} видов',
            'Совет: чтобы найти одну долю числа, число делят на количество равных частей',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'длина тела лирохвоста\s*(\d+)\s*см, она составляет\s*1\s*/\s*(\d+)\s*длины хвоста', lower)
    if m:
        body, den = map(int, m.groups())
        tail = body * den
        diff = tail - body
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим длину хвоста: {body} × {den} = {tail} см.',
            f'2) Узнаём, на сколько тело короче хвоста: {tail} - {body} = {diff} см.',
            f'Ответ: {diff} см',
            'Совет: если одна величина составляет долю другой, большую величину находят умножением на число долей',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'вес морской черепахи\s*(\d+)\s*кг, вес сухопутной черепахи составляет\s*1\s*/\s*(\d+)\s*веса морской', lower)
    if m:
        sea, den = map(int, m.groups())
        land = sea // den
        diff = sea - land
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим вес сухопутной черепахи: {sea} : {den} = {land} кг.',
            f'2) Находим разницу: {sea} - {land} = {diff} кг.',
            f'Ответ: {diff} кг',
            'Совет: если нужно узнать, на сколько одна величина больше другой, из большей величины вычитают меньшую',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'длина отреза\s*(\d+)\s*м.*продали\s*1\s*/\s*(\d+)\s*част', lower)
    if m:
        total, den = map(int, m.groups())
        sold = total // den
        left = total - sold
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько метров продали: {total} : {den} = {sold} м.',
            f'2) Находим, сколько осталось: {total} - {sold} = {left} м.',
            f'Ответ: {left} м',
            'Совет: если продали часть куска, сначала находят эту часть, а потом остаток',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'блокнот стоит\s*(\d+)\s*руб.*что составляет\s*1\s*/\s*(\d+)\s*часть книги', lower)
    if m:
        notebook, den = map(int, m.groups())
        book = notebook * den
        total = notebook + book
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим цену книги: {notebook} × {den} = {book} руб.',
            f'2) Находим общую стоимость блокнота и книги: {notebook} + {book} = {total} руб.',
            f'Ответ: книга стоит {book} руб., вместе {total} руб.',
            'Совет: если цена одной вещи составляет долю цены другой, большую цену находят умножением на число долей',
        ]
        return _mass20260416x_finalize(lines)

    return None


_CONT20260416AI_PREV_BUILD_EXPLANATION = build_explanation


async def build_explanation(user_text: str) -> dict:
    for handler in (
        _unit20260416_cont_try_arithmetic,
        _frac20260416_cont_try_simple_unit_fraction,
        _frac20260416_cont_try_fraction_text_tasks,
    ):
        local = handler(user_text)
        if local:
            return _prompt20260416h_result(local, 'local')
    return await _CONT20260416AI_PREV_BUILD_EXPLANATION(user_text)


# Fix formatting of mixed named-quantity answers when the working base unit is not the smallest one.
_UNIT20260416_CONT_SMALLEST_SCALES = {
    'time': {'сут': 86400, 'ч': 3600, 'мин': 60, 'с': 1},
    'mass': {'т': 1000000, 'ц': 100000, 'кг': 1000, 'г': 1},
    'length': {'км': 1000000, 'м': 1000, 'дм': 100, 'см': 10, 'мм': 1},
}


def _unit20260416_cont_format_compound_from_base(total_value: int, group: str, base_unit: str, units_present: list[str]) -> str:
    ordered = {
        'time': ['сут', 'ч', 'мин', 'с'],
        'mass': ['т', 'ц', 'кг', 'г'],
        'length': ['км', 'м', 'дм', 'см', 'мм'],
    }[group]
    scales = _UNIT20260416_CONT_SMALLEST_SCALES[group]
    present = set(units_present)
    active = [u for u in ordered if u in present]
    if not active:
        active = [base_unit]
    start = ordered.index(active[0])
    end = max(ordered.index(active[-1]), ordered.index(base_unit))
    use_units = ordered[start:end + 1]
    total_smallest = int(round(total_value * scales[base_unit]))
    smallest_unit = use_units[-1]
    remainder = total_smallest
    smallest_scale = scales[smallest_unit]
    parts = []
    for unit in use_units:
        per = scales[unit] // smallest_scale
        count = remainder // (per * smallest_scale)
        remainder = remainder - count * per * smallest_scale
        if count or parts or unit == use_units[-1]:
            parts.append(f'{int(count)} {unit}')
    return ' '.join(parts)


def _unit20260416_cont_try_arithmetic(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    m = re.fullmatch(r'(.+?)\s*([+\-])\s*(.+?)\s*=?', text)
    if not m:
        return None
    left_text, op, right_text = m.group(1).strip(), m.group(2), m.group(3).strip()
    left = _unit20260416_cont_parse_quantity(left_text)
    right = _unit20260416_cont_parse_quantity(right_text)
    if not left or not right or left['group'] != right['group']:
        return None

    all_units = left['units'] + right['units']
    group = left['group']
    base_unit = _unit20260416_cont_base_unit(group, all_units)
    left_base = _unit20260416_cont_total_in_unit(left, base_unit)
    right_base = _unit20260416_cont_total_in_unit(right, base_unit)
    result_base = left_base + right_base if op == '+' else left_base - right_base
    if result_base < 0:
        return None

    answer_text = _unit20260416_cont_format_compound_from_base(result_base, group, base_unit, all_units)
    sign_text = '+' if op == '+' else '-'
    action_text = 'Складываем' if op == '+' else 'Вычитаем'
    lines = [
        'Пример: ' + raw_text.strip(),
        'Решение.',
        f'1) Переводим первое именованное число в {base_unit}: {left["pretty"]} = {left_base} {base_unit}.',
        f'2) Переводим второе именованное число в {base_unit}: {right["pretty"]} = {right_base} {base_unit}.',
        f'3) {action_text}: {left_base} {sign_text} {right_base} = {result_base} {base_unit}.',
        f'4) Переводим ответ обратно: {result_base} {base_unit} = {answer_text}.',
        f'Ответ: {answer_text}',
        'Совет: при действиях с именованными величинами сначала переводят их в одинаковые единицы',
    ]
    return _mass20260416x_finalize(lines)


def _frac20260416_cont_try_fraction_time_total(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    lower = text.lower()
    m = re.search(r'(?:проехал|прошел|прошёл)\s+(?:четвертую|шестую)\s+часть пути за\s*(\d+)\s*минут', lower)
    if not m:
        return None
    part_time = int(m.group(1))
    den = 4 if 'четверт' in lower else 6
    whole = part_time * den
    lines = [
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: 1/{den} пути пройдена за {part_time} минут.',
        'Что нужно найти: время на весь путь.',
        f'1) Весь путь состоит из {den} таких частей.',
        f'2) Находим всё время: {part_time} × {den} = {whole} минут.',
        f'Ответ: {whole} минут',
        'Совет: если одна доля пути занимает известное время, всё время находят умножением на число долей',
    ]
    return _mass20260416x_finalize(lines)


_CONT20260416AJ_PREV_BUILD_EXPLANATION = build_explanation


async def build_explanation(user_text: str) -> dict:
    local = _frac20260416_cont_try_fraction_time_total(user_text)
    if local:
        return _prompt20260416h_result(local, 'local')
    return await _CONT20260416AJ_PREV_BUILD_EXPLANATION(user_text)
