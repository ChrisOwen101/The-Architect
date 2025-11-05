# The Architect - Self-Modifying Matrix Bot

A conversational Matrix bot that can modify itself. Mention the bot and ask it to do things in natural language - it can even generate and add new commands to itself on the fly.

## What It Does

**The Architect** is a Matrix bot powered by OpenAI GPT-5 that responds to mentions and can extend its own capabilities. Instead of typing commands like `!ping` or `/help`, you simply mention the bot and tell it what you want:

- `@architect what commands do you have?`
- `@architect add a dice roller command`
- `@architect roll 2d6 for me`
- `@architect remember that I prefer Python 3.11`
- `@architect what do you remember about me?`

The bot uses natural language understanding to figure out what you want, executes the appropriate commands, and responds in threaded messages to keep conversations organized.

## Key Features

### Natural Language Interface

Mention the bot and describe what you want. No need to memorize command syntax - just talk to it naturally.

### Self-Modifying

Ask the bot to add new commands and it will:

1. Use Claude Code CLI to generate the command code
2. Validate the code for safety
3. Write tests automatically
4. Commit changes to git
5. Hot reload the new command (no restart needed)

### Automatic Memory

The bot remembers important information from conversations:

- User preferences and facts
- Project details and dates
- Context from previous discussions
- Searchable with `@architect recall` command

### Thread-Based Conversations

All replies are sent as threaded messages, keeping conversations organized and easy to follow.

## Quick Start

### Prerequisites

