"""Add command - dynamically adds new commands using Claude AI."""
from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Optional
from . import command
from ..claude_integration import generate_command_code
from ..code_validator import validate_command_code, validate_test_code
from ..git_integration import git_commit
from ..reload import restart_bot

logger = logging.getLogger(__name__)


@command(
    name="add",
    description="Add a new command using AI (usage: !add -n <name> -d \"<description>\")",
    pattern=r"^!add\s+"
)
async def add_handler(body: str) -> Optional[str]:
    """
    Add a new command using Claude AI to generate the code.

    Usage: !add -n <command_name> -d "<description>"
    Example: !add -n calculate -d "Calculate mathematical expressions"
    """
    # Parse arguments
    name_match = re.search(r'-n\s+(\w+)', body)
    desc_match = re.search(r'-d\s+"([^"]+)"', body)

    if not name_match or not desc_match:
        return (
            "Usage: !add -n <command_name> -d \"<description>\"\n\n"
            "Example: !add -n calculate -d \"Calculate mathematical expressions\"\n\n"
            "The command name should be alphanumeric (no spaces).\n"
            "The description should be in quotes."
        )

    command_name = name_match.group(1).lower()
    command_description = desc_match.group(1)

    # Validate command name
    if not re.match(r'^[a-z][a-z0-9_]*$', command_name):
        return "Command name must start with a letter and contain only lowercase letters, numbers, and underscores."

    # Check if command already exists
    command_file = Path(f"bot/commands/{command_name}.py")
    if command_file.exists():
        return f"Command '{command_name}' already exists. Use !remove first if you want to replace it."

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
    logger.info(f"Generating code for command '{command_name}' using Claude Code CLI")

    # Note: Claude Code CLI will write files directly to bot/commands/ and tests/commands/
    # We'll validate the generated files after they're created

    try:
        command_code, test_code, error = await generate_command_code(
            api_key=api_key,  # Not used with CLI
            command_name=command_name,
            command_description=command_description
        )

        if error or not command_code:
            logger.error(f"Failed to generate command code: {error}")
            return f"Failed to generate command using Claude Code CLI: {error}"

        # Validate generated code
        is_valid, validation_error = validate_command_code(command_code, command_name)
        if not is_valid:
            logger.error(f"Generated code validation failed: {validation_error}")
            return f"Generated code validation failed: {validation_error}"

        # Validate test code if generated
        if test_code:
            is_valid, validation_error = validate_test_code(test_code)
            if not is_valid:
                logger.warning(f"Generated test code validation failed: {validation_error}")
                test_code = None  # Skip test if invalid

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
            success, commit_error = git_commit(
                files_to_commit,
                f"Add command: {command_name}\n\nDescription: {command_description}"
            )
            if not success:
                logger.error(f"Git commit failed: {commit_error}")
                # Don't fail the command, just warn
                return (
                    f"Command '{command_name}' created successfully but git commit failed: {commit_error}\n"
                    "Bot will restart shortly to apply changes."
                )

        # Schedule bot restart
        import asyncio
        asyncio.create_task(_delayed_restart())

        return (
            f"Command '{command_name}' created successfully!\n"
            f"Description: {command_description}\n"
            f"Bot will restart in 2 seconds to load the new command."
        )

    except Exception as e:
        logger.exception(f"Error creating command: {e}")
        # Clean up partial files
        if command_file.exists():
            command_file.unlink()
        return f"Error creating command: {e}"


async def _delayed_restart():
    """Restart the bot after a short delay to allow message to be sent."""
    import asyncio
    await asyncio.sleep(2)  # Wait 2 seconds for message to be sent
    restart_bot()
