"""Claude Code CLI integration for generating command code."""
from __future__ import annotations
import asyncio
import logging
import subprocess
import os
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum retry attempts for Claude Code CLI
MAX_RETRIES = 3


def check_claude_cli_available() -> tuple[bool, Optional[str]]:
    """
    Check if Claude Code CLI is available.

    Returns:
        tuple: (is_available, error_message)
    """
    try:
        result = subprocess.run(
            ['claude', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info(f"Claude Code CLI found: {result.stdout.strip()}")
            return True, None
        else:
            return False, "Claude Code CLI command failed"
    except FileNotFoundError:
        return False, "Claude Code CLI not found. Please install it first: https://docs.claude.com/claude-code"
    except subprocess.TimeoutExpired:
        return False, "Claude Code CLI check timed out"
    except Exception as e:
        return False, f"Error checking Claude Code CLI: {e}"


async def _read_stream(stream, prefix: str, lines_buffer: list) -> None:
    """
    Read stream line by line and log each line in real-time.

    Args:
        stream: Async stream to read from (stdout or stderr)
        prefix: Prefix for log messages (e.g., "Claude CLI")
        lines_buffer: List to accumulate lines for later use
    """
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            line_str = line.decode('utf-8').rstrip()
            if line_str:  # Only log non-empty lines
                logger.info(f"{prefix}: {line_str}")
            lines_buffer.append(line_str)
    except Exception as e:
        logger.warning(f"Error reading {prefix}: {e}")


async def generate_command_code(
    api_key: str,  # Kept for backward compatibility, not used with CLI
    command_name: str,
    command_description: str,
    model: str = "claude-sonnet-4-5-20250929"  # Kept for backward compatibility
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Generate command code using Claude Code CLI.

    Args:
        api_key: Not used (kept for backward compatibility)
        command_name: Name of the command to generate
        command_description: Description of what the command should do
        model: Not used (kept for backward compatibility)

    Returns:
        tuple: (command_code, test_code, error_message)
               - command_code: Generated Python code for the command (read from file)
               - test_code: Generated test code for the command (read from file)
               - error_message: Error message if generation failed, None otherwise
    """
    # Check if Claude CLI is available
    is_available, error = check_claude_cli_available()
    if not is_available:
        return None, None, error

    # Get the bot root directory
    bot_root = Path(__file__).parent.parent.absolute()
    command_file = bot_root / "bot" / "commands" / f"{command_name}.py"
    test_file = bot_root / "tests" / "commands" / f"test_{command_name}.py"

    # Build the prompt for Claude Code CLI
    prompt = f"""I need you to create a new Matrix bot command. Please create TWO files:

1. Command file: bot/commands/{command_name}.py
2. Test file: tests/commands/test_{command_name}.py

Command name: {command_name}
Description: {command_description}

**Command file requirements (bot/commands/{command_name}.py):**
- Create a single async function: `async def {command_name}_handler(body: str) -> Optional[str]`
- The function should parse the command from `body` (the full message text)
- Return a string response to send back to the user, or None if no response needed
- Keep responses under 4000 characters
- Include the @command decorator with appropriate pattern
- The pattern should match `!{command_name}` followed by any arguments
- Include clear docstring explaining what the command does

**Command file structure:**
```python
from __future__ import annotations
from typing import Optional
from . import command

@command(
    name="{command_name}",
    description="{command_description}",
    pattern=r"^!{command_name}\\s*(.*)$"
)
async def {command_name}_handler(body: str) -> Optional[str]:
    \"\"\"Your docstring here.\"\"\"
    # Your implementation here
    return "Your response"
```

**Test file requirements (tests/commands/test_{command_name}.py):**
- Create async tests using pytest-asyncio
- Test the happy path (successful execution)
- Test edge cases (empty input, invalid input, etc.)
- Import: `import pytest` and `from bot.commands.{command_name} import {command_name}_handler`
- Test function names should be descriptive (e.g., `test_{command_name}_success`)
- Each test should call the handler function and assert the response

Please create both files now. Make sure to handle edge cases gracefully and keep the code simple and focused."""

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(
                f"Generating code for command '{command_name}' using Claude Code CLI (attempt {attempt + 1}/{MAX_RETRIES})")

            # Remove existing files if they exist (for retry attempts)
            if command_file.exists():
                command_file.unlink()
            if test_file.exists():
                test_file.unlink()

            # Invoke Claude Code CLI with auto-accept (async subprocess)
            process = await asyncio.create_subprocess_exec(
                'claude', '--dangerously-skip-permissions', prompt,
                cwd=str(bot_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Read output streams concurrently for real-time logging
            stdout_lines = []
            stderr_lines = []

            try:
                # Read both streams and wait for process completion concurrently
                await asyncio.wait_for(
                    asyncio.gather(
                        _read_stream(process.stdout,
                                     "Claude CLI", stdout_lines),
                        _read_stream(process.stderr,
                                     "Claude CLI [stderr]", stderr_lines),
                        process.wait()
                    ),
                    timeout=120  # 2 minutes timeout for code generation
                )
                stdout = '\n'.join(stdout_lines)
                stderr = '\n'.join(stderr_lines)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise subprocess.TimeoutExpired('claude', 120)

            # Log full output at debug level for reference
            if stdout:
                logger.debug(f"Claude Code CLI complete stdout:\n{stdout}")
            if stderr:
                logger.debug(f"Claude Code CLI complete stderr:\n{stderr}")

            # Poll for file existence (Claude CLI may spawn bg processes or delay writes)
            poll_timeout = 120  # seconds
            poll_interval = 0.5  # seconds
            poll_elapsed = 0.0

            while not command_file.exists() and poll_elapsed < poll_timeout:
                logger.debug(
                    f"Waiting for command file to be created: {command_file}")
                await asyncio.sleep(poll_interval)
                poll_elapsed += poll_interval

            # Check if files were created after polling
            if not command_file.exists():
                error_msg = f"Command file not created: {command_file}"
                logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
                if attempt == MAX_RETRIES - 1:
                    return None, None, f"Failed to generate command file after {MAX_RETRIES} attempts. Claude Code output: {stdout}"
                continue

            # Read the generated command code
            command_code = command_file.read_text()
            logger.info(f"Successfully generated command file: {command_file}")

            # Check if test file was created (test file is optional)
            test_code = None
            if test_file.exists():
                test_code = test_file.read_text()
                logger.info(f"Successfully generated test file: {test_file}")
            else:
                logger.warning(
                    f"Test file not created, using fallback template")
                # Create a basic test template as fallback
                test_code = f"""import pytest
from bot.commands.{command_name} import {command_name}_handler


@pytest.mark.asyncio
async def test_{command_name}_basic():
    \"\"\"Basic test for {command_name} command.\"\"\"
    result = await {command_name}_handler("!{command_name} test")
    assert result is not None
"""
                # Write the fallback test file
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_text(test_code)

            logger.info(
                f"Successfully generated code for command '{command_name}'")
            return command_code, test_code, None

        except subprocess.TimeoutExpired:
            logger.warning(
                f"Attempt {attempt + 1} failed: Claude Code CLI timed out")
            if attempt == MAX_RETRIES - 1:
                return None, None, f"Claude Code CLI timed out after {MAX_RETRIES} attempts"
        except subprocess.CalledProcessError as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                return None, None, f"Claude Code CLI failed after {MAX_RETRIES} attempts: {e}"
        except Exception as e:
            logger.exception(f"Unexpected error generating code: {e}")
            return None, None, f"Unexpected error: {e}"

    return None, None, "Failed to generate code (should not reach here)"
