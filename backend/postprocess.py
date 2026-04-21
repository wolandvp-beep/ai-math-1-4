from __future__ import annotations

import re


_ORDER_ONLY_RE = re.compile(r"^\s*\d+(?:\s+\d+)*\.\s*$")


def clean_explanation_text(text: str) -> str:
    if not text:
        return text
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out = []
    in_order_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == 'Порядок действий:':
            in_order_section = True
            out.append('Порядок действий:')
            continue
        if in_order_section and _ORDER_ONLY_RE.fullmatch(stripped):
            continue
        if stripped == 'Решение по действиям:':
            in_order_section = False
        out.append(line.rstrip())
    while out and not out[-1].strip():
        out.pop()
    return '\n'.join(out)


def clean_result_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    result = payload.get('result')
    if isinstance(result, str):
        payload = dict(payload)
        payload['result'] = clean_explanation_text(result)
    return payload
