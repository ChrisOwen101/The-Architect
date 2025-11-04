from __future__ import annotations
import pytest
from bot.commands.roll2d6 import roll2d6_handler


@pytest.mark.asyncio
async def test_roll2d6_success():
    """Test that roll2d6 returns a valid response."""
    result = await roll2d6_handler()

    assert result is not None
    assert isinstance(result, str)
    assert "Die 1:" in result
    assert "Die 2:" in result
    assert "Total:" in result


@pytest.mark.asyncio
async def test_roll2d6_valid_range():
    """Test that dice results are within valid range (1-6)."""
    # Run multiple times to check randomness
    for _ in range(10):
        result = await roll2d6_handler()

        # Extract the numbers from the result
        lines = result.split('\n')
        die1_value = int(lines[0].split(': ')[1])
        die2_value = int(lines[1].split(': ')[1])
        total_value = int(lines[2].split(': ')[1])

        # Verify dice are in valid range
        assert 1 <= die1_value <= 6
        assert 1 <= die2_value <= 6

        # Verify total is correct
        assert total_value == die1_value + die2_value

        # Verify total is in valid range
        assert 2 <= total_value <= 12


@pytest.mark.asyncio
async def test_roll2d6_with_matrix_context():
    """Test that roll2d6 works with matrix_context parameter."""
    matrix_context = {
        "room_id": "!test:example.com",
        "event_id": "$test123",
        "sender": "@user:example.com"
    }

    result = await roll2d6_handler(matrix_context=matrix_context)

    assert result is not None
    assert isinstance(result, str)
    assert "Die 1:" in result
    assert "Die 2:" in result
    assert "Total:" in result
