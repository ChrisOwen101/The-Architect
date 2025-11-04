# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**The Architect** - A self-modifying Matrix bot using `matrix-nio` and Claude Code CLI. The bot can dynamically generate and add new commands to itself using natural language descriptions. Users mention the bot and describe what they want (e.g., "@architect add a command called foo that does bar"), and the bot uses OpenAI function calling with Claude Code CLI to generate code, validates it, commits to git, and hot reloads commands without stopping. All commands are invoked via natural language mentions and processed through OpenAI GPT-5 function calling. Architecture prioritizes safety, modularity, and extensibility.

## Development Commands

### Setup
```bash
# Create and activate virtual environment (Python 3.11+ required)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Claude Code CLI (required for add command)
# Visit: https://docs.claude.com/claude-code

# Copy example config and edit
cp config.example.toml config.toml
# Create .env file with tokens:
# MATRIX_ACCESS_TOKEN="syt_xxx"
# OPENAI_API_KEY="sk-xxx"  # Required for AI mention responses
# Note: ANTHROPIC_API_KEY no longer needed (Claude Code CLI uses its own auth)
```

### Running
```bash
# Run the bot
python -m bot.main
```

### Testing
```bash
# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_handlers.py -v
```

## Architecture

### Core Components

**bot/config.py** - Configuration management
- Loads and validates `config.toml` using `tomllib` (Python 3.11+) or `tomli` fallback
- Exposes `BotConfig.access_token` and `BotConfig.openai_api_key` from environment (loaded from `.env`)
- Note: `anthropic_api_key` field still exists for backward compatibility but is no longer required
- Fails fast if required config keys are missing
- Config keys: `homeserver`, `user_id`, `device_id`, `display_name`, `log_level`, `allowed_rooms`, `enable_auto_commit`

**bot/commands/__init__.py** - Dynamic command registry system
- `CommandRegistry`: Manages command registration and execution with type-annotated parameters
- `@command` decorator: Registers commands with name, description, and optional parameter definitions (no patterns)
- Parameter definitions: List of tuples (param_name, param_type, description, required)
- `load_commands()`: Auto-discovers and loads all `.py` files in `bot/commands/`
- `execute_command(name, arguments)`: Executes command by name with structured arguments dictionary
- `generate_function_schemas()`: Generates OpenAI function calling schemas from command parameters

**bot/handlers.py** - Message handling
- `generate_reply(body)`: Deprecated, now routes to OpenAI function calling when bot is mentioned
- `on_message(client, room, event)`: Event handler that filters messages and sends replies as threaded messages
- Message filtering: Self-messages, historical events, and non-allowed rooms are filtered out
- **Mention-based invocation**: All commands require bot mention and are processed via OpenAI function calling
- Command execution: OpenAI decides which functions to call based on user's natural language request
- Threading: Intelligently determines thread root by checking if incoming event is already in a thread, then uses `rel_type: "m.thread"` to ensure all replies stay in the same thread. Includes `m.in_reply_to` fallback for non-thread-aware clients
- Timestamp filtering: Ignores historical events with `server_timestamp < START_TIME_MS - HISTORICAL_SKEW_MS` (5s skew)
- Room filtering: Uses `_config.allowed_rooms` from config.toml (set via `set_config()`)

**bot/main.py** - Bot lifecycle and Matrix client
- Bootstraps bot: loads config, calls `set_config()`, creates `AsyncClient`, registers event callbacks
- `login_if_needed()`: Injects pre-issued access token (no password login). Manually sets `client.user_id` at bot/main.py:42
- Sync loop with basic retry (5s sleep on exception)
- Signal handlers for graceful shutdown on SIGINT/SIGTERM (sets `STOP` event)

**bot/claude_integration.py** - Claude Code CLI integration
- `generate_command_code()`: Invokes Claude Code CLI to generate and write command code and tests
- `check_claude_cli_available()`: Verifies Claude Code CLI is installed and accessible
- Uses `subprocess` to call `claude --auto-accept <prompt>` with working directory set to bot root
- Claude Code writes files directly to `bot/commands/` and `tests/commands/`
- Retry logic: Up to 3 attempts if files aren't created successfully
- Returns tuple: (command_code, test_code, error_message) by reading generated files

