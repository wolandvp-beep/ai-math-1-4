from __future__ import annotations

from typing import Any, Callable, MutableMapping

from backend.candidate_chain_exports import export_candidate_chain
from backend.handler_source_registry import handler_source_wrapper_spec
from backend.runtime_candidate_registry import runtime_module_wrapper_spec, runtime_source_wrapper_spec

from .metadata import module_filename


def initialize_wrapper(
    module_globals: MutableMapping[str, Any],
    spec_factory: Callable[[str], Any],
) -> tuple[list[str], str]:
    wrapper_spec = spec_factory(module_filename(module_globals))
    exported_names, wrapper_origin = export_candidate_chain(
        module_globals,
        module_candidates=wrapper_spec.module_candidates,
        seeded_module_fallback=wrapper_spec.seeded_exec_module,
        deep_seeded_modules=getattr(wrapper_spec, 'deep_seeded_modules', ()),
        runtime_module_name=str(module_globals.get('__name__', '__runtime_wrapper__')),
        deep_origin=getattr(wrapper_spec, 'deep_origin', 'seeded_exec_fallback'),
    )
    return exported_names, wrapper_origin


def init_runtime_source_wrapper(module_globals: MutableMapping[str, Any]) -> tuple[list[str], str]:
    return initialize_wrapper(module_globals, runtime_source_wrapper_spec)


def init_runtime_module_wrapper(module_globals: MutableMapping[str, Any]) -> tuple[list[str], str]:
    return initialize_wrapper(module_globals, runtime_module_wrapper_spec)


def init_handler_source_wrapper(module_globals: MutableMapping[str, Any]) -> tuple[list[str], str]:
    return initialize_wrapper(module_globals, handler_source_wrapper_spec)


__all__ = [
    'init_handler_source_wrapper',
    'init_runtime_module_wrapper',
    'init_runtime_source_wrapper',
    'initialize_wrapper',
]
