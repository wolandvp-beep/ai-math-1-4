from __future__ import annotations

from pathlib import Path
from typing import Any, MutableMapping


def module_filename(module_globals: MutableMapping[str, Any]) -> str:
    module_file = module_globals.get('__file__')
    if module_file:
        return Path(str(module_file)).name
    module_name = str(module_globals.get('__name__', 'runtime_wrapper'))
    return f"{module_name.rsplit('.', 1)[-1]}.py"


__all__ = ['module_filename']
