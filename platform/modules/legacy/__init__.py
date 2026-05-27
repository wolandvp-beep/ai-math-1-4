from __future__ import annotations

from backend.package_bootstrap import bootstrap_package
from backend.layout_specs.legacy import LEGACY_ROOT

__path__ = bootstrap_package(__path__, __name__, [LEGACY_ROOT])

__all__ = ['LEGACY_ROOT']
