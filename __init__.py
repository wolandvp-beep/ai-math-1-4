from __future__ import annotations

from pkgutil import extend_path

from .platform.compat_paths import BACKEND_COMPAT_DIRS, PLATFORM_ROOT, extend_module_path

__path__ = extend_path(__path__, __name__)
extend_module_path(__path__, BACKEND_COMPAT_DIRS)

PLATFORM_COMPAT_DIRS = list(BACKEND_COMPAT_DIRS)

__all__: list[str] = ['PLATFORM_COMPAT_DIRS', 'PLATFORM_ROOT']
