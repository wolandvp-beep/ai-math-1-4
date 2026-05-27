from __future__ import annotations

from backend.package_bootstrap import bootstrap_package

from backend.compat_paths import STATIC_RUNTIME_MODULE_IMPORT_PACKAGE_DIRS, extend_module_path

__path__ = bootstrap_package(__path__, __name__, STATIC_RUNTIME_MODULE_IMPORT_PACKAGE_DIRS)

__all__ = ['STATIC_RUNTIME_MODULE_IMPORT_PACKAGE_DIRS']
