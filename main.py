from __future__ import annotations


def _ensure_backend_import_context() -> None:
    import importlib
    import importlib.util
    import sys
    from pathlib import Path

    current_dir = Path(__file__).resolve().parent
    parent_dir = current_dir.parent

    # Keep the repository parent first so `backend` is imported as a package.
    # Do not leave the backend directory itself on sys.path: it contains
    # `backend/platform`, which can shadow Python's stdlib `platform` module
    # during FastAPI/Pydantic imports when running `uvicorn main:app` from
    # the backend directory.
    parent_str = str(parent_dir)
    if parent_str not in sys.path:
        sys.path.insert(0, parent_str)

    cwd = Path.cwd().resolve()
    for entry in list(sys.path):
        entry_path = Path(entry or cwd).resolve()
        if entry_path == current_dir:
            sys.path.remove(entry)

    loaded_platform = sys.modules.get('platform')
    loaded_platform_file = getattr(loaded_platform, '__file__', '') if loaded_platform else ''
    if loaded_platform_file:
        try:
            Path(loaded_platform_file).resolve().relative_to(current_dir)
        except ValueError:
            pass
        else:
            sys.modules.pop('platform', None)

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
