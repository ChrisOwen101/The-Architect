"""Bot reload mechanism for applying code changes."""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def reload_commands() -> None:
    """
    Hot reload all command modules without restarting the bot process.

    This uses Python's importlib to reload command modules dynamically,
    allowing the bot to continue running and processing the current request.
    The command registry is cleared and all modules are reloaded, ensuring
    that new or modified commands are immediately available.
    """
    logger.info("Hot reloading commands...")

    try:
        # Import the load_commands function from the command registry
        from bot.commands import load_commands

        # Reload all command modules
        # This clears the registry and reloads each module using importlib.reload()
        load_commands()

        logger.info("Commands reloaded successfully")

    except Exception as e:
        logger.exception(f"Failed to reload commands: {e}")
        # If reload fails, the bot continues with old commands
        raise RuntimeError(f"Command reload failed: {e}")
