"""List command - shows all available commands."""
from __future__ import annotations
from typing import Optional
from . import command, get_registry


@command(
    name="list",
    description="List all available commands"
)
async def list_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    """List all registered commands."""
    registry = get_registry()
    commands_list = registry.list_commands()

    if not commands_list:
        return "No commands available."

    # Format the list nicely
    lines = ["Available commands:"]
    for name, description in commands_list:
        lines.append(f"  {name} - {description}")

    return "\n".join(lines)
