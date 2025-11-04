"""Bot reload mechanism for applying code changes."""
from __future__ import annotations
import os
import sys
import logging

logger = logging.getLogger(__name__)


def restart_bot() -> None:
    """
    Restart the bot process.

    This uses os.execv() to replace the current process with a new one,
    maintaining the same process ID and ensuring a clean restart.

    Always restarts using the module format (python -m bot.main) to avoid
    relative import errors.
    """
    logger.info("Restarting bot...")

    try:
        # Get the Python executable
        python = sys.executable

        # Always use module format to avoid relative import errors
        # This ensures 'python -m bot.main' format regardless of how bot was started
        args = [python, '-m', 'bot.main']

        # Preserve any command-line arguments after the script name
        # (skip sys.argv[0] which is the script name)
        if len(sys.argv) > 1:
            args.extend(sys.argv[1:])

        # Close file descriptors to avoid issues
        # (nio client should be closed before this is called)

        # Replace the current process with a new one
        os.execv(python, args)

    except Exception as e:
        logger.exception(f"Failed to restart bot: {e}")
        # If restart fails, we should at least try to continue running
        raise RuntimeError(f"Bot restart failed: {e}")
