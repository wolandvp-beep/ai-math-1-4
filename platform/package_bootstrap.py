from __future__ import annotations

from pkgutil import extend_path
from typing import Iterable

from .layout_specs.shared import module_path_entries


def bootstrap_package(module_path: list[str], module_name: str, directories: Iterable[str | object]) -> list[str]:
    module_path = extend_path(module_path, module_name)
    for directory in directories:
        for entry in module_path_entries(directory):
            if entry not in module_path:
                module_path.append(entry)
    return module_path


__all__ = ['bootstrap_package']
