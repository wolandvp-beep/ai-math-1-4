from __future__ import annotations


def _ensure_project_root_on_sys_path() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


_ensure_project_root_on_sys_path()

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
