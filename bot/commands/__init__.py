"""Dynamic command registry system for The Architect bot."""
from __future__ import annotations
import importlib
import inspect
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Awaitable, Any

logger = logging.getLogger(__name__)


@dataclass
class CommandParam:
    """Represents a command parameter."""
    name: str
    param_type: type
    description: str
    required: bool = True


@dataclass
class Command:
    """Represents a registered command."""
    name: str
    description: str
    params: list[CommandParam] = field(default_factory=list)
    handler: Callable[..., Awaitable[Optional[str]]] = None
    module_name: str = "unknown"


class CommandRegistry:
    """Registry for dynamically loaded commands."""

    def __init__(self):
        self._commands: dict[str, Command] = {}

    def register(self, name: str, description: str, params: list[tuple[str, type, str, bool]],
                 handler: Callable[..., Awaitable[Optional[str]]],
                 module_name: str = "unknown") -> None:
        """Register a command with the registry.

        Args:
            name: Command name
            description: Command description
            params: List of tuples (param_name, param_type, param_description, required)
            handler: Async handler function
            module_name: Module name for tracking
        """
        # Convert param tuples to CommandParam objects
        command_params = [
            CommandParam(name=p[0], param_type=p[1], description=p[2], required=p[3])
            for p in params
        ]

        cmd = Command(
            name=name,
            description=description,
            params=command_params,
            handler=handler,
            module_name=module_name
        )
        self._commands[name] = cmd
        logger.info(f"Registered command: {name} with {len(command_params)} parameter(s)")

    def unregister(self, name: str) -> bool:
        """Unregister a command by name."""
        if name not in self._commands:
            return False

        self._commands.pop(name)
        logger.info(f"Unregistered command: {name}")
        return True

    async def execute(self, name: str, arguments: dict[str, Any],
                     matrix_context: Optional[dict[str, Any]] = None) -> Optional[str]:
        """Execute a command by name with structured arguments.

        Args:
            name: Command name to execute
            arguments: Dictionary of parameter name -> value
            matrix_context: Optional dictionary containing Matrix client, room, and event
                           Keys: 'client', 'room', 'event'
        """
        cmd = self._commands.get(name)
        if not cmd:
            logger.warning(f"Command not found: {name}")
            return f"Command '{name}' not found."

        try:
            logger.debug(f"Executing command: {cmd.name} with arguments: {arguments}")

            # Inspect handler signature
            sig = inspect.signature(cmd.handler)
            params = sig.parameters

            # Check if handler has 'matrix_context' parameter
            has_context_param = 'matrix_context' in params

            # Call handler with arguments
            if has_context_param and matrix_context:
                return await cmd.handler(**arguments, matrix_context=matrix_context)
            else:
                return await cmd.handler(**arguments)
        except Exception:
            logger.exception(f"Error executing command {cmd.name}")
            return f"Error executing command '{cmd.name}'. Check logs for details."

    def list_commands(self) -> list[tuple[str, str]]:
        """Return list of (name, description) for all commands."""
        return [(cmd.name, cmd.description) for cmd in self._commands.values()]

    def get_command(self, name: str) -> Optional[Command]:
        """Get command by name."""
        return self._commands.get(name)

    def clear(self) -> None:
        """Clear all registered commands."""
        self._commands.clear()

    def generate_function_schemas(self) -> list[dict[str, Any]]:
        """
        Generate OpenAI function calling schemas from registered commands.

        Uses decorator parameter definitions to generate schemas.

        Returns:
            List of function schema dicts in OpenAI format
        """

        schemas = []

        for name, cmd in self._commands.items():
            # Build parameters schema from command params
            parameters_schema = {
                "type": "object",
                "properties": {},
                "required": []
            }

            for param in cmd.params:
                # Map Python types to JSON schema types
                param_type = "string"  # Default
                if param.param_type == str:
                    param_type = "string"
                elif param.param_type == int:
                    param_type = "integer"
                elif param.param_type == float:
                    param_type = "number"
                elif param.param_type == bool:
                    param_type = "boolean"
                elif hasattr(param.param_type, '__origin__'):
                    # Handle Optional, List, etc.
                    origin = param.param_type.__origin__
                    if origin is list:
                        param_type = "array"
                    elif origin is dict:
                        param_type = "object"

                # Add parameter to schema
                parameters_schema["properties"][param.name] = {
                    "type": param_type,
                    "description": param.description
                }

                # Mark as required if specified
                if param.required:
                    parameters_schema["required"].append(param.name)

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


def command(name: str, description: str, params: Optional[list[tuple[str, type, str, bool]]] = None):
    """Decorator to register a command handler with type-annotated parameters.

    Args:
        name: Command name
        description: Command description
        params: Optional list of tuples defining (param_name, param_type, param_description, required)
                If None, command takes no parameters

    Usage:
        # Command with parameters
        @command(
            name="add",
            description="Add a new command",
            params=[
                ("command_name", str, "Name of the command to add", True),
                ("description", str, "Description of what the command does", True)
            ]
        )
        async def add_handler(command_name: str, description: str, matrix_context: Optional[dict] = None) -> Optional[str]:
            # Implementation
            return "Command added"

        # Parameterless command
        @command(
            name="ping",
            description="Check if bot is online"
        )
        async def ping_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
            return "pong"
    """
    if params is None:
        params = []

    def decorator(func: Callable[..., Awaitable[Optional[str]]]):
        # Get the module name of the function for tracking
        module_name = func.__module__
        _registry.register(name, description, params, func, module_name)
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


async def execute_command(name: str, arguments: dict[str, Any],
                         matrix_context: Optional[dict[str, Any]] = None) -> Optional[str]:
    """Execute a command by name with structured arguments.

    Args:
        name: Command name to execute
        arguments: Dictionary of parameter name -> value
        matrix_context: Optional dictionary containing Matrix client, room, and event
                       Keys: 'client', 'room', 'event'
    """
    return await _registry.execute(name, arguments, matrix_context=matrix_context)


def get_registry() -> CommandRegistry:
    """Get the global command registry instance."""
    return _registry


# Auto-load commands on import
load_commands()
