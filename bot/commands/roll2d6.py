from __future__ import annotations
import random
from typing import Optional
from . import command


@command(
    name="roll2d6",
    description="Rolls two six-sided dice and returns the individual results and their sum."
)
async def roll2d6_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    """
    Rolls two six-sided dice and returns the individual results along with their sum.

    Returns:
        A string showing the two dice results and their sum.
    """
    # Roll two six-sided dice
    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    total = die1 + die2

    return f"🎲 Die 1: {die1}\n🎲 Die 2: {die2}\n📊 Total: {total}"
