from __future__ import annotations

from ..package_bootstrap import bootstrap_package
from ..layout_specs.shared import FEATURES_ROOT

__path__ = bootstrap_package(__path__, __name__, [FEATURES_ROOT])

__all__ = ['FEATURES_ROOT']