- Python 3.11 or newer
- Claude Code CLI installed and authenticated ([install instructions](https://docs.claude.com/claude-code))
- Matrix account with access token
- OpenAI API key

### Installation

1. **Create and activate virtual environment:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure the bot:**

```bash
# Copy example config
cp config.example.toml config.toml

# Edit config.toml to set your Matrix homeserver, user_id, device_id, and allowed_rooms
$EDITOR config.toml
```

4. **Set up environment variables:**

```bash
# Create .env file with your tokens
echo 'MATRIX_ACCESS_TOKEN="syt_xxx"' > .env
echo 'OPENAI_API_KEY="sk-xxx"' >> .env
```

You'll need:

- **Matrix Access Token**: Obtain from your Matrix account settings or login API
- **OpenAI API Key**: Get from https://platform.openai.com/
- **Claude Code CLI**: Install and authenticate separately (used for code generation)

5. **Run the bot:**

```bash
python -m bot.main
```

## Using The Architect

All interactions with the bot happen by mentioning it in a Matrix room. The bot will respond to natural language requests.

### Example Interactions

**List available commands:**

```
@architect what can you do?
@architect list your commands
```

**Add a new command:**

```
@architect add a command that rolls dice
@architect create a command to convert temperatures from F to C
```

**Use commands:**

```
@architect roll 3d6
@architect convert 72F to celsius
```

**Memory commands:**

```
@architect remember that I'm working on a Python web scraper
@architect what do you remember about my projects?
@architect recall query="Python" days=7
@architect forget memory_id="abc-123-def"
```

**Remove commands:**

```
@architect remove the dice command
```

### Built-in Commands

The bot comes with several built-in commands:

- **add** - Generate and add new commands using natural language descriptions
- **remove** - Remove dynamically added commands
- **list** - List all available commands
- **recall** - Search your stored memories
- **forget** - Delete specific memories by ID
- **memory_stats** - View memory system statistics
- **createdm** - Create direct message rooms
- **listmembers** - List members of current room
- **imagine** - Generate images using DALL-E (if configured)

## How It Works

### Natural Language Processing

All bot interactions use OpenAI function calling. When you mention the bot:

1. The bot fetches the conversation thread context (up to 50 messages)
2. Sends your request to OpenAI GPT-5 with available commands as "functions"
3. OpenAI decides which command to call based on your natural language
4. The bot executes the command and responds in the same thread

### Self-Modification System

When you ask the bot to add a command:

1. OpenAI function calling identifies it as an "add command" request
2. The bot invokes Claude Code CLI to generate the command code and tests
3. Generated code is validated for safety (AST parsing, dangerous operation detection)
4. Code is written to `bot/commands/<name>.py` and tests to `tests/commands/test_<name>.py`
5. Changes are committed to git (if enabled)
6. Commands are hot reloaded using Python's `importlib.reload()` - no restart needed

### Automatic Memory System

The bot automatically remembers important information:

- **Extraction**: After each conversation, analyzes the last 10 messages for important facts
- **Storage**: Stores memories in markdown files with YAML frontmatter (`data/memories/`)
- **Injection**: Before responding, retrieves recent memories (last 30 days) and includes them in context
- **Organization**: Per-user memories (private) and per-room memories (shared)
- **Importance Scoring**: Combines recency and access frequency to prioritize relevant memories

### Safety Features

- **Code Validation**: AST parsing blocks dangerous imports (`subprocess`, `eval`, `exec`, etc.)
- **Type Safety**: Commands use structured parameters with type annotations
- **Git Tracking**: All code changes are version controlled
- **Protected Commands**: Core meta-commands cannot be removed
- **Room Allowlist**: Bot only responds in configured allowed rooms

## Architecture

```
bot/
  commands/              # Dynamic command modules (hot-reloadable)
    __init__.py         # Command registry with type-annotated parameters
    add.py              # Self-modification command
    remove.py           # Command removal
    list.py             # List commands
    recall.py           # Search memories
    forget.py           # Delete memories
    memory_stats.py     # Memory statistics
    <custom>.py         # Your dynamically added commands

  config.py             # Configuration management (config.toml + .env)
  handlers.py           # Message event handlers and thread detection
  main.py               # Bot lifecycle and Matrix client

  claude_integration.py # Claude Code CLI subprocess integration
  code_validator.py     # AST-based code safety validation
  git_integration.py    # Git commit operations
  reload.py             # Hot reload mechanism (importlib)

  openai_integration.py # OpenAI GPT-5 function calling
  memory_store.py       # Persistent memory storage (markdown + YAML)
  memory_extraction.py  # Automatic memory extraction and injection

tests/
  commands/             # Tests for commands
  test_*.py             # Core system tests
```

## Configuration

**config.toml:**

```toml
[bot]
homeserver = "https://matrix.example.com"
user_id = "@architect:example.com"
device_id = "ARCHITECT_DEV"
display_name = "The Architect"
log_level = "INFO"

# List of room IDs where the bot can respond
allowed_rooms = ["!roomid:example.com"]

# Auto-commit code changes to git
enable_auto_commit = true
```

**.env:**

```bash
MATRIX_ACCESS_TOKEN="syt_your_matrix_token"
OPENAI_API_KEY="sk-your_openai_key"
```

## Testing

```bash
# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_handlers.py -v

# Run specific test
pytest tests/test_memory_store.py::test_add_memory -v
```

## Important Notes

- **Mention Required**: The bot only responds to messages that mention its user_id
- **OpenAI Costs**: Every conversation uses OpenAI API (GPT-5) - monitor your usage
- **Memory Extraction**: Doubles OpenAI API usage (one call for response, one for memory extraction)
- **Claude Code CLI**: Required for adding new commands - must be installed and authenticated separately
- **Hot Reload**: Commands are reloaded without restarting the bot using `importlib.reload()`
- **Thread Context**: The bot maintains conversation context within Matrix threads (up to 50 messages)
- **Memory Privacy**: Memories are stored in `data/memories/` (not tracked in git) - backup separately

## Security Considerations

- Never commit `.env` file or expose tokens
- Review generated code before deploying to production
- Code validator blocks many dangerous patterns but isn't foolproof
- Consider adding user permission system (currently anyone in allowed rooms can add commands)
- Memory files contain conversation data - handle per your privacy requirements

## Development

See `CLAUDE.md` for detailed development guidelines, architecture decisions, and extension points.

## License

MIT
