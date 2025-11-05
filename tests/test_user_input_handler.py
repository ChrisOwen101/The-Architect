"""Tests for user input handler module."""
from __future__ import annotations
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from bot.user_input_handler import (
    PendingQuestion,
    ask_user_and_wait,
    handle_user_response,
    is_pending_question,
    cleanup_expired_questions,
    _pending_questions
)


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


@pytest.fixture
def mock_thread_context():
    """Create mock Matrix context for a threaded message."""
    mock_client = AsyncMock()
    mock_client.user_id = "@bot:example.com"
    mock_client.room_send = AsyncMock(return_value=MagicMock())

    mock_room = MagicMock()
    mock_room.room_id = "!test:example.com"

    mock_event = MagicMock()
    mock_event.event_id = "$reply1"
    mock_event.sender = "@user:example.com"
    mock_event.body = "Reply message"
    mock_event.source = {
        "content": {
            "m.relates_to": {
                "rel_type": "m.thread",
                "event_id": "$thread_root"
            }
        }
    }

    return {
        "client": mock_client,
        "room": mock_room,
        "event": mock_event
    }


@pytest.fixture(autouse=True)
def clear_pending_questions():
    """Clear pending questions before each test."""
    _pending_questions.clear()
    yield
    _pending_questions.clear()


# PendingQuestion Tests

def test_pending_question_creation():
    """Test creating a PendingQuestion."""
    question = PendingQuestion(
        question="What's your name?",
        thread_root_id="$thread1",
        user_id="@user:example.com",
        timeout_at=time.time() + 120
    )

    assert question.question == "What's your name?"
    assert question.thread_root_id == "$thread1"
    assert question.user_id == "@user:example.com"
    assert question.response is None
    assert isinstance(question.event, asyncio.Event)
    assert not question.event.is_set()


# ask_user_and_wait Tests

@pytest.mark.asyncio
async def test_ask_user_and_wait_success(mock_matrix_context):
    """Test asking user and receiving response."""
    question = "What's your email?"

    # Start asking in background
    ask_task = asyncio.create_task(
        ask_user_and_wait(question, mock_matrix_context, timeout=5)
    )

    # Give it a moment to register the question
    await asyncio.sleep(0.1)

    # Verify question was sent
    mock_matrix_context["client"].room_send.assert_called_once()
    call_args = mock_matrix_context["client"].room_send.call_args
    assert call_args[1]["room_id"] == "!test:example.com"
    assert "❓ What's your email?" in call_args[1]["content"]["body"]

    # Verify pending question is registered
    assert is_pending_question("$event1")

    # Simulate user response
    was_handled = handle_user_response(
        "$event1",
        "@user:example.com",
        "user@example.com"
    )
    assert was_handled

    # Wait for result
    response = await ask_task

    # Verify response
    assert response == "user@example.com"
    assert not is_pending_question("$event1")


@pytest.mark.asyncio
async def test_ask_user_and_wait_timeout(mock_matrix_context):
    """Test asking user with timeout."""
    question = "What's your name?"

    # Ask with very short timeout
    response = await ask_user_and_wait(question, mock_matrix_context, timeout=0.1)

    # Should return timeout message
    assert "Timeout" in response
    assert "0.1" in response or "0" in response
    assert not is_pending_question("$event1")


@pytest.mark.asyncio
async def test_ask_user_and_wait_in_thread(mock_thread_context):
    """Test asking user in an existing thread."""
    question = "Continue?"

    # Start asking
    ask_task = asyncio.create_task(
        ask_user_and_wait(question, mock_thread_context, timeout=5)
    )

    await asyncio.sleep(0.1)

    # Verify pending question uses thread root
    assert is_pending_question("$thread_root")
    assert not is_pending_question("$reply1")

    # Respond using thread root
    was_handled = handle_user_response("$thread_root", "@user:example.com", "yes")
    assert was_handled

    response = await ask_task
    assert response == "yes"


@pytest.mark.asyncio
async def test_ask_user_and_wait_missing_context():
    """Test asking user without proper Matrix context."""
    # Missing client
    response = await ask_user_and_wait(
        "Question?",
        {"room": MagicMock(), "event": MagicMock()},
        timeout=1
    )
    assert "Error" in response
    assert "Invalid matrix context" in response

    # Empty context
    response = await ask_user_and_wait("Question?", {}, timeout=1)
    assert "Error" in response


@pytest.mark.asyncio
async def test_ask_user_and_wait_concurrent_in_same_thread(mock_matrix_context):
    """Test that concurrent questions in the same thread are blocked."""
    # Start first question
    ask_task1 = asyncio.create_task(
        ask_user_and_wait("First question?", mock_matrix_context, timeout=5)
    )

    await asyncio.sleep(0.1)

    # Try to start second question in same thread
    response2 = await ask_user_and_wait(
        "Second question?",
        mock_matrix_context,
        timeout=1
    )

    # Second should fail
    assert "Error" in response2
    assert "already pending" in response2

    # Clean up first task
    handle_user_response("$event1", "@user:example.com", "answer1")
    await ask_task1


