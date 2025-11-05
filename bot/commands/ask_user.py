"""Ask user command - prompts user for input during conversations.

This command enables multi-turn interactions within a single conversation flow.
The bot can ask follow-up questions and wait for responses, allowing for
complex workflows like:
- Gathering required information step by step
- Confirming user intent before taking action
- Escalating to user when uncertain
- Collecting sensitive information (credentials, API keys, etc.)

Example flows:
- "@architect book a flight" → bot asks origin → bot asks destination → books
- "@architect create account" → bot asks email → bot asks name → creates account
- "@architect deploy to production" → bot asks for confirmation → deploys
"""
from __future__ import annotations
from typing import Optional
from . import command


@command(
    name="ask_user",
    description=(
        "Ask the user a question and wait for their response. "
        "Use this when you need additional information from the user to complete a task. "
        "Use this to gather inputs like email, confirmation, details, etc. "
        "The bot will wait up to 2 minutes for the user's answer. "
        "The user does NOT need to mention the bot in their response."
    ),
    params=[
        ("question", str, "The question to ask the user", True)
    ]
)
async def ask_user_handler(
    question: str,
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """Ask the user a question and wait for their response.

    This command sends a question message to the user and waits synchronously
    (but non-blocking) for their response. The waiting is done using asyncio.Event,
    which allows other Matrix messages to be processed while waiting.

    Args:
        question: The question to ask the user
        matrix_context: Matrix context containing client, room, and event

    Returns:
        The user's response, formatted as "User answered: {response}",
        or an error/timeout message if something goes wrong

    Examples:
        >>> # OpenAI calls: ask_user(question="What's your email?")
        >>> # Bot sends: "❓ What's your email?"
        >>> # User responds: "user@example.com"
        >>> # Function returns: "User answered: user@example.com"

        >>> # OpenAI calls: ask_user(question="Confirm deployment? (yes/no)")
        >>> # Bot sends: "❓ Confirm deployment? (yes/no)"
        >>> # User responds: "yes"
        >>> # Function returns: "User answered: yes"
    """
    if not matrix_context:
        return "Error: This command requires Matrix context and can only be used in conversations."

    from ..user_input_handler import ask_user_and_wait

    # Send question and wait for response (with 120s timeout)
    response = await ask_user_and_wait(
        question=question,
        matrix_context=matrix_context,
        timeout=120  # 2 minutes
    )

    # Check if response indicates an error or timeout
    if response.startswith("["):
        # Error messages are wrapped in brackets
        return response

    # Format successful response for OpenAI
    return f"User answered: {response}"
