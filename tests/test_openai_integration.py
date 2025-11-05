from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.openai_integration import (
    is_bot_mentioned,
    build_conversation_history,
    call_openai_api,
    generate_ai_reply,
    get_thread_context,
)


class MockEvent:
    """Mock Matrix event for testing."""

    def __init__(self, body, sender, event_id="$test", timestamp=1000, formatted_body=None, source=None):
        self.body = body
        self.sender = sender
        self.event_id = event_id
        self.server_timestamp = timestamp
        self.formatted_body = formatted_body
        self.source = source or {}


class MockClient:
    """Mock Matrix client for testing."""

    def __init__(self, user_id="@architect:matrix.org"):
        self.user_id = user_id

    async def room_messages(self, room_id, start, limit):
        """Mock room_messages method."""
        return MagicMock(chunk=[])


class MockRoom:
    """Mock Matrix room for testing."""

    def __init__(self, room_id="!test:matrix.org", prev_batch="s12345_token"):
        self.room_id = room_id
        self.prev_batch = prev_batch


class MockConfig:
    """Mock bot config for testing."""

    @property
    def openai_api_key(self):
        return "sk-test-key"


# Tests for is_bot_mentioned


def test_is_bot_mentioned_in_body():
    """Test bot mention detection in plain body."""
    client = MockClient(user_id="@architect:matrix.org")
    event = MockEvent(body="Hello @architect:matrix.org how are you?", sender="@user:matrix.org")
    assert is_bot_mentioned(client, event) is True


def test_is_bot_mentioned_not_present():
    """Test when bot is not mentioned."""
    client = MockClient(user_id="@architect:matrix.org")
    event = MockEvent(body="Hello everyone!", sender="@user:matrix.org")
    assert is_bot_mentioned(client, event) is False


def test_is_bot_mentioned_in_formatted_body():
    """Test bot mention detection in formatted body."""
    client = MockClient(user_id="@architect:matrix.org")
    event = MockEvent(
        body="Hello architect",
        sender="@user:matrix.org",
        formatted_body='<a href="https://matrix.to/#/@architect:matrix.org">architect</a> hello'
    )
    assert is_bot_mentioned(client, event) is True


def test_is_bot_mentioned_no_user_id():
    """Test when client has no user_id."""
    client = MockClient(user_id=None)
    event = MockEvent(body="Hello @architect:matrix.org", sender="@user:matrix.org")
    assert is_bot_mentioned(client, event) is False


# Tests for build_conversation_history


def test_build_conversation_history_simple():
    """Test building conversation history from messages."""
    bot_user_id = "@architect:matrix.org"
    messages = [
        MockEvent(body="Hello bot", sender="@user:matrix.org"),
        MockEvent(body="Hello! How can I help?", sender=bot_user_id),
        MockEvent(body="What is the Matrix?", sender="@user:matrix.org"),
    ]

    history = build_conversation_history(messages, bot_user_id)

    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert "[user]" in history[0]["content"]
    assert "Hello bot" in history[0]["content"]

    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hello! How can I help?"

    assert history[2]["role"] == "user"
    assert "What is the Matrix?" in history[2]["content"]


def test_build_conversation_history_multi_user():
    """Test conversation history with multiple users."""
    bot_user_id = "@architect:matrix.org"
    messages = [
        MockEvent(body="Question 1", sender="@alice:matrix.org"),
        MockEvent(body="Response 1", sender=bot_user_id),
        MockEvent(body="Question 2", sender="@bob:matrix.org"),
    ]

    history = build_conversation_history(messages, bot_user_id)

    assert len(history) == 3
    assert "[alice]" in history[0]["content"]
    assert "[bob]" in history[2]["content"]


def test_build_conversation_history_empty():
    """Test with empty message list."""
    history = build_conversation_history([], "@bot:matrix.org")
    assert history == []


# Tests for call_openai_api


@pytest.mark.asyncio
async def test_call_openai_api_success():
    """Test successful OpenAI API call."""
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"}
    ]

    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "Hello! How can I help you?"
                }
            }
        ]
    }

    with patch('bot.openai_integration.aiohttp.ClientSession') as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session.post = MagicMock(return_value=mock_resp)

        reply, error = await call_openai_api(messages, "sk-test-key")

        assert reply == {"content": "Hello! How can I help you?"}
        assert error is None


