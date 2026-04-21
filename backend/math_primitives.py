from __future__ import annotations

from typing import List, Tuple

PLACE_NAMES = ["единицы", "десятки", "сотни", "тысячи", "десятки тысяч", "сотни тысяч", "миллионы"]
NEXT_PLACE_NAMES = ["десяток", "сотню", "тысячу", "десяток тысяч", "сотню тысяч", "миллион", "следующий разряд"]


def get_digits(n: int) -> List[int]:
    return [int(ch) for ch in str(abs(n))]


def digits_by_place(n: int, width: int) -> List[int]:
    s = str(abs(n)).rjust(width, "0")
    return [int(ch) for ch in s]


def split_tens_units(n: int) -> Tuple[int, int]:
    return n - n % 10, n % 10


__all__ = [
    'PLACE_NAMES',
    'NEXT_PLACE_NAMES',
    'get_digits',
    'digits_by_place',
    'split_tens_units',
]
