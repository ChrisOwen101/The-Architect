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

                    # Inspect handler signature
                    sig = inspect.signature(cmd.handler)
                    params = sig.parameters

                    # Check if handler has 'body' parameter (old-style)
                    has_body_param = 'body' in params
                    has_context_param = 'matrix_context' in params

                    if has_body_param:
                        # Old-style handler with body parameter
                        if has_context_param and matrix_context:
                            return await cmd.handler(body_stripped, matrix_context=matrix_context)
                        else:
                            return await cmd.handler(body_stripped)
                    else:
                        # New-style handler without body parameter (structured params)
                        if has_context_param and matrix_context:
                            return await cmd.handler(matrix_context=matrix_context)
                        else:
                            return await cmd.handler()
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

    def generate_function_schemas(self) -> list[dict[str, Any]]:
        """
        Generate OpenAI function calling schemas from registered commands.

        Uses handler signatures and docstrings to generate schemas.

        Returns:
            List of function schema dicts in OpenAI format
        """

        schemas = []

        for name, cmd in self._commands.items():
            # Inspect handler signature to extract parameters
            sig = inspect.signature(cmd.handler)
            parameters_schema = {
                "type": "object",
                "properties": {},
                "required": []
            }

            for param_name, param in sig.parameters.items():
                # Skip 'body', 'matrix_context' - these are internal
                if param_name in ('body', 'matrix_context'):
                    continue

                # Extract type from annotation
                param_type = "string"  # Default
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == str:
                        param_type = "string"
                    elif param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    elif hasattr(param.annotation, '__origin__'):
                        # Handle Optional, List, etc.
                        origin = param.annotation.__origin__
                        if origin is list:
                            param_type = "array"
                        elif origin is dict:
                            param_type = "object"

                # Add parameter to schema
                parameters_schema["properties"][param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}"
                }

                # Mark as required if no default value
                if param.default == inspect.Parameter.empty:
                    parameters_schema["required"].append(param_name)

            # Parse docstring for better descriptions if available
            docstring = inspect.getdoc(cmd.handler)
            param_descriptions = {}
            if docstring:
                # Simple docstring parsing - look for "param_name: description" patterns
                for line in docstring.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith((':param', 'Args:', 'Returns:')):
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            param_descriptions[parts[0].strip()
                                               ] = parts[1].strip()

            # Update parameter descriptions from docstring
            for param_name in parameters_schema["properties"]:
                if param_name in param_descriptions:
                    parameters_schema["properties"][param_name]["description"] = param_descriptions[param_name]

            # Build function schema
            function_schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": cmd.description,
                    "parameters": parameters_schema
                }
            }

            schemas.append(function_schema)
            logger.debug(f"Generated function schema for command: {name}")

        logger.info(f"Generated {len(schemas)} function schema(s)")
        return schemas


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