**bot/code_validator.py** - Code safety validation
- `validate_command_code()`: AST parsing, dangerous operation detection, structure validation
- Blocks dangerous imports: `subprocess`, `os.system`, `eval`, `exec`, `open`
- Verifies required handler function structure and @command decorator
- `validate_test_code()`: Basic syntax and compilation checks for tests

**bot/git_integration.py** - Git operations
- `git_commit()`: Stages files and commits with message
- `git_remove()`: Removes files from git and commits
- Uses subprocess to call git commands
- Returns (success, error_message) tuple

**bot/reload.py** - Command hot reload mechanism
- `reload_commands()`: Dynamically reloads command modules using `importlib.reload()`
- Keeps bot running without process restart
- Called after successful command add/remove operations
- Allows current requests to continue processing

**bot/openai_integration.py** - OpenAI GPT-5 integration for conversational AI
- `is_bot_mentioned()`: Detects if bot's user_id appears in message body or formatted_body
- `get_thread_context()`: Fetches up to 50 messages from a thread using `client.room_messages()`
- `build_conversation_history()`: Converts Matrix messages to OpenAI API format with role labels
- `call_openai_api()`: Makes HTTP POST requests to OpenAI Chat Completions API using aiohttp
- `generate_ai_reply()`: Main function that orchestrates thread context gathering, API calls, and error handling
- Uses GPT-5 model with "The Architect" Matrix-themed system prompt
- Retry logic: Two attempts with 2-second delay between failures
- Returns user-friendly error messages on API failures

### Key Architectural Decisions

1. **Type-annotated command system**: Commands are individual Python modules in `bot/commands/`. Each uses `@command` decorator with explicit parameter definitions (name, type, description, required). No regex patterns - all parameters are type-safe.

2. **Natural language invocation**: All commands are invoked by mentioning the bot with natural language (e.g., "@architect list commands", "@architect add a dice roller"). OpenAI GPT-5 function calling interprets user intent and maps to appropriate command with structured parameters.

3. **Self-modifying capability**: `add` command uses OpenAI function calling + Claude Code CLI to generate new command code. Claude Code writes files directly, code is validated, committed to git, and commands are hot reloaded without stopping the bot.

4. **Safety-first validation**: All generated code goes through AST parsing, dangerous operation detection, and compilation checks before execution.

5. **Git integration**: All code changes are automatically committed (if `enable_auto_commit` is true) for version control and rollback capability.

6. **Hot reload with importlib**: Bot uses Python's `importlib.reload()` to dynamically reload command modules without process restart, keeping the bot running and allowing current requests to complete.

7. **Token injection pattern**: Uses pre-issued access tokens (Matrix + OpenAI) rather than password login. The `client.user_id` must be set manually when injecting tokens (handled in `login_if_needed` at bot/main.py:42).

8. **Historical event filtering**: Uses bot start time (`START_TIME_MS`) to filter old messages during initial sync, preventing replies to historical messages.

9. **Config-based room allowlist**: Room filtering uses `allowed_rooms` from config.toml rather than hardcoded values.

10. **Thread-based replies**: Bot replies are sent as threaded messages using Matrix's `m.thread` relation type. The bot intelligently detects if an incoming message is already part of a thread and replies to the same thread root, keeping entire conversations organized together. The `m.in_reply_to` fallback is included for clients that don't support threads.

11. **OpenAI function calling integration**: The bot automatically generates OpenAI function schemas from command parameter definitions. This enables natural language command invocation without manual pattern matching. The bot fetches full thread context (up to 50 messages) to maintain conversation continuity.

## Development Patterns

### Adding New Commands (Two Methods)

**Method 1: Using natural language (recommended for bot users)**
```
@architect add a command called mycommand that does [description]
```
The bot will generate, validate, and install the command automatically using OpenAI function calling.

**Method 2: Manual creation (for developers)**
Create `bot/commands/mycommand.py`:

**For commands with parameters:**
```python
from __future__ import annotations
from typing import Optional
from . import command

@command(
    name="mycommand",
    description="What this command does",
    params=[
        ("param1", str, "Description of param1", True),
        ("param2", int, "Description of param2", False)
    ]
)
async def mycommand_handler(param1: str, param2: int = 0, matrix_context: Optional[dict] = None) -> Optional[str]:
    """Implementation here."""
    # param1 and param2 are already parsed and typed
    return f"Response: {param1}, {param2}"
```

**For parameterless commands:**
```python
@command(
    name="mycommand",
    description="What this command does"
)
async def mycommand_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    """Implementation here."""
    return "Response"
```

