from __future__ import annotations

from .package_bootstrap import bootstrap_package

from .compat_paths import PLATFORM_COMPAT_DIRS, PLATFORM_ROOT, extend_module_path

__path__ = bootstrap_package(__path__, __name__, PLATFORM_COMPAT_DIRS)

__all__ = ['PLATFORM_COMPAT_DIRS', 'PLATFORM_ROOT']
