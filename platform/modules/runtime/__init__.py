from __future__ import annotations

from backend.package_bootstrap import bootstrap_package
from backend.layout_specs.runtime import RUNTIME_ROOT

__path__ = bootstrap_package(__path__, __name__, [RUNTIME_ROOT])

__all__ = ['RUNTIME_ROOT']
