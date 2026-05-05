from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_geometry_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_geometry_handlers_source import (
    _try_rectangle_geometry,
    _try_square_geometry,
    _try_triangle_perimeter,
)


__all__ = ['_try_rectangle_geometry', '_try_square_geometry', '_try_triangle_perimeter']
