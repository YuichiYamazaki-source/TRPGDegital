from __future__ import annotations

import random
import re
from dataclasses import dataclass

DICE_EXPRESSION_RE = re.compile(r"^\s*(?:(\d*)d(\d+)|(\d+))(?:([+-])(\d+))?\s*$", re.IGNORECASE)


@dataclass
class DiceRoll:
    expression: str
    rolls: list[int]
    sides: int | None
    modifier: int
    total: int


def roll_percentile() -> int:
    return random.randint(1, 100)


def roll_expression(expression: str) -> DiceRoll:
    match = DICE_EXPRESSION_RE.fullmatch(expression.strip())
    if match is None:
        raise ValueError(f"Invalid dice expression: {expression}")

    count_str, sides_str, flat_value_str, sign, modifier_str = match.groups()

    if flat_value_str is not None:
        base_total = int(flat_value_str)
        rolls: list[int] = []
        sides: int | None = None
    else:
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        if count < 1 or count > 100 or sides < 1 or sides > 1000:
            raise ValueError(f"Dice out of supported range: {expression}")
        rolls = [random.randint(1, sides) for _ in range(count)]
        base_total = sum(rolls)

    modifier = int(modifier_str or "0")
    if sign == "-":
        modifier *= -1

    return DiceRoll(
        expression=expression,
        rolls=rolls,
        sides=sides,
        modifier=modifier,
        total=base_total + modifier,
    )
