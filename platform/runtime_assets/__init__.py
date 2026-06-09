from __future__ import annotations

from ..package_bootstrap import bootstrap_package
from ..layout_specs.shared import RUNTIME_ASSETS_ROOT

__path__ = bootstrap_package(__path__, __name__, [RUNTIME_ASSETS_ROOT])

__all__ = ['RUNTIME_ASSETS_ROOT']
