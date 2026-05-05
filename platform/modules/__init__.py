from __future__ import annotations

from ..package_bootstrap import bootstrap_package
from ..layout_specs.shared import MODULES_ROOT

__path__ = bootstrap_package(__path__, __name__, [MODULES_ROOT])

__all__ = ['MODULES_ROOT']
