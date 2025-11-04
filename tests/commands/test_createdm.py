"""Tests for the createdm command."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.commands.createdm import createdm_handler
from nio.responses import DirectRoomsResponse, DirectRoomsErrorResponse, RoomCreateResponse, RoomCreateError


@pytest.mark.asyncio
async def test_createdm_no_matrix_context():
    """Test createdm without Matrix context."""
    result = await createdm_handler(user_identifier="@user:example.com")
    assert result is not None
    assert "Error" in result
    assert "Matrix context" in result


@pytest.mark.asyncio
async def test_createdm_empty_user_identifier():
    """Test createdm with empty user identifier."""
    mock_context = {"client": object()}
    result = await createdm_handler(user_identifier="", matrix_context=mock_context)
    assert result is not None
    assert "Error" in result
    assert "cannot be empty" in result


@pytest.mark.asyncio
async def test_createdm_whitespace_only_user_identifier():
    """Test createdm with whitespace-only user identifier."""
    mock_context = {"client": object()}
    result = await createdm_handler(user_identifier="   ", matrix_context=mock_context)
    assert result is not None
    assert "Error" in result
    assert "cannot be empty" in result


@pytest.mark.asyncio
async def test_createdm_no_client_in_context():
    """Test createdm with Matrix context but no client."""
    mock_context = {"room": object(), "event": object()}
    result = await createdm_handler(user_identifier="@user:example.com", matrix_context=mock_context)
    assert result is not None
    assert "Error" in result
    assert "client not available" in result


@pytest.mark.asyncio
async def test_createdm_existing_dm_room():
    """Test createdm when a DM room already exists."""
    # Mock client with list_direct_rooms returning existing DM
    mock_client = MagicMock()
    mock_direct_rooms_response = DirectRoomsResponse(
        rooms={"@alice:example.com": ["!existing_room:example.com"]}
    )
    mock_client.list_direct_rooms = AsyncMock(return_value=mock_direct_rooms_response)

    mock_context = {"client": mock_client}
    result = await createdm_handler(user_identifier="@alice:example.com", matrix_context=mock_context)

    assert result is not None
    assert "already exists" in result
    assert "@alice:example.com" in result
    assert "!existing_room:example.com" in result
    mock_client.list_direct_rooms.assert_called_once()


@pytest.mark.asyncio
async def test_createdm_create_new_dm_room():
    """Test createdm when creating a new DM room."""
    # Mock client with no existing DM rooms
    mock_client = MagicMock()
    mock_direct_rooms_response = DirectRoomsResponse(rooms={})
    mock_client.list_direct_rooms = AsyncMock(return_value=mock_direct_rooms_response)

    mock_create_response = RoomCreateResponse(room_id="!newroom:example.com")
    mock_client.room_create = AsyncMock(return_value=mock_create_response)

    mock_context = {"client": mock_client}
    result = await createdm_handler(user_identifier="@bob:example.com", matrix_context=mock_context)

    assert result is not None
    assert "Created new DM room" in result
    assert "@bob:example.com" in result
    assert "!newroom:example.com" in result
    mock_client.list_direct_rooms.assert_called_once()
    mock_client.room_create.assert_called_once_with(
        is_direct=True,
        invite=["@bob:example.com"],
        preset=None
    )


@pytest.mark.asyncio
async def test_createdm_create_error():
    """Test createdm when room creation fails."""
    # Mock client with no existing DM rooms
    mock_client = MagicMock()
    mock_direct_rooms_response = DirectRoomsResponse(rooms={})
    mock_client.list_direct_rooms = AsyncMock(return_value=mock_direct_rooms_response)

    mock_create_error = RoomCreateError(message="User not found", status_code="M_NOT_FOUND")
    mock_client.room_create = AsyncMock(return_value=mock_create_error)

    mock_context = {"client": mock_client}
    result = await createdm_handler(user_identifier="@invalid:example.com", matrix_context=mock_context)

    assert result is not None
    assert "Error creating DM room" in result
    assert "User not found" in result


@pytest.mark.asyncio
async def test_createdm_display_name_lookup_success():
    """Test createdm with display name that can be resolved."""
    # Mock room with users
    mock_member = MagicMock()
    mock_member.display_name = "Alice"

    mock_room = MagicMock()
    mock_room.users = {"@alice:example.com": mock_member}

    # Mock client
    mock_client = MagicMock()
    mock_direct_rooms_response = DirectRoomsResponse(rooms={})
    mock_client.list_direct_rooms = AsyncMock(return_value=mock_direct_rooms_response)

    mock_create_response = RoomCreateResponse(room_id="!newroom:example.com")
    mock_client.room_create = AsyncMock(return_value=mock_create_response)

    mock_context = {"client": mock_client, "room": mock_room}
    result = await createdm_handler(user_identifier="Alice", matrix_context=mock_context)

    assert result is not None
    assert "Created new DM room" in result
    assert "@alice:example.com" in result
    mock_client.room_create.assert_called_once_with(
        is_direct=True,
        invite=["@alice:example.com"],
        preset=None
    )


@pytest.mark.asyncio
async def test_createdm_display_name_lookup_failure():
    """Test createdm with display name that cannot be resolved."""
    # Mock room with users (but none matching the display name)
    mock_member = MagicMock()
    mock_member.display_name = "Alice"

    mock_room = MagicMock()
    mock_room.users = {"@alice:example.com": mock_member}

    mock_client = MagicMock()
    mock_context = {"client": mock_client, "room": mock_room}

    result = await createdm_handler(user_identifier="Bob", matrix_context=mock_context)

    assert result is not None
    assert "Error" in result
    assert "Could not find user" in result
    assert "Bob" in result


@pytest.mark.asyncio
async def test_createdm_display_name_case_insensitive():
    """Test that display name lookup is case-insensitive."""
    # Mock room with users
    mock_member = MagicMock()
    mock_member.display_name = "Alice"

    mock_room = MagicMock()
    mock_room.users = {"@alice:example.com": mock_member}

    # Mock client
    mock_client = MagicMock()
    mock_direct_rooms_response = DirectRoomsResponse(rooms={})
    mock_client.list_direct_rooms = AsyncMock(return_value=mock_direct_rooms_response)

    mock_create_response = RoomCreateResponse(room_id="!newroom:example.com")
    mock_client.room_create = AsyncMock(return_value=mock_create_response)

    mock_context = {"client": mock_client, "room": mock_room}
    result = await createdm_handler(user_identifier="aLiCe", matrix_context=mock_context)

    assert result is not None
    assert "Created new DM room" in result
    assert "@alice:example.com" in result


@pytest.mark.asyncio
async def test_createdm_direct_rooms_error_response():
    """Test createdm when list_direct_rooms returns an error."""
    # Mock client with error response (no DMs marked)
    mock_client = MagicMock()
    mock_direct_rooms_error = DirectRoomsErrorResponse(message="No direct rooms", status_code="M_NOT_FOUND")
    mock_client.list_direct_rooms = AsyncMock(return_value=mock_direct_rooms_error)

    mock_create_response = RoomCreateResponse(room_id="!newroom:example.com")
    mock_client.room_create = AsyncMock(return_value=mock_create_response)

    mock_context = {"client": mock_client}
    result = await createdm_handler(user_identifier="@user:example.com", matrix_context=mock_context)

    # Should still create a new DM room even if list_direct_rooms fails
    assert result is not None
    assert "Created new DM room" in result
    assert "!newroom:example.com" in result


@pytest.mark.asyncio
async def test_createdm_strips_whitespace():
    """Test that createdm strips leading/trailing whitespace from user identifier."""
    mock_client = MagicMock()
    mock_direct_rooms_response = DirectRoomsResponse(rooms={})
    mock_client.list_direct_rooms = AsyncMock(return_value=mock_direct_rooms_response)

    mock_create_response = RoomCreateResponse(room_id="!newroom:example.com")
    mock_client.room_create = AsyncMock(return_value=mock_create_response)

    mock_context = {"client": mock_client}
    result = await createdm_handler(user_identifier="  @user:example.com  ", matrix_context=mock_context)

    assert result is not None
    assert "Created new DM room" in result
    assert "@user:example.com" in result
    mock_client.room_create.assert_called_once_with(
        is_direct=True,
        invite=["@user:example.com"],
        preset=None
    )


@pytest.mark.asyncio
async def test_createdm_exception_handling():
    """Test createdm handles unexpected exceptions gracefully."""
    mock_client = MagicMock()
    mock_client.list_direct_rooms = AsyncMock(side_effect=Exception("Unexpected error"))

    mock_context = {"client": mock_client}
    result = await createdm_handler(user_identifier="@user:example.com", matrix_context=mock_context)

    assert result is not None
    assert "Error creating DM" in result
    assert "Unexpected error" in result
