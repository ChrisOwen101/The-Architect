"""Tests for command registry system."""
import pytest


@pytest.mark.asyncio
async def test_registry_registration():
    """Test basic command registration."""
    from bot.commands import get_registry

    # Get the global registry
    registry = get_registry()

    # Commands loaded from bot/commands/ should already be registered
    # Test that ping command exists
    assert registry.get_command("ping") is not None


@pytest.mark.asyncio
async def test_registry_execute_matching():
    """Test executing a matching command."""
    from bot.commands import execute_command

    # Commands should already be loaded from bot/commands/
    result = await execute_command("ping", {})
    assert result == "pong"


@pytest.mark.asyncio
async def test_registry_execute_no_match():
    """Test executing with no matching command."""
    from bot.commands import execute_command

    result = await execute_command("nonexistent_command", {})
    assert result is not None  # Returns error message
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_list_commands():
    """Test listing all commands."""
    from bot.commands import get_registry

    registry = get_registry()
    commands = registry.list_commands()

    # Should have at least our basic commands
    assert len(commands) > 0
    command_names = [name for name, _ in commands]
    assert "ping" in command_names
