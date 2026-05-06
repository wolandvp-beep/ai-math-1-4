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

import argparse
import json
from pathlib import Path
from typing import Any

from backend.health_bundle_export import export_health_bundle
from backend.health_markdown_report import render_health_markdown
from backend.health_section_registry import HEALTH_SECTION_BUILDERS
from backend.runtime_cache_control import clear_runtime_caches
from backend.platform.modules.health.reporting.registry.sections.support.invocation import (
    invoke_health_builder,
)


def _build_payload(section: str, *, fresh: bool) -> dict[str, Any]:
    return invoke_health_builder(HEALTH_SECTION_BUILDERS[section], fresh=fresh)


def main() -> int:
    parser = argparse.ArgumentParser(description='Run backend regression and health checks.')
    parser.add_argument('--section', choices=sorted(HEALTH_SECTION_BUILDERS), default='healthcheck')
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    parser.add_argument('--output', help='Optional output file path.')
    parser.add_argument('--bundle-dir', help='Optional directory for exporting a multi-file health bundle.')
    parser.add_argument('--fresh', action='store_true', help='Clear health/runtime caches before running the section.')
    parser.add_argument('--strict-exit', action='store_true', help='Return exit code 1 when the selected section reports all_passed=false.')
    args = parser.parse_args()

    if args.fresh:
        clear_runtime_caches()

    if args.bundle_dir:
        payload = export_health_bundle(args.bundle_dir, fresh=args.fresh)
    else:
        payload = _build_payload(args.section, fresh=args.fresh)

    if args.format == 'markdown':
        if not isinstance(payload, dict):
            text = str(payload)
        elif args.bundle_dir:
            text = '# Exported health bundle\n\n' + json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
        else:
            text = (
                render_health_markdown(_build_payload('healthcheck', fresh=args.fresh))
                if args.section in {'healthcheck', 'summary'}
                else '# Section payload\n\n```json\n' + json.dumps(payload, ensure_ascii=False, indent=2) + '\n```\n'
            )
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(text + ('\n' if not text.endswith('\n') else ''), encoding='utf-8')
    else:
        print(text)

    if args.strict_exit and isinstance(payload, dict) and payload.get('all_passed') is False:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