@pytest.mark.asyncio
async def test_call_openai_api_error():
    """Test OpenAI API call with error response."""
    messages = [{"role": "user", "content": "Hello"}]

    with patch('bot.openai_integration.aiohttp.ClientSession') as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_resp.text = AsyncMock(return_value="Unauthorized")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session.post = MagicMock(return_value=mock_resp)

        reply, error = await call_openai_api(messages, "invalid-key")

        assert reply is None
        assert "401" in error


@pytest.mark.asyncio
async def test_call_openai_api_timeout():
    """Test OpenAI API call timeout."""
    messages = [{"role": "user", "content": "Hello"}]

    with patch('bot.openai_integration.aiohttp.ClientSession') as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Simulate timeout
        import asyncio

        mock_resp = AsyncMock()
        mock_resp.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_session.post = MagicMock(return_value=mock_resp)

        reply, error = await call_openai_api(messages, "sk-test-key")

        assert reply is None
        assert "timed out" in error.lower()


@pytest.mark.asyncio
async def test_call_openai_api_empty_response():
    """Test OpenAI API with empty response content."""
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = {
        "choices": [
            {
                "message": {
                    "content": ""
                }
            }
        ]
    }

    with patch('bot.openai_integration.aiohttp.ClientSession') as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session.post = MagicMock(return_value=mock_resp)

        reply, error = await call_openai_api(messages, "sk-test-key")

        assert reply == {"content": ""}
        assert error is None


# Tests for get_thread_context


@pytest.mark.asyncio
async def test_get_thread_context_basic():
    """Test fetching thread context."""
    client = MockClient()
    room = MockRoom()
    thread_root_id = "$thread_root"

    # Mock messages in thread
    mock_messages = [
        MockEvent(
            body="Message 1",
            sender="@user:matrix.org",
            event_id=thread_root_id,
            timestamp=1000,
            source={"content": {}}
        ),
        MockEvent(
            body="Message 2",
            sender="@user:matrix.org",
            event_id="$msg2",
            timestamp=2000,
            source={
                "content": {
                    "m.relates_to": {
                        "event_id": thread_root_id,
                        "rel_type": "m.thread"
                    }
                }
            }
        ),
    ]

    mock_response = MagicMock()
    mock_response.chunk = mock_messages

    client.room_messages = AsyncMock(return_value=mock_response)

    messages = await get_thread_context(client, room, thread_root_id, limit=10)

    assert len(messages) == 2
    assert messages[0].event_id == thread_root_id
    assert messages[1].event_id == "$msg2"


@pytest.mark.asyncio
async def test_get_thread_context_filters_non_thread():
    """Test that get_thread_context filters out non-thread messages."""
    client = MockClient()
    room = MockRoom()
    thread_root_id = "$thread_root"

    # Mock messages - some in thread, some not
    mock_messages = [
        MockEvent(
            body="Thread root",
            sender="@user:matrix.org",
            event_id=thread_root_id,
            timestamp=1000
        ),
        MockEvent(
            body="In thread",
            sender="@user:matrix.org",
            event_id="$msg2",
            timestamp=2000,
            source={
                "content": {
                    "m.relates_to": {
                        "event_id": thread_root_id,
                        "rel_type": "m.thread"
                    }
                }
            }
        ),
        MockEvent(
            body="Not in thread",
            sender="@user:matrix.org",
            event_id="$msg3",
            timestamp=3000,
            source={"content": {}}
        ),
    ]

    mock_response = MagicMock()
    mock_response.chunk = mock_messages

    client.room_messages = AsyncMock(return_value=mock_response)

    messages = await get_thread_context(client, room, thread_root_id, limit=10)

    assert len(messages) == 2  # Only thread messages
    assert messages[0].event_id == thread_root_id
    assert messages[1].event_id == "$msg2"


# Tests for generate_ai_reply


