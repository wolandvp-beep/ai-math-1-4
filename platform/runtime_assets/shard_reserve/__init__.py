from __future__ import annotations

from backend.package_bootstrap import bootstrap_package
from backend.layout_specs.runtime_assets import RUNTIME_ASSETS_SHARD_RESERVE_ROOT

__path__ = bootstrap_package(__path__, __name__, [RUNTIME_ASSETS_SHARD_RESERVE_ROOT])

__all__ = ['RUNTIME_ASSETS_SHARD_RESERVE_ROOT']
