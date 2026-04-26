from __future__ import annotations


def _ensure_project_root_on_sys_path() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


_ensure_project_root_on_sys_path()

from backend.api import app


__all__ = ['app']
