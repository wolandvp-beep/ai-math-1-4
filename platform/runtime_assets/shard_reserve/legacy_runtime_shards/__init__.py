from __future__ import annotations

from backend.package_bootstrap import bootstrap_package
from backend.layout_specs.runtime_assets import LEGACY_RUNTIME_SHARDS_ROOT

__path__ = bootstrap_package(__path__, __name__, [LEGACY_RUNTIME_SHARDS_ROOT])

__all__ = ['LEGACY_RUNTIME_SHARDS_ROOT']