@pytest.mark.asyncio
async def test_ask_user_and_wait_concurrent_different_threads():
    """Test concurrent questions in different threads work independently."""
    # Create two different contexts with different event IDs
    context1 = {
        "client": AsyncMock(user_id="@bot:example.com", room_send=AsyncMock()),
        "room": MagicMock(room_id="!test:example.com"),
        "event": MagicMock(event_id="$event1", sender="@user1:example.com", source={})
    }

    context2 = {
        "client": AsyncMock(user_id="@bot:example.com", room_send=AsyncMock()),
        "room": MagicMock(room_id="!test:example.com"),
        "event": MagicMock(event_id="$event2", sender="@user2:example.com", source={})
    }

    # Start both questions
    task1 = asyncio.create_task(
        ask_user_and_wait("Question 1?", context1, timeout=5)
    )
    task2 = asyncio.create_task(
        ask_user_and_wait("Question 2?", context2, timeout=5)
    )

    await asyncio.sleep(0.1)

    # Both should be pending
    assert is_pending_question("$event1")
    assert is_pending_question("$event2")

    # Respond to both
    handle_user_response("$event1", "@user1:example.com", "answer1")
    handle_user_response("$event2", "@user2:example.com", "answer2")

    # Both should get their responses
    response1 = await task1
    response2 = await task2

    assert response1 == "answer1"
    assert response2 == "answer2"


# handle_user_response Tests

def test_handle_user_response_no_pending_question():
    """Test handling response when no question is pending."""
    result = handle_user_response("$thread1", "@user:example.com", "answer")
    assert result is False


def test_handle_user_response_wrong_user():
    """Test handling response from wrong user."""
    # Register question for user1
    pending = PendingQuestion(
        question="Question?",
        thread_root_id="$thread1",
        user_id="@user1:example.com",
        timeout_at=time.time() + 120
    )
    _pending_questions["$thread1"] = pending

    # Try to respond as user2
    result = handle_user_response("$thread1", "@user2:example.com", "answer")
    assert result is False
    assert pending.response is None
    assert not pending.event.is_set()


def test_handle_user_response_correct_user():
    """Test handling response from correct user."""
    # Register question
    pending = PendingQuestion(
        question="Question?",
        thread_root_id="$thread1",
        user_id="@user1:example.com",
        timeout_at=time.time() + 120
    )
    _pending_questions["$thread1"] = pending

    # Respond as correct user
    result = handle_user_response("$thread1", "@user1:example.com", "my answer")
    assert result is True
    assert pending.response == "my answer"
    assert pending.event.is_set()


# is_pending_question Tests

def test_is_pending_question_empty():
    """Test checking for pending question when none exist."""
    assert not is_pending_question("$thread1")


def test_is_pending_question_exists():
    """Test checking for pending question that exists."""
    pending = PendingQuestion(
        question="Question?",
        thread_root_id="$thread1",
        user_id="@user:example.com",
        timeout_at=time.time() + 120
    )
    _pending_questions["$thread1"] = pending

    assert is_pending_question("$thread1")
    assert not is_pending_question("$thread2")


# cleanup_expired_questions Tests

@pytest.mark.asyncio
async def test_cleanup_expired_questions():
    """Test cleanup of expired pending questions."""
    # Create one expired and one active question
    expired = PendingQuestion(
        question="Expired?",
        thread_root_id="$thread1",
        user_id="@user:example.com",
        timeout_at=time.time() - 10  # Already expired
    )

    active = PendingQuestion(
        question="Active?",
        thread_root_id="$thread2",
        user_id="@user:example.com",
        timeout_at=time.time() + 3600  # Not expired
    )

    _pending_questions["$thread1"] = expired
    _pending_questions["$thread2"] = active

    # Run cleanup once (don't run infinite loop)
    cleanup_task = asyncio.create_task(cleanup_expired_questions())

    # Let it run for a bit
    await asyncio.sleep(0.2)

    # Cancel the task
    cleanup_task.cancel()

    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Note: The cleanup runs every 60 seconds, so in this short test
    # we just verify the task can be started and cancelled without errors


@pytest.mark.asyncio
async def test_cleanup_signals_expired_events():
    """Test that cleanup signals events for expired questions."""
    # Create expired question
    pending = PendingQuestion(
        question="Expired?",
        thread_root_id="$thread1",
        user_id="@user:example.com",
        timeout_at=time.time() - 1
    )
    _pending_questions["$thread1"] = pending

    # Manually trigger cleanup logic (simulating what the task does)
    now = time.time()
    expired_threads = [
        tid for tid, pq in _pending_questions.items()
        if now > pq.timeout_at
    ]

    for tid in expired_threads:
        pq = _pending_questions.pop(tid, None)
        if pq and not pq.event.is_set():
            pq.event.set()

    # Verify cleanup
    assert "$thread1" not in _pending_questions
    assert pending.event.is_set()


@pytest.mark.asyncio
async def test_ask_user_no_response():
    """Test asking user who never responds (returns timeout)."""
    mock_context = {
        "client": AsyncMock(room_send=AsyncMock()),
        "room": MagicMock(room_id="!test:example.com"),
        "event": MagicMock(event_id="$event1", sender="@user:example.com", source={})
    }

    # Ask with very short timeout and don't respond
    response = await ask_user_and_wait("Hello?", mock_context, timeout=0.1)

    assert "[Timeout" in response
    assert not is_pending_question("$event1")


@pytest.mark.asyncio
async def test_ask_user_error_during_send(mock_matrix_context):
    """Test handling error when sending question message."""
    # Make room_send raise an exception
    mock_matrix_context["client"].room_send.side_effect = Exception("Send failed")

    response = await ask_user_and_wait("Question?", mock_matrix_context, timeout=1)

    assert "[Error" in response
    assert "Send failed" in response
    assert not is_pending_question("$event1")
