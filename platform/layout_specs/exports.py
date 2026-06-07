from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .core import *
from .features import *
from .health import *
from .legacy import *
from .runtime import *
from .runtime_assets import *
from .shared import FEATURES_ROOT, PLATFORM_ROOT, module_path_entries


def existing_dirs(paths: Iterable[Path]) -> list[str]:
    entries: list[str] = []
    for path in paths:
        entries.extend(module_path_entries(path))
    return entries


def extend_module_path(module_path: list[str], directories: Iterable[Path]) -> list[str]:
    for directory in existing_dirs(directories):
        if directory not in module_path:
            module_path.append(directory)
    return module_path


LEGACY_INTERNAL_IMPORT_DIRS = [
    *CORE_PACKAGE_DIRS,
    *LEGACY_CORE_PACKAGE_DIRS,
    *[path for path in LEGACY_RUNTIME_PACKAGE_DIRS if path != LEGACY_RUNTIME_ROOT],
    *[path for path in LEGACY_HANDLER_PACKAGE_DIRS if path != LEGACY_HANDLERS_ROOT],
    *[path for path in LEGACY_SUPPORT_PACKAGE_DIRS if path != LEGACY_SUPPORT_ROOT],
    *(path for path in RUNTIME_COMPAT_DIRS if path != RUNTIME_ROOT),
]
LEGACY_COMPAT_DIRS = [
    LEGACY_ROOT,
    *LEGACY_INTERNAL_IMPORT_DIRS,
]

RUNTIME_ASSET_COMPAT_DIRS = [
    RUNTIME_ASSETS_ROOT,
    *RUNTIME_ASSET_GROUP_ROOTS,
]

BACKEND_COMPAT_DIRS = [
    PLATFORM_ROOT,
    *CORE_PACKAGE_DIRS,
    *(path for path in HEALTH_COMPAT_DIRS if path != HEALTH_ROOT),
    *(path for path in RUNTIME_COMPAT_DIRS if path != RUNTIME_ROOT),
    *(path for path in LEGACY_COMPAT_DIRS if path != LEGACY_ROOT),
    FEATURES_ROOT,
    FEATURE_FORMATTERS_ROOT,
    *FEATURE_FORMATTER_PACKAGE_DIRS,
    *FEATURE_HANDLER_PACKAGE_DIRS,
    *RUNTIME_ASSET_COMPAT_DIRS,
]

PLATFORM_COMPAT_DIRS = [
    *CORE_PACKAGE_DIRS,
    *(path for path in HEALTH_COMPAT_DIRS if path != HEALTH_ROOT),
    *(path for path in RUNTIME_COMPAT_DIRS if path != RUNTIME_ROOT),
    *(path for path in LEGACY_COMPAT_DIRS if path != LEGACY_ROOT),
    FEATURES_ROOT,
    FEATURE_FORMATTERS_ROOT,
    *FEATURE_FORMATTER_PACKAGE_DIRS,
    *FEATURE_HANDLER_PACKAGE_DIRS,
    *RUNTIME_ASSET_COMPAT_DIRS,
]


def runtime_asset_dir(package_name: str) -> Path:
    try:
        return RUNTIME_ASSET_PACKAGE_DIRS[package_name]
    except KeyError as exc:  # pragma: no cover - defensive helper
        raise KeyError(f'Unknown runtime asset package: {package_name}') from exc


__all__ = [
    'BACKEND_COMPAT_DIRS',
    'LEGACY_COMPAT_DIRS',
    'LEGACY_INTERNAL_IMPORT_DIRS',
    'PLATFORM_COMPAT_DIRS',
    'RUNTIME_ASSET_COMPAT_DIRS',
    'existing_dirs',
    'extend_module_path',
    'runtime_asset_dir',
]
