from __future__ import annotations

from backend.package_bootstrap import bootstrap_package

from backend.compat_paths import (
    CORE_PACKAGE_DIRS,
    FEATURE_HANDLER_PACKAGE_DIRS,
    LEGACY_INTERNAL_IMPORT_DIRS,
    extend_module_path,
)

__path__ = bootstrap_package(__path__, __name__, [*CORE_PACKAGE_DIRS, *FEATURE_HANDLER_PACKAGE_DIRS, *LEGACY_INTERNAL_IMPORT_DIRS])

from backend.change_word_problems import build_change_word_problem_payload, resolve_change_word_problem
from backend.column_math import build_column_math_explanation, get_column_operation, should_use_column
from backend.legacy_word_problems import build_legacy_word_problem_payload, resolve_legacy_word_problem
from backend.fraction_word_problems import build_fraction_word_problem_payload, resolve_fraction_word_problem
from backend.geometry_word_problems import build_geometry_word_problem_payload, resolve_geometry_word_problem
from backend.letter_problems import build_letter_problem_explanation
from backend.motion_word_problems import build_motion_word_problem_payload, resolve_motion_word_problem
from backend.named_quantities import build_fraction_time_total_explanation, build_named_quantity_arithmetic_explanation
from backend.purchase_word_problems import build_purchase_word_problem_payload, resolve_purchase_word_problem
from backend.quantity_word_problems import build_quantity_word_problem_payload, resolve_quantity_word_problem
from backend.relation_word_problems import build_relation_word_problem_payload, resolve_relation_word_problem
from backend.dual_subject_word_problems import build_dual_subject_word_problem_payload, resolve_dual_subject_word_problem
from backend.verbal_arithmetic_word_problems import build_verbal_arithmetic_word_problem_payload, resolve_verbal_arithmetic_word_problem

__all__ = [
    'build_change_word_problem_payload',
    'resolve_change_word_problem',
    'build_column_math_explanation',
    'get_column_operation',
    'should_use_column',
    'build_legacy_word_problem_payload',
    'resolve_legacy_word_problem',
    'build_fraction_word_problem_payload',
    'resolve_fraction_word_problem',
    'build_geometry_word_problem_payload',
    'resolve_geometry_word_problem',
    'build_letter_problem_explanation',
    'build_motion_word_problem_payload',
    'resolve_motion_word_problem',
    'build_fraction_time_total_explanation',
    'build_named_quantity_arithmetic_explanation',
    'build_purchase_word_problem_payload',
    'resolve_purchase_word_problem',
    'build_quantity_word_problem_payload',
    'resolve_quantity_word_problem',
    'build_relation_word_problem_payload',
    'resolve_relation_word_problem',
    'build_dual_subject_word_problem_payload',
    'resolve_dual_subject_word_problem',
    'build_verbal_arithmetic_word_problem_payload',
    'resolve_verbal_arithmetic_word_problem',
]