@pytest.mark.asyncio
async def test_generate_ai_reply_success():
    """Test successful AI reply generation."""
    client = MockClient()
    room = MockRoom()
    event = MockEvent(
        body="Hello @architect:matrix.org",
        sender="@user:matrix.org",
        event_id="$test"
    )
    config = MockConfig()

    # Mock the OpenAI API call
    with patch('bot.openai_integration.call_openai_api') as mock_api:
        mock_api.return_value = ({"content": "Hello! How can I help?"}, None)

        # Mock get_thread_context
        with patch('bot.openai_integration.get_thread_context') as mock_context:
            mock_context.return_value = [event]

            # Mock get_registry
            with patch('bot.commands.get_registry') as mock_get_registry:
                mock_registry = MagicMock()
                mock_registry.generate_function_schemas.return_value = []
                mock_get_registry.return_value = mock_registry

                reply = await generate_ai_reply(event, room, client, config)

                assert reply == "Hello! How can I help?"
                mock_api.assert_called_once()


@pytest.mark.asyncio
async def test_generate_ai_reply_with_thread():
    """Test AI reply generation with thread context."""
    client = MockClient()
    room = MockRoom()
    event = MockEvent(
        body="Follow-up question",
        sender="@user:matrix.org",
        event_id="$msg2",
        source={
            "content": {
                "m.relates_to": {
                    "event_id": "$thread_root",
                    "rel_type": "m.thread"
                }
            }
        }
    )
    config = MockConfig()

    thread_messages = [
        MockEvent(body="Initial question", sender="@user:matrix.org", event_id="$thread_root"),
        event
    ]

    with patch('bot.openai_integration.call_openai_api') as mock_api:
        mock_api.return_value = ({"content": "Here's the answer"}, None)

        with patch('bot.openai_integration.get_thread_context') as mock_context:
            mock_context.return_value = thread_messages

            # Mock get_registry
            with patch('bot.commands.get_registry') as mock_get_registry:
                mock_registry = MagicMock()
                mock_registry.generate_function_schemas.return_value = []
                mock_get_registry.return_value = mock_registry

                reply = await generate_ai_reply(event, room, client, config)

                assert reply == "Here's the answer"
                # Verify API was called with conversation history
                call_args = mock_api.call_args
                messages = call_args[0][0]
                # Should have system prompt + 2 user messages
                assert len(messages) == 3
                assert messages[0]["role"] == "system"


@pytest.mark.asyncio
async def test_generate_ai_reply_api_failure():
    """Test AI reply when API fails."""
    client = MockClient()
    room = MockRoom()
    event = MockEvent(body="Hello", sender="@user:matrix.org")
    config = MockConfig()

    with patch('bot.openai_integration.call_openai_api') as mock_api:
        mock_api.return_value = (None, "API Error")

        with patch('bot.openai_integration.get_thread_context') as mock_context:
            mock_context.return_value = [event]

            # Mock get_registry
            with patch('bot.commands.get_registry') as mock_get_registry:
                mock_registry = MagicMock()
                mock_registry.generate_function_schemas.return_value = []
                mock_get_registry.return_value = mock_registry

                reply = await generate_ai_reply(event, room, client, config)

                assert reply is not None
                assert "error" in reply.lower()
                # Should be called once (no retry logic in new version)
                assert mock_api.call_count == 1


@pytest.mark.asyncio
async def test_get_thread_context_timeout():
    """Test that get_thread_context handles timeout gracefully."""
    import asyncio

    client = MockClient()
    room = MockRoom()
    thread_root_id = "$thread_root"

    # Mock room_messages to timeout
    async def timeout_func(*args, **kwargs):
        await asyncio.sleep(100)  # Longer than any reasonable timeout

    client.room_messages = AsyncMock(side_effect=timeout_func)

    # Should return empty list on timeout
    messages = await get_thread_context(client, room, thread_root_id, limit=10)
    assert messages == []


@pytest.mark.asyncio
async def test_get_thread_context_no_prev_batch():
    """Test that get_thread_context handles missing prev_batch token."""
    client = MockClient()
    room = MockRoom(prev_batch=None)
    thread_root_id = "$thread_root"

    # Should return empty list when no prev_batch
    messages = await get_thread_context(client, room, thread_root_id, limit=10)
    assert messages == []


@pytest.mark.asyncio
async def test_get_thread_context_empty_prev_batch():
    """Test that get_thread_context handles empty prev_batch token."""
    client = MockClient()
    room = MockRoom(prev_batch="")
    thread_root_id = "$thread_root"

    # Should return empty list when prev_batch is empty string
    messages = await get_thread_context(client, room, thread_root_id, limit=10)
    assert messages == []
