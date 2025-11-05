from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from bot.function_executor import execute_function, execute_functions, FunctionExecutionError
from bot.commands import CommandRegistry


class MockCommand:
    """Mock command for testing."""

    def __init__(self, name, description, handler, params=None):
        self.name = name
        self.description = description
        self.handler = handler
        self.params = params or []
        self.module_name = "test"


# Test Function Executor


@pytest.mark.asyncio
async def test_execute_function_no_params():
    """Test executing a function with no parameters."""

    async def test_handler():
        return "success"

    with patch('bot.commands.get_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_command = MockCommand("test", "Test command", test_handler)
        mock_registry._commands = {"test": mock_command}
        mock_get_registry.return_value = mock_registry

        result = await execute_function("test", {})

        assert result == "success"


@pytest.mark.asyncio
async def test_execute_function_with_params():
    """Test executing a function with parameters."""

    async def test_handler(name: str, count: int):
        return f"Hello {name}, count={count}"

    with patch('bot.commands.get_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_command = MockCommand("test", "Test command", test_handler)
        mock_registry._commands = {"test": mock_command}
        mock_get_registry.return_value = mock_registry

        result = await execute_function("test", {"name": "Alice", "count": 5})

        assert result == "Hello Alice, count=5"


@pytest.mark.asyncio
async def test_execute_function_with_matrix_context():
    """Test executing a function that needs matrix_context."""

    async def test_handler(name: str, matrix_context=None):
        assert matrix_context is not None
        assert matrix_context["test_key"] == "test_value"
        return f"Hello {name}"

    with patch('bot.commands.get_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_command = MockCommand("test", "Test command", test_handler)
        mock_registry._commands = {"test": mock_command}
        mock_get_registry.return_value = mock_registry

        matrix_context = {"test_key": "test_value"}
        result = await execute_function("test", {"name": "Bob"}, matrix_context)

        assert result == "Hello Bob"


@pytest.mark.asyncio
async def test_execute_function_not_found():
    """Test executing a non-existent function."""
    with patch('bot.commands.get_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry._commands = {}
        mock_get_registry.return_value = mock_registry

        with pytest.raises(FunctionExecutionError, match="not found"):
            await execute_function("nonexistent", {})


@pytest.mark.asyncio
async def test_execute_function_argument_error():
    """Test executing a function with wrong arguments."""

    async def test_handler(name: str):
        return f"Hello {name}"

    with patch('bot.commands.get_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_command = MockCommand("test", "Test command", test_handler)
        mock_registry._commands = {"test": mock_command}
        mock_get_registry.return_value = mock_registry

        # Missing required argument
        with pytest.raises(FunctionExecutionError, match="Invalid arguments"):
            await execute_function("test", {})


@pytest.mark.asyncio
async def test_execute_functions_parallel():
    """Test executing multiple functions in parallel."""

    async def ping_handler():
        return "pong"

    async def echo_handler(message: str):
        return f"Echo: {message}"

    with patch('bot.commands.get_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry._commands = {
            "ping": MockCommand("ping", "Ping", ping_handler),
            "echo": MockCommand("echo", "Echo", echo_handler)
        }
        mock_get_registry.return_value = mock_registry

        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "ping",
                    "arguments": "{}"
                }
            },
            {
                "id": "call_2",
                "function": {
                    "name": "echo",
                    "arguments": '{"message": "test"}'
                }
            }
        ]

        results = await execute_functions(tool_calls)

        assert len(results) == 2
        assert results[0]["tool_call_id"] == "call_1"
        assert results[0]["content"] == "pong"
        assert results[1]["tool_call_id"] == "call_2"
        assert results[1]["content"] == "Echo: test"


@pytest.mark.asyncio
async def test_execute_functions_with_error():
    """Test executing functions where one fails."""

    async def success_handler():
        return "success"

    with patch('bot.commands.get_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry._commands = {
            "success": MockCommand("success", "Success", success_handler),
        }
        mock_get_registry.return_value = mock_registry

        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "success",
                    "arguments": "{}"
                }
            },
            {
                "id": "call_2",
                "function": {
                    "name": "nonexistent",
                    "arguments": "{}"
                }
            }
        ]

        results = await execute_functions(tool_calls)

        assert len(results) == 2
        assert results[0]["content"] == "success"
        assert "Error" in results[1]["content"]


# Test Function Schema Generation


def test_generate_function_schemas():
    """Test generating function schemas from command registry."""
    registry = CommandRegistry()

    # Register test commands
    async def ping_handler():
        """Check if bot is online."""
        return "pong"

    async def greet_handler(name: str, greeting: str = "Hello"):
        """Greet a user."""
        return f"{greeting}, {name}!"

    async def add_handler(command_name: str, description: str):
        """Add command."""
        return "added"

    registry.register("ping", "Ping the bot", [], ping_handler)
    registry.register("greet", "Greet someone", [
        ("name", str, "Name of person to greet", True),
        ("greeting", str, "Greeting to use", False)
    ], greet_handler)
    registry.register("add", "Add command", [
        ("command_name", str, "Name of command", True),
        ("description", str, "Description", True)
    ], add_handler)

    schemas = registry.generate_function_schemas()

    # Should have all 3 schemas
    assert len(schemas) == 3

    # Check ping schema
    ping_schema = next(s for s in schemas if s["function"]["name"] == "ping")
    assert ping_schema["type"] == "function"
    assert ping_schema["function"]["description"] == "Ping the bot"
    assert ping_schema["function"]["parameters"]["type"] == "object"
    assert ping_schema["function"]["parameters"]["properties"] == {}

    # Check greet schema
    greet_schema = next(s for s in schemas if s["function"]["name"] == "greet")
    assert "name" in greet_schema["function"]["parameters"]["properties"]
    assert "greeting" in greet_schema["function"]["parameters"]["properties"]
    assert greet_schema["function"]["parameters"]["properties"]["name"]["type"] == "string"
    assert "name" in greet_schema["function"]["parameters"]["required"]
    assert "greeting" not in greet_schema["function"]["parameters"]["required"]  # Not required (False)


