"""Tests for the ask_user command."""
from __future__ import annotations
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from bot.commands.ask_user import ask_user_handler


@pytest.fixture
def mock_matrix_context():
    """Create mock Matrix context for testing."""
    mock_client = AsyncMock()
    mock_client.user_id = "@bot:example.com"
    mock_client.room_send = AsyncMock(return_value=MagicMock())

    mock_room = MagicMock()
    mock_room.room_id = "!test:example.com"

    mock_event = MagicMock()
    mock_event.event_id = "$event1"
    mock_event.sender = "@user:example.com"
    mock_event.body = "Test message"
    mock_event.source = {}

    return {
        "client": mock_client,
        "room": mock_room,
        "event": mock_event
    }


@pytest.mark.asyncio
async def test_ask_user_no_context():
    """Test that ask_user handles missing matrix_context gracefully."""
    result = await ask_user_handler(
        question="What's your name?",
        matrix_context=None
    )

    assert result is not None
    assert isinstance(result, str)
    assert "Error" in result
    assert "Matrix context" in result


@pytest.mark.asyncio
async def test_ask_user_with_response(mock_matrix_context):
    """Test ask_user receiving a valid response."""
    question = "What's your email?"

    # Mock ask_user_and_wait to simulate user response
    with patch("bot.user_input_handler.ask_user_and_wait", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = "user@example.com"

        result = await ask_user_handler(
            question=question,
            matrix_context=mock_matrix_context
        )

        # Verify ask_user_and_wait was called correctly
        mock_ask.assert_called_once_with(
            question=question,
            matrix_context=mock_matrix_context,
            timeout=120
        )

        # Verify result is formatted correctly
        assert result == "User answered: user@example.com"


@pytest.mark.asyncio
async def test_ask_user_with_timeout(mock_matrix_context):
    """Test ask_user handling timeout."""
    question = "What's your name?"

    # Mock ask_user_and_wait to simulate timeout
    with patch("bot.user_input_handler.ask_user_and_wait", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = "[Timeout after 120s - no response received from user]"

        result = await ask_user_handler(
            question=question,
            matrix_context=mock_matrix_context
        )

        # Verify timeout message is returned as-is (not wrapped)
        assert result == "[Timeout after 120s - no response received from user]"
        assert not result.startswith("User answered:")


@pytest.mark.asyncio
async def test_ask_user_with_error(mock_matrix_context):
    """Test ask_user handling error from user_input_handler."""
    question = "Confirm action?"

    # Mock ask_user_and_wait to simulate error
    with patch("bot.user_input_handler.ask_user_and_wait", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = "[Error: Another question is already pending in this thread]"

        result = await ask_user_handler(
            question=question,
            matrix_context=mock_matrix_context
        )

        # Verify error message is returned as-is
        assert result == "[Error: Another question is already pending in this thread]"
        assert not result.startswith("User answered:")


@pytest.mark.asyncio
async def test_ask_user_integration(mock_matrix_context):
    """Test ask_user end-to-end with actual user_input_handler."""
    from bot.user_input_handler import _pending_questions, handle_user_response

    # Clear any pending questions from other tests
    _pending_questions.clear()

    question = "Do you want to continue?"

    # Start the ask_user command in background
    ask_task = asyncio.create_task(
        ask_user_handler(
            question=question,
            matrix_context=mock_matrix_context
        )
    )

    # Give it a moment to register the question
    await asyncio.sleep(0.1)

    # Verify question was sent to Matrix
    mock_matrix_context["client"].room_send.assert_called_once()

    # Simulate user response
    was_handled = handle_user_response(
        "$event1",  # thread_root_id from mock_event
        "@user:example.com",  # sender from mock_event
        "yes, continue"
    )
    assert was_handled

    # Wait for result
    result = await ask_task

    # Verify result
    assert result == "User answered: yes, continue"

    # Clean up
    _pending_questions.clear()


@pytest.mark.asyncio
async def test_ask_user_with_empty_question(mock_matrix_context):
    """Test ask_user with empty question string."""
    # Mock ask_user_and_wait
    with patch("bot.user_input_handler.ask_user_and_wait", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = ""

        result = await ask_user_handler(
            question="",
            matrix_context=mock_matrix_context
        )

        # Even with empty question, it should be passed through
        mock_ask.assert_called_once_with(
            question="",
            matrix_context=mock_matrix_context,
            timeout=120
        )

        # Empty response should still be formatted
        assert result == "User answered: "


@pytest.mark.asyncio
async def test_ask_user_with_multiline_response(mock_matrix_context):
    """Test ask_user handling multiline user response."""
    question = "Describe the issue:"

    multiline_response = """The issue is that:
1. Login fails
2. Session expires
3. Redirect broken"""

    with patch("bot.user_input_handler.ask_user_and_wait", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = multiline_response

        result = await ask_user_handler(
            question=question,
            matrix_context=mock_matrix_context
        )

        # Verify multiline response is preserved
        assert result.startswith("User answered: ")
        assert "1. Login fails" in result
        assert "2. Session expires" in result
        assert "3. Redirect broken" in result


@pytest.mark.asyncio
async def test_ask_user_with_special_characters(mock_matrix_context):
    """Test ask_user with question and response containing special characters."""
    question = "What's the API key? (format: sk-xxxxx)"

    with patch("bot.user_input_handler.ask_user_and_wait", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = "sk-abc123!@#$%^&*()"

        result = await ask_user_handler(
            question=question,
            matrix_context=mock_matrix_context
        )

        # Verify special characters are preserved
        assert result == "User answered: sk-abc123!@#$%^&*()"


@pytest.mark.asyncio
async def test_ask_user_concurrent_questions():
    """Test that multiple ask_user calls are handled correctly."""
    from bot.user_input_handler import _pending_questions

    # Clear pending questions
    _pending_questions.clear()

    # Create two different contexts
    context1 = {
        "client": AsyncMock(room_send=AsyncMock()),
        "room": MagicMock(room_id="!test:example.com"),
        "event": MagicMock(event_id="$event1", sender="@user1:example.com", source={})
    }

    context2 = {
        "client": AsyncMock(room_send=AsyncMock()),
        "room": MagicMock(room_id="!test:example.com"),
        "event": MagicMock(event_id="$event2", sender="@user2:example.com", source={})
    }

    # Start both questions
    task1 = asyncio.create_task(
        ask_user_handler(question="Question 1?", matrix_context=context1)
    )
    task2 = asyncio.create_task(
        ask_user_handler(question="Question 2?", matrix_context=context2)
    )

    # Give them time to register
    await asyncio.sleep(0.1)

    # Respond to both
    from bot.user_input_handler import handle_user_response
    handle_user_response("$event1", "@user1:example.com", "answer1")
    handle_user_response("$event2", "@user2:example.com", "answer2")

    # Both should get their responses
    result1 = await task1
    result2 = await task2

    assert result1 == "User answered: answer1"
    assert result2 == "User answered: answer2"

    # Clean up
    _pending_questions.clear()
