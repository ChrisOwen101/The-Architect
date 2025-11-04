"""Add command - dynamically adds new commands using Claude AI."""
from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Optional, Any
from . import command
from ..claude_integration import generate_command_code
from ..code_validator import validate_command_code, validate_test_code
from ..git_integration import git_commit
from ..reload import reload_commands

logger = logging.getLogger(__name__)


@command(
    name="add",
    description="Add new functionality/tools to the bot. Used when requested or when you need to extend capabilities proactively to achieve what a user wants if you can't do it with existing commands.",
    params=[
        ("command_name", str, "Name of the new command (alphanumeric, lowercase)", True),
        ("description", str, "Description of what the command does", True)
    ]
)
async def add_handler(command_name: str, description: str, matrix_context: Optional[dict[str, Any]] = None) -> Optional[str]:
    """
    Add new functionality/tools to the bot.

    Args:
        command_name: Name of the new command (alphanumeric, lowercase)
        description: Description of what the command does
        matrix_context: Optional Matrix context containing client, room, event
    """
    command_name = command_name.lower()
    command_description = description
    # Extract Matrix components for sending status updates
    client = None
    room = None
    event = None
    if matrix_context:
        client = matrix_context.get('client')
        room = matrix_context.get('room')
        event = matrix_context.get('event')

    # Helper to send status updates to the user
    async def send_status(message: str) -> None:
        """Send a status update message to the user."""
        if not (client and room and event):
            return

        try:
            # Determine thread root (same logic as in handlers.py)
            thread_root = event.event_id
            if hasattr(event, 'source') and isinstance(event.source, dict):
                relates_to = event.source.get(
                    'content', {}).get('m.relates_to', {})
                if relates_to.get('rel_type') == 'm.thread':
                    thread_root = relates_to.get('event_id', event.event_id)

            await client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": message,
                    "m.relates_to": {
                        "rel_type": "m.thread",
                        "event_id": thread_root,
                        "is_falling_back": True,
                        "m.in_reply_to": {"event_id": event.event_id}
                    },
                },
            )
            logger.debug(f"Status update sent: {message}")
        except Exception as e:
            logger.warning(f"Failed to send status update: {e}")
            # Don't fail the command if status update fails

    # Validate command name
    if not re.match(r'^[a-z][a-z0-9_]*$', command_name):
        return "Command name must start with a letter and contain only lowercase letters, numbers, and underscores."

    # Check if command already exists
    command_file = Path(f"bot/commands/{command_name}.py")
    if command_file.exists():
        return f"Command '{command_name}' already exists. Ask me to remove it first if you want to replace it."

    # Load config
    from ..config import load_config
    try:
        cfg = load_config()
        # Note: api_key not needed for Claude Code CLI (uses its own auth)
        api_key = None  # Passed for backward compatibility
        enable_auto_commit = cfg.enable_auto_commit
    except Exception as e:
        logger.exception("Failed to load config")
        return f"Configuration error: {e}"

    # Generate code using Claude Code CLI
    logger.info(
        f"Generating code for command '{command_name}' using Claude Code CLI")

    # Note: Claude Code CLI will write files directly to bot/commands/ and tests/commands/
    # We'll validate the generated files after they're created

    try:
        command_code, test_code, error = await generate_command_code(
            api_key=api_key,  # Not used with CLI
            command_name=command_name,
            command_description=command_description,
            status_callback=send_status  # Pass callback for periodic updates
        )

        if error or not command_code:
            logger.error(f"Failed to generate command code: {error}")
            return f"Failed to generate command using Claude Code CLI: {error}"

        await send_status("Validating generated code...")

        # Validate generated code
        is_valid, validation_error = validate_command_code(
            command_code, command_name)
        if not is_valid:
            logger.error(
                f"Generated code validation failed: {validation_error}")
            return f"Generated code validation failed: {validation_error}"

        # Validate test code if generated
        if test_code:
            is_valid, validation_error = validate_test_code(test_code)
            if not is_valid:
                logger.warning(
                    f"Generated test code validation failed: {validation_error}")
                test_code = None  # Skip test if invalid

        await send_status("Code validated successfully!")

        # Note: Files are already written by Claude Code CLI
        # We just need to track them for git commit
        files_to_commit = [str(command_file)]

        test_file = Path(f"tests/commands/test_{command_name}.py")
        if test_file.exists():
            files_to_commit.append(str(test_file))
            logger.info(f"Test file created: {test_file}")

        # Check if __init__.py exists in tests/commands
        test_init = Path("tests/commands/__init__.py")
        if test_init.exists():
            files_to_commit.append(str(test_init))

        # Commit to git if enabled
        if enable_auto_commit:
            await send_status("Committing to git...")
            success, commit_error = git_commit(
                files_to_commit,
                f"Add command: {command_name}\n\nDescription: {command_description}"
            )
            if not success:
                logger.error(f"Git commit failed: {commit_error}")
                # Don't fail the command, just warn
                return (
                    f"Command '{command_name}' created successfully but git commit failed: {commit_error}\n"
                    "Commands will be reloaded shortly to apply changes."
                )

        # Schedule command reload
        import asyncio
        asyncio.create_task(_delayed_reload())

        await send_status(f"Command '{command_name}' added successfully! Reloading commands...")

        return (
            f"Command '{command_name}' created successfully!\n"
            f"Description: {command_description}\n"
            f"Commands are being reloaded. The new command is now available!"
        )

    except Exception as e:
        logger.exception(f"Error creating command: {e}")
        # Clean up partial files
        if command_file.exists():
            command_file.unlink()
        return f"Error creating command: {e}"


async def _delayed_reload():
    """Reload commands after a short delay to allow message to be sent."""
    import asyncio
    await asyncio.sleep(1)  # Wait 1 second for message to be sent
    reload_commands()