Add tests in `tests/commands/test_mycommand.py`. Commands are hot reloaded automatically when added/removed, or you can manually trigger a reload by restarting the bot.

### Testing Patterns
- Use pytest with pytest-asyncio for async tests
- Test command handlers directly by importing and calling them
- Test both happy paths and edge cases (especially None returns)
- Command tests go in `tests/commands/test_<name>.py`
- Core system tests in `tests/test_*.py`

### Security
- **Never log or print tokens**: Matrix access token and OpenAI API key are sensitive
- **All secrets from environment**: Load via `.env` file, never hardcode
- **Claude Code CLI auth**: Uses its own authentication system (separate from bot)
- **OpenAI API key**: Required for all bot interactions (mention-based commands and AI responses)
- **Code validation**: All generated code goes through AST validation to block dangerous operations
- **Command protection**: Core meta-commands (add, remove, list) are protected from removal in code
- **Git tracking**: All code changes are version controlled for audit trail
- **CLI requirements**: Claude Code CLI must be installed and authenticated separately
- **Type safety**: Structured parameters prevent injection attacks common in string-based command parsing

### Extension Points
- **Command permissions**: Add user-based permission checks in meta-commands (currently anyone in allowed rooms can add/remove)
- **Command categories**: Extend registry to support command grouping/categories via additional metadata
- **Rate limiting**: Add rate limits on add command to prevent API abuse
- **Command versioning**: Track command versions in registry for rollback capability
- **Persistence**: Add `SqliteStore` to persist sync tokens and avoid processing missed events
- **Approval workflow**: Add manual approval step before executing generated code
- **Parameter validation**: Add custom validators for parameter types beyond basic type checking

## Important Gotchas

1. **Manual user_id assignment**: When injecting access token, must manually set `client.user_id` (see bot/main.py:42). The nio library doesn't populate this automatically.

2. **Command reload**: After adding/removing commands, commands are hot reloaded automatically using `importlib.reload()`. The bot stays running with no downtime, and current requests continue processing.

3. **Command name collisions**: If a command already exists, the add command will fail. Ask the bot to remove it first to replace.

4. **Delayed reload**: Commands use `asyncio.create_task(_delayed_reload())` to allow response message to send before reloading (1 second delay). This ensures the user sees the success message before the reload happens.

5. **Timestamp filtering**: The `START_TIME_MS` and `HISTORICAL_SKEW_MS` constants prevent historical replies. Modifying these affects first-sync behavior.

6. **Code validation limitations**: AST validation catches many issues but can't detect all malicious code patterns. Review generated code in production.

7. **Git must be initialized**: Auto-commit feature requires the directory to be a git repository with proper remote setup.

8. **Test generation**: Tests are auto-generated but may not be comprehensive. Review and enhance them as needed.

9. **Claude Code CLI requirement**: The add command requires Claude Code CLI to be installed and authenticated. Without it, command generation will fail with a helpful error message.

10. **CLI timeout**: Claude Code CLI invocations have a 2-minute timeout. Complex commands may need adjustment of this timeout in `bot/claude_integration.py`.

11. **Command loading order**: Commands are loaded alphabetically by filename. If order matters, use numeric prefixes (e.g., `01_base.py`, `02_advanced.py`).

12. **Thread-based replies**: All bot replies are sent as threaded messages using Matrix's threading feature. This means responses appear in a thread rooted at the user's original message. Commands should not override this behavior unless there's a specific reason to do so.

13. **OpenAI API key requirement**: All bot interactions require a valid OpenAI API key in the `.env` file. Without it, the bot will raise a RuntimeError on startup when config is loaded. The bot must be mentioned to respond.

14. **Mention required**: The bot will only respond to messages that mention it (contain its user_id). This prevents accidental invocations and reduces API costs.

15. **Thread context limitations**: The bot fetches up to 50 messages from a thread for AI context. For very long threads, earlier messages will be truncated. The `matrix-nio` library doesn't have native thread API support, so the bot filters messages manually by checking `m.relates_to` fields.

16. **Self-message filtering**: The bot filters out its own messages to prevent infinite loops. This is critical for the AI response feature, as the bot would otherwise respond to its own AI-generated messages.

17. **Parameter types**: Handler function signatures must match the params defined in @command decorator. The params define (name, type, description, required), and the handler must accept those parameters with matching names and types.
