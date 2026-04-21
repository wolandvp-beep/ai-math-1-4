from __future__ import annotations

from .legacy_text_helpers import audit_task_line, finalize_legacy_lines


def safe_cannot_reliably_solve_math(text: str) -> str:
    return finalize_legacy_lines([
        'Задача.',
        audit_task_line(text),
        'Решение.',
        'Не удалось надёжно решить эту задачу ни локально, ни через проверенный AI-резерв.',
        'Ответ: пока нет надёжного решения',
        'Совет: напишите условие полностью, без сокращений, и укажите, что нужно найти.',
    ])


def safe_cannot_reliably_explain_math(text: str) -> str:
    return finalize_legacy_lines([
        'Вопрос.',
        audit_task_line(text),
        'Объяснение.',
        'Не удалось надёжно подготовить объяснение для этого математического вопроса.',
        'Ответ: пока нет надёжного объяснения',
        'Совет: сформулируйте вопрос короче и добавьте, какое правило или тему нужно объяснить.',
    ])


def safe_cannot_parse(text: str, topic: str) -> str:
    return finalize_legacy_lines([
        'Задача.',
        audit_task_line(text),
        'Решение.',
        f'Не удалось надёжно разобрать {topic} в этой записи.',
        'Ответ: нужно уточнить условие задачи',
        'Совет: отдельно напишите, что известно, и что нужно найти.',
    ])


def guard_result(text: str, *, source: str = 'guard-extra-20260416ak') -> dict[str, object]:
    return {'result': text, 'source': source, 'validated': True}


__all__ = [
    'guard_result',
    'safe_cannot_parse',
    'safe_cannot_reliably_explain_math',
    'safe_cannot_reliably_solve_math',
]
