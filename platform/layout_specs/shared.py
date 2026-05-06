from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence

PLATFORM_ROOT = Path(__file__).resolve().parent.parent
MODULES_ROOT = PLATFORM_ROOT / 'modules'
FEATURES_ROOT = PLATFORM_ROOT / 'features'
RUNTIME_ASSETS_ROOT = PLATFORM_ROOT / 'runtime_assets'
BUNDLES_ROOT = PLATFORM_ROOT / '_bundles'
MODULES_BUNDLE_FILE = BUNDLES_ROOT / 'platform_modules.zip'
FEATURES_BUNDLE_FILE = BUNDLES_ROOT / 'platform_features.zip'
RUNTIME_SHARDS_BUNDLE_FILE = BUNDLES_ROOT / 'runtime_shards.zip'


def package_dirs(root: Path, relative_dirs: Sequence[str] = ()) -> list[Path]:
    return [root, *[root / relative_dir for relative_dir in relative_dirs]]


def nested_package_dirs(root: Path, relative_dir_map: Mapping[str, Sequence[str]]) -> list[Path]:
    directories: list[Path] = [root]
    for parent_name, child_names in relative_dir_map.items():
        parent_root = root / parent_name
        directories.append(parent_root)
        directories.extend(parent_root / child_name for child_name in child_names)
    return directories


def _zip_internal_path(bundle_file: Path, internal_root: str, relative_path: str = '') -> str:
    suffix = f"/{relative_path.strip('/')}" if relative_path else ''
    return f"{bundle_file.as_posix()}/{internal_root.strip('/')}" + suffix


def _zip_marker_index(path_str: str) -> int:
    for marker in ('.zip/', '.zip\\'):
        index = path_str.find(marker)
        if index >= 0:
            return index + 4
    return -1


def is_existing_zip_subpath(path: Path | str) -> bool:
    path_str = str(path)
    marker_index = _zip_marker_index(path_str)
    if marker_index < 0:
        return False
    return Path(path_str[:marker_index]).is_file()


def module_path_entries(directory: Path | str) -> list[str]:
    path_str = str(directory)
    entries: list[str] = []
    if is_existing_zip_subpath(path_str):
        entries.append(path_str.replace('\\', '/'))
    path = Path(path_str)
    if path.is_dir():
        entries.append(str(path))
    bundle_roots = (
        (MODULES_ROOT, MODULES_BUNDLE_FILE, 'backend/platform/modules'),
        (FEATURES_ROOT, FEATURES_BUNDLE_FILE, 'backend/platform/features'),
        (RUNTIME_ASSETS_ROOT / 'shard_reserve', RUNTIME_SHARDS_BUNDLE_FILE, 'backend/platform/runtime_assets/shard_reserve'),
    )
    for root_path, bundle_file, internal_root in bundle_roots:
        if not bundle_file.is_file():
            continue
        try:
            relative_path = path.relative_to(root_path).as_posix()
        except ValueError:
            continue
        if relative_path == '.':
            relative_path = ''
        entries.append(_zip_internal_path(bundle_file, internal_root, relative_path))
    seen: set[str] = set()
    result: list[str] = []
    for entry in entries:
        normalized = entry.replace('\\', '/')
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


__all__ = [
    'BUNDLES_ROOT',
    'FEATURES_BUNDLE_FILE',
    'FEATURES_ROOT',
    'MODULES_BUNDLE_FILE',
    'MODULES_ROOT',
    'PLATFORM_ROOT',
    'RUNTIME_ASSETS_ROOT',
    'RUNTIME_SHARDS_BUNDLE_FILE',
    'is_existing_zip_subpath',
    'module_path_entries',
    'nested_package_dirs',
    'package_dirs',
]
