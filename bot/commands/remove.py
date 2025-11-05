"""Remove command - removes a dynamically added command."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
from . import command, get_registry
from ..git_integration import git_remove
from ..reload import reload_commands

logger = logging.getLogger(__name__)

# Protected commands that cannot be removed
PROTECTED_COMMANDS = {"add", "remove", "list", "ping", "greetings"}


@command(
    name="remove",
    description="Remove a dynamically added command",
    params=[
        ("command_name", str, "Name of the command to remove", True)
    ]
)
async def remove_handler(command_name: str, matrix_context: Optional[dict] = None) -> Optional[str]:
    """Remove a command from the system.

    command_name: Name of the command to remove
    """
    command_name = command_name.lower()

    # Check if it's a protected command
    if command_name in PROTECTED_COMMANDS:
        return f"Cannot remove protected command '{command_name}'"

    # Check if command exists
    registry = get_registry()
    if not registry.get_command(command_name):
        return f"Command '{command_name}' not found. Mention me and say 'list' to see available commands."

    # Get file paths
    command_file = Path(f"bot/commands/{command_name}.py")
    test_file = Path(f"tests/commands/test_{command_name}.py")

    # Check if command file exists
    if not command_file.exists():
        return f"Command file not found: {command_file}"

    # Import config to check if auto-commit is enabled
    from ..config import load_config
    try:
        cfg = load_config()
        enable_auto_commit = cfg.enable_auto_commit
    except Exception:
        enable_auto_commit = False

    # Remove command file
    if enable_auto_commit:
        success, error = git_remove(str(command_file), f"Remove command: {command_name}")
        if not success:
            logger.error(f"Failed to remove command file from git: {error}")
            return f"Failed to remove command: {error}"
    else:
        command_file.unlink(missing_ok=True)

    # Remove test file if it exists
    if test_file.exists():
        if enable_auto_commit:
            success, error = git_remove(str(test_file), f"Remove tests for command: {command_name}")
            if not success:
                logger.warning(f"Failed to remove test file from git: {error}")
        else:
            test_file.unlink(missing_ok=True)

    logger.info(f"Removed command: {command_name}")

    # Unregister from registry
    registry.unregister(command_name)

    # Schedule command reload (will happen after this message is sent)
    # We need to do this in a way that doesn't interrupt the message send
    import asyncio
    asyncio.create_task(_delayed_reload())

    return f"Command '{command_name}' removed successfully. Commands are being reloaded."


async def _delayed_reload():
    """Reload commands after a short delay to allow message to be sent."""
    import asyncio
    await asyncio.sleep(1)  # Wait 1 second for message to be sent
    reload_commands()
