"""Bot reload mechanism for applying code changes."""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


async def reload_commands() -> None:
    """
    Hot reload all command modules without restarting the bot process.

    This uses Python's importlib to reload command modules dynamically,
    allowing the bot to continue running and processing the current request.
    The command registry is cleared and all modules are reloaded, ensuring
    that new or modified commands are immediately available.

    The reload uses versioning to ensure in-flight requests can complete
    with the old command registry before it's garbage collected (30s grace period).
    """
    logger.info("Hot reloading commands...")

    try:
        # Import the registry
        from bot.commands import get_registry

        # Reload all command modules with versioning
        registry = get_registry()
        await registry.reload_commands()

        logger.info("Commands reloaded successfully")

    except Exception as e:
        logger.exception(f"Failed to reload commands: {e}")
        # If reload fails, the bot continues with old commands
        raise RuntimeError(f"Command reload failed: {e}")