def test_generate_function_schemas_all_commands():
    """Test that all commands are included in schemas."""
    registry = CommandRegistry()

    async def add_handler(command_name: str, description: str):
        return "added"

    async def remove_handler(command_name: str):
        return "removed"

    async def list_handler():
        return "listed"

    async def safe_handler():
        return "safe"

    registry.register("add", "Add", [
        ("command_name", str, "Name", True),
        ("description", str, "Description", True)
    ], add_handler)
    registry.register("remove", "Remove", [
        ("command_name", str, "Name", True)
    ], remove_handler)
    registry.register("list", "List", [], list_handler)
    registry.register("safe", "Safe", [], safe_handler)

    schemas = registry.generate_function_schemas()

    # All 4 commands should be included
    assert len(schemas) == 4
    command_names = {s["function"]["name"] for s in schemas}
    assert command_names == {"add", "remove", "list", "safe"}


def test_generate_function_schemas_with_types():
    """Test schema generation with different parameter types."""
    registry = CommandRegistry()

    async def complex_handler(
        text: str,
        count: int,
        ratio: float,
        enabled: bool
    ):
        return "ok"

    registry.register("complex", "Complex", [
        ("text", str, "Text parameter", True),
        ("count", int, "Count parameter", True),
        ("ratio", float, "Ratio parameter", True),
        ("enabled", bool, "Enabled parameter", True)
    ], complex_handler)

    schemas = registry.generate_function_schemas()

    assert len(schemas) == 1
    props = schemas[0]["function"]["parameters"]["properties"]

    assert props["text"]["type"] == "string"
    assert props["count"]["type"] == "integer"
    assert props["ratio"]["type"] == "number"
    assert props["enabled"]["type"] == "boolean"

    # All should be required
    required = schemas[0]["function"]["parameters"]["required"]
    assert set(required) == {"text", "count", "ratio", "enabled"}


# Test Integration


@pytest.mark.asyncio
async def test_function_calling_flow_integration():
    """Test the full function calling flow with mocked OpenAI API."""
    from bot.openai_integration import generate_ai_reply

    # Mock components
    mock_client = MagicMock()
    mock_client.user_id = "@bot:matrix.org"
    mock_room = MagicMock()
    mock_room.room_id = "!test:matrix.org"
    mock_event = MagicMock()
    mock_event.body = "@bot:matrix.org hello"
    mock_event.sender = "@user:matrix.org"
    mock_event.event_id = "$event1"
    mock_event.server_timestamp = 1000

    mock_config = MagicMock()
    mock_config.openai_api_key = "sk-test"

    # Mock get_thread_context to return simple context
    with patch('bot.openai_integration.get_thread_context') as mock_get_context:
        mock_get_context.return_value = [mock_event]

        # Mock get_registry
        with patch('bot.commands.get_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.generate_function_schemas.return_value = []
            mock_get_registry.return_value = mock_registry

            # Mock OpenAI API to return text response (no function calls)
            with patch('bot.openai_integration.call_openai_api') as mock_api:
                mock_api.return_value = (
                    {"content": "Hello! How can I help you?"},
                    None
                )

                result = await generate_ai_reply(mock_event, mock_room, mock_client, mock_config)

                assert result == "Hello! How can I help you?"
                assert mock_api.call_count == 1


@pytest.mark.asyncio
async def test_function_calling_with_tool_calls():
    """Test function calling flow when LLM requests tool calls."""
    from bot.openai_integration import generate_ai_reply

    # Mock components
    mock_client = MagicMock()
    mock_client.user_id = "@bot:matrix.org"
    mock_room = MagicMock()
    mock_event = MagicMock()
    mock_event.body = "@bot:matrix.org ping me"
    mock_event.sender = "@user:matrix.org"
    mock_event.event_id = "$event1"
    mock_event.server_timestamp = 1000

    mock_config = MagicMock()
    mock_config.openai_api_key = "sk-test"

    with patch('bot.openai_integration.get_thread_context') as mock_get_context:
        mock_get_context.return_value = [mock_event]

        # Mock registry with ping function
        async def ping_handler():
            return "pong"

        with patch('bot.commands.get_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_command = MockCommand("ping", "Ping", ping_handler)
            mock_registry._commands = {"ping": mock_command}
            mock_registry.generate_function_schemas.return_value = [{
                "type": "function",
                "function": {
                    "name": "ping",
                    "description": "Ping the bot",
                    "parameters": {"type": "object", "properties": {}}
                }
            }]
            mock_get_registry.return_value = mock_registry

            # Mock OpenAI API - first call returns tool_calls, second returns text
            with patch('bot.openai_integration.call_openai_api') as mock_api:
                mock_api.side_effect = [
                    # First call: LLM wants to call ping
                    ({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_123",
                            "function": {
                                "name": "ping",
                                "arguments": "{}"
                            }
                        }]
                    }, None),
                    # Second call: LLM synthesizes response
                    ({"content": "The bot is online and responded with pong!"}, None)
                ]

                result = await generate_ai_reply(mock_event, mock_room, mock_client, mock_config)

                assert result == "The bot is online and responded with pong!"
                assert mock_api.call_count == 2
