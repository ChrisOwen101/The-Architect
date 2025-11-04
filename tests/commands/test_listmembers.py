"""Tests for the listmembers command."""
from __future__ import annotations
import pytest
from unittest.mock import Mock, MagicMock
from bot.commands.listmembers import listmembers_handler


@pytest.mark.asyncio
async def test_listmembers_success():
    """Test that listmembers returns a valid member list."""
    # Create mock room with members
    mock_member1 = Mock()
    mock_member1.display_name = "Alice"

    mock_member2 = Mock()
    mock_member2.display_name = "Bob"

    mock_member3 = Mock()
    mock_member3.display_name = None  # Some users may not have display names

    mock_room = Mock()
    mock_room.users = {
        "@alice:example.com": mock_member1,
        "@bob:example.com": mock_member2,
        "@charlie:example.com": mock_member3,
    }

    mock_client = Mock()

    matrix_context = {
        "client": mock_client,
        "room": mock_room,
        "event": Mock()
    }

    result = await listmembers_handler(matrix_context=matrix_context)

    assert result is not None
    assert isinstance(result, str)
    assert "Room members (3):" in result
    assert "Alice (@alice:example.com)" in result
    assert "Bob (@bob:example.com)" in result
    assert "@charlie:example.com" in result


@pytest.mark.asyncio
async def test_listmembers_no_context():
    """Test that listmembers handles missing matrix_context gracefully."""
    result = await listmembers_handler(matrix_context=None)

    assert result is not None
    assert isinstance(result, str)
    assert "Error" in result
    assert "requires Matrix room context" in result


@pytest.mark.asyncio
async def test_listmembers_missing_client():
    """Test that listmembers handles missing client in context."""
    matrix_context = {
        "room": Mock(),
        "event": Mock()
    }

    result = await listmembers_handler(matrix_context=matrix_context)

    assert result is not None
    assert isinstance(result, str)
    assert "Error" in result
    assert "Unable to access room information" in result


@pytest.mark.asyncio
async def test_listmembers_missing_room():
    """Test that listmembers handles missing room in context."""
    matrix_context = {
        "client": Mock(),
        "event": Mock()
    }

    result = await listmembers_handler(matrix_context=matrix_context)

    assert result is not None
    assert isinstance(result, str)
    assert "Error" in result
    assert "Unable to access room information" in result


@pytest.mark.asyncio
async def test_listmembers_empty_room():
    """Test that listmembers handles rooms with no members."""
    mock_room = Mock()
    mock_room.users = {}

    matrix_context = {
        "client": Mock(),
        "room": mock_room,
        "event": Mock()
    }

    result = await listmembers_handler(matrix_context=matrix_context)

    assert result is not None
    assert isinstance(result, str)
    assert "No members found" in result


@pytest.mark.asyncio
async def test_listmembers_no_users_attribute():
    """Test that listmembers handles rooms without users attribute."""
    mock_room = Mock(spec=[])  # Room without users attribute

    matrix_context = {
        "client": Mock(),
        "room": mock_room,
        "event": Mock()
    }

    result = await listmembers_handler(matrix_context=matrix_context)

    assert result is not None
    assert isinstance(result, str)
    assert "No members found" in result


@pytest.mark.asyncio
async def test_listmembers_sorted_output():
    """Test that listmembers returns members in alphabetical order."""
    mock_member1 = Mock()
    mock_member1.display_name = "Zoe"

    mock_member2 = Mock()
    mock_member2.display_name = "Alice"

    mock_member3 = Mock()
    mock_member3.display_name = "Bob"

    mock_room = Mock()
    mock_room.users = {
        "@zoe:example.com": mock_member1,
        "@alice:example.com": mock_member2,
        "@bob:example.com": mock_member3,
    }

    matrix_context = {
        "client": Mock(),
        "room": mock_room,
        "event": Mock()
    }

    result = await listmembers_handler(matrix_context=matrix_context)

    assert result is not None
    # Check that Alice appears before Bob, and Bob before Zoe
    alice_index = result.index("Alice")
    bob_index = result.index("Bob")
    zoe_index = result.index("Zoe")

    assert alice_index < bob_index < zoe_index


@pytest.mark.asyncio
async def test_listmembers_large_room():
    """Test that listmembers handles large rooms with truncation."""
    # Create a large room with many members
    mock_room = Mock()
    mock_room.users = {}

    for i in range(100):
        mock_member = Mock()
        mock_member.display_name = f"User{i:03d}"
        mock_room.users[f"@user{i}:example.com"] = mock_member

    matrix_context = {
        "client": Mock(),
        "room": mock_room,
        "event": Mock()
    }

    result = await listmembers_handler(matrix_context=matrix_context)

    assert result is not None
    assert isinstance(result, str)
    assert "Room members (100):" in result
    # Verify result is under 4000 characters
    assert len(result) <= 4000


@pytest.mark.asyncio
async def test_listmembers_display_name_equals_user_id():
    """Test that when display name equals user ID, only show once."""
    mock_member = Mock()
    mock_member.display_name = "@alice:example.com"

    mock_room = Mock()
    mock_room.users = {
        "@alice:example.com": mock_member,
    }

    matrix_context = {
        "client": Mock(),
        "room": mock_room,
        "event": Mock()
    }

    result = await listmembers_handler(matrix_context=matrix_context)

    assert result is not None
    # Should only show user ID once, not "user_id (user_id)"
    assert result.count("@alice:example.com") == 1
    assert "(@alice:example.com)" not in result or result.count("@alice:example.com") == 1
