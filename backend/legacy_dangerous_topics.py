from __future__ import annotations

from typing import Callable, Optional


_NSBoolFn = Callable[[str], bool]


def _resolve_ns(ns):
    if ns is not None:
        return ns
    from . import legacy_core as core
    return core.__dict__


def _call_bool(ns: dict, name: str, user_text: str) -> bool:
    fn: Optional[_NSBoolFn] = ns.get(name)
    if not callable(fn):
        return False
    try:
        return bool(fn(user_text))
    except Exception:
        return False


def dangerous_topic_for_old_solver(user_text: str, ns: dict | None = None) -> Optional[str]:
    ns = _resolve_ns(ns)

    checks = (
        ('_should_prevent_old_price_solver', 'задачу о цене и количестве'),
        ('_looks_like_unit_price_purchase_problem', 'задачу о покупке по цене за штуку'),
        ('_should_prevent_old_motion_solver', 'задачу на движение'),
        ('_looks_like_ambiguous_reverse_dual_subject_total_after_changes_problem', 'обратную задачу о двух объектах с общей суммой после изменений'),
        ('_looks_like_ambiguous_reverse_dual_subject_measured_total_after_changes_problem', 'обратную задачу о двух величинах с общей величиной после изменений'),
        ('_should_prevent_old_fraction_change_solver', 'задачу с долями и остатком'),
        ('_should_prevent_old_equal_parts_solver', 'задачу на деление на равные части'),
        ('_should_prevent_old_post_change_equal_parts_solver', 'задачу, где остаток после изменений делят поровну'),
        ('_should_prevent_old_ratio_after_change_solver', 'задачу на сравнение во сколько раз после изменения'),
        ('_should_prevent_old_difference_after_change_solver', 'задачу на сравнение после изменения'),
        ('_should_prevent_old_temperature_solver', 'задачу об изменении температуры'),
        ('_looks_like_reverse_dual_subject_total_relation_after_changes_problem', 'обратную задачу о двух объектах с итоговой суммой и сравнением после изменений'),
        ('_looks_like_reverse_dual_subject_equality_after_changes_problem', 'обратную задачу о двух объектах, где после изменений стало поровну'),
        ('_looks_like_reverse_dual_subject_measured_total_relation_after_changes_problem', 'обратную задачу о двух величинах с общей суммой и итоговым сравнением'),
        ('_looks_like_reverse_dual_subject_measured_equality_after_changes_problem', 'обратную задачу о двух величинах, которые после изменений стали равны'),
        ('_looks_like_reverse_dual_subject_measured_total_problem', 'обратную задачу о двух величинах после изменений'),
        ('_looks_like_reverse_measured_change_problem', 'обратную задачу с величинами'),
        ('_looks_like_reverse_dual_subject_total_after_changes_problem', 'обратную задачу о двух объектах и общей сумме после изменений'),
        ('_looks_like_reverse_transfer_mixed_total_problem', 'обратную задачу после передач и внешних изменений'),
        ('_looks_like_reverse_transfer_total_pattern', 'обратную задачу после передач и общей суммы'),
        ('_looks_like_reverse_transfer_relation_problem', 'обратную задачу после передач и сравнения'),
        ('_looks_like_reverse_transfer_problem', 'обратную задачу после передач'),
        ('_looks_like_dual_subject_money_after_changes_problem', 'задачу о деньгах у двух людей после изменений'),
        ('_looks_like_dual_subject_measured_after_changes_problem', 'задачу о двух величинах после изменений'),
        ('_looks_like_volume_change_problem', 'задачу с величинами в литрах и миллилитрах'),
    )

    for fn_name, label in checks:
        if _call_bool(ns, fn_name, user_text):
            return label
    return None


__all__ = [
    'dangerous_topic_for_old_solver',
]
