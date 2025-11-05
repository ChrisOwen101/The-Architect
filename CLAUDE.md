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
- **Memory Integration**: Automatically injects relevant memories into conversation context and extracts new memories after replies

**bot/memory_store.py** - Persistent memory storage system
- `MemoryEntry`: Dataclass representing a single memory with id, timestamp, content, tags, and access tracking
- `MemoryStore`: Manages memory storage using markdown files with YAML frontmatter
- `add_memory()`: Stores new memories with automatic timestamp and UUID generation
- `get_recent_memories()`: Retrieves memories from a time window (default: 30 days) sorted by importance
- `search_memories()`: Search memories by keyword, date range, and tags with limit support
- `delete_memory()`: Removes specific memory by ID with ownership verification
- `get_stats()`: Returns statistics including count, age range, access patterns, and importance scores
- `calculate_importance()`: Scores memories based on recency (age-based decay) and access frequency
- Storage format: Markdown files in `data/memories/users/{user_id}.md` and `data/memories/rooms/{room_id}.md`
- Hybrid scope: Per-user memories (private) and per-room memories (shared within room)

**bot/memory_extraction.py** - Automatic memory extraction and injection
- `extract_memories_from_conversation()`: Uses OpenAI to analyze conversations and extract important facts
  - Runs as background task after AI replies (fire-and-forget, doesn't block responses)
  - Analyzes last 10 messages for facts about preferences, projects, dates, and personal information
  - Returns structured JSON with content, context, and tags
  - Stores extracted memories automatically via `MemoryStore`
- `inject_memories_into_context()`: Retrieves recent memories and adds them to conversation context
  - Fetches memories from last 30 days for both user and room scopes
  - Injects as system message after main prompt but before conversation history
  - Provides AI with awareness of past interactions for personalized responses
  - Gracefully handles errors by returning original context if injection fails
- Extraction prompt: Specialized system prompt that identifies preferences, projects, events, and personal details
- Memory context format: Markdown with separate sections for user-specific and room-wide memories

**bot/commands/recall.py** - Search and retrieve memories
- Command for users to explicitly search their stored memories
- Parameters: `query` (optional text search), `days` (time window, default 30), `limit` (max results, default 10)
- Displays memories with timestamps, content, context, tags, importance scores, and memory IDs
- Supports keyword search across content, context, and tags
- Access count increments on retrieval for importance scoring

**bot/commands/forget.py** - Delete specific memories
- Command for users to remove unwanted memories by ID
- Parameter: `memory_id` (UUID from recall command output)
- Ownership verification: Users can only delete their own memories
- Returns confirmation or error message

**bot/commands/memory_stats.py** - Display memory statistics
- Parameterless command showing overview of stored memories
- Statistics: total count, oldest/newest memories, most accessed memory, average importance
- Includes usage hints for recall and forget commands
- Handles empty state gracefully

**bot/user_input_handler.py** - Synchronous user input gathering system
- `PendingQuestion`: Dataclass tracking questions awaiting user responses with asyncio.Event coordination
- `ask_user_and_wait()`: Sends question to user and waits (non-blocking) for response with timeout (default 120s)
- `handle_user_response()`: Routes incoming messages to waiting questions (called from handlers.py)
- `is_pending_question()`: Checks if a thread has a pending question
- `cleanup_expired_questions()`: Background task that removes expired questions every 60 seconds
- Global `_pending_questions` dict keyed by thread_root_id enables message routing
- Uses asyncio.Event for non-blocking waiting while allowing other messages to be processed
- Automatic cleanup in try/finally blocks prevents memory leaks

**bot/commands/ask_user.py** - Ask user for input during conversations
- Command for multi-turn interactions within a single conversation flow
- Parameter: `question` (str, required) - the question to ask the user
- Sends question with ❓ emoji prefix for visual indication
- Waits up to 2 minutes for user response (configurable timeout)
- Returns "User answered: {response}" or timeout/error message
- Users do NOT need to mention the bot in their responses (mention requirement bypassed for pending questions)
- Enables complex workflows: gathering info step-by-step, confirming actions, escalating when uncertain

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

12. **Automatic memory system**: The bot automatically extracts and remembers important information from conversations using OpenAI analysis. Memories are stored in markdown files with YAML frontmatter, organized per-user and per-room. The system uses importance scoring (recency + access frequency) to prioritize relevant memories. Memory injection happens before each AI call (last 30 days), and extraction happens after responses as a background task (fire-and-forget). Users can search (`recall`), delete (`forget`), and view statistics (`memory_stats`) for their memories. Storage location: `data/memories/` (excluded from git for privacy).

13. **Multi-turn conversation support**: The `ask_user` command enables OpenAI to ask follow-up questions and wait for responses within a single conversation flow. Uses asyncio.Event-based waiting (non-blocking) with pending question registry keyed by thread_root_id. Responses bypass the bot mention requirement. Supports multiple sequential exchanges (OpenAI conversation loop handles up to 20 iterations). Timeout handling (120s default) prevents indefinite waits. Background cleanup task removes expired questions every 60 seconds to prevent memory leaks.

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

### Using Memory Commands

The bot automatically extracts and stores important information from conversations. Users can interact with their memories using these commands:

**View memory statistics:**
```
@architect memory_stats
```
Shows total count, oldest/newest memories, most accessed memory, and average importance score.

**Search memories:**
```
@architect recall                           # Show recent memories (last 30 days)
@architect recall query="Python"             # Search for specific keywords
@architect recall days=7                     # Memories from last week
@architect recall query="project" limit=5    # Search with custom limit
```
Returns memories with timestamps, content, context, tags, importance scores, and IDs.

**Delete specific memory:**
```
@architect forget memory_id="abc-123-def"
```
Deletes the memory with the specified ID (from `recall` output). Users can only delete their own memories.

**Memory system behavior:**
- **Automatic extraction**: After each conversation, the bot analyzes the last 10 messages and extracts important facts (runs as background task, doesn't block responses)
- **Automatic injection**: Before generating replies, the bot retrieves relevant memories from the last 30 days and includes them in the conversation context
- **Importance scoring**: Memories are ranked by `importance = (1.0 / (days_old + 1)) * log(access_count + 1)`, combining recency and access frequency
- **Privacy**: User memories are stored separately per user and per room (`data/memories/users/` and `data/memories/rooms/`)
- **Storage format**: Markdown files with YAML frontmatter (human-readable, version-control friendly)

### Using Multi-Turn Conversations

The bot can ask follow-up questions during conversations using the `ask_user` command. This is handled automatically by OpenAI function calling - you don't invoke it directly. The bot uses it when it needs additional information to complete a task.

**How it works:**
1. User makes a request: `@architect book me a flight`
2. OpenAI calls `ask_user(question="Where are you flying from?")`
3. Bot sends: `❓ Where are you flying from?`
4. User responds: `San Francisco` (no mention required)
5. OpenAI receives: `User answered: San Francisco`
6. OpenAI calls `ask_user(question="Where to?")`
7. Bot sends: `❓ Where to?`
8. User responds: `New York`
9. OpenAI receives: `User answered: New York`
10. OpenAI calls `book_flight(from="SFO", to="NYC")`
11. Bot completes the task

**Key behaviors:**
- **No mention required for responses**: Users can respond to questions without mentioning the bot
- **Timeout handling**: Questions expire after 2 minutes if user doesn't respond
- **Thread isolation**: Each thread can have one pending question at a time
- **Multiple exchanges**: OpenAI can ask multiple follow-up questions in sequence (up to 20 iterations)
- **Natural flow**: OpenAI decides when it has enough information to proceed

**Common use cases:**
- **Gathering required information**: `@architect create user` → bot asks for email, name, role
- **Confirming destructive actions**: `@architect delete database` → bot asks "Are you sure? (yes/no)"
- **Escalating when uncertain**: `@architect deploy` → bot asks "Which environment? (staging/prod)"
- **Collecting sensitive data**: `@architect setup API` → bot asks for API keys step-by-step

**Developer notes:**
- The `ask_user` command is registered like any other command and exposed to OpenAI
- Implemented in `bot/commands/ask_user.py` using `bot/user_input_handler.py`
- Responses are intercepted in `bot/handlers.py` before the bot mention check
- Uses asyncio.Event for non-blocking waiting (other messages can be processed)
- Global `_pending_questions` dict tracks questions by thread_root_id

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

18. **Memory extraction timing**: Memory extraction runs as a background task after AI replies using `asyncio.create_task()`. This is fire-and-forget - extraction errors don't affect user responses. Check logs for extraction failures.

19. **Memory storage location**: Memories are stored in `data/memories/` which is excluded from git (see `.gitignore`). This directory is created automatically on first memory storage. Backup this directory separately if you want to preserve conversation memories.

20. **Memory extraction costs**: Each conversation triggers an additional OpenAI API call for memory extraction (analyzing last 10 messages). This doubles OpenAI API usage. Monitor costs accordingly.

21. **Memory injection context window**: The bot injects all memories from the last 30 days into every conversation. For users with many memories, this may consume significant tokens. The 30-day window is hardcoded in `bot/openai_integration.py:322` - adjust if needed.

22. **Memory file format**: Memories use markdown with YAML frontmatter. Manual editing is possible but be careful with YAML syntax (especially timestamps and UUIDs). The parser is strict and will skip invalid entries.

23. **Room vs user memories**: Currently only user-specific memories are actively used (scope="user"). Room-wide memories (scope="room") are supported in the storage layer but not automatically extracted. You can add room memory extraction by modifying `bot/memory_extraction.py`.

24. **Memory deletion ownership**: Users can only delete their own memories. The `delete_memory()` function checks that `user_id` matches. This prevents cross-user memory deletion but doesn't prevent users from deleting memories in shared rooms.

25. **Dependencies for memory system**: The memory system requires `aiofiles` (async file I/O) and `PyYAML` (YAML parsing). These are in `requirements.txt`. Missing dependencies will cause import errors on bot startup.

26. **ask_user timeout behavior**: When using `ask_user`, if the user doesn't respond within 120 seconds (2 minutes), the function returns a timeout message to OpenAI. OpenAI can handle this gracefully (e.g., "I didn't receive a response, so I'll skip this step"). The timeout is configurable in `bot/commands/ask_user.py`.

27. **ask_user mention bypass**: When a question is pending in a thread, responses bypass the bot mention requirement. This is intentional - users shouldn't have to mention the bot for every answer. The bypass is implemented in `bot/handlers.py` by checking `is_pending_question()` before the mention check.

28. **ask_user thread isolation**: Each thread can have only ONE pending question at a time. If OpenAI tries to call `ask_user` twice in the same thread simultaneously, the second call will fail with an error message. This prevents confusion about which question the user is answering.

29. **ask_user cleanup task**: The cleanup task in `bot/user_input_handler.py` runs every 60 seconds to remove expired questions. This prevents memory leaks if questions somehow don't get cleaned up in the try/finally block. The task is automatically started in `bot/main.py` during bot initialization and stopped during shutdown.

30. **ask_user wrong user responses**: If user A is asked a question but user B responds in the same thread, the response is ignored. Only the user who was originally asked can provide the answer. This prevents security issues where one user could hijack another's conversation.

31. **ask_user and bot restarts**: If the bot restarts while questions are pending, those questions are lost (not persisted). Users will need to restart their requests. This is acceptable for most use cases but could be improved with persistence if needed.

32. **ask_user iteration limit**: The OpenAI conversation loop has a maximum of 20 iterations (defined in `bot/openai_integration.py`). If a conversation requires more than 20 function calls (including multiple `ask_user` calls), it will be truncated. This prevents infinite loops but could limit very complex multi-turn interactions.
