"""Dynamic command registry system for The Architect bot."""
from __future__ import annotations
import importlib
import inspect
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Awaitable, Any

logger = logging.getLogger(__name__)


@dataclass
class Command:
    """Represents a registered command."""
    name: str
    description: str
    pattern: str  # Regex pattern to match command
    handler: Callable[[str], Awaitable[Optional[str]]]
    module_name: str  # For reload tracking


class CommandRegistry:
    """Registry for dynamically loaded commands."""

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._patterns: list[tuple[re.Pattern, Command]] = []

    def register(self, name: str, description: str, pattern: str,
                 handler: Callable[[str], Awaitable[Optional[str]]],
                 module_name: str = "unknown") -> None:
        """Register a command with the registry."""
        cmd = Command(
            name=name,
            description=description,
            pattern=pattern,
            handler=handler,
            module_name=module_name
        )
        self._commands[name] = cmd
        # Compile and cache regex pattern
        self._patterns.append((re.compile(pattern, re.IGNORECASE), cmd))
        logger.info(f"Registered command: {name} (pattern: {pattern})")

    def unregister(self, name: str) -> bool:
        """Unregister a command by name."""
        if name not in self._commands:
            return False

        cmd = self._commands.pop(name)
        # Remove from patterns list
        self._patterns = [(p, c) for p, c in self._patterns if c.name != name]
        logger.info(f"Unregistered command: {name}")
        return True

    async def execute(self, body: str, matrix_context: Optional[dict[str, Any]] = None) -> Optional[str]:
        """Execute the first matching command.

        Args:
            body: The message body to match against command patterns
            matrix_context: Optional dictionary containing Matrix client, room, and event
                           Keys: 'client', 'room', 'event'
        """
        body_stripped = body.strip()

        # Try to match against all registered patterns
        for pattern, cmd in self._patterns:
            if pattern.match(body_stripped):
                try:
                    logger.debug(f"Executing command: {cmd.name}")

                    # Check if handler accepts matrix_context parameter
                    sig = inspect.signature(cmd.handler)
                    params = sig.parameters

                    if 'matrix_context' in params and matrix_context:
                        # Handler accepts Matrix context, pass it
                        return await cmd.handler(body_stripped, matrix_context=matrix_context)
                    else:
                        # Handler doesn't accept Matrix context, call normally
                        return await cmd.handler(body_stripped)
                except Exception:
                    logger.exception(f"Error executing command {cmd.name}")
                    return f"Error executing command '{cmd.name}'. Check logs for details."

        return None  # No command matched

    def list_commands(self) -> list[tuple[str, str]]:
        """Return list of (name, description) for all commands."""
        return [(cmd.name, cmd.description) for cmd in self._commands.values()]

    def get_command(self, name: str) -> Optional[Command]:
        """Get command by name."""
        return self._commands.get(name)

    def clear(self) -> None:
        """Clear all registered commands."""
        self._commands.clear()
        self._patterns.clear()


# Global registry instance
_registry = CommandRegistry()


def command(name: str, description: str, pattern: str):
    """Decorator to register a command handler.

    Usage:
        @command(name="ping", description="Ping the bot", pattern=r"^!ping$")
        async def ping_handler(body: str) -> Optional[str]:
            return "pong"
    """
    def decorator(func: Callable[[str], Awaitable[Optional[str]]]):
        # Get the module name of the function for tracking
        module_name = func.__module__
        _registry.register(name, description, pattern, func, module_name)
        return func
    return decorator


def load_commands() -> None:
    """Dynamically load all command modules from bot/commands/ directory."""
    commands_dir = Path(__file__).parent

    # Clear existing commands before reload
    _registry.clear()

    # Find all .py files except __init__.py
    for file_path in commands_dir.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        module_name = f"bot.commands.{file_path.stem}"
        try:
            # Import or reload the module
            if module_name in importlib.sys.modules:
                importlib.reload(importlib.sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            logger.info(f"Loaded command module: {module_name}")
        except Exception:
            logger.exception(f"Failed to load command module: {module_name}")


async def execute_command(body: str, matrix_context: Optional[dict[str, Any]] = None) -> Optional[str]:
    """Execute a command based on message body. This is the main entry point.

    Args:
        body: The message body to match against command patterns
        matrix_context: Optional dictionary containing Matrix client, room, and event
                       Keys: 'client', 'room', 'event'
    """
    return await _registry.execute(body, matrix_context=matrix_context)


def get_registry() -> CommandRegistry:
    """Get the global command registry instance."""
    return _registry


# Auto-load commands on import
load_commands()
