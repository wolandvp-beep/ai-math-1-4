from __future__ import annotations

from backend.package_bootstrap import bootstrap_package

from backend.compat_paths import LEGACY_RUNTIME_MODULE_WRAPPER_PACKAGE_DIRS, extend_module_path

__path__ = bootstrap_package(__path__, __name__, LEGACY_RUNTIME_MODULE_WRAPPER_PACKAGE_DIRS)

__all__ = ['LEGACY_RUNTIME_MODULE_WRAPPER_PACKAGE_DIRS']
