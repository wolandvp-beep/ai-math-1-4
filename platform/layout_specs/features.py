from __future__ import annotations

from .shared import FEATURES_ROOT, nested_package_dirs

FEATURE_HANDLERS_ROOT = FEATURES_ROOT / 'handlers'
FEATURE_WORD_PROBLEMS_ROOT = FEATURE_HANDLERS_ROOT / 'word_problems'
FEATURE_WORD_PROBLEM_DIR_MAP = {
    'change': ('sequential', 'reverse', 'transfer'),
    'subject_relations': ('dual_subject', 'quantity', 'relation'),
    'applied_contexts': ('geometry', 'motion', 'purchase'),
    'arithmetic': ('fractions', 'verbal'),
}
FEATURE_WORD_PROBLEM_PACKAGE_DIRS = nested_package_dirs(
    FEATURE_WORD_PROBLEMS_ROOT,
    FEATURE_WORD_PROBLEM_DIR_MAP,
)
FEATURE_DIRECT_MATH_ROOT = FEATURE_HANDLERS_ROOT / 'direct_math'
FEATURE_DIRECT_MATH_DIR_MAP = {
    'columns': ('solvers',),
    'algebra': ('letters',),
    'quantities': ('named',),
}
FEATURE_DIRECT_MATH_PACKAGE_DIRS = nested_package_dirs(
    FEATURE_DIRECT_MATH_ROOT,
    FEATURE_DIRECT_MATH_DIR_MAP,
)
FEATURE_HANDLER_PACKAGE_DIRS = [
    FEATURE_HANDLERS_ROOT,
    *FEATURE_DIRECT_MATH_PACKAGE_DIRS,
    FEATURE_HANDLERS_ROOT / 'legacy_bridges',
    *FEATURE_WORD_PROBLEM_PACKAGE_DIRS,
]

FEATURE_FORMATTERS_ROOT = FEATURES_ROOT / 'formatters'
FEATURE_FORMATTER_DIR_MAP = {
    'columns': ('renderers',),
    'expressions': ('renderers',),
    'solutions': ('renderers',),
}
FEATURE_FORMATTER_PACKAGE_DIRS = nested_package_dirs(
    FEATURE_FORMATTERS_ROOT,
    FEATURE_FORMATTER_DIR_MAP,
)

__all__ = [
    'FEATURE_DIRECT_MATH_DIR_MAP',
    'FEATURE_DIRECT_MATH_PACKAGE_DIRS',
    'FEATURE_DIRECT_MATH_ROOT',
    'FEATURE_FORMATTER_DIR_MAP',
    'FEATURE_FORMATTER_PACKAGE_DIRS',
    'FEATURE_FORMATTERS_ROOT',
    'FEATURE_HANDLER_PACKAGE_DIRS',
    'FEATURE_HANDLERS_ROOT',
    'FEATURE_WORD_PROBLEM_DIR_MAP',
    'FEATURE_WORD_PROBLEM_PACKAGE_DIRS',
    'FEATURE_WORD_PROBLEMS_ROOT',
]
