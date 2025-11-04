from __future__ import annotations
import logging
import asyncio
import json
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, List

logger = logging.getLogger(__name__)


class FunctionExecutionError(Exception):
    """Raised when function execution fails."""
    pass


async def execute_function(
    function_name: str,
    arguments: Dict[str, Any],
    matrix_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Execute a single function by name with given arguments.

    Args:
        function_name: Name of the function to call
        arguments: Dictionary of arguments to pass
        matrix_context: Optional Matrix context (client, room, event)

    Returns:
        String result from function execution

    Raises:
        FunctionExecutionError: If function execution fails
    """
    from .commands import get_registry

    try:
        registry = get_registry()

        # Check if function exists in registry
        if function_name not in registry._commands:
            raise FunctionExecutionError(
                f"Function '{function_name}' not found in command registry")

        command = registry._commands[function_name]
        handler = command.handler

        # Inspect handler signature to determine what it needs
        import inspect
        sig = inspect.signature(handler)
        needs_body = 'body' in sig.parameters
        needs_context = 'matrix_context' in sig.parameters

        # Call handler with appropriate arguments
        if needs_body:
            # Old-style handler that expects body parameter
            # For function calling, we provide empty body since the structured args are used
            if needs_context:
                result = await handler(body="", matrix_context=matrix_context, **arguments)
            else:
                result = await handler(body="", **arguments)
        else:
            # New-style handler with structured parameters only
            if needs_context:
                result = await handler(**arguments, matrix_context=matrix_context)
            else:
                result = await handler(**arguments)

        # Convert result to string
        if result is None:
            return "Function executed successfully (no return value)"
        elif isinstance(result, str):
            return result
        else:
            # Convert non-string results to JSON
            return json.dumps(result)

    except TypeError as e:
        # Handle argument mismatch errors
        logger.error(f"Argument error calling {function_name}: {e}", exc_info=True)
        raise FunctionExecutionError(
            f"Invalid arguments for function '{function_name}': {str(e)}")
    except Exception as e:
        logger.error(f"Error executing function {function_name}: {e}", exc_info=True)
        raise FunctionExecutionError(
            f"Error executing function '{function_name}': {str(e)}")


async def execute_functions(
    tool_calls: List[Dict[str, Any]],
    matrix_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Execute multiple function calls in parallel.

    Args:
        tool_calls: List of tool_call dicts from OpenAI API response
                   Each contains: id, type, function: {name, arguments}
        matrix_context: Optional Matrix context for commands that need it

    Returns:
        List of tool result dicts in OpenAI format:
        [
            {
                "tool_call_id": "call_abc123",
                "role": "tool",
                "name": "function_name",
                "content": "function result"
            },
            ...
        ]
    """
    logger.info(f"Executing {len(tool_calls)} function call(s)")

    async def execute_single_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool call and return result in OpenAI format."""
        tool_call_id = tool_call.get('id')
        function_data = tool_call.get('function', {})
        function_name = function_data.get('name')

        # Parse arguments JSON string to dict
        arguments_str = function_data.get('arguments', '{}')
        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse arguments for {function_name}: {e}")
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": function_name,
                "content": f"Error: Invalid JSON arguments: {str(e)}"
            }

        # Execute the function
        try:
            result = await execute_function(
                function_name,
                arguments,
                matrix_context
            )
            logger.debug(f"Function {function_name} returned: {result[:100]}...")

            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": function_name,
                "content": result
            }
        except FunctionExecutionError as e:
            logger.warning(f"Function execution error for {function_name}: {e}")
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": function_name,
                "content": f"Error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error executing {function_name}: {e}", exc_info=True)
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": function_name,
                "content": f"Unexpected error: {str(e)}"
            }

    # Execute all tool calls in parallel
    results = await asyncio.gather(
        *[execute_single_tool_call(tc) for tc in tool_calls],
        return_exceptions=False  # Exceptions already handled above
    )

    logger.info(f"Completed {len(results)} function execution(s)")
    return list(results)
