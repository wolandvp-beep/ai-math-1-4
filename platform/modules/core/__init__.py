from __future__ import annotations

from backend.package_bootstrap import bootstrap_package
from backend.layout_specs.core import CORE_ROOT

__path__ = bootstrap_package(__path__, __name__, [CORE_ROOT])

__all__ = ['CORE_ROOT']
