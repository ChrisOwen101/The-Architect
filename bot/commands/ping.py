"""Ping command - responds with pong."""
from __future__ import annotations
from typing import Optional
from . import command


@command(
    name="ping",
    description="Check if the bot is online and responsive",
    pattern=r"^!ping$"
)
async def ping_handler() -> Optional[str]:
    """
    Check if the bot is online and responsive.

    This is a simple health check command that requires no parameters.
    Returns 'pong' if the bot is operational.
    """
    return "pong"
