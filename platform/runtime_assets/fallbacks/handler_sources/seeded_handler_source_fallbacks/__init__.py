from __future__ import annotations

from backend.package_bootstrap import bootstrap_package

from backend.platform.compat_paths import SEEDED_HANDLER_SOURCE_FALLBACK_PACKAGE_DIRS, extend_module_path

__path__ = bootstrap_package(__path__, __name__, SEEDED_HANDLER_SOURCE_FALLBACK_PACKAGE_DIRS)

__all__ = ['SEEDED_HANDLER_SOURCE_FALLBACK_PACKAGE_DIRS']
