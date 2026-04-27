from __future__ import annotations

from backend.package_bootstrap import bootstrap_package

from backend.compat_paths import BACKEND_COMPAT_DIRS, FEATURE_FORMATTER_PACKAGE_DIRS, extend_module_path

__path__ = bootstrap_package(__path__, __name__, [*FEATURE_FORMATTER_PACKAGE_DIRS, *BACKEND_COMPAT_DIRS])

from backend.solution_formatter import format_solution
from backend.expression_formatter import format_expression_solution, format_simple_expression_solution
from backend.column_formatter import format_column_operation_solution, normalize_column_body_lines

__all__ = [
    'format_solution',
    'format_expression_solution',
    'format_simple_expression_solution',
    'format_column_operation_solution',
    'normalize_column_body_lines',
]
