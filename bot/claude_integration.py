"""Claude Code CLI integration for generating command code."""
from __future__ import annotations
import asyncio
import json
import logging
import subprocess
from typing import Optional, Callable, Awaitable
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum retry attempts for Claude Code CLI
MAX_RETRIES = 3

# Session storage for multi-turn conversations
# Format: {command_name: session_id}
_session_store: dict[str, str] = {}


def save_session(command_name: str, session_id: str) -> None:
    """
    Save a session ID for a command (for multi-turn refinement).

    Args:
        command_name: Name of the command
        session_id: Session ID from Claude Code CLI
    """
    _session_store[command_name] = session_id
    logger.info(f"Saved session for command '{command_name}': {session_id}")


def get_session(command_name: str) -> Optional[str]:
    """
    Get a stored session ID for a command.

    Args:
        command_name: Name of the command

    Returns:
        Session ID if exists, None otherwise
    """
    return _session_store.get(command_name)


def clear_session(command_name: str) -> None:
    """
    Clear a stored session for a command.

    Args:
        command_name: Name of the command
    """
    if command_name in _session_store:
        del _session_store[command_name]
        logger.info(f"Cleared session for command '{command_name}'")


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
    model: str = "claude-sonnet-4-5-20250929",  # Kept for backward compatibility
    status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    resume_session: bool = False
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Generate command code using Claude Code CLI in headless mode.

    Args:
        api_key: Not used (kept for backward compatibility)
        command_name: Name of the command to generate
        command_description: Description of what the command should do
        model: Not used (kept for backward compatibility)
        status_callback: Optional async callback to send status updates
        resume_session: If True, resume previous session for this command

    Returns:
        tuple: (command_code, test_code, error_message)
               - command_code: Generated Python code for the command (read from file)
               - test_code: Generated test code for the command (read from file)
               - error_message: Error message if generation failed, None otherwise
    """
    # Helper to send status updates
    async def _send_status(message: str) -> None:
        logger.info(message)
        if status_callback:
            await status_callback(message)

    # Check if Claude CLI is available
    is_available, error = check_claude_cli_available()
    if not is_available:
        return None, None, error

    await _send_status(f"Generating command '{command_name}'...")

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
- Create a single async function with type-annotated parameters
- Return a string response to send back to the user, or None if no response needed
- Keep responses under 4000 characters
- Include the @command decorator with type-annotated parameters (NO pattern parameter)
- Parameters should be defined as tuples: (param_name, type, description, required)
- Include clear docstring explaining what the command does
- Always include matrix_context: Optional[dict] = None as the last parameter

**Command file structure:**
```python
from __future__ import annotations
from typing import Optional
from . import command

@command(
    name="{command_name}",
    description="{command_description}",
    params=[
        ("param1", str, "Description of param1", True),
        ("param2", int, "Description of param2", False)
    ]
)
async def {command_name}_handler(param1: str, param2: int = 0, matrix_context: Optional[dict] = None) -> Optional[str]:
    \"\"\"Your docstring here.\"\"\"
    # Your implementation here
    return "Your response"
```

For parameterless commands, omit the params argument or use an empty list:
```python
@command(
    name="{command_name}",
    description="{command_description}"
)
async def {command_name}_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    \"\"\"Your docstring here.\"\"\"
    return "Your response"
```

**Test file requirements (tests/commands/test_{command_name}.py):**
- Create async tests using pytest-asyncio
- Test the happy path (successful execution)
- Test edge cases (empty input, invalid input, etc.)
- Import: `import pytest` and `from bot.commands.{command_name} import {command_name}_handler`
- Test function names should be descriptive (e.g., `test_{command_name}_success`)
- Call the handler with structured parameters (NOT body strings)
- Example: `result = await {command_name}_handler(param1="test", param2=5)`

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

            # Build Claude CLI command with headless mode
            cmd = ['claude', '-p', prompt, '--output-format',
                   'json', '--dangerously-skip-permissions']

            # Resume previous session if requested
            if resume_session:
                session_id = get_session(command_name)
                if session_id:
                    cmd.extend(['--resume', session_id])
                    await _send_status(f"Resuming previous session for '{command_name}'...")

            # Invoke Claude Code CLI in headless mode (async subprocess)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(bot_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Read output streams concurrently
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
                    timeout=500  # 2 minutes timeout for code generation
                )
                stdout = '\n'.join(stdout_lines)
                _ = '\n'.join(stderr_lines)  # stderr captured but not used
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise subprocess.TimeoutExpired('claude', 120)

            # Parse JSON response
            try:
                response = json.loads(stdout)
                session_id = response.get('session_id')
                is_error = response.get('is_error', False)
                result_text = response.get('result', '')

                # Save session ID for future refinements
                if session_id:
                    save_session(command_name, session_id)

                if is_error:
                    error_msg = f"Claude Code CLI returned error: {result_text}"
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {error_msg}")
                    if attempt == MAX_RETRIES - 1:
                        return None, None, error_msg
                    continue

                logger.debug(f"Claude Code CLI response: {result_text}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                logger.debug(f"Raw stdout: {stdout}")
                # Continue with file checking logic anyway
                pass

            await _send_status("Checking generated files...")

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

            await _send_status("Reading generated command code...")

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
                    "Test file not created, using fallback template")
                await _send_status("Creating fallback test file...")
                # Create a basic test template as fallback
                test_code = f"""import pytest
from bot.commands.{command_name} import {command_name}_handler


@pytest.mark.asyncio
async def test_{command_name}_basic():
    \"\"\"Basic test for {command_name} command.\"\"\"
    result = await {command_name}_handler()
    assert result is not None
"""
                # Write the fallback test file
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_text(test_code)

            await _send_status(f"Successfully generated code for command '{command_name}'")
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
