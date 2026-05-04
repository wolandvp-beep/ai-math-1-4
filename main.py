from __future__ import annotations


def _ensure_backend_import_context() -> None:
    import importlib
    import importlib.util
    import sys
    from pathlib import Path

    current_dir = Path(__file__).resolve().parent
    for candidate in (current_dir.parent, current_dir):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)

    if 'backend' in sys.modules:
        return

    try:
        importlib.import_module('backend')
        return
    except ModuleNotFoundError:
        pass

    backend_init = current_dir / '__init__.py'
    if not backend_init.is_file():
        return

    spec = importlib.util.spec_from_file_location(
        'backend',
        backend_init,
        submodule_search_locations=[str(current_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError('Unable to bootstrap backend package import context')

    module = importlib.util.module_from_spec(spec)
    sys.modules['backend'] = module
    spec.loader.exec_module(module)


_ensure_backend_import_context()

from backend.api import app


__all__ = ['app']
