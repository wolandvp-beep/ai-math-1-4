from __future__ import annotations

DEFAULT_ADVICE = {
    'expression': 'называй действия по порядку и следи за знаками',
    'equation': 'сначала оставь x один, потом сделай проверку',
    'fraction': 'сначала смотри на знаменатели, потом считай',
    'geometry': 'сначала назови правило, потом подставь числа',
    'word': 'сначала пойми, что известно и что нужно найти',
    'other': 'решай по шагам и не перескакивай',
}


def default_advice(kind: str) -> str:
    return DEFAULT_ADVICE.get(kind, DEFAULT_ADVICE['other'])


__all__ = ['DEFAULT_ADVICE', 'default_advice']
