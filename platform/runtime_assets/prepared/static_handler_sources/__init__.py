from __future__ import annotations

from backend.package_bootstrap import bootstrap_package

from backend.platform.compat_paths import STATIC_HANDLER_SOURCE_IMPORT_PACKAGE_DIRS, extend_module_path

__path__ = bootstrap_package(__path__, __name__, STATIC_HANDLER_SOURCE_IMPORT_PACKAGE_DIRS)

__all__ = ['STATIC_HANDLER_SOURCE_IMPORT_PACKAGE_DIRS']
